"""Retrieval quality on evals/policy_qa.json, scored against the labeled evidence chunks.

  python -m northstar.evals.retrieval --local                     Keyword fallback, free
  python -m northstar.evals.retrieval --confirm [--effort low] [--split development] [--top 6]

Deterministic metrics only: no model judges anything here. The knowledge base run makes
one retrieval call per question, which is billed.
"""
import argparse
from datetime import date
import json
import math
from pathlib import Path
import statistics
import sys

from ..azure_login import SignInError, explain
from ..config import Settings, load_env_file, use_utf8_output
from ..rag.catalog import load_chunks
from ..rag.retrieval import EFFORTS, LocalKeywordRetriever


def score(retrieved, relevant, k):
    """Metrics for one question. retrieved is ranked; relevant is the labeled evidence."""
    top, wanted = retrieved[:k], set(relevant)
    hits = [chunk_id in wanted for chunk_id in top]
    first = next((position for position, hit in enumerate(hits, 1) if hit), None)
    gain = sum(1 / math.log2(position + 1) for position, hit in enumerate(hits, 1) if hit)
    ideal = sum(1 / math.log2(position + 1) for position in range(1, min(len(wanted), k) + 1))
    return {"recall": sum(hits) / len(wanted), "precision": sum(hits) / len(top) if top else 0.0,
            "hit": float(any(hits)), "all_found": float(sum(hits) == len(wanted)),
            "mrr": 1 / first if first else 0.0, "ndcg": gain / ideal if ideal else 0.0}


def dates_for(question, as_of):
    reference = date.fromisoformat(question["reference_date"])
    return (reference if question["date_field"] == "order_date" else as_of,
            reference if question["date_field"] == "event_date" else as_of)


def evaluate(retriever, questions, as_of, k, effort=None):
    rows = []
    for question in questions:
        order_date, event_date = dates_for(question, as_of)
        result = retriever.retrieve(question["question"], order_date, event_date, effort, k)
        retrieved = [item.chunk_id for item in result.evidence]
        row = {"qa_id": question["qa_id"], "type": question["type"], "question": question["question"],
               "expected": question["expected_chunk_ids"], "retrieved": retrieved, "rejected": result.rejected,
               "sub_queries": len(result.sub_queries), "input_tokens": result.input_tokens,
               "output_tokens": result.output_tokens, "service_ms": result.elapsed_ms}
        if question["answerable"]:
            row.update(score(retrieved, question["expected_chunk_ids"], k))
        rows.append(row)
    return rows


def summarize(rows, k):
    answerable = [row for row in rows if "recall" in row]
    mean = lambda rows_, key: round(statistics.mean(row[key] for row in rows_), 3) if rows_ else None
    summary = {"questions": len(rows), "answerable": len(answerable), "k": k}
    for key in ("recall", "precision", "hit", "all_found", "mrr", "ndcg"):
        summary[f"{key}@{k}" if key != "mrr" else "mrr"] = mean(answerable, key)
    summary["by_type"] = {kind: {"n": len(group), f"recall@{k}": mean(group, "recall"), "mrr": mean(group, "mrr")}
                          for kind in sorted({row["type"] for row in answerable})
                          for group in [[row for row in answerable if row["type"] == kind]]}
    # A policy outside its effective dates reaching the evidence would be a versioning failure.
    summary["rejected_references"] = sum(len(row["rejected"]) for row in rows)
    latencies = sorted(row["service_ms"] for row in rows)
    summary["service_ms_p50"] = latencies[len(latencies) // 2]
    summary["service_ms_p95"] = latencies[min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)]
    summary["input_tokens"] = sum(row["input_tokens"] for row in rows)
    summary["output_tokens"] = sum(row["output_tokens"] for row in rows)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local", action="store_true", help="Keyword fallback instead of Azure AI Search")
    parser.add_argument("--confirm", action="store_true", help="Required for the billed knowledge base run")
    parser.add_argument("--effort", choices=EFFORTS, default="low")
    parser.add_argument("--split", choices=("development", "test", "all"), default="development")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    load_env_file()
    use_utf8_output()
    settings = Settings.from_env()
    as_of = settings.fixed_date or date.today()
    questions = [q for q in json.loads((settings.dataset_dir / "evals" / "policy_qa.json").read_text(encoding="utf-8"))
                 if args.split in ("all", q["split"])]
    if args.local:
        chunks, problems = load_chunks(settings.dataset_dir)
        if problems:
            raise SystemExit("\n".join(problems))
        retriever, backend = LocalKeywordRetriever(chunks, settings.region), "local-keyword-fallback"
    elif not args.confirm:
        print(f"This makes {len(questions)} billed retrieval calls at '{args.effort}' effort. Add --confirm to run, or --local for the free fallback.")
        return 2
    else:
        from ..rag.cli import provisioner
        retriever, backend = provisioner().retriever(args.effort, settings.region), "azure-ai-search-knowledge-base"
    try:
        rows = evaluate(retriever, questions, as_of, args.top, args.effort)
    except Exception as error:
        try:
            explain(error)
        except SignInError as sign_in:
            print(sign_in, file=sys.stderr)
            return 1
    report = {"backend": backend, "effort": None if args.local else args.effort, "split": args.split, "as_of": str(as_of),
              "summary": summarize(rows, args.top), "rows": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("backend", "effort", "split", "summary")}, indent=2))
    misses = [row for row in rows if row.get("all_found") == 0.0]
    for row in misses:
        missing = [chunk for chunk in row["expected"] if chunk not in row["retrieved"]]
        print(f"MISSED {row['qa_id']} ({row['type']}): {missing}  <- {row['question'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
