"""Pipeline coordination: triage, product search, writer and reviewer with a feedback loop."""
import json
import logging
from time import perf_counter
from uuid import uuid4

from agents import product, reviewer, triage, writer
from contracts import CHECK_GUIDANCE, ContractError, checks, parse_json, validate_case

AGENTS = {agent.NAME: agent for agent in (triage, product, writer, reviewer)}
PROMPTS = {name: agent.PROMPT for name, agent in AGENTS.items()}
PROMPT_VERSION = "retail-v3"
log = logging.getLogger("uvicorn.error")
MAX_REVISIONS = 2


def parse_output(role, raw):
    value = parse_json(raw)
    if role not in AGENTS or not AGENTS[role].valid(value):
        raise ContractError(f"Invalid {role} contract")
    return value


def message(kind, text, data=None):
    return {"type": kind, "message": text, "data": data or {}}


def start_message(role):
    return message("message", f"Starting {role} agent task...", {"agent": role})


def complete_message(role, data):
    return message(role, f"Completed {role} task", data)


class Pipeline:
    """Application orchestration over native SDK calls, with validated handoffs."""
    def __init__(self, complete, max_calls=12, stream=None):
        if not 4 <= max_calls <= 12:
            raise ValueError("Call budget must be 4 through 12")
        self.complete, self.max_calls, self.stream = complete, max_calls, stream

    def invoke(self, role, payload, result, stream=False):
        for attempt in range(2):
            if len(result["trace"]) >= self.max_calls:
                raise ContractError("Call budget exhausted")
            event = {"agent": role, "attempt": attempt + 1}
            result["trace"].append(event)
            tick = perf_counter()
            try:
                if stream and self.stream:
                    raw = ""
                    for token in self.stream(role, PROMPTS[role], json.dumps(payload)):
                        raw += token
                        # Tokens are unreviewed draft text; only the result event carries a reply.
                        yield message("partial", f"{role} token", {"text": token, "attempt": attempt + 1})
                else:
                    raw = self.complete(role, PROMPTS[role], json.dumps(payload))
                output = parse_output(role, raw)
                event["outcome"] = "valid"
                return output
            except ContractError:
                event["outcome"] = "invalid_contract"
                payload = {**payload, "format_feedback": "Return exactly the required JSON schema."}
                if attempt == 1:
                    raise
            except Exception as error:
                event["outcome"] = "backend_error"
                # Kept out of the trace and the response; the local console is the place to diagnose it.
                log.error("%s backend error: %s", role, error)
                raise
            finally:
                event["seconds"] = round(perf_counter() - tick, 4)

    def stages(self, case, result):
        facts = case["facts"]
        payload = {"trusted_facts": facts, "customer_message": case["customer"]}

        yield start_message("triage")
        category = yield from triage.classify(self, payload, result)
        yield complete_message("triage", {"category": category})
        if category != "mismatch":
            result["reason"] = "Unsupported category"
            return

        yield start_message("product")
        matches = yield from product.find_products(self, facts, result)
        result["catalog_matches"] = [item["id"] for item in matches]
        yield complete_message("product", {"matches": matches})
        payload["catalog_matches"] = matches

        for revision in range(MAX_REVISIONS + 1):
            yield start_message("writer")
            draft = yield from writer.write(self, payload, result)
            rules = checks(draft, facts)
            yield complete_message("writer", {"revision": revision})

            yield start_message("reviewer")
            review = yield from reviewer.review(self, payload, draft, result)
            failed = [name for name, passed in rules.items() if not passed]
            approved = not failed and review["approved"]
            yield complete_message("reviewer", {"approved": approved, "failed_checks": failed,
                                                "reasons": review["reasons"]})
            if approved:
                result.update(status="draft_ready", reply=draft, checks=rules)
                return
            payload = {**payload, "revision_feedback": {
                "required_fixes": [CHECK_GUIDANCE[name] for name in failed],
                "review_reasons": review["reasons"]}}
        result["reason"] = f"Draft failed review after {MAX_REVISIONS} revisions"

    def create(self, case):
        """Yield progress messages for one case; the last message carries the result."""
        validate_case(case)
        result = {"run_id": str(uuid4()), "case_id": case["id"], "status": "escalated",
                  "human_review_required": True, "reply": None, "trace": []}
        started = perf_counter()
        try:
            yield from self.stages(case, result)
        except Exception as error:
            result.update(status="escalated", reply=None, reason=type(error).__name__)
            yield message("error", "Run escalated", {"error": type(error).__name__})
        result["seconds"] = round(perf_counter() - started, 4)
        result["calls"] = len(result["trace"])
        yield message("result", f"Run {result['status']}", result)

    def run(self, case):
        for event in self.create(case):
            pass
        return event["data"]
