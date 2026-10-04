"""The support tools: ownership, eligibility, confirmed writes, idempotency and audit.

Every write follows the same path: a read-only step produces a proposal, the customer
confirms it through a channel the model cannot call, and the write re-checks everything
inside one transaction before changing anything.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import timedelta
import hashlib
import hmac
import json
import secrets

from .eligibility import ReturnRequest, evaluate_return

TICKET_CATEGORIES = ("marketplace_review", "final_sale_defect", "warranty_review", "lost_parcel",
                     "delivered_not_received", "policy_exception", "disputed_decision", "other")


class NotFound(Exception):
    """Missing, or not owned by the caller. The two are deliberately indistinguishable."""


class Conflict(Exception):
    """The request cannot be applied in the current state."""


class InvalidConfirmation(Exception):
    """The proposal is unconfirmed, expired, or the token does not match."""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SupportService:
    def __init__(self, repository, policies, clock, proposal_ttl_seconds=900, region="US"):
        self.repository, self.policies, self.clock = repository, policies, clock
        self.ttl, self.region = timedelta(seconds=proposal_ttl_seconds), region

    # ------------------------------------------------------------------ reads
    def get_order(self, actor, order_id, trace_id=None):
        with self._audit_denials(actor, "get_order", order_id, trace_id), self.repository.transaction() as uow:
            order = self._owned_order(uow, actor, order_id)
            items = []
            for item in uow.get_items(order_id):
                product = uow.get_product(item["product_id"])
                items.append({**item, "product_name": product["name"], "category": product["category"],
                              "seller_type": product["seller_type"], "final_sale": bool(product["final_sale"]),
                              "returnable_quantity": item["quantity"] - uow.reserved_quantity(item["item_id"])})
            return {**order, "items": items, "shipment": uow.get_shipment(order_id)}

    def check_return_eligibility(self, actor, request, trace_id=None):
        """Read-only. An eligible result carries a proposal the customer can confirm."""
        request.validate()
        with self._audit_denials(actor, "check_return_eligibility", request.order_id, trace_id), self.repository.transaction() as uow:
            self._owned_order(uow, actor, request.order_id)
            decision = self._evaluate(uow, request)
        result = {"outcome": decision.outcome, "reasons": list(decision.reasons), "policy_ids": list(decision.policy_ids),
                  "fee_cents": decision.fee_cents, "days_since_delivery": decision.days_since_delivery,
                  "refund_issued": False}
        if decision.outcome == "eligible":
            binding = {**asdict(request), "fee_cents": decision.fee_cents, "policy_ids": list(decision.policy_ids)}
            result["proposal"] = self._propose(actor, "create_return", binding)
        self._audit(actor, "check_return_eligibility", decision.outcome, order_id=request.order_id,
                    policy_ids=decision.policy_ids, trace_id=trace_id)
        return result

    def get_return_status(self, actor, return_id, trace_id=None):
        with self._audit_denials(actor, "get_return_status", None, trace_id), self.repository.transaction() as uow:
            record = uow.get_return(return_id)
            order = record and uow.get_order(record["order_id"])
            if not order or order["customer_id"] != actor:
                raise NotFound("Not found")
            refund = uow.get_refund(return_id)
            # No refund record means no refund: an authorization alone is never reported as paid.
            return {**record, "refund": refund, "refund_issued": bool(refund and refund["status"] == "paid")}

    # ------------------------------------------------------------------ proposals and confirmation
    def propose_cancel_order(self, actor, order_id, trace_id=None):
        with self._audit_denials(actor, "propose_cancel_order", order_id, trace_id), self.repository.transaction() as uow:
            order = self._owned_order(uow, actor, order_id)
        if order["status"] != "processing":
            return {"outcome": "ineligible", "reasons": [f"order_is_{order['status']}"],
                    "policy_ids": [self.policies.applicable("cancellation", self.clock.today(), self.region).policy_id]}
        return {"outcome": "eligible", "proposal": self._propose(actor, "cancel_order", {"order_id": order_id})}

    def propose_support_ticket(self, actor, category, summary, order_id=None, trace_id=None):
        if category not in TICKET_CATEGORIES:
            raise ValueError(f"category must be one of {TICKET_CATEGORIES}")
        if not isinstance(summary, str) or not 0 < len(summary.strip()) <= 1000:
            raise ValueError("summary must be 1 to 1000 characters")
        if order_id is not None:
            with self._audit_denials(actor, "propose_support_ticket", order_id, trace_id), self.repository.transaction() as uow:
                self._owned_order(uow, actor, order_id)
        binding = {"category": category, "summary": summary.strip(), "order_id": order_id}
        return {"proposal": self._propose(actor, "create_support_ticket", binding)}

    def confirm(self, actor, proposal_id, trace_id=None):
        """Record the customer's confirmation. Called by the customer-facing client, never exposed as an agent tool."""
        now = self.clock.now()
        with self.repository.transaction(write=True) as uow:
            proposal = uow.get_proposal(proposal_id)
            if not proposal or proposal["actor_id"] != actor:
                raise NotFound("Not found")
            if proposal["consumed_at"] or now.isoformat() >= proposal["expires_at"]:
                raise InvalidConfirmation("The proposal has expired or was already used; start again")
            token = secrets.token_urlsafe(24)
            uow.update_proposal(proposal_id, confirmed_at=now.isoformat(), token_hash=digest(token))
            uow.add_audit({"at": now.isoformat(), "actor_id": actor, "action": "confirm:" + proposal["action"],
                           "result": "confirmed", "confirmation_id": proposal_id, "trace_id": trace_id})
        return {"proposal_id": proposal_id, "confirmation_token": token, "expires_at": proposal["expires_at"]}

    # ------------------------------------------------------------------ writes
    def create_return(self, actor, proposal_id, confirmation_token, idempotency_key, trace_id=None):
        def perform(uow, binding):
            request = ReturnRequest(**{name: binding[name] for name in ReturnRequest.__dataclass_fields__})
            order = uow.get_order(request.order_id)
            if not order or order["customer_id"] != actor:
                raise NotFound("Not found")
            decision = self._evaluate(uow, request)       # re-checked inside the write transaction
            if (decision.outcome, decision.fee_cents, list(decision.policy_ids)) != ("eligible", binding["fee_cents"], binding["policy_ids"]):
                raise Conflict("Eligibility changed since the summary was shown; check eligibility again")
            return_id = "RET-" + secrets.token_hex(5).upper()
            uow.insert_return({"return_id": return_id, "order_id": request.order_id, "item_id": request.item_id,
                               "quantity": request.quantity, "reason": request.reason, "condition": request.condition,
                               "status": "authorized", "created_at": str(self.clock.today()), "received_at": None,
                               "shipping_fee_cents": decision.fee_cents, "policy_id": decision.policy_ids[0]})
            return {"return_id": return_id, "status": "authorized", "order_id": request.order_id, "item_id": request.item_id,
                    "quantity": request.quantity, "shipping_fee_cents": decision.fee_cents,
                    "policy_ids": list(decision.policy_ids), "refund_issued": False}
        return self._confirmed_write(actor, "create_return", proposal_id, confirmation_token, idempotency_key, perform, trace_id)

    def cancel_order(self, actor, proposal_id, confirmation_token, idempotency_key, trace_id=None):
        def perform(uow, binding):
            order = uow.get_order(binding["order_id"])
            if not order or order["customer_id"] != actor:
                raise NotFound("Not found")
            if order["status"] != "processing":           # may have shipped since the proposal
                raise Conflict(f"The order is {order['status']} and can no longer be cancelled")
            uow.set_order_cancelled(order["order_id"], str(self.clock.today()))
            return {"order_id": order["order_id"], "status": "cancelled", "refund_issued": False}
        return self._confirmed_write(actor, "cancel_order", proposal_id, confirmation_token, idempotency_key, perform, trace_id)

    def create_support_ticket(self, actor, proposal_id, confirmation_token, idempotency_key, trace_id=None):
        def perform(uow, binding):
            if binding["order_id"]:
                order = uow.get_order(binding["order_id"])
                if not order or order["customer_id"] != actor:
                    raise NotFound("Not found")
            ticket_id = "TKT-" + secrets.token_hex(5).upper()
            uow.insert_ticket({"ticket_id": ticket_id, "customer_id": actor, "order_id": binding["order_id"],
                               "category": binding["category"], "summary": binding["summary"], "status": "open",
                               "created_at": self.clock.now().isoformat()})
            return {"ticket_id": ticket_id, "status": "open", "category": binding["category"], "order_id": binding["order_id"]}
        return self._confirmed_write(actor, "create_support_ticket", proposal_id, confirmation_token, idempotency_key, perform, trace_id)

    # ------------------------------------------------------------------ internals
    def _confirmed_write(self, actor, action, proposal_id, token, idempotency_key, perform, trace_id):
        if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key) <= 200:
            raise ValueError("idempotency_key must be 1 to 200 characters")
        key_hash, payload_hash = digest(idempotency_key), digest(f"{action}:{proposal_id}")
        now = self.clock.now().isoformat()
        order_id = None
        try:
            with self.repository.transaction(write=True) as uow:
                earlier = uow.get_idempotent(actor, key_hash)
                if earlier:
                    if (earlier["action"], earlier["payload_hash"]) != (action, payload_hash):
                        raise Conflict("This idempotency key was already used for a different request")
                    return {**json.loads(earlier["result_json"]), "idempotent_replay": True}
                proposal = uow.get_proposal(proposal_id)
                if not proposal or proposal["actor_id"] != actor or proposal["action"] != action:
                    raise NotFound("Not found")
                binding = json.loads(proposal["binding_json"])
                order_id = binding.get("order_id")
                if proposal["consumed_at"]:
                    raise Conflict("This proposal was already used")
                if now >= proposal["expires_at"]:
                    raise InvalidConfirmation("The confirmation has expired; start again")
                if not proposal["token_hash"] or not isinstance(token, str) or not hmac.compare_digest(proposal["token_hash"], digest(token)):
                    raise InvalidConfirmation("The customer has not confirmed this action")
                result = perform(uow, binding)
                uow.update_proposal(proposal_id, consumed_at=now)
                uow.save_idempotent({"actor_id": actor, "key_hash": key_hash, "action": action, "payload_hash": payload_hash,
                                     "result_json": json.dumps(result), "created_at": now})
                uow.add_audit({"at": now, "actor_id": actor, "action": action, "result": "success", "order_id": order_id,
                               "policy_ids": result.get("policy_ids"), "confirmation_id": proposal_id,
                               "idempotency_key_hash": key_hash, "trace_id": trace_id})
                return result
        except (NotFound, Conflict, InvalidConfirmation) as error:
            # The failed transaction rolled back, so the attempt is audited separately.
            self._audit(actor, action, f"failed:{type(error).__name__}", order_id=order_id, confirmation_id=proposal_id,
                        idempotency_key_hash=key_hash, trace_id=trace_id)
            raise

    def _evaluate(self, uow, request):
        item = uow.get_item(request.item_id)
        order = uow.get_order(request.order_id)
        if not item or item["order_id"] != request.order_id:
            raise NotFound("Not found")
        shipment = uow.get_shipment(request.order_id)
        return evaluate_return(self.policies, order=order, product=uow.get_product(item["product_id"]),
                               item_quantity=item["quantity"], reserved_quantity=uow.reserved_quantity(item["item_id"]),
                               delivered_at=shipment and shipment["delivered_at"], request=request,
                               today=self.clock.today(), region=self.region)

    def _owned_order(self, uow, actor, order_id):
        order = uow.get_order(order_id)
        if not order or order["customer_id"] != actor:
            raise NotFound("Not found")
        return order

    @contextmanager
    def _audit_denials(self, actor, action, order_id, trace_id):
        """Audit a refused lookup after its read transaction has closed."""
        try:
            yield
        except NotFound:
            self._audit(actor, action, "not_found_or_not_owned", order_id=order_id, trace_id=trace_id)
            raise

    def _propose(self, actor, action, binding):
        now = self.clock.now()
        proposal = {"proposal_id": "PRP-" + secrets.token_hex(8), "actor_id": actor, "action": action,
                    "binding_json": json.dumps(binding), "created_at": now.isoformat(),
                    "expires_at": (now + self.ttl).isoformat(), "confirmed_at": None, "token_hash": None, "consumed_at": None}
        with self.repository.transaction(write=True) as uow:
            uow.save_proposal(proposal)
        return {"proposal_id": proposal["proposal_id"], "action": action, "summary": binding,
                "expires_at": proposal["expires_at"], "requires_customer_confirmation": True}

    def _audit(self, actor, action, result, **fields):
        with self.repository.transaction(write=True) as uow:
            uow.add_audit({"at": self.clock.now().isoformat(), "actor_id": actor, "action": action, "result": result, **fields})
