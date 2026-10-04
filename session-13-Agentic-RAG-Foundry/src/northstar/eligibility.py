"""Deterministic return eligibility. Every number comes from policies.json, never from prose."""
from dataclasses import dataclass
from datetime import date

from .policies import PolicyConflict

REASONS = ("change_of_mind", "defective")
CONDITIONS = ("unused", "opened", "damaged")


@dataclass(frozen=True)
class ReturnRequest:
    order_id: str
    item_id: str
    quantity: int
    reason: str
    condition: str
    accessories_present: bool
    original_packaging: bool

    def validate(self):
        if type(self.quantity) is not int:
            raise ValueError("quantity must be an integer")
        if self.reason not in REASONS:
            raise ValueError(f"reason must be one of {REASONS}")
        if self.condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        if type(self.accessories_present) is not bool or type(self.original_packaging) is not bool:
            raise ValueError("accessories_present and original_packaging must be true or false")


@dataclass(frozen=True)
class Decision:
    outcome: str                    # eligible | ineligible | review_required
    reasons: tuple
    policy_ids: tuple               # primary policy first
    fee_cents: int | None = None
    days_since_delivery: int | None = None


def evaluate_return(policies, *, order, product, item_quantity, reserved_quantity, delivered_at, request, today, region):
    """Apply the return rules in their documented order. Ownership is checked by the caller."""
    ordered = date.fromisoformat(order["ordered_at"])
    try:
        if order["status"] != "delivered" or not delivered_at:
            # Operational policy: the version in effect today applies.
            return Decision("ineligible", ("order_not_delivered",), (policies.applicable("shipping-status", today, region).policy_id,))
        days = (today - date.fromisoformat(delivered_at)).days
        rule = lambda topic: policies.applicable(topic, ordered, region)     # eligibility applies by order date

        def decided(outcome, reason, topic, fee=None, extra=()):
            return Decision(outcome, (reason, *extra), (rule(topic).policy_id,) + ((rule("return-shipping").policy_id,) if fee is not None else ()),
                            fee, days)

        if not 1 <= request.quantity <= item_quantity:
            return decided("ineligible", "quantity_out_of_range", "partial-returns")
        if request.quantity > item_quantity - reserved_quantity:
            return decided("ineligible", "quantity_already_returned", "duplicate-returns")
        if product["seller_type"] == "marketplace":
            return decided("review_required", "marketplace_seller_review", "marketplace")
        defect = request.reason == "defective"
        if product["final_sale"]:
            if defect:
                return decided("review_required", "final_sale_defect_review", "final-sale")
            return decided("ineligible", "final_sale_no_change_of_mind", "final-sale")
        fees = rule("return-shipping").parameters
        if defect:
            if days <= rule("defective-items").parameters["defect_window_days"]:
                return decided("eligible", "defect_within_window", "defective-items", fees["defect_fee_cents"])
            return decided("review_required", "defect_outside_window_warranty_review", "warranty")
        topic = f"{product['category']}-returns"
        failures = []
        if days > rule(topic).parameters["change_of_mind_window_days"]:
            failures.append("outside_return_window")
        if product["category"] == "electronics":
            if request.condition == "damaged":
                failures.append("item_damaged")
            if not request.accessories_present:
                failures.append("accessories_missing")
        else:
            if request.condition != "unused":
                failures.append("item_not_unused")
            if not request.original_packaging:
                failures.append("original_packaging_missing")
        if failures:
            return decided("ineligible", failures[0], topic, extra=tuple(failures[1:]))
        return decided("eligible", "within_return_window", topic, fees["change_of_mind_fee_cents"])
    except (PolicyConflict, KeyError):
        # Missing, overlapping or incomplete policy: a person decides, the engine does not guess.
        return Decision("review_required", ("policy_conflict",), ())
