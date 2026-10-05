"""OpenTelemetry tracing for application and tool logic.

Foundry records server-side traces for the agent on its own. These spans add what only
this process knows: which policy passages were retrieved, whether citations checked out,
and what the backend decided. They carry ids, counts and outcomes, never the customer's
words, the answer text or order contents, unless NORTHSTAR_TRACE_CONTENT=1 is set.

NORTHSTAR_TRACING selects the exporter: "azure" (the Application Insights resource connected
to the Foundry project), "console" (print spans locally), or unset for no export.
"""
from contextlib import contextmanager
import os

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("northstar")
_provider = None


def tracing_mode():
    return os.environ.get("NORTHSTAR_TRACING", "off").lower()


def content_recording():
    return os.environ.get("NORTHSTAR_TRACE_CONTENT") == "1"


def configure(project_client=None):
    """Start exporting spans. Returns a short description of where they go, or None when tracing is off."""
    global _provider
    mode = tracing_mode()
    if mode in ("off", "", "0") or _provider is not None:
        return None
    if mode == "console":
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
        _provider = TracerProvider()
        _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(_provider)
        return "console"
    if mode != "azure":
        raise ValueError("NORTHSTAR_TRACING must be azure, console or off")
    connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection:
        if project_client is None:
            raise ValueError("Tracing to Azure needs a Foundry project client or APPLICATIONINSIGHTS_CONNECTION_STRING")
        # The connection string identifies the telemetry resource; it is fetched at run time and never stored.
        connection = project_client.telemetry.get_application_insights_connection_string()
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=connection)
    _provider = trace.get_tracer_provider()
    return "Application Insights"


def flush():
    """Send buffered spans before the process exits."""
    if _provider is not None and hasattr(_provider, "force_flush"):
        _provider.force_flush()


def current_trace_id():
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def clean(attributes):
    """Drop empty values and flatten lists."""
    result = {}
    for key, value in attributes.items():
        if value is None:
            continue
        # Lists become one comma-separated string, which is easy to filter on in Application Insights.
        result[key] = ",".join(str(item) for item in value) if isinstance(value, (list, tuple, set)) else value
    return result


@contextmanager
def span(name, **attributes):
    """A span that records the error type on failure. Attribute values must already be redacted."""
    with tracer.start_as_current_span(name, attributes=clean(attributes)) as active:
        try:
            yield active
        except Exception as error:
            active.set_status(Status(StatusCode.ERROR, type(error).__name__))
            active.set_attribute("error.type", type(error).__name__)
            raise


def set_attributes(active, **attributes):
    for key, value in clean(attributes).items():
        active.set_attribute(key, value)


def estimated_cost_usd(input_tokens, output_tokens):
    """An ESTIMATE from configurable list prices, or None when no prices are configured.

    Set NORTHSTAR_PRICE_INPUT_PER_1M and NORTHSTAR_PRICE_OUTPUT_PER_1M (US dollars per million
    tokens) to your own rates. This is not a bill.
    """
    try:
        price_in = float(os.environ["NORTHSTAR_PRICE_INPUT_PER_1M"])
        price_out = float(os.environ["NORTHSTAR_PRICE_OUTPUT_PER_1M"])
    except (KeyError, ValueError):
        return None
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)
