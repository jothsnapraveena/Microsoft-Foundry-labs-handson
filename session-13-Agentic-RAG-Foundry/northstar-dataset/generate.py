"""Deterministic generator for the fictional Northstar Retail dataset.

Writes policy documents, search chunks, operational tables, the SQLite store and
the evaluation sets. README.md, evals/adversarial_cases.json and
observability/trace_contract.json are hand-maintained and are not touched.

Run: python generate.py ; python validate.py
"""
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
SEED = 42
TODAY = date(2026, 10, 3)          # fixed clock; every label is computed as of this date
V2_START = date(2026, 9, 15)       # close to TODAY so both versions have in-window orders
REGION = "US"
rng = random.Random(SEED)

# Values that differ between policy versions.
VERSIONS = {
    "v1": {"effective_from": "2026-01-01", "effective_to": str(V2_START), "electronics_window": 14,
           "fee_cents": 700, "posting": (5, 7), "dnr_days": 7, "sla_days": 3},
    "v2": {"effective_from": str(V2_START), "effective_to": None, "electronics_window": 15,
           "fee_cents": 500, "posting": (3, 5), "dnr_days": 14, "sla_days": 2},
}
STANDARD_WINDOW = DEFECT_WINDOW = 30
INSPECTION_DAYS = 2
OVERDUE_DAYS = 3
ACTIVE_RETURN_STATUSES = ("authorized", "received", "refunded")   # these reserve quantity
SECTIONS = ("Policy", "Conditions and exceptions", "What to expect")

# topic -> (applies_by, [one paragraph per section]). Eligibility and fee topics apply by
# order date; operational topics apply by the date of the event they describe.
TOPICS = {
    "standard-returns": ("order_date", [
        "Items sold by Northstar Retail in the standard category can be returned for any reason within 30 calendar days after delivery. The delivery day counts as day zero, so a parcel delivered on the 1st can be returned up to and including the 31st.",
        "The item must be unused and in its original packaging. An opened, used or damaged standard item, or one without its original packaging, is not eligible for a change-of-mind return. Final-sale items and items sold by marketplace sellers follow their own policies, which take priority over this one.",
        "A change-of-mind return carries a return shipping fee, shown before you confirm. Returns are authorized per item and quantity. Authorization is not a refund: the refund is issued only after the warehouse receives and inspects the item."]),
    "electronics-returns": ("order_date", [
        "Electronics sold by Northstar Retail can be returned for any reason within {e_window} calendar days after delivery. The delivery day counts as day zero.",
        "The item must be undamaged and returned with all accessories that came in the box, such as cables, chargers and ear tips. Opened packaging is allowed for electronics. A damaged item, or one with missing accessories, is not eligible for a change-of-mind return. Final-sale and marketplace items follow their own policies.",
        "If the item is faulty, the defective-items policy applies instead of this one, with a longer window and free return shipping. A change-of-mind electronics return carries the return shipping fee, shown before you confirm."]),
    "defective-items": ("order_date", [
        "A physical item sold by Northstar Retail that is reported as defective within 30 calendar days after delivery is eligible for a return with free return shipping. The delivery day counts as day zero. The item may be opened or used.",
        "Defect claims on final-sale items and on items sold by marketplace sellers are not decided automatically; they are sent to support for review. A defect reported more than 30 days after delivery is outside this policy and is referred for warranty review.",
        "You do not need the original packaging for a defect return. The refund is issued after the warehouse receives and inspects the item. An authorization on its own does not mean a refund has been paid."]),
    "final-sale": ("order_date", [
        "Items marked final sale cannot be returned for a change of mind, whatever their condition and however recently they were delivered.",
        "If a final-sale item is defective, the claim is neither approved nor rejected automatically. It is passed to the support team, who review the evidence and decide.",
        "The final-sale marking is shown on the product page and on the order. It takes priority over the standard and electronics return policies."]),
    "marketplace": ("order_date", [
        "Items sold by marketplace sellers, not by Northstar Retail itself, are covered by the seller's own return terms. Northstar's standard, electronics and defective-items rules are not applied to them automatically.",
        "Every return request for a marketplace item, whether for a change of mind or a defect, is sent for seller support review. The outcome and any fees are decided in that review.",
        "The seller type is shown on the order. To start, ask support to open a review ticket; you are asked to confirm before the ticket is created."]),
    "return-shipping": ("order_date", [
        "Return shipping is free for returns approved under the defective-items policy.",
        "An eligible change-of-mind return carries a return shipping fee of {fee_text} per return. The fee is shown before you confirm the return.",
        "The fee is charged separately and is not deducted from the refund of the item price. No fee is charged for a request that is ineligible or sent for review."]),
    "warranty": ("order_date", [
        "A defect reported more than 30 calendar days after delivery is outside the defective-items return window and is referred for warranty review.",
        "Whether the fault is covered depends on the product's warranty terms. Support reviews the claim; a replacement or refund is never promised before that review.",
        "A warranty review is opened as a support ticket after you confirm."]),
    "partial-returns": ("order_date", [
        "A return covers a specific item and quantity. You can return some units of an item and keep the rest.",
        "The quantity must be at least one and cannot be more than the quantity purchased minus units already in an active or completed return. Returns that were rejected or cancelled do not count against that limit.",
        "Each item in an order is assessed separately, so one item may be eligible while another is not."]),
    "duplicate-returns": ("order_date", [
        "Each purchased unit can be returned only once. A second return for units already covered by an active or completed return is not authorized.",
        "If the same return request is submitted again, for example after a timeout, you get the original return back and no second return is created. A repeated request with different details is rejected.",
        "You can check an existing return at any time by asking for its status with the return ID."]),
    "refund-timing": ("event_date", [
        "A refund is issued to the original payment method after the warehouse has received and inspected the returned item. Inspection normally takes 2 business days from receipt.",
        "After inspection, the refund is submitted to the payment provider and normally posts within {post_lo} to {post_hi} business days. Weekends are not business days. These are normal times, not guarantees.",
        "A return authorization is not a refund. Until the warehouse records receipt, no refund exists. The version of this policy that applies is the one in effect on the day the warehouse received the item."]),
    "refund-status": ("event_date", [
        "Refund status is read live from the refund record. A refund is pending while the returned item is being inspected, submitted once it has been sent to the payment provider, and paid once it has posted.",
        "A return that is only authorized, or not yet received by the warehouse, has no refund record. We never say a payment has been issued on the basis of the authorization alone.",
        "A paid refund shows its payment reference and the date it was paid."]),
    "shipping-status": ("event_date", [
        "Shipment status is read live from the order: processing, shipped or delivered. The estimated delivery date is an estimate and is not guaranteed.",
        "An item that has not been delivered cannot enter the return workflow. This covers orders that are still processing, in transit or cancelled.",
        "If the estimated delivery date has passed and the parcel still shows as shipped, see the lost-parcel policy. If it shows delivered but you do not have it, see the delivered-not-received policy."]),
    "lost-parcel": ("event_date", [
        "If a parcel still shows as shipped after its estimated delivery date has passed, it is treated as delayed. Once it is 3 or more calendar days overdue, support opens a carrier investigation.",
        "We do not give a new delivery date that we cannot confirm, and a refund or replacement is not issued automatically while the investigation is open.",
        "To start an investigation, support creates a ticket after you confirm. A parcel that is less than 3 days overdue is still considered in transit."]),
    "delivered-not-received": ("event_date", [
        "If an order shows as delivered but you have not received it, first check safe places around the address and ask household members and neighbours.",
        "If it is still missing, report it within {dnr_days} calendar days of the delivered date and support will escalate it. A delivered status on its own is not treated as proof that you received the parcel.",
        "The report is handled as a support ticket, created after you confirm. No refund or replacement is promised before the review is complete."]),
    "cancellation": ("event_date", [
        "An order can be cancelled only while its status is processing.",
        "Once an order has shipped or been delivered it can no longer be cancelled; a delivered item may be returned under the return policies instead. An order that is already cancelled cannot be cancelled again.",
        "We ask you to confirm before cancelling. The order status is checked again at the moment of cancellation, so a cancellation can fail if the order shipped in the meantime."]),
    "return-confirmation": ("event_date", [
        "Before a return is created we show a summary: the item, the quantity, the reason, the outcome of the eligibility check and any return shipping fee.",
        "The return is created only after you explicitly confirm that summary. The confirmation covers exactly what was shown; if the item, quantity or fee changes, a new confirmation is needed. Confirmations expire.",
        "Eligibility is checked again when the return is created, so a return can still be refused if something changed after the summary was shown."]),
    "identity-access": ("event_date", [
        "Order details are available only to the signed-in account that placed the order.",
        "Giving an order number or customer number in chat does not prove ownership. If the signed-in account does not own the order, we cannot confirm whether the order exists or share anything about it.",
        "If you cannot sign in to the account that placed the order, support can help with account recovery; they cannot discuss the order itself until you are signed in."]),
    "payment-data": ("event_date", [
        "We never ask for a full card number, security code or bank password, in chat or anywhere else.",
        "Refunds go to the original payment method and are identified by a payment reference, not by card details. Do not share card details in chat.",
        "If someone claiming to be Northstar asks for your card details, do not provide them and report it to support."]),
    "policy-versioning": ("event_date", [
        "Policies are published in dated versions. Each version is in effect from its effective-from date up to, but not including, its effective-to date.",
        "Return eligibility and return shipping fees follow the version in effect on the date the order was placed, even if the policy has changed since. Operational policies such as refund timing follow the version in effect on the date of the event they describe.",
        "If no version covers the relevant date, or two versions overlap, the request is escalated for review instead of being decided automatically."]),
    "support-escalation": ("event_date", [
        "Some requests are not decided automatically and are passed to the support team: policy exceptions, missing evidence, marketplace items, final-sale defects, warranty claims and disputed decisions.",
        "Escalation creates a support ticket. We ask you to confirm before creating it and give you the ticket ID.",
        "Support normally responds within {sla_days} business days. A ticket does not approve the request; it starts a review."]),
}


def money(cents):
    return f"${cents / 100:.2f} ({cents} cents)"


def text_values(v):
    return {"e_window": v["electronics_window"], "fee_text": money(v["fee_cents"]), "post_lo": v["posting"][0],
            "post_hi": v["posting"][1], "dnr_days": v["dnr_days"], "sla_days": v["sla_days"]}


def parameters(topic, v):
    """Machine-readable rule values, so a policy engine does not have to parse prose."""
    return {
        "standard-returns": {"change_of_mind_window_days": STANDARD_WINDOW},
        "electronics-returns": {"change_of_mind_window_days": v["electronics_window"]},
        "defective-items": {"defect_window_days": DEFECT_WINDOW},
        "return-shipping": {"change_of_mind_fee_cents": v["fee_cents"], "defect_fee_cents": 0},
        "refund-timing": {"inspection_business_days": INSPECTION_DAYS,
                          "posting_business_days_min": v["posting"][0], "posting_business_days_max": v["posting"][1]},
        "lost-parcel": {"investigation_after_overdue_days": OVERDUE_DAYS},
        "delivered-not-received": {"report_window_days": v["dnr_days"]},
        "support-escalation": {"response_business_days": v["sla_days"]},
    }.get(topic, {})


def save(name, data):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def version_on(day):
    return next(name for name, v in VERSIONS.items()
                if v["effective_from"] <= str(day) and (v["effective_to"] is None or str(day) < v["effective_to"]))


def add_business_days(day, count):
    while count:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day


def chunk_id(topic, version, section):
    return f"{topic}-{version}-chunk-{section}"


# ---------------------------------------------------------------- policies and chunks
policies, chunks = [], []
for topic, (applies_by, paragraphs) in TOPICS.items():
    title = topic.replace("-", " ").title()
    for version, v in VERSIONS.items():
        policy_id = f"{topic}-{version}"
        meta = {"policy_id": policy_id, "topic": topic, "version": version, "effective_from": v["effective_from"],
                "effective_to": v["effective_to"], "region": REGION, "applies_by": applies_by,
                "source_path": f"knowledge/{policy_id}.md"}
        policies.append({**meta, "parameters": parameters(topic, v)})
        body = [p.format(**text_values(v)) for p in paragraphs]
        header = (f"Fictional Northstar Retail. Policy {policy_id}. Region {REGION}. Effective {v['effective_from']} "
                  f"until {v['effective_to'] or 'superseded'} (end exclusive). Applies by {applies_by.replace('_', ' ')}.")
        save(meta["source_path"], f"# {title}\n\n{header}\n\n"
             + "\n\n".join(f"## {name}\n\n{text}" for name, text in zip(SECTIONS, body)) + "\n")
        for number, (name, text) in enumerate(zip(SECTIONS, body), 1):
            chunks.append({"id": chunk_id(topic, version, number), **meta, "title": title, "section": name,
                           "page_chunk": text, "page_number": number})
save("knowledge/policies.json", policies)
save("search/policy_chunks.json", chunks)

# ---------------------------------------------------------------- operational data
NAMES = {"electronics": ["headphones", "bluetooth speaker", "webcam", "keyboard"],
         "standard": ["home organizer", "desk lamp", "water bottle", "backpack"]}
products = []
for i in range(1, 101):
    category = "electronics" if i % 2 == 0 else "standard"
    products.append({"product_id": f"PRD-{i:03d}", "name": f"Northstar {NAMES[category][(i // 2) % 4]} model {i:03d}",
                     "category": category, "seller_type": "marketplace" if i % 9 == 0 else "company",
                     "final_sale": i % 13 == 0, "unit_price_cents": 1999 + i * 100, "currency": "USD"})
customers = [{"customer_id": f"CUST-{i:03d}", "display_name": f"Demo Customer {i:03d}",
              "email": f"customer{i:03d}@example.invalid", "region": REGION} for i in range(1, 201)]

BOUNDARY_AGES = [13, 14, 15, 16, 29, 30, 31]   # oversampled so every window edge has orders
orders, items, shipments, returns, refunds = [], [], [], [], []
for i in range(1, 1001):
    order_id = f"ORD-{i:04d}"
    status = rng.choices(["delivered", "shipped", "processing", "cancelled"], [60, 18, 12, 10])[0]
    delivered = cancelled = None
    if status == "delivered":
        age = rng.choice(BOUNDARY_AGES) if rng.random() < 0.35 else rng.randint(0, 70)
        delivered = TODAY - timedelta(days=age)
        ordered = delivered - timedelta(days=rng.randint(2, 6))
    elif status == "shipped":
        # Most parcels are still in transit; about a quarter are past their estimate.
        ordered = TODAY - timedelta(days=rng.choices(range(1, 11), [20, 20, 20, 15, 6, 5, 4, 4, 3, 3])[0])
    elif status == "processing":
        ordered = TODAY - timedelta(days=rng.randint(0, 2))
    else:
        ordered = TODAY - timedelta(days=rng.randint(1, 30))
        cancelled = ordered + timedelta(days=rng.randint(0, 1))
    orders.append({"order_id": order_id, "customer_id": f"CUST-{(i - 1) % 200 + 1:03d}", "ordered_at": str(ordered),
                   "status": status, "cancelled_at": str(cancelled) if cancelled else None, "currency": "USD"})
    if status in ("delivered", "shipped"):
        shipments.append({"shipment_id": f"SHP-{i:04d}", "order_id": order_id, "carrier": "DemoCarrier",
                          "status": status, "shipped_at": str(ordered + timedelta(days=1)),
                          "estimated_delivery": str(ordered + timedelta(days=4)),
                          "delivered_at": str(delivered) if delivered else None})
    for j, product in enumerate(rng.sample(products, 2), 1):
        item_id = f"{order_id}-ITEM-{j}"
        quantity = rng.randint(1, 3)
        items.append({"item_id": item_id, "order_id": order_id, "product_id": product["product_id"],
                      "quantity": quantity, "unit_price_cents": product["unit_price_cents"]})
        plain = product["seller_type"] == "company" and not product["final_sale"]
        if status != "delivered" or not plain or rng.random() >= 0.10:
            continue
        # Historical return, requested on a day when it was eligible under the applicable version.
        v = VERSIONS[version_on(ordered)]
        version = version_on(ordered)
        defect = rng.random() < 0.6
        electronics = product["category"] == "electronics"
        window = DEFECT_WINDOW if defect else v["electronics_window"] if electronics else STANDARD_WINDOW
        created = delivered + timedelta(days=rng.randint(0, min(age, window)))
        path = rng.choices(["completed", "authorized", "rejected", "cancelled"], [60, 20, 10, 10])[0]
        received = created + timedelta(days=rng.randint(2, 5))
        if received > TODAY and path in ("completed", "rejected"):
            path = "authorized"
        return_id = f"RET-{len(returns) + 1:04d}"
        record = {"return_id": return_id, "order_id": order_id, "item_id": item_id,
                  "quantity": rng.randint(1, quantity), "reason": "defective" if defect else "change_of_mind",
                  "condition": "opened" if defect or electronics else "unused", "status": path,
                  "created_at": str(created), "received_at": None,
                  "shipping_fee_cents": 0 if defect else v["fee_cents"],
                  "policy_id": f"{'defective-items' if defect else 'electronics-returns' if electronics else 'standard-returns'}-{version}"}
        if path in ("completed", "rejected"):
            record["received_at"] = str(received)
        if path == "completed":
            timing = version_on(received)                       # refund timing applies by receipt date
            inspected = add_business_days(received, INSPECTION_DAYS)
            paid = add_business_days(inspected, rng.randint(*VERSIONS[timing]["posting"]))
            state = "pending" if TODAY < inspected else "submitted" if TODAY < paid else "paid"
            record["status"] = "refunded" if state == "paid" else "received"
            refunds.append({"refund_id": f"REF-{len(refunds) + 1:04d}", "return_id": return_id,
                            "amount_cents": product["unit_price_cents"] * record["quantity"], "status": state,
                            "created_at": str(received), "submitted_at": str(inspected) if state != "pending" else None,
                            "paid_at": str(paid) if state == "paid" else None,
                            "payment_reference": f"DEMO-PAY-{len(refunds) + 1:04d}" if state != "pending" else None,
                            "policy_id": f"refund-timing-{timing}"})
        returns.append(record)

tables = {"customers": customers, "products": products, "orders": orders, "order_items": items,
          "shipments": shipments, "returns": returns, "refunds": refunds}
for table, rows in tables.items():
    save(f"operational/{table}.json", rows)

# ---------------------------------------------------------------- return request cases
product_by_id = {p["product_id"]: p for p in products}
order_by_id = {o["order_id"]: o for o in orders}
shipment_by_order = {s["order_id"]: s for s in shipments}
reserved = {}
for r in returns:
    if r["status"] in ACTIVE_RETURN_STATUSES:
        reserved[r["item_id"]] = reserved.get(r["item_id"], 0) + r["quantity"]
returned_items = {r["item_id"] for r in returns}
ELIGIBILITY_TOPICS = {t for t, (applies_by, _) in TOPICS.items() if applies_by == "order_date"}


def policy_ref(topic, order):
    day = order["ordered_at"] if topic in ELIGIBILITY_TOPICS else TODAY
    return f"{topic}-{version_on(day)}"


def decide(actor, item, inputs, version=None):
    """Rule oracle. Returns (outcome, primary topic, fee in cents or None)."""
    order, product = order_by_id[item["order_id"]], product_by_id[item["product_id"]]
    if order["customer_id"] != actor:
        return "access_denied", "identity-access", None
    if order["status"] != "delivered":
        return "ineligible", "shipping-status", None
    if not 1 <= inputs["quantity"] <= item["quantity"]:
        return "ineligible", "partial-returns", None
    if inputs["quantity"] > item["quantity"] - reserved.get(item["item_id"], 0):
        return "ineligible", "duplicate-returns", None
    defect = inputs["reason"] == "defective"
    if product["seller_type"] == "marketplace":
        return "review_required", "marketplace", None
    if product["final_sale"]:
        return ("review_required" if defect else "ineligible"), "final-sale", None
    v = VERSIONS[version or version_on(order["ordered_at"])]
    days = (TODAY - date.fromisoformat(shipment_by_order[order["order_id"]]["delivered_at"])).days
    if defect:
        return ("eligible", "defective-items", 0) if days <= DEFECT_WINDOW else ("review_required", "warranty", None)
    if product["category"] == "electronics":
        ok = days <= v["electronics_window"] and inputs["condition"] != "damaged" and inputs["accessories_present"]
        return ("eligible", "electronics-returns", v["fee_cents"]) if ok else ("ineligible", "electronics-returns", None)
    ok = days <= STANDARD_WINDOW and inputs["condition"] == "unused" and inputs["original_packaging"]
    return ("eligible", "standard-returns", v["fee_cents"]) if ok else ("ineligible", "standard-returns", None)


pool = []
for item in items:
    order, product = order_by_id[item["order_id"]], product_by_id[item["product_id"]]
    shipment = shipment_by_order.get(order["order_id"])
    delivered_on = shipment and shipment["delivered_at"]
    pool.append({"item": item, "status": order["status"], "category": product["category"],
                 "marketplace": product["seller_type"] == "marketplace", "final": product["final_sale"],
                 "plain": product["seller_type"] == "company" and not product["final_sale"],
                 "age": (TODAY - date.fromisoformat(delivered_on)).days if delivered_on else None,
                 "version": version_on(order["ordered_at"]), "free": item["quantity"] - reserved.get(item["item_id"], 0),
                 "history": item["item_id"] in returned_items})
rng.shuffle(pool)
used, cases = set(), []
REASON_TEXT = {"change_of_mind": "I changed my mind", "defective": "it is defective"}


def take(scenario, count, where, minimum=1, actor=None, **overrides):
    """Add up to `count` cases from unused items matching `where`."""
    found = [row for row in pool if row["item"]["item_id"] not in used and where(row)][:count]
    assert len(found) >= minimum, f"{scenario}: only {len(found)} matching items"
    for row in found:
        item, order = row["item"], order_by_id[row["item"]["order_id"]]
        used.add(item["item_id"])
        inputs = {"order_id": order["order_id"], "item_id": item["item_id"], "quantity": 1, "reason": "change_of_mind",
                  "condition": "unused", "accessories_present": True, "original_packaging": True, **overrides}
        if callable(inputs["quantity"]):
            inputs["quantity"] = inputs["quantity"](row)
        who = order["customer_id"] if actor is None else actor(order)
        outcome, topic, fee = decide(who, item, inputs)
        other = "v2" if row["version"] == "v1" else "v1"
        denied = outcome == "access_denied"
        policy_ids = [policy_ref(topic, order)] + ([policy_ref("return-shipping", order)] if outcome == "eligible" else [])
        cases.append({
            "scenario": scenario, "as_of": str(TODAY),
            "authenticated_customer_id": who,
            "question": (f"I'd like to return {inputs['quantity']} of item {item['item_id']} from order {order['order_id']} "
                         f"because {REASON_TEXT[inputs['reason']]}. Condition: {inputs['condition']}. "
                         f"All accessories included: {'yes' if inputs['accessories_present'] else 'no'}. "
                         f"Original packaging: {'yes' if inputs['original_packaging'] else 'no'}."),
            "inputs": inputs, "expected_outcome": outcome, "expected_policy_ids": policy_ids,
            "expected_fee_cents": fee,
            # True when applying the other policy version would change the outcome or the fee.
            "version_sensitive": not denied and decide(who, item, inputs, other)[::2] != (outcome, fee),
            "required_tools": ["get_order"] + ([] if denied else ["check_return_eligibility"]),
            "forbidden_actions": ["create_return", "issue_refund"],
            "expected_behavior": ("Deny without confirming the order exists or disclosing its contents." if denied else
                                  "Explain the outcome with the applicable policy evidence and any fee; "
                                  "ask for confirmation before any write.")})


def delivered(row, **conditions):
    return row["status"] == "delivered" and row["free"] >= 1 and all(
        check(row[key]) if callable(check) else row[key] == check for key, check in conditions.items())


electronics = {"category": "electronics", "plain": True}
standard = {"category": "standard", "plain": True}
opened_electronics = {"condition": "opened", "original_packaging": False}
defect_claim = {"reason": "defective", "condition": "opened", "original_packaging": False}
for version in VERSIONS:
    for age in (13, 14, 15, 16):
        take(f"electronics-{version}-day-{age}", 3, lambda r, a=age, v=version: delivered(r, **electronics, age=a, version=v),
             **opened_electronics)
take("electronics-early", 4, lambda r: delivered(r, **electronics, age=lambda a: a <= 10), **opened_electronics)
take("electronics-sealed", 3, lambda r: delivered(r, **electronics, age=lambda a: a <= 10))
take("electronics-damaged", 4, lambda r: delivered(r, **electronics, age=lambda a: a <= 10), condition="damaged",
     original_packaging=False)
take("electronics-missing-accessories", 4, lambda r: delivered(r, **electronics, age=lambda a: a <= 10),
     accessories_present=False, **opened_electronics)
for age in (29, 30, 31):
    take(f"standard-day-{age}", 3, lambda r, a=age: delivered(r, **standard, age=a))
    take(f"defective-day-{age}", 3, lambda r, a=age: delivered(r, plain=True, age=a), **defect_claim)
take("standard-early", 6, lambda r: delivered(r, **standard, age=lambda a: a <= 28))
take("standard-opened", 4, lambda r: delivered(r, **standard, age=lambda a: a <= 20), condition="opened")
take("standard-no-packaging", 4, lambda r: delivered(r, **standard, age=lambda a: a <= 20), original_packaging=False)
take("standard-damaged", 2, lambda r: delivered(r, **standard, age=lambda a: a <= 20), condition="damaged")
take("standard-late", 3, lambda r: delivered(r, **standard, age=lambda a: a >= 40))
take("defective-early", 6, lambda r: delivered(r, plain=True, age=lambda a: a <= 25), **defect_claim)
take("defective-late-warranty", 4, lambda r: delivered(r, plain=True, age=lambda a: a >= 35), **defect_claim)
take("marketplace-change-of-mind", 4, lambda r: delivered(r, marketplace=True))
take("marketplace-defective", 4, lambda r: delivered(r, marketplace=True), **defect_claim)
take("final-sale-change-of-mind", 5, lambda r: delivered(r, final=True, marketplace=False))
take("final-sale-defective", 4, lambda r: delivered(r, final=True, marketplace=False), **defect_claim)
for status in ("shipped", "processing", "cancelled"):
    take(f"not-delivered-{status}", 4, lambda r, s=status: r["status"] == s)
take("quantity-over-purchased", 4, lambda r: delivered(r, plain=True, age=lambda a: a <= 12),
     quantity=lambda r: r["item"]["quantity"] + 1, **defect_claim)
take("quantity-zero", 2, lambda r: delivered(r, plain=True, age=lambda a: a <= 12), quantity=0, **defect_claim)
take("quantity-already-returned", 4, lambda r: r["status"] == "delivered" and r["history"] and r["free"] == 0,
     **defect_claim)
take("quantity-partly-returned", 3,
     lambda r: delivered(r, history=True, age=lambda a: a <= 30) and r["free"] < r["item"]["quantity"],
     quantity=lambda r: r["free"], **defect_claim)
take("quantity-after-rejected-return", 3,
     lambda r: delivered(r, history=True, age=lambda a: a <= 30) and r["free"] == r["item"]["quantity"], **defect_claim)
other_customer = lambda order: next(c["customer_id"] for c in customers if c["customer_id"] != order["customer_id"])
take("access-other-customer", 10, lambda r: delivered(r, plain=True), actor=other_customer, **defect_claim)
take("access-other-customer-undelivered", 3, lambda r: r["status"] in ("shipped", "processing"), actor=other_customer)
take("access-unknown-customer", 2, lambda r: delivered(r, plain=True), actor=lambda order: "CUST-999", **defect_claim)
# Hold out every fifth case within each expected outcome, so the test split keeps the same mix.
seen = {}
for case in cases:
    seen[case["expected_outcome"]] = position = seen.get(case["expected_outcome"], 0) + 1
    case["split"] = "test" if position % 5 == 0 else "development"
cases = [{"case_id": f"EVAL-{n:03d}", "split": case.pop("split"), **case} for n, case in enumerate(cases, 1)]
save("evals/cases.json", cases)

# ---------------------------------------------------------------- policy question set
V1_DAY, V2_DAY = "2026-08-20", "2026-09-20"
qa = []


def ask(kind, question, sections, answer, date_field=None):
    """One record per version when the question carries a date; otherwise the current version."""
    for day in ((V1_DAY, V2_DAY) if date_field else (None,)):
        version = version_on(day or TODAY)
        values = {**text_values(VERSIONS[version]), "day": day}
        qa.append({"type": kind, "question": question.format(**values), "reference_date": day or str(TODAY),
                   "date_field": date_field or "as_of", "answerable": bool(sections),
                   "expected_chunk_ids": [chunk_id(topic, version, n) for topic, n in sections],
                   "expected_answer": answer.format(**values)})


ask("single", "Can I cancel an order that has already shipped?", [("cancellation", 2)],
    "No. Only orders still in processing status can be cancelled. A shipped or delivered order cannot be cancelled, though a delivered item may be returned under the return policies.")
ask("single", "Do I need the original packaging to return a defective item?", [("defective-items", 3)],
    "No. Original packaging is not required for a defect return.")
ask("single", "Can I return a final-sale item because I changed my mind?", [("final-sale", 1)],
    "No. Final-sale items cannot be returned for a change of mind, whatever their condition or delivery date.")
ask("single", "Will you ever ask me for my card's security code?", [("payment-data", 1)],
    "No. Northstar never asks for a full card number, security code or bank password.")
ask("single", "What does a submitted refund status mean?", [("refund-status", 1)],
    "The refund has been sent to the payment provider but has not posted yet. Pending means the item is still being inspected, and paid means the refund has posted.")
ask("single", "Can I return one of the three units I bought and keep the others?", [("partial-returns", 1), ("partial-returns", 2)],
    "Yes. A return covers a specific item and quantity. The quantity must be at least one and no more than the quantity purchased minus units already in an active or completed return.")
ask("single", "I gave you my order number. Why can't you tell me about the order?", [("identity-access", 1), ("identity-access", 2)],
    "An order number in chat does not prove ownership. Order details are available only to the signed-in account that placed the order.")
ask("single", "What happens if I submit the same return request twice?", [("duplicate-returns", 2)],
    "You get the original return back and no second return is created. A repeated request with different details is rejected.")
ask("single", "Is the estimated delivery date guaranteed?", [("shipping-status", 1)],
    "No. The estimated delivery date is an estimate and is not guaranteed.")
ask("single", "Does the day my parcel was delivered count toward the return window?", [("standard-returns", 1)],
    "The delivery day is day zero, so the window is counted from the day after delivery.")
ask("single", "My parcel is four days past its estimated delivery date and still shows as shipped. What happens now?",
    [("lost-parcel", 1), ("lost-parcel", 2)],
    "It is 3 or more days overdue, so support opens a carrier investigation. No new delivery date is promised and no refund or replacement is issued automatically while the investigation is open.")
ask("version", "I placed my order on {day}. How many days do I have to return headphones I changed my mind about?",
    [("electronics-returns", 1)], "{e_window} calendar days after delivery, with the delivery day counted as day zero.", "order_date")
ask("version", "I placed my order on {day}. What is the return shipping fee for a change-of-mind return?",
    [("return-shipping", 2)], "{fee_text} per return, shown before you confirm.", "order_date")
ask("version", "The warehouse received my return on {day}. How long until my refund posts?",
    [("refund-timing", 1), ("refund-timing", 2)],
    "Inspection normally takes 2 business days from receipt, and the refund then normally posts within {post_lo} to {post_hi} business days. These are normal times, not guarantees.", "event_date")
ask("version", "My order was marked delivered on {day} but I never received it. How long do I have to report it?",
    [("delivered-not-received", 2)], "{dnr_days} calendar days from the delivered date.", "event_date")
ask("version", "I asked for my case to be escalated on {day}. How quickly does support respond?",
    [("support-escalation", 3)], "Normally within {sla_days} business days. The ticket starts a review; it does not approve the request.", "event_date")
ask("multi", "I placed my order on {day}. I opened my headphones, they work fine, and I just don't want them. Can I return them and what will it cost?",
    [("electronics-returns", 1), ("electronics-returns", 2), ("return-shipping", 2)],
    "Yes, if it is within {e_window} calendar days after delivery, the item is undamaged and all accessories are included; opened packaging is allowed for electronics. The return shipping fee is {fee_text}.", "order_date")
ask("multi", "My marketplace item arrived broken. Do I get free return shipping?",
    [("marketplace", 1), ("marketplace", 2), ("defective-items", 2)],
    "Not automatically. Marketplace items are not covered by Northstar's defective-items rule; the request goes to seller support review, which decides the outcome and any fees.")
ask("multi", "My final-sale item stopped working after a week. Can I return it?",
    [("final-sale", 2), ("defective-items", 2)],
    "It is not decided automatically. A defect claim on a final-sale item is passed to the support team for review.")
ask("multi", "My item broke 45 days after delivery. What are my options?",
    [("defective-items", 2), ("warranty", 1), ("warranty", 2)],
    "It is outside the 30-day defective-items window, so it is referred for warranty review. Coverage depends on the product's warranty terms, and no replacement or refund is promised before the review.")
ask("multi", "My return was authorized yesterday. Has my refund been paid?",
    [("refund-timing", 3), ("refund-status", 2)],
    "No. An authorization is not a refund. No refund record exists until the warehouse receives the item, and the refund is issued after inspection.")
ask("multi", "Before you create my return, what will you show me, and can the result still change afterwards?",
    [("return-confirmation", 1), ("return-confirmation", 2), ("return-confirmation", 3)],
    "You see a summary of the item, quantity, reason, eligibility outcome and any fee, and the return is created only after you confirm it. Eligibility is checked again at creation, so it can still be refused if something changed.")
ask("multi", "The return policy changed after I placed my order. Which version applies to me?",
    [("policy-versioning", 1), ("policy-versioning", 2)],
    "Return eligibility and return shipping fees follow the version in effect on the date the order was placed, even if the policy changed afterwards.")
for question in ("Can I return an item I bought in a Northstar store in Canada?", "Do you price match other retailers?",
                 "Can I pay for an order with a gift card?", "Do you offer gift wrapping?"):
    ask("unanswerable", question, [], "The policies do not cover this. Say so and offer to escalate to support; do not invent a rule.")
qa = [{"qa_id": f"QA-{n:03d}", "split": "test" if n % 5 == 0 else "development", **record} for n, record in enumerate(qa, 1)]
save("evals/policy_qa.json", qa)

# ---------------------------------------------------------------- SQLite store
SCHEMA = """
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, email TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE products (product_id TEXT PRIMARY KEY, name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('electronics','standard')),
  seller_type TEXT NOT NULL CHECK (seller_type IN ('company','marketplace')),
  final_sale INTEGER NOT NULL CHECK (final_sale IN (0,1)),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0), currency TEXT NOT NULL);
CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  ordered_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('processing','shipped','delivered','cancelled')),
  cancelled_at TEXT, currency TEXT NOT NULL);
CREATE TABLE order_items (item_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
  product_id TEXT NOT NULL REFERENCES products(product_id), quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0));
CREATE TABLE shipments (shipment_id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE REFERENCES orders(order_id),
  carrier TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('shipped','delivered')), shipped_at TEXT NOT NULL,
  estimated_delivery TEXT NOT NULL, delivered_at TEXT);
CREATE TABLE returns (return_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
  item_id TEXT NOT NULL REFERENCES order_items(item_id), quantity INTEGER NOT NULL CHECK (quantity > 0),
  reason TEXT NOT NULL CHECK (reason IN ('defective','change_of_mind')), condition TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('authorized','received','refunded','rejected','cancelled')),
  created_at TEXT NOT NULL, received_at TEXT, shipping_fee_cents INTEGER NOT NULL CHECK (shipping_fee_cents >= 0),
  policy_id TEXT NOT NULL);
CREATE TABLE refunds (refund_id TEXT PRIMARY KEY, return_id TEXT NOT NULL UNIQUE REFERENCES returns(return_id),
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  status TEXT NOT NULL CHECK (status IN ('pending','submitted','paid')), created_at TEXT NOT NULL,
  submitted_at TEXT, paid_at TEXT, payment_reference TEXT, policy_id TEXT NOT NULL);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
CREATE INDEX idx_returns_item ON returns(item_id);
"""
db = ROOT / "northstar.sqlite"
if db.exists():
    db.unlink()
conn = sqlite3.connect(db)
conn.execute("PRAGMA foreign_keys=ON")
conn.executescript(SCHEMA)
for table, rows in tables.items():
    columns = list(rows[0])
    conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                     [[row[c] for c in columns] for row in rows])
conn.commit()
assert not conn.execute("PRAGMA foreign_key_check").fetchall()
conn.close()

counts = {**{name: len(rows) for name, rows in tables.items()}, "policy_documents": len(policies),
          "policy_chunks": len(chunks), "return_cases": len(cases), "policy_questions": len(qa), "adversarial_specs": 6}
save("manifest.json", {"synthetic": True, "schema_version": 2, "seed": SEED, "as_of": str(TODAY),
                       "v2_effective_from": str(V2_START), "counts": counts})
if __name__ == "__main__":
    print(json.dumps(counts))
