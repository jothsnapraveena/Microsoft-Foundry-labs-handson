"""Shared Foundry Local configuration: one loaded model and chat client for all agents."""
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from types import SimpleNamespace

# Optional during test/help use; required when starting the native runtime.
try:
    from foundry_local_sdk import Configuration, FoundryLocalManager
except ImportError:
    Configuration = FoundryLocalManager = None

MODEL_ALIAS = "phi-3.5-mini"
# The SDK keeps one model cache per app name: ~/.<APP_NAME>/cache/models
APP_NAME = "retail_support_agents"


@contextmanager
def native_backend(alias, offline, runtime_dir):
    if FoundryLocalManager is None:
        raise ImportError("Install the native Foundry Local SDK from requirements.txt")
    # Step 1: initialize the in-process native runtime
    runtime_dir = runtime_dir.resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    FoundryLocalManager.initialize(Configuration(
        app_name=APP_NAME, logs_dir=str(runtime_dir / "logs")))
    model = FoundryLocalManager.instance.catalog.get_model(alias)
    if model is None:
        raise ValueError("Model alias unavailable")
    if model.is_loaded:
        raise ValueError("Unload the selected model first")
    # Step 2: use the cached model, downloading only when allowed
    if not model.is_cached:
        if offline:
            raise ValueError("Model is not downloaded; run once without offline mode")
        print(f"Downloading model: {alias} (this may take several minutes)...", flush=True)
        model.download()
    try:
        # Step 3: load the model into memory
        model.load()
        # Step 4: one chat client shared by every agent
        client = model.get_chat_client()
        client.settings.temperature, client.settings.max_tokens = 0.0, 500

        def messages(instructions, payload):
            return [{"role": "system", "content": instructions},
                    {"role": "user", "content": payload}]

        def complete(role, instructions, payload):
            response = client.complete_chat(messages(instructions, payload))
            return response.choices[0].message.content

        def stream(role, instructions, payload):
            for chunk in client.complete_streaming_chat(messages(instructions, payload)):
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        packages = {}
        for name in ("foundry-local-sdk", "foundry-local-sdk-winml"):
            try:
                packages[name] = version(name)
            except PackageNotFoundError:
                pass
        yield SimpleNamespace(complete=complete, stream=stream, metadata={
            "model_id": model.id, "alias": alias, "sdk_versions": packages,
            "temperature": 0.0, "max_tokens": 500,
            "orchestrator": "Python application using native Foundry Local SDK"})
    finally:
        model.unload()
