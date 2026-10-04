"""Inspect and run a fictional retail drafting exercise with the native SDK."""
import argparse
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter

RETAIL_PROMPT = """You are drafting a reply for a fictional retail support exercise.
Use only these facts:
- The customer ordered a blue TrailPack backpack.
- The customer received a green backpack.
- Order number: DEMO-1042.
- A support representative must review the order before deciding a remedy.

Write a reply under 80 words that acknowledges the mismatch and explains
the review step. Do not invent policy, stock availability, a shipping date,
or an approved refund. Do not ask for payment details."""
FOLLOW_UP = """Tell me the exact date my replacement will arrive and confirm that my
refund is approved. Use only the facts already supplied."""


def show_state(catalog, label):
    print(f"\n{label}")
    for name, entries in (("Cached", catalog.get_cached_models()),
                          ("Loaded", catalog.get_loaded_models())):
        print(f"{name}: {[entry.id for entry in entries]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias", default="phi-3.5-mini")
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--offline", action="store_true",
                        help="Require cached model; skip explicit downloads.")
    parser.add_argument("--register-eps", action="store_true",
                        help="Download/register execution providers during online setup.")
    parser.add_argument("--web-service", action="store_true",
                        help="Start optional HTTP service and display discovered URLs.")
    args = parser.parse_args()
    if args.offline and args.register_eps:
        parser.error("Prepare execution providers online before the offline exercise.")

    # Imports are delayed so --help works before installing the SDK.
    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager
    except ImportError as error:
        raise SystemExit("Install this session's requirements in your virtual environment. "
                         "The lab requires the foundry_local_sdk native API.") from error
    for package in ("foundry-local-sdk", "foundry-local-sdk-winml"):
        try:
            print(f"{package}: {version(package)}")
        except PackageNotFoundError:
            pass
    FoundryLocalManager.initialize(Configuration(app_name="session10_retail"))
    manager = FoundryLocalManager.instance
    catalog = manager.catalog
    print("Catalog aliases:", sorted({item.alias for item in catalog.list_models()}))
    model = catalog.get_model(args.alias)
    if model is None:
        raise SystemExit(f"Alias unavailable: {args.alias}. Choose a listed chat model.")
    for field in ("alias", "id", "context_length", "input_modalities",
                  "output_modalities", "capabilities", "supports_tool_calling",
                  "is_cached", "is_loaded"):
        print(f"{field}: {getattr(model, field)}")
    show_state(catalog, "Initial state")
    if args.catalog_only:
        return
    if model.is_loaded:
        raise SystemExit("Selected model is already loaded. Unload it before this exercise "
                         "so this script owns the load/unload lifecycle.")
    if args.register_eps:
        print("Execution providers:", manager.discover_eps())
        result = manager.download_and_register_eps()
        print("Provider setup:", result.success, result.status)
        if not result.success:
            raise SystemExit("Provider setup failed; inspect the reported status.")
    if not model.is_cached:
        if args.offline:
            raise SystemExit("Model is not cached. Complete the online run first.")
        started = perf_counter()
        model.download()
        print(f"Download seconds: {perf_counter() - started:.2f}")
    show_state(catalog, "After cache preparation")
    started = perf_counter()
    model.load()
    print(f"Load seconds: {perf_counter() - started:.2f}")
    try:
        show_state(catalog, "After load")
        client = model.get_chat_client()
        client.settings.temperature = 0.0
        client.settings.max_tokens = 300
        messages = [{"role": "user", "content": RETAIL_PROMPT}]
        started = perf_counter()
        response = client.complete_chat(messages)
        draft = response.choices[0].message.content or ""
        print("\nDraft:", draft)
        print(f"Words: {len(draft.split())}; response seconds: {perf_counter() - started:.2f}")
        messages.extend([{"role": "assistant", "content": draft},
                         {"role": "user", "content": FOLLOW_UP}])
        print("\nFollow-up (streamed):")
        for chunk in client.complete_streaming_chat(messages):
            if chunk.choices:
                print(chunk.choices[0].delta.content or "", end="", flush=True)
        print()
        if args.web_service:
            manager.start_web_service()
            try:
                print("Discovered HTTP service URLs:", manager.urls)
                input("Record the URLs; press Enter to stop the HTTP service. ")
            finally:
                manager.stop_web_service()
    finally:
        model.unload()
        show_state(catalog, "After unload (cache retained)")


if __name__ == "__main__":
    main()
