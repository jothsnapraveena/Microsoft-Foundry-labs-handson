"""A genuine Foundry Responses server; --local explicitly disables model calls."""
import argparse
import asyncio
import json
import os
from azure.ai.agentserver.responses import ResponsesAgentServerHost, TextResponse
from assistant import answer
from support import ROOT, chat, load_env, project, required, text

if not os.environ.get("FOUNDRY_PROJECT_ENDPOINT"):
    os.environ.setdefault("AGENTSERVER_STATE_ROOT", str(ROOT / "artifacts/agentserver"))
app = ResponsesAgentServerHost(configure_observability=None)


def respond(question):
    if os.environ.get("MODEL_BACKEND") == "local":
        return answer(question, os.environ.get("HANDLER_VERSION", "v2"))
    if not os.environ.get("AZURE_AI_PROJECT_ENDPOINT") and os.environ.get("FOUNDRY_PROJECT_ENDPOINT"):
        os.environ["AZURE_AI_PROJECT_ENDPOINT"] = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    with project() as (_, client):
        def synthesize(result):
            return chat(client, required("MODEL_DEPLOYMENT"), text("assets/baseline-instructions.md"),
                        json.dumps({"trusted_lookup": result}))["answer"]
        return answer(question, os.environ.get("HANDLER_VERSION", "v2"), synthesize)


@app.response_handler
async def handle(request, context, _cancellation_signal):
    question = await context.get_input_text() or ""
    result = await asyncio.to_thread(respond, question)
    return TextResponse(context, request, text=result["answer"])


def configure_tracing():
    if os.environ.get("TRACE_EXPORT") == "console":
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
    elif os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    load_env()
    if args.local:
        os.environ["MODEL_BACKEND"] = "local"
    configure_tracing()
    app.run(host="0.0.0.0", port=8088)
