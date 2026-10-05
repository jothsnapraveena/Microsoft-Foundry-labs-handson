"""Evaluate the policy agent on evals/policy_qa.json and publish the run to Microsoft Foundry.

  python -m northstar.evals.policy_agent                      Show what a run would do. Free.
  python -m northstar.evals.policy_agent --confirm            Development split: run the agent, grade, publish.
  python -m northstar.evals.policy_agent --confirm --limit 5  A small sample first.
  python -m northstar.evals.policy_agent --confirm --from-rows data/eval/<run>/rows.jsonl   Re-grade saved answers.

Two kinds of metric, kept apart on purpose:
  Deterministic checks computed here from labels: retrieval recall and ranking, citation validity,
    citation precision and recall, correct abstention. No model is involved.
  Model-graded quality from the Azure AI Evaluation SDK: groundedness, relevance, response
    completeness, similarity, retrieval and coherence, each scored 1 to 5 by a judge model.

Model grades measure answer quality. They are never the check for citations or abstention.
Every question is a billed agent run, and each graded metric is another billed model call.
"""
import argparse
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

from .. import telemetry
from ..azure_login import SignInError, azure_credential, explain
from ..config import PROJECT_ROOT, AzureSettings, Settings, load_env_file, use_utf8_output
from .retrieval import dates_for, score

JUDGED = ("groundedness", "relevance", "response_completeness", "similarity", "retrieval", "coherence")
DETERMINISTIC = ("citation_valid", "abstention_correct", "retrieval_recall", "retrieval_mrr", "retrieval_ndcg",
                 "citation_precision", "citation_recall")
API_VERSION = "2025-04-01-preview"


def deterministic_metrics(question, retrieved, cited, invalid, verified, not_covered, top):
    """Label-based checks for one answer. Retrieval and citation overlap are undefined for unanswerable questions."""
    metrics = {"citation_valid": float(verified and not invalid),
               "abstention_correct": float(not_covered == (not question["answerable"]))}
    if question["answerable"]:
        expected = set(question["expected_chunk_ids"])
        ranked = score(retrieved, question["expected_chunk_ids"], top)
        metrics.update(retrieval_recall=ranked["recall"], retrieval_mrr=ranked["mrr"], retrieval_ndcg=ranked["ndcg"],
                       citation_precision=len(expected & set(cited)) / len(cited) if cited else 0.0,
                       citation_recall=len(expected & set(cited)) / len(expected))
    else:
        metrics.update(retrieval_recall=None, retrieval_mrr=None, retrieval_ndcg=None,
                       citation_precision=None, citation_recall=None)
    return metrics


def collect(agent, questions, as_of, top=6, progress=print):
    """Run the agent on each question and record what a grader needs."""
    rows = []
    for number, question in enumerate(questions, 1):
        started = time.perf_counter()
        answer = agent.ask(question["question"])
        seconds = round(time.perf_counter() - started, 2)
        retrieved = [item.chunk_id for item in answer.evidence]
        row = {"qa_id": question["qa_id"], "type": question["type"], "answerable": question["answerable"],
               "query": question["question"], "response": answer.answer, "ground_truth": question["expected_answer"],
               "context": "\n\n".join(f"[{item.chunk_id}] {item.title} / {item.section}: {item.text}" for item in answer.evidence)
                          or "No policy passage was retrieved.",
               "expected_chunk_ids": question["expected_chunk_ids"], "retrieved_chunk_ids": retrieved,
               "citations": answer.citations, "invalid_citations": answer.invalid_citations, "verified": answer.verified,
               "not_covered": answer.not_covered, "blocked": answer.blocked, "tool_calls": len(answer.retrievals),
               "latency_seconds": seconds, "agent_input_tokens": answer.input_tokens, "agent_output_tokens": answer.output_tokens,
               "retrieval_input_tokens": sum(call["input_tokens"] for call in answer.retrievals),
               "retrieval_output_tokens": sum(call["output_tokens"] for call in answer.retrievals),
               "response_id": answer.response_id, "trace_id": answer.trace_id, "prompt_version": answer.prompt_version,
               **deterministic_metrics(question, retrieved, answer.citations, answer.invalid_citations, answer.verified,
                                       answer.not_covered, top)}
        rows.append(row)
        progress(f"  {number}/{len(questions)} {question['qa_id']} {question['type']:12} verified={answer.verified} {seconds}s")
    return rows


def summarize(rows):
    def mean(key, subset=rows):
        values = [row[key] for row in subset if row.get(key) is not None]
        return round(statistics.mean(values), 3) if values else None
    latencies = sorted(row["latency_seconds"] for row in rows)
    summary = {"questions": len(rows), "deterministic": {key: mean(key) for key in DETERMINISTIC},
               "by_type": {kind: {"n": len(group), "retrieval_recall": mean("retrieval_recall", group),
                                  "citation_recall": mean("citation_recall", group), "citation_valid": mean("citation_valid", group)}
                           for kind in sorted({row["type"] for row in rows})
                           for group in [[row for row in rows if row["type"] == kind]]},
               "latency_seconds": {"p50": latencies[len(latencies) // 2],
                                   "p95": latencies[min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)]},
               "tokens": {key: sum(row[key] for row in rows) for key in
                          ("agent_input_tokens", "agent_output_tokens", "retrieval_input_tokens", "retrieval_output_tokens")}}
    cost = telemetry.estimated_cost_usd(summary["tokens"]["agent_input_tokens"] + summary["tokens"]["retrieval_input_tokens"],
                                        summary["tokens"]["agent_output_tokens"] + summary["tokens"]["retrieval_output_tokens"])
    if cost is not None:
        summary["estimated_cost_usd"] = cost        # an estimate from configured list prices, not a bill
    # Release gates: these must hold on every answer, whatever the quality scores are.
    summary["gates"] = {
        "no_citation_of_unretrieved_passage": all(not row["invalid_citations"] for row in rows),
        "every_answer_verified": all(row["verified"] for row in rows),
        "abstains_when_policies_do_not_cover": all(row["not_covered"] for row in rows if not row["answerable"]),
    }
    return summary


PORTAL_COLUMNS = ("qa_id", "type", "query", "response", "context", "ground_truth")


def write_portal_dataset(rows, path):
    """Answers in the flat, text-only shape the Foundry portal accepts for a Dataset evaluation."""
    path.write_text("".join(json.dumps({key: row[key] for key in PORTAL_COLUMNS}) + "\n" for row in rows), encoding="utf-8")
    return path


def write_portal_questions(questions, path):
    """Questions and expected answers only, for evaluating an agent the portal can run by itself."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"qa_id": q["qa_id"], "type": q["type"], "query": q["question"],
                                        "ground_truth": q["expected_answer"]}) + "\n" for q in questions), encoding="utf-8")
    return path


class LabelChecks:
    """Passes the deterministic metrics through the evaluation run so they are published beside the model grades."""
    def __call__(self, *, citation_valid, abstention_correct, retrieval_recall=None, retrieval_mrr=None, retrieval_ndcg=None,
                 citation_precision=None, citation_recall=None):
        values = dict(citation_valid=citation_valid, abstention_correct=abstention_correct, retrieval_recall=retrieval_recall,
                      retrieval_mrr=retrieval_mrr, retrieval_ndcg=retrieval_ndcg, citation_precision=citation_precision,
                      citation_recall=citation_recall)
        return {key: float("nan") if value is None or (isinstance(value, float) and math.isnan(value)) else float(value)
                for key, value in values.items()}


def grade(rows_path, output_dir, azure, credential, judge_deployment, run_name, publish, judges=True):
    """Run the Azure AI Evaluation SDK over saved rows. Returns its result, including the Foundry link when published."""
    from azure.ai.evaluation import (AzureOpenAIModelConfiguration, CoherenceEvaluator, GroundednessEvaluator, RelevanceEvaluator,
                                     ResponseCompletenessEvaluator, RetrievalEvaluator, SimilarityEvaluator, evaluate)
    evaluators = {"label_checks": LabelChecks()}
    if judges:
        model = AzureOpenAIModelConfiguration(azure_endpoint=azure.openai_endpoint, azure_deployment=judge_deployment,
                                              api_version=os.environ.get("AZURE_OPENAI_API_VERSION", API_VERSION))
        # GPT-5 and o-series deployments are reasoning models and need different request parameters.
        options = {"credential": credential, "is_reasoning_model": judge_deployment.lower().startswith(("gpt-5", "o1", "o3", "o4"))}
        evaluators.update(groundedness=GroundednessEvaluator(model, **options), relevance=RelevanceEvaluator(model, **options),
                          response_completeness=ResponseCompletenessEvaluator(model, **options),
                          similarity=SimilarityEvaluator(model, **options), retrieval=RetrievalEvaluator(model, **options),
                          coherence=CoherenceEvaluator(model, **options))
    mapping = {key: f"${{data.{key}}}" for key in DETERMINISTIC}
    return evaluate(data=str(rows_path), evaluators=evaluators, evaluation_name=run_name,
                    evaluator_config={"label_checks": {"column_mapping": mapping}},
                    azure_ai_project=azure.project_endpoint if publish else None,
                    output_path=str(output_dir / "evaluation_result.json"),
                    tags={"dataset": "policy_qa", "judge": judge_deployment if judges else "none"})


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--confirm", action="store_true", help="Required: the run makes billed calls")
    parser.add_argument("--split", choices=("development", "test", "all"), default="development")
    parser.add_argument("--limit", type=int, help="Only the first N questions")
    parser.add_argument("--from-rows", type=Path, help="Grade saved answers instead of running the agent again")
    parser.add_argument("--no-judges", action="store_true", help="Deterministic checks only")
    parser.add_argument("--no-publish", action="store_true", help="Keep results local; do not send the run to Foundry")
    parser.add_argument("--export-questions", action="store_true", help="Write the questions as a portal dataset and stop. Free")
    args = parser.parse_args(argv)
    load_env_file()
    use_utf8_output()
    settings, azure = Settings.from_env(), AzureSettings.from_env()
    as_of = settings.fixed_date or date.today()
    judge = os.environ.get("EVALUATION_MODEL_DEPLOYMENT", azure.planning_deployment)
    questions = [q for q in json.loads((settings.dataset_dir / "evals" / "policy_qa.json").read_text(encoding="utf-8"))
                 if args.split in ("all", q["split"])][:args.limit]
    if args.export_questions:
        path = write_portal_questions(questions, PROJECT_ROOT / "data" / "eval" / f"policy_qa_{args.split}_questions.jsonl")
        print(f"Wrote {len(questions)} questions to {path}")
        return 0
    graded = 0 if args.no_judges else len(JUDGED)
    if not args.confirm:
        print(f"Questions: {len(questions)} ({args.split} split)")
        print("Agent runs: " + ("none, grading saved answers" if args.from_rows else f"{len(questions)} on '{azure.agent_model}', each with a retrieval call"))
        print(f"Judge calls: about {len(questions) * graded} on '{judge}' ({', '.join(JUDGED) if graded else 'none'})")
        print(f"Publish to Foundry: {'no' if args.no_publish else azure.project_endpoint}")
        print("\nNothing was run. These calls are billed. Add --confirm to run.")
        return 2

    credential = azure_credential()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = PROJECT_ROOT / "data" / "eval" / f"policy-agent-{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.from_rows:
        rows = [json.loads(line) for line in args.from_rows.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        from ..agent.cli import build_agent
        print(f"Running the agent on {len(questions)} questions...")
        rows = collect(build_agent(), questions, as_of)
        telemetry.flush()
    rows_path = output_dir / "rows.jsonl"
    rows_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    write_portal_dataset(rows, output_dir / "portal_dataset.jsonl")
    summary = summarize(rows)
    prompt_version = rows[0].get("prompt_version", "unknown")
    run_name = f"northstar-policy-agent {prompt_version} {args.split} {stamp}"
    print(f"Grading with the Azure AI Evaluation SDK{'' if args.no_publish else ' and publishing to Foundry'}...")
    result = grade(rows_path, output_dir, azure, credential, judge, run_name, not args.no_publish, not args.no_judges)
    metrics = result.get("metrics") or {}
    # One mean score (1 to 5) and one pass rate per judge; the SDK reports several aliases of each.
    judged = {name: {"mean_score": round(metrics[f"{name}.{name}"], 3), "pass_rate": round(metrics.get(f"{name}.binary_aggregate", float("nan")), 3)}
              for name in JUDGED if isinstance(metrics.get(f"{name}.{name}"), (int, float))}
    report = {"run_name": run_name, "created_utc": stamp, "split": args.split, "as_of": str(as_of), "agent_model": azure.agent_model,
              "judge_model": None if args.no_judges else judge, "prompt_version": prompt_version,
              "dataset": "northstar-dataset/evals/policy_qa.json", "summary": summary, "model_graded": judged,
              "foundry_url": result.get("studio_url"), "published": not args.no_publish}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("run_name", "summary", "model_graded")}, indent=2))
    for row in rows:
        if not row["verified"] or row["invalid_citations"] or row["abstention_correct"] == 0:
            print(f"CHECK {row['qa_id']} ({row['type']}): verified={row['verified']} not_covered={row['not_covered']} "
                  f"invalid={row['invalid_citations']} trace={row['trace_id']}")
    print(f"\nLocal report: {output_dir / 'report.json'}")
    print(f"Foundry: {report['foundry_url'] or 'not published'}")
    return 0 if all(summary["gates"].values()) else 1


def main(argv=None):
    try:
        return run(argv)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    except Exception as error:
        try:
            explain(error)
        except SignInError as sign_in:
            print(sign_in, file=sys.stderr)
            return 1
    finally:
        telemetry.flush()


if __name__ == "__main__":
    sys.exit(main())
