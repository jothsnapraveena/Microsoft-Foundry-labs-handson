"""Writer agent: drafts the reply and streams tokens when the backend supports it."""
from contracts import COMMON

NAME = "writer"
PROMPT = COMMON + ('\nReturn {"reply":"..."}. Use fewer than 80 words. State what the customer ordered and '
                   'what the customer received, quoting order_id, ordered and received exactly as written. '
                   'Say that a human support representative will review the order. '
                   'catalog_matches only confirm what the items are: do not list them, quote product IDs, '
                   'or say anything is available or in stock. '
                   'Apply every item in revision_feedback if supplied.')


def valid(value):
    return (set(value) == {"reply"} and isinstance(value["reply"], str)
            and bool(value["reply"].strip()) and len(value["reply"]) <= 2000)


def write(pipeline, payload, result):
    return (yield from pipeline.invoke(NAME, payload, result, stream=True))["reply"]
