"""Read-only checklist lookup with a deliberate, observable fault."""
import json
import re
from support import ROOT


class LookupFailure(RuntimeError):
    pass


def get_checklist(device):
    if not isinstance(device, str) or not re.fullmatch(r"(?:W-\d{3}|DEMO-FAIL)", device):
        raise ValueError("invalid_device_id")
    if device == "DEMO-FAIL":
        raise LookupFailure("DEMO_LOOKUP_FAILURE")
    equipment = json.loads((ROOT / "data/equipment.json").read_text())
    match = next((d for d in equipment["devices"] if d["device_id"] == device), None)
    return {"status": "ok", **match} if match else {"status": "unknown", "device_id": device}


def answer(question, handler_version="v2", synthesize=None):
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    tracer = trace.get_tracer("s18.willow")
    device = re.search(r"\b(?:W-\d{3}|DEMO-FAIL)\b", question)
    if not device:
        return {"answer": "Provide a device ID such as W-101.", "status": "missing_device"}
    with tracer.start_as_current_span("willow.answer") as outer:
        outer.set_attribute("willow.handler_version", handler_version)
        with tracer.start_as_current_span("execute_tool get_checklist") as span:
            span.set_attribute("device_id", device.group())
            try:
                result = get_checklist(device.group())
                span.set_attribute("lookup.outcome", result["status"])
            except LookupFailure:
                span.set_attribute("lookup.outcome", "error")
                span.set_attribute("error.type", "DEMO_LOOKUP_FAILURE")
                span.set_status(Status(StatusCode.ERROR, "controlled lookup failure"))
                if handler_version == "v1":
                    raise
                result = {"status": "error", "device_id": device.group(), "error_code": "DEMO_LOOKUP_FAILURE"}
        if result["status"] == "error":
            message = "The checklist could not be retrieved. Please contact the equipment owner."
        elif result["status"] == "unknown":
            message = "This device is unknown; no checklist is available."
        elif synthesize:
            with tracer.start_as_current_span("gen_ai.chat") as span:
                span.set_attribute("gen_ai.operation.name", "chat")
                message = synthesize(result)
        else:
            message = result["device_id"] + ": " + "; ".join(result["checklist"])
        context = outer.get_span_context()
        return {"answer": message, "status": result["status"],
                "trace_id": format(context.trace_id, "032x") if context.is_valid else None, "handler_version": handler_version}
