"""Paired Model Router versus fixed-model benchmark. No handwritten router."""
import argparse
import json
import math
from pathlib import Path
from time import perf_counter, sleep
from support import ROOT, chat, confirm, exact_json, project, record, required, rows, save, stats, text


def estimate_cost(usage, billed_key, prices):
    entry = prices.get("models", {}).get(billed_key)
    if not entry or not usage:
        return None
    # A response model name is not guaranteed to identify Azure billing.
    if not entry.get("verified_billing_match") or not prices.get("price_date"):
        return None
    cached = ((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    incoming, outgoing = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if incoming is None or outgoing is None:
        return None
    if cached and "cached_input_per_million" not in entry:
        return None
    return ((incoming - cached) * entry["input_per_million"]
            + cached * entry.get("cached_input_per_million", 0)
            + outgoing * entry["output_per_million"]) / 1_000_000


def benchmark(client, deployments, cases, instructions, prices=None, repeats=1, checkpoint=None, request_interval=0):
    result = []
    for repeat in range(repeats):
        for index, case in enumerate(cases):
            order = deployments if (index + repeat) % 2 == 0 else list(reversed(deployments))
            for name in order:
                if result and request_interval:
                    sleep(request_interval)
                row = {"case_id": case["id"], "category": case["category"], "deployment": name,
                       "repeat": repeat + 1, "pass": None, "expected": case["expected"]}
                tick = perf_counter()
                try:
                    response = chat(client, name, instructions, case["input"])
                    row.update(status="completed", **response)
                    if isinstance(case["expected"], dict):
                        row["pass"] = exact_json(row["answer"], case["expected"])
                    else:
                        row["review_required"] = True
                    row["estimated_cost_usd"] = estimate_cost(row["usage"], row["response_model"], prices or {})
                except Exception as error:
                    row.update(status="error", error_type=type(error).__name__, estimated_cost_usd=None,
                               error_code=getattr(error, "code", None),
                               http_status=getattr(error, "status_code", None),
                               request_id=getattr(error, "request_id", None))
                    if isinstance(case["expected"], dict):
                        row["pass"] = False
                row["latency_ms"] = round((perf_counter() - tick) * 1000, 2)
                result.append(row)
                if checkpoint:
                    checkpoint(result)
    return result


def summarize(result):
    summary = {}
    for deployment in sorted({r["deployment"] for r in result}):
        group = [r for r in result if r["deployment"] == deployment]
        known = [r["estimated_cost_usd"] for r in group if r.get("estimated_cost_usd") is not None]
        summary[deployment] = {**stats(group),
            "by_task": {task: stats([r for r in group if r["category"] == task])
                        for task in sorted({r["category"] for r in group})},
            "known_cost_usd": sum(known) if known else None,
            "unknown_cost_rows": len(group) - len(known)}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "run", "summarize"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int, help="First N cases per deployment; use 1 for a three-call smoke test")
    parser.add_argument("--request-interval", type=float, default=7,
                        help="Seconds between calls; adjust to your deployment limits (default 7)")
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/benchmark.json")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be 1 through 20")
    if args.limit is not None and not 1 <= args.limit <= len(rows()):
        parser.error("limit must be between 1 and the fixture count")
    if not math.isfinite(args.request_interval) or args.request_interval < 0:
        parser.error("request-interval must be finite and nonnegative")
    cases = rows()[:args.limit]
    if args.command == "plan":
        print(json.dumps({"cases": len(cases), "targets": ["ROUTER_DEPLOYMENT", "FIXED_SMALL_DEPLOYMENT", "FIXED_LARGE_DEPLOYMENT"],
            "requests": len(cases) * 3 * args.repeats, "cloud_calls_made": 0}, indent=2))
        return
    if args.command == "summarize":
        report = json.loads(args.report.read_text())
        report["summary"] = summarize(report["results"])
        save(args.report, report)
        print(json.dumps(report["summary"], indent=2))
        return
    confirm(args)
    prices = json.loads(args.prices.read_text()) if args.prices else {}
    with project() as (_, client):
        deployments = [required(k) for k in ("ROUTER_DEPLOYMENT", "FIXED_SMALL_DEPLOYMENT", "FIXED_LARGE_DEPLOYMENT")]
        if len(set(deployments)) != 3:
            raise ValueError("Choose three distinct deployments")
        report = record(15, [], summary={}, price_config=prices, execution_status="running",
                        project_endpoint=required("AZURE_AI_PROJECT_ENDPOINT"),
                        deployments=deployments, repeats=args.repeats,
                        request_interval_seconds=args.request_interval)
        def checkpoint(result):
            report.update(results=result, summary=summarize(result))
            save(args.report, report)
        checkpoint([])
        result = benchmark(client, deployments, cases, text("assets/baseline-instructions.md"),
                           prices, args.repeats, checkpoint, args.request_interval)
        report["execution_status"] = "error" if any(r["status"] == "error" for r in result) else "completed"
        save(args.report, report)
        print(json.dumps(summarize(result), indent=2))
        if report["execution_status"] == "error":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
