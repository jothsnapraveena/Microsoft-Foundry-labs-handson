"""Paired Model Router versus fixed-model benchmark. No handwritten router."""
import argparse
import json
from pathlib import Path
from time import perf_counter
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


def benchmark(client, deployments, cases, instructions, prices=None, repeats=1, checkpoint=None):
    result = []
    for repeat in range(repeats):
        for index, case in enumerate(cases):
            order = deployments if (index + repeat) % 2 == 0 else list(reversed(deployments))
            for name in order:
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
                    row.update(status="error", error_type=type(error).__name__, estimated_cost_usd=None)
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
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/benchmark.json")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be 1 through 20")
    if args.command == "plan":
        print(json.dumps({"cases": len(rows()), "targets": ["ROUTER_DEPLOYMENT", "FIXED_SMALL_DEPLOYMENT", "FIXED_LARGE_DEPLOYMENT"],
            "requests": len(rows()) * 3 * args.repeats, "cloud_calls_made": 0}, indent=2))
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
        def checkpoint(result):
            save(args.report, record(15, result, summary=summarize(result), price_config=prices))
        result = benchmark(client, deployments, rows(), text("assets/baseline-instructions.md"),
                           prices, args.repeats, checkpoint)
        print(json.dumps(summarize(result), indent=2))


if __name__ == "__main__":
    main()
