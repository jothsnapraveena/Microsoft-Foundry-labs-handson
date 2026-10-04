"""Reviewer agent: accepts a draft for human review or sends it back for revision."""
from contracts import COMMON

NAME = "reviewer"
PROMPT = COMMON + ('\nYou are the reviewer. Judge only the text in draft. Approve it when it states '
                   'order_id, ordered and received as they appear in trusted_facts, says a human will '
                   'review the order, and claims nothing else. Reject it when a fact is wrong or missing, '
                   'or when it adds a policy, price, stock, date, remedy or payment request. '
                   'Return {"approved":true,"reasons":[]} or '
                   '{"approved":false,"reasons":["specific issue"]}. Approval is for human review only.')


def valid(value):
    return (set(value) == {"approved", "reasons"} and type(value["approved"]) is bool
            and isinstance(value["reasons"], list) and len(value["reasons"]) <= 10
            and all(isinstance(r, str) and 0 < len(r) <= 500 for r in value["reasons"])
            and (not value["reasons"] if value["approved"] else bool(value["reasons"])))


def review(pipeline, payload, draft, result):
    # The customer message is withheld: the reviewer compares the draft with trusted data only.
    trusted = {key: payload[key] for key in ("trusted_facts", "catalog_matches")}
    return (yield from pipeline.invoke(NAME, {**trusted, "draft": draft}, result))
