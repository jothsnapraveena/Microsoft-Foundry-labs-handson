"""Ownership, confirmation, idempotency, concurrency and state-transition checks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import unittest

from fixtures import DATASET, Environment, case
from northstar.policies import PolicyStore
from northstar.service import Conflict, InvalidConfirmation, NotFound


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.env = Environment()
        self.service = self.env.service
        self.addCleanup(self.env.close)

    def confirmed(self, actor, request):
        """Check eligibility and confirm as the customer; returns (proposal_id, token)."""
        proposal = self.service.check_return_eligibility(actor, request)["proposal"]
        return proposal["proposal_id"], self.service.confirm(actor, proposal["proposal_id"])["confirmation_token"]

    def returns_for(self, item_id):
        return self.env.query("SELECT return_id, quantity, status FROM returns WHERE item_id = ? AND created_at = ?",
                              item_id, str(self.env.clock.today()))


class OwnershipTests(ServiceTestCase):
    def test_other_customers_order_looks_like_a_missing_order(self):
        owner, request, _ = case("defective-early")
        intruder = "CUST-001" if owner != "CUST-001" else "CUST-002"
        with self.assertRaises(NotFound) as other:
            self.service.get_order(intruder, request.order_id)
        with self.assertRaises(NotFound) as missing:
            self.service.get_order(intruder, "ORD-9999")
        self.assertEqual(str(other.exception), str(missing.exception))
        for call in (lambda: self.service.check_return_eligibility(intruder, request),
                     lambda: self.service.propose_cancel_order(intruder, request.order_id),
                     lambda: self.service.propose_support_ticket(intruder, "other", "help", request.order_id)):
            with self.assertRaises(NotFound):
                call()
        audited = self.env.query("SELECT COUNT(*) FROM audit_log WHERE actor_id = ? AND result = 'not_found_or_not_owned'", intruder)
        self.assertEqual(audited[0][0], 5)

    def test_owner_sees_order_with_items_and_shipment(self):
        owner, request, _ = case("defective-early")
        order = self.service.get_order(owner, request.order_id)
        self.assertEqual(order["customer_id"], owner)
        self.assertEqual(len(order["items"]), 2)
        self.assertEqual(order["shipment"]["status"], "delivered")

    def test_item_from_another_order_is_not_found(self):
        owner, request, _ = case("defective-early")
        _, other, _ = case("standard-early")
        with self.assertRaises(NotFound):
            self.service.check_return_eligibility(owner, replace(request, item_id=other.item_id))

    def test_return_status_is_owner_only_and_reports_refund_state(self):
        return_id, order_id = self.env.query("SELECT return_id, order_id FROM returns WHERE status = 'refunded' LIMIT 1")[0]
        owner = self.env.query("SELECT customer_id FROM orders WHERE order_id = ?", order_id)[0][0]
        status = self.service.get_return_status(owner, return_id)
        self.assertTrue(status["refund_issued"])
        self.assertEqual(status["refund"]["status"], "paid")
        with self.assertRaises(NotFound):
            self.service.get_return_status("CUST-001" if owner != "CUST-001" else "CUST-002", return_id)
        authorized, order_id = self.env.query("SELECT return_id, order_id FROM returns WHERE status = 'authorized' LIMIT 1")[0]
        owner = self.env.query("SELECT customer_id FROM orders WHERE order_id = ?", order_id)[0][0]
        status = self.service.get_return_status(owner, authorized)
        self.assertIsNone(status["refund"])
        self.assertFalse(status["refund_issued"])


class ConfirmedReturnTests(ServiceTestCase):
    def test_confirmed_return_creates_exactly_one_authorization_and_no_refund(self):
        owner, request, fixture = case("electronics-early")
        refunds = self.env.count("refunds")
        proposal_id, token = self.confirmed(owner, request)
        result = self.service.create_return(owner, proposal_id, token, "key-1")
        self.assertEqual(result["status"], "authorized")
        self.assertEqual(result["shipping_fee_cents"], fixture["expected_fee_cents"])
        self.assertFalse(result["refund_issued"])
        self.assertEqual(len(self.returns_for(request.item_id)), 1)
        self.assertEqual(self.env.count("refunds"), refunds)
        self.assertIsNone(self.service.get_return_status(owner, result["return_id"])["refund"])

    def test_unconfirmed_proposal_writes_nothing(self):
        owner, request, _ = case("defective-early")
        proposal = self.service.check_return_eligibility(owner, request)["proposal"]
        for token in (None, "", "guess", True):
            with self.assertRaises(InvalidConfirmation):
                self.service.create_return(owner, proposal["proposal_id"], token, "key-1")
        self.assertEqual(self.returns_for(request.item_id), [])

    def test_wrong_token_and_other_actor_are_refused(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        with self.assertRaises(InvalidConfirmation):
            self.service.create_return(owner, proposal_id, token + "x", "key-1")
        intruder = "CUST-001" if owner != "CUST-001" else "CUST-002"
        with self.assertRaises(NotFound):
            self.service.confirm(intruder, proposal_id)
        with self.assertRaises(NotFound):
            self.service.create_return(intruder, proposal_id, token, "key-2")
        self.assertEqual(self.returns_for(request.item_id), [])

    def test_token_for_one_action_cannot_drive_another(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        with self.assertRaises(NotFound):
            self.service.cancel_order(owner, proposal_id, token, "key-1")
        with self.assertRaises(NotFound):
            self.service.create_support_ticket(owner, proposal_id, token, "key-2")

    def test_expired_confirmation_is_refused(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        self.env.clock.advance(minutes=16)
        with self.assertRaises(InvalidConfirmation):
            self.service.create_return(owner, proposal_id, token, "key-1")
        with self.assertRaises(InvalidConfirmation):
            self.service.confirm(owner, proposal_id)
        self.assertEqual(self.returns_for(request.item_id), [])

    def test_eligibility_is_rechecked_at_write_time(self):
        owner, request, _ = case("electronics-v2-day-15")
        proposal_id, token = self.confirmed(owner, request)
        self.env.clock.date += timedelta(days=1)          # the window closes before the write
        with self.assertRaises(Conflict):
            self.service.create_return(owner, proposal_id, token, "key-1")
        self.assertEqual(self.returns_for(request.item_id), [])


class IdempotencyTests(ServiceTestCase):
    def test_retry_with_same_key_returns_the_original_return(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        first = self.service.create_return(owner, proposal_id, token, "key-1")
        retry = self.service.create_return(owner, proposal_id, token, "key-1")
        self.assertEqual(retry["return_id"], first["return_id"])
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(len(self.returns_for(request.item_id)), 1)

    def test_same_key_with_a_different_request_fails(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        self.service.create_return(owner, proposal_id, token, "key-1")
        other_owner, other_request, _ = case("standard-early")
        self.env.execute("UPDATE orders SET customer_id = ? WHERE order_id = ?", owner, other_request.order_id)
        other_proposal, other_token = self.confirmed(owner, other_request)
        with self.assertRaises(Conflict):
            self.service.create_return(owner, other_proposal, other_token, "key-1")
        self.assertEqual(self.returns_for(other_request.item_id), [])

    def test_used_proposal_cannot_create_a_second_return_with_a_new_key(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        self.service.create_return(owner, proposal_id, token, "key-1")
        with self.assertRaises(Conflict):
            self.service.create_return(owner, proposal_id, token, "key-2")
        self.assertEqual(len(self.returns_for(request.item_id)), 1)

    def test_concurrent_retries_have_one_side_effect(self):
        owner, request, _ = case("defective-early")
        proposal_id, token = self.confirmed(owner, request)
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.service.create_return(owner, proposal_id, token, "key-1"), range(8)))
        self.assertEqual(len({r["return_id"] for r in results}), 1)
        self.assertEqual(len(self.returns_for(request.item_id)), 1)

    def test_concurrent_returns_cannot_exceed_purchased_quantity(self):
        owner, request, _ = case("defective-early")
        items = self.service.get_order(owner, request.order_id)["items"]
        available = next(i["returnable_quantity"] for i in items if i["item_id"] == request.item_id)
        request = replace(request, quantity=available)    # each attempt asks for every remaining unit
        attempts = [self.confirmed(owner, request) for _ in range(6)]

        def attempt(numbered):
            index, (proposal_id, token) = numbered
            try:
                return self.service.create_return(owner, proposal_id, token, f"key-{index}")
            except Conflict:
                return None

        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(attempt, enumerate(attempts)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(sum(row[1] for row in self.returns_for(request.item_id)), available)


class CancellationAndTicketTests(ServiceTestCase):
    def order_with_status(self, status):
        return self.env.query("SELECT order_id, customer_id FROM orders WHERE status = ? LIMIT 1", status)[0]

    def test_processing_order_is_cancelled_after_confirmation(self):
        order_id, owner = self.order_with_status("processing")
        proposal = self.service.propose_cancel_order(owner, order_id)["proposal"]
        with self.assertRaises(InvalidConfirmation):
            self.service.cancel_order(owner, proposal["proposal_id"], "guess", "key-1")
        token = self.service.confirm(owner, proposal["proposal_id"])["confirmation_token"]
        self.assertEqual(self.service.cancel_order(owner, proposal["proposal_id"], token, "key-1")["status"], "cancelled")
        self.assertEqual(self.env.query("SELECT status, cancelled_at FROM orders WHERE order_id = ?", order_id)[0],
                         ("cancelled", str(self.env.clock.today())))

    def test_shipped_delivered_and_cancelled_orders_cannot_be_cancelled(self):
        for status in ("shipped", "delivered", "cancelled"):
            order_id, owner = self.order_with_status(status)
            result = self.service.propose_cancel_order(owner, order_id)
            self.assertEqual(result["outcome"], "ineligible")
            self.assertNotIn("proposal", result)

    def test_order_that_ships_after_the_proposal_is_not_cancelled(self):
        order_id, owner = self.order_with_status("processing")
        proposal_id = self.service.propose_cancel_order(owner, order_id)["proposal"]["proposal_id"]
        token = self.service.confirm(owner, proposal_id)["confirmation_token"]
        self.env.execute("UPDATE orders SET status = 'shipped' WHERE order_id = ?", order_id)
        with self.assertRaises(Conflict):
            self.service.cancel_order(owner, proposal_id, token, "key-1")
        self.assertEqual(self.env.query("SELECT status FROM orders WHERE order_id = ?", order_id)[0][0], "shipped")

    def test_ticket_is_stored_only_after_confirmation(self):
        owner, request, _ = case("marketplace-defective")
        proposal_id = self.service.propose_support_ticket(owner, "marketplace_review", "Broken on arrival", request.order_id)["proposal"]["proposal_id"]
        self.assertEqual(self.env.count("support_tickets"), 0)
        token = self.service.confirm(owner, proposal_id)["confirmation_token"]
        ticket = self.service.create_support_ticket(owner, proposal_id, token, "key-1")
        self.assertEqual(self.env.query("SELECT customer_id, category, status FROM support_tickets WHERE ticket_id = ?", ticket["ticket_id"])[0],
                         (owner, "marketplace_review", "open"))
        self.assertEqual(self.service.create_support_ticket(owner, proposal_id, token, "key-1")["ticket_id"], ticket["ticket_id"])
        self.assertEqual(self.env.count("support_tickets"), 1)

    def test_ticket_input_is_validated(self):
        with self.assertRaises(ValueError):
            self.service.propose_support_ticket("CUST-001", "refund_now", "help")
        with self.assertRaises(ValueError):
            self.service.propose_support_ticket("CUST-001", "other", " ")


class PolicyAndAuditTests(ServiceTestCase):
    def test_overlapping_or_missing_policies_go_to_review(self):
        owner, request, _ = case("electronics-early")
        records = json.loads((DATASET / "knowledge" / "policies.json").read_text(encoding="utf-8"))
        overlapping = [dict(r, effective_to=None) if r["policy_id"] == "electronics-returns-v1" else r for r in records]
        missing = [r for r in records if r["topic"] != "return-shipping"]
        for name, changed in (("overlap", overlapping), ("missing", missing)):
            with self.subTest(name):
                path = Path(self.env.directory.name) / f"{name}.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                self.service.policies = PolicyStore.load(path)
                result = self.service.check_return_eligibility(owner, request)
                self.assertEqual((result["outcome"], result["reasons"]), ("review_required", ["policy_conflict"]))
                self.assertNotIn("proposal", result)

    def test_invalid_input_is_rejected_before_any_lookup(self):
        owner, request, _ = case("defective-early")
        for change in ({"reason": "gift"}, {"condition": "mint"}, {"quantity": "1"}, {"quantity": True}, {"accessories_present": "yes"}):
            with self.subTest(change), self.assertRaises(ValueError):
                self.service.check_return_eligibility(owner, replace(request, **change))

    def test_audit_links_actions_without_storing_secrets_or_free_text(self):
        owner, request, _ = case("marketplace-defective")
        proposal_id = self.service.propose_support_ticket(owner, "marketplace_review", "SECRET-SUMMARY-TEXT", request.order_id)["proposal"]["proposal_id"]
        token = self.service.confirm(owner, proposal_id)["confirmation_token"]
        self.service.create_support_ticket(owner, proposal_id, token, "IDEMPOTENCY-KEY-VALUE", trace_id="trace-123")
        rows = self.env.query("SELECT action, result, confirmation_id, idempotency_key_hash, trace_id FROM audit_log WHERE action = 'create_support_ticket'")
        self.assertEqual(rows[0][:3], ("create_support_ticket", "success", proposal_id))
        self.assertEqual(rows[0][4], "trace-123")
        dump = json.dumps(self.env.query("SELECT * FROM audit_log"))
        for secret in ("SECRET-SUMMARY-TEXT", "IDEMPOTENCY-KEY-VALUE", token):
            self.assertNotIn(secret, dump)
        self.assertNotIn(token, json.dumps(self.env.query("SELECT * FROM proposals")))


if __name__ == "__main__":
    unittest.main()
