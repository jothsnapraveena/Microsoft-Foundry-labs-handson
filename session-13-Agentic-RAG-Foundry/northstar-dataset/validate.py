"""Integrity, chronology, policy and label checks for the Northstar dataset.

The rule check here is written separately from generate.py and reads its numbers from
knowledge/policies.json, so a mistake in the generator's oracle shows up as a mismatch.
It is still a second synthetic implementation of the same rules, not human review.

Run: python validate.py
"""
import json
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
problems = []


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def check(condition, message):
    if not condition:
        problems.append(message)


def day(text):
    return date.fromisoformat(text)


def business_days_between(start, end):
    count, current = 0, start
    while current < end:
        current += timedelta(days=1)
        count += current.weekday() < 5
    return count


manifest = load("manifest.json")
AS_OF = day(manifest["as_of"])
names = ["customers", "products", "orders", "order_items", "shipments", "returns", "refunds"]
tables = {name: load(f"operational/{name}.json") for name in names}
policies = load("knowledge/policies.json")
chunks = load("search/policy_chunks.json")
cases = load("evals/cases.json")
questions = load("evals/policy_qa.json")

customers = {c["customer_id"] for c in tables["customers"]}
products = {p["product_id"]: p for p in tables["products"]}
orders = {o["order_id"]: o for o in tables["orders"]}
items = {i["item_id"]: i for i in tables["order_items"]}
shipments = {s["order_id"]: s for s in tables["shipments"]}
returns = {r["return_id"]: r for r in tables["returns"]}
policy_by_id = {p["policy_id"]: p for p in policies}

# ------------------------------------------------------------ SQLite matches the JSON tables
con = sqlite3.connect(ROOT / "northstar.sqlite")
check(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed")
check(not con.execute("PRAGMA foreign_key_check").fetchall(), "SQLite foreign key violations")
for name, rows in tables.items():
    check(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == len(rows), f"{name}: SQLite row count differs")
    check(manifest["counts"][name] == len(rows), f"{name}: manifest count differs")

# ------------------------------------------------------------ policies and chunks
by_topic = {}
for policy in policies:
    by_topic.setdefault((policy["topic"], policy["region"]), []).append(policy)
    check(policy["applies_by"] in ("order_date", "event_date"), f"{policy['policy_id']}: unknown applies_by")
    source = (ROOT / policy["source_path"]).read_text(encoding="utf-8")
    check(policy["policy_id"] in source and policy["effective_from"] in source, f"{policy['policy_id']}: header mismatch")
    for key, value in policy["parameters"].items():     # every rule number must appear in the prose
        check(str(value) in source, f"{policy['policy_id']}: parameter {key}={value} not stated in the document")
for (topic, region), versions in by_topic.items():
    versions.sort(key=lambda p: p["effective_from"])
    for earlier, later in zip(versions, versions[1:]):
        check(earlier["effective_to"] == later["effective_from"], f"{topic}/{region}: versions overlap or leave a gap")
    check(versions[-1]["effective_to"] is None, f"{topic}/{region}: latest version is not open-ended")
chunk_ids = {c["id"] for c in chunks}
check(len(chunk_ids) == len(chunks), "duplicate chunk ids")
for chunk in chunks:
    policy = policy_by_id.get(chunk["policy_id"])
    check(policy is not None, f"{chunk['id']}: unknown policy")
    if policy:
        check(all(chunk[k] == policy[k] for k in ("topic", "version", "effective_from", "effective_to", "region", "source_path")),
              f"{chunk['id']}: metadata differs from its policy")
        check(chunk["page_chunk"] in (ROOT / chunk["source_path"]).read_text(encoding="utf-8"),
              f"{chunk['id']}: text not found in source document")
differing = {topic for (topic, _), versions in by_topic.items()
             if len({json.dumps(v["parameters"], sort_keys=True) for v in versions}) > 1}
check(len(differing) >= 3, "fewer than three topics differ between versions")


def applicable(topic, on):
    """The single policy in effect for a topic on a date; anything else is an error."""
    found = [p for p in policies if p["topic"] == topic and p["effective_from"] <= str(on)
             and (p["effective_to"] is None or str(on) < p["effective_to"])]
    check(len(found) == 1, f"{topic}: {len(found)} policies apply on {on}")
    return found[0]


# ------------------------------------------------------------ chronology
for order in orders.values():
    check(order["customer_id"] in customers, f"{order['order_id']}: unknown customer")
    check(day(order["ordered_at"]) <= AS_OF, f"{order['order_id']}: ordered in the future")
    check((order["order_id"] in shipments) == (order["status"] in ("shipped", "delivered")),
          f"{order['order_id']}: shipment presence does not match status {order['status']}")
    check((order["cancelled_at"] is not None) == (order["status"] == "cancelled"), f"{order['order_id']}: cancelled_at mismatch")
for shipment in shipments.values():
    order = orders[shipment["order_id"]]
    check(shipment["status"] == order["status"], f"{shipment['shipment_id']}: status differs from order")
    check(order["ordered_at"] <= shipment["shipped_at"] <= str(AS_OF), f"{shipment['shipment_id']}: shipped date out of order")
    check((shipment["delivered_at"] is not None) == (order["status"] == "delivered"), f"{shipment['shipment_id']}: delivered_at mismatch")
    if shipment["delivered_at"]:
        check(shipment["shipped_at"] <= shipment["delivered_at"] <= str(AS_OF), f"{shipment['shipment_id']}: delivery date out of order")

ACTIVE = ("authorized", "received", "refunded")
reserved = Counter()
refund_by_return = {f["return_id"]: f for f in tables["refunds"]}
for r in returns.values():
    item, order = items[r["item_id"]], orders[r["order_id"]]
    product = products[item["product_id"]]
    check(item["order_id"] == r["order_id"], f"{r['return_id']}: item is not in the order")
    check(order["status"] == "delivered", f"{r['return_id']}: return on an undelivered order")
    delivered = day(shipments[r["order_id"]]["delivered_at"])
    created = day(r["created_at"])
    check(delivered <= created <= AS_OF, f"{r['return_id']}: created outside delivery..as_of")
    check(product["seller_type"] == "company" and not product["final_sale"], f"{r['return_id']}: history on a review-only product")
    # The return must have been inside its window, under the version for the order date, when requested.
    topic = "defective-items" if r["reason"] == "defective" else f"{product['category']}-returns"
    policy = applicable(topic, order["ordered_at"])
    window = policy["parameters"].get("defect_window_days") or policy["parameters"]["change_of_mind_window_days"]
    check((created - delivered).days <= window, f"{r['return_id']}: requested after the {window}-day window")
    check(r["policy_id"] == policy["policy_id"], f"{r['return_id']}: policy_id is not the version for the order date")
    fees = applicable("return-shipping", order["ordered_at"])["parameters"]
    check(r["shipping_fee_cents"] == fees["defect_fee_cents" if r["reason"] == "defective" else "change_of_mind_fee_cents"],
          f"{r['return_id']}: shipping fee differs from policy")
    check((r["received_at"] is not None) == (r["status"] in ("received", "refunded", "rejected")), f"{r['return_id']}: received_at mismatch")
    if r["received_at"]:
        check(r["created_at"] <= r["received_at"] <= str(AS_OF), f"{r['return_id']}: received date out of order")
    check((r["return_id"] in refund_by_return) == (r["status"] in ("received", "refunded")), f"{r['return_id']}: refund record mismatch")
    if r["status"] in ACTIVE:
        reserved[r["item_id"]] += r["quantity"]
for item_id, quantity in reserved.items():
    check(quantity <= items[item_id]["quantity"], f"{item_id}: returned more than purchased")

for refund in tables["refunds"]:
    r = returns[refund["return_id"]]
    check(refund["amount_cents"] == items[r["item_id"]]["unit_price_cents"] * r["quantity"], f"{refund['refund_id']}: wrong amount")
    check(refund["created_at"] == r["received_at"], f"{refund['refund_id']}: not created at warehouse receipt")
    check((r["status"] == "refunded") == (refund["status"] == "paid"), f"{refund['refund_id']}: status disagrees with return")
    timing = applicable("refund-timing", r["received_at"])       # applies by the receipt date
    check(refund["policy_id"] == timing["policy_id"], f"{refund['refund_id']}: wrong refund-timing version")
    rule = timing["parameters"]
    received = day(r["received_at"])
    check((refund["submitted_at"] is not None) == (refund["status"] != "pending"), f"{refund['refund_id']}: submitted_at mismatch")
    check((refund["paid_at"] is not None) == (refund["status"] == "paid"), f"{refund['refund_id']}: paid_at mismatch")
    if refund["submitted_at"]:
        check(business_days_between(received, day(refund["submitted_at"])) == rule["inspection_business_days"],
              f"{refund['refund_id']}: inspection time differs from policy")
    if refund["paid_at"]:
        posting = business_days_between(day(refund["submitted_at"]), day(refund["paid_at"]))
        check(rule["posting_business_days_min"] <= posting <= rule["posting_business_days_max"],
              f"{refund['refund_id']}: posting took {posting} business days, outside policy")
        check(day(refund["paid_at"]) <= AS_OF, f"{refund['refund_id']}: paid in the future")


# ------------------------------------------------------------ return case labels
def expected(case, order_date_override=None):
    """Independent rule check driven by policies.json. Returns (outcome, policy ids, fee)."""
    inputs = case["inputs"]
    item, order = items[inputs["item_id"]], orders[inputs["order_id"]]
    product = products[item["product_id"]]
    if case["authenticated_customer_id"] != order["customer_id"]:
        return "access_denied", [applicable("identity-access", AS_OF)["policy_id"]], None
    if order["status"] != "delivered":
        return "ineligible", [applicable("shipping-status", AS_OF)["policy_id"]], None
    ordered = order_date_override or order["ordered_at"]
    rule = lambda topic: applicable(topic, ordered)
    if inputs["quantity"] < 1 or inputs["quantity"] > item["quantity"]:
        return "ineligible", [rule("partial-returns")["policy_id"]], None
    if inputs["quantity"] > item["quantity"] - reserved[item["item_id"]]:
        return "ineligible", [rule("duplicate-returns")["policy_id"]], None
    if product["seller_type"] == "marketplace":
        return "review_required", [rule("marketplace")["policy_id"]], None
    defect = inputs["reason"] == "defective"
    if product["final_sale"]:
        return ("review_required" if defect else "ineligible"), [rule("final-sale")["policy_id"]], None
    days = (AS_OF - day(shipments[order["order_id"]]["delivered_at"])).days
    fees = rule("return-shipping")
    if defect:
        policy = rule("defective-items")
        if days <= policy["parameters"]["defect_window_days"]:
            return "eligible", [policy["policy_id"], fees["policy_id"]], fees["parameters"]["defect_fee_cents"]
        return "review_required", [rule("warranty")["policy_id"]], None
    policy = rule(f"{product['category']}-returns")
    in_window = days <= policy["parameters"]["change_of_mind_window_days"]
    if product["category"] == "electronics":
        condition_ok = inputs["condition"] != "damaged" and inputs["accessories_present"]
    else:
        condition_ok = inputs["condition"] == "unused" and inputs["original_packaging"]
    if in_window and condition_ok:
        return "eligible", [policy["policy_id"], fees["policy_id"]], fees["parameters"]["change_of_mind_fee_cents"]
    return "ineligible", [policy["policy_id"]], None


VERSION_BOUNDARY = max(p["effective_from"] for p in policies)
FIRST_VERSION_START = min(p["effective_from"] for p in policies)
INPUT_KEYS = {"order_id", "item_id", "quantity", "reason", "condition", "accessories_present", "original_packaging"}
case_ids = set()
for case in cases:
    cid = case["case_id"]
    check(cid not in case_ids, f"{cid}: duplicate case id")
    case_ids.add(cid)
    check(set(case["inputs"]) == INPUT_KEYS, f"{cid}: unexpected input fields")
    check(case["inputs"]["order_id"] in orders and case["inputs"]["item_id"] in items, f"{cid}: unknown order or item")
    check(items[case["inputs"]["item_id"]]["order_id"] == case["inputs"]["order_id"], f"{cid}: item not in order")
    check(case["as_of"] == str(AS_OF), f"{cid}: as_of differs from manifest")
    outcome, policy_ids, fee = expected(case)
    check((case["expected_outcome"], case["expected_policy_ids"], case["expected_fee_cents"]) == (outcome, policy_ids, fee),
          f"{cid}: label {case['expected_outcome']}/{case['expected_policy_ids']}/{case['expected_fee_cents']} "
          f"but rules give {outcome}/{policy_ids}/{fee}")
    # Re-run with an order date on the other side of the version boundary.
    ordered = orders[case["inputs"]["order_id"]]["ordered_at"]
    swapped = expected(case, FIRST_VERSION_START if ordered >= VERSION_BOUNDARY else VERSION_BOUNDARY)
    check(case["version_sensitive"] == (outcome != "access_denied" and (swapped[0], swapped[2]) != (outcome, fee)),
          f"{cid}: version_sensitive flag is wrong")
    check("create_return" in case["forbidden_actions"], f"{cid}: unconfirmed write is not forbidden")
check(len(case_ids) == manifest["counts"]["return_cases"], "manifest return_cases count differs")

# Coverage: the cases must be able to tell a correct system from a plausible wrong one.
outcomes = Counter(c["expected_outcome"] for c in cases)
check(max(outcomes.values()) <= 0.5 * len(cases), f"one outcome dominates the cases: {dict(outcomes)}")
for split in ("development", "test"):
    present = {c["expected_outcome"] for c in cases if c["split"] == split}
    check(present == set(outcomes), f"{split} split is missing outcomes: {set(outcomes) - present}")
denied = [c for c in cases if c["expected_outcome"] == "access_denied"]
check(sum(c["authenticated_customer_id"] in customers for c in denied) >= 5, "too few denials by a real other customer")
flips = [c for c in cases if c["version_sensitive"] and c["expected_fee_cents"] is None]
check(len(flips) >= 2, "no case where the wrong policy version changes an ineligible outcome")
check(sum(c["version_sensitive"] and c["expected_outcome"] == "eligible" for c in cases) >= 5, "too few version-sensitive eligible cases")
ages = Counter()
for case in cases:
    shipment = shipments.get(case["inputs"]["order_id"])
    if shipment and shipment["delivered_at"] and case["expected_outcome"] != "access_denied":
        ages[(AS_OF - day(shipment["delivered_at"])).days] += 1
for boundary in (14, 15, 16, 30, 31):
    check(ages[boundary] >= 2, f"fewer than two cases on day {boundary}")
check({c["inputs"]["condition"] for c in cases} >= {"unused", "opened", "damaged"}, "a condition value is never used")
overdue = [s for s in shipments.values() if s["status"] == "shipped" and s["estimated_delivery"] < str(AS_OF)]
check(len(overdue) >= 5, "no overdue shipments for the lost-parcel policy")
check({r["status"] for r in returns.values()} == {"authorized", "received", "refunded", "rejected", "cancelled"}, "a return status is unused")
check({f["status"] for f in tables["refunds"]} == {"pending", "submitted", "paid"}, "a refund status is unused")

# ------------------------------------------------------------ policy questions
for q in questions:
    check(all(chunk in chunk_ids for chunk in q["expected_chunk_ids"]), f"{q['qa_id']}: unknown chunk id")
    check(q["answerable"] == bool(q["expected_chunk_ids"]), f"{q['qa_id']}: answerable flag disagrees with evidence")
    for chunk in (c for c in chunks if c["id"] in q["expected_chunk_ids"]):
        check(chunk["effective_from"] <= q["reference_date"] and (chunk["effective_to"] is None or q["reference_date"] < chunk["effective_to"]),
              f"{q['qa_id']}: evidence {chunk['id']} is not in effect on {q['reference_date']}")
check({q["type"] for q in questions} == {"single", "version", "multi", "unanswerable"}, "a question type is missing")
check(len(questions) == manifest["counts"]["policy_questions"], "manifest policy_questions count differs")

if problems:
    print(f"FAIL: {len(problems)} problem(s)")
    for problem in problems[:40]:
        print(" -", problem)
    raise SystemExit(1)
print(f"PASS: {len(orders)} orders, {len(returns)} returns, {len(tables['refunds'])} refunds, {len(policies)} policies, "
      f"{len(chunks)} chunks, {len(cases)} return cases {dict(outcomes)}, {len(questions)} policy questions.")
print("Checked: SQLite integrity and counts, policy intervals and parameters, chunk text, order/shipment/return/refund "
      "chronology, refund timing against policy, every return-case label recomputed from policies.json, and coverage.")
