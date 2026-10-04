"""Run and evaluate the bounded four-agent workflow using Foundry Local."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src/api"))
from contracts import validate_case
from foundry_config import MODEL_ALIAS, native_backend
from orchestrator import PROMPT_VERSION, PROMPTS, Pipeline


def run_with_progress(pipeline, case):
    """Print each agent's progress, as the web service streams it, and return the result."""
    for event in pipeline.create(case):
        if event["type"] == "partial":
            print(event["data"]["text"], end="", file=sys.stderr, flush=True)
        elif event["type"] != "result":
            print(f"\n[{event['type']}] {event['message']}", file=sys.stderr)
    return event["data"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "evaluate"))
    parser.add_argument("--alias", default=MODEL_ALIAS)
    parser.add_argument("--offline", action="store_true", help="Prevent explicit model downloads")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parents[1] / "eval/cases.jsonl")
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation.json"))
    parser.add_argument("--runtime-dir", type=Path, default=Path("artifacts/runtime"))
    parser.add_argument("--max-calls", type=int, choices=range(4, 13), default=12)
    parser.add_argument("--min-ready-rate", type=float, default=1.0)
    parser.add_argument("--max-latency-seconds", type=float, default=120.0)
    args = parser.parse_args()
    if not 0 <= args.min_ready_rate <= 1 or not 0 < args.max_latency_seconds < float("inf"):
        parser.error("Invalid evaluation thresholds")
    dataset = args.dataset.read_bytes()
    cases = [json.loads(line) for line in dataset.decode("utf-8").splitlines() if line.strip()]
    if not cases:
        parser.error("Empty dataset")
    for case in cases:
        validate_case(case)
    if len({c["id"] for c in cases}) != len(cases):
        parser.error("Duplicate case IDs")
    with native_backend(args.alias, args.offline, args.runtime_dir) as backend:
        if args.command == "run":
            pipeline = Pipeline(backend.complete, args.max_calls, stream=backend.stream)
            results = [run_with_progress(pipeline, cases[0])]
        else:
            pipeline = Pipeline(backend.complete, args.max_calls)
            results = [pipeline.run(case) for case in cases]
    ready_rate = sum(r["status"] == "draft_ready" for r in results) / len(results)
    passed = ready_rate >= args.min_ready_rate and all(r["seconds"] <= args.max_latency_seconds for r in results)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), **backend.metadata,
              "prompt_version": PROMPT_VERSION, "dataset_sha256": hashlib.sha256(dataset).hexdigest(),
              "prompts_sha256": hashlib.sha256(json.dumps(PROMPTS, sort_keys=True).encode()).hexdigest(),
              "ready_rate": ready_rate, "passed": passed, "results": results,
              "thresholds": {"min_ready_rate": args.min_ready_rate,
                             "max_latency_seconds": args.max_latency_seconds}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "ready_rate": ready_rate, "passed": passed}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Startup or report failure ({type(error).__name__}). Check dataset, SDK, catalog "
              "connectivity, model cache and writable output directory.", file=sys.stderr)
        raise SystemExit(2) from None
