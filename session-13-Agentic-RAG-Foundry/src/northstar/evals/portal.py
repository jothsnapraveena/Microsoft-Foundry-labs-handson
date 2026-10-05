"""Evaluations and traffic that show up inside the Foundry portal, on the agents themselves.

  python -m northstar.evals.portal status
  python -m northstar.evals.portal continuous --confirm   Grade every new response of the portal agent, as it happens.
  python -m northstar.evals.portal traffic --confirm      Ask the portal agent sample questions, to fill Traces and Monitor.
  python -m northstar.evals.portal agent-run --confirm    Foundry runs the portal agent on the questions and grades it.
  python -m northstar.evals.portal dataset-run --confirm  Foundry grades saved answers on the RAG metrics (no agent calls).
  python -m northstar.evals.portal remove --confirm       Delete the continuous evaluation rules.

Everything here targets one agent, the portal agent, because Foundry can run it by itself and
one monitored agent keeps the cost down. Set NORTHSTAR_MONITORED_AGENT to choose another.
Results appear under Evaluations and on the agent's Monitor tab. They complement, and do not replace, the label-based run in
evals/policy_agent.py: Foundry's graders judge style and adherence, and do not know which
policy passage is correct.

Continuous evaluation needs the Foundry project's managed identity to hold the Foundry User role
on the Foundry resource (docs/azure-setup.md). Every graded response is a billed model call.
"""
import argparse
import json
import os
import sys
import time

from ..azure_login import SignInError, azure_credential, explain
from ..config import AzureSettings, Settings, load_env_file, use_utf8_output

# Graders that need only the question and the response. Each scores 1 to 5 using the judge model.
QUALITY_GRADERS = ("coherence", "fluency", "relevance", "intent_resolution", "task_adherence")
# Graders for saved answers: each row already holds the question, answer, retrieved evidence and expected answer.
DATASET_GRADERS = {
    "groundedness": ("query", "response", "context"),
    "retrieval": ("query", "context"),
    "relevance": ("query", "response"),
    "response_completeness": ("response", "ground_truth"),
    "similarity": ("query", "response", "ground_truth"),
    "coherence": ("query", "response"),
}
RULE_PREFIX = "northstar-continuous-"
TRAFFIC = [
    "How many days do I have to return headphones I changed my mind about?",
    "What is the return shipping fee for a change-of-mind return?",
    "Can I cancel an order that has already shipped?",
    "My item broke 45 days after delivery. What are my options?",
    "Do I need the original packaging to return a defective item?",
    "My marketplace item arrived broken. Do I get free return shipping?",
    "My return was authorized yesterday. Has my refund been paid?",
    "Do you price match other retailers?",
]


def monitored_agent():
    return os.environ.get("NORTHSTAR_MONITORED_AGENT") or os.environ.get("NORTHSTAR_PORTAL_AGENT", "northstar-portal-agent")


def criteria(judge, response_field):
    """Foundry built-in graders. Content-safety graders need no judge model."""
    from azure.ai.projects.models import TestingCriterionAzureAIEvaluator
    mapping = {"query": "{{item.query}}", "response": response_field} if response_field else None
    graders = [TestingCriterionAzureAIEvaluator(type="azure_ai_evaluator", name="violence", evaluator_name="builtin.violence",
                                                **({"data_mapping": mapping} if mapping else {}))]
    for name in QUALITY_GRADERS:
        options = {"initialization_parameters": {"model": judge}}
        if mapping:
            # Task adherence judges the whole run, including tool calls; the others judge the final text.
            options["data_mapping"] = {**mapping, "response": "{{sample.output_items}}"} if name == "task_adherence" else mapping
        graders.append(TestingCriterionAzureAIEvaluator(type="azure_ai_evaluator", name=name, evaluator_name=f"builtin.{name}", **options))
    return graders


def setup_continuous(project, judge, max_hourly_runs=50):
    """An evaluation definition and a rule that runs it on every completed response of the monitored agent."""
    from azure.ai.projects.models import (AzureAIDataSourceConfig, ContinuousEvaluationRuleAction, EvaluationRule,
                                          EvaluationRuleEventType, EvaluationRuleFilter)
    client = project.get_openai_client()
    evaluation = client.evals.create(name="Northstar continuous evaluation",
                                     data_source_config=AzureAIDataSourceConfig(type="azure_ai_source", scenario="responses"),
                                     testing_criteria=criteria(judge, None))
    agent = monitored_agent()
    rule = project.evaluation_rules.create_or_update(id=RULE_PREFIX + agent, evaluation_rule=EvaluationRule(
        display_name=f"Continuous evaluation: {agent}", description="Grades each completed response of this agent",
        action=ContinuousEvaluationRuleAction(eval_id=evaluation.id, max_hourly_runs=max_hourly_runs),
        event_type=EvaluationRuleEventType.RESPONSE_COMPLETED, filter=EvaluationRuleFilter(agent_name=agent), enabled=True))
    return evaluation.id, rule.id


def send_traffic(count, progress=print):
    """Ask the portal agent the sample questions, as a customer would."""
    from ..agent.cli import build_portal_agent
    portal = build_portal_agent()
    for number, question in enumerate(TRAFFIC[:count], 1):
        _, response_id = portal.ask(question)
        progress(f"  {number}/{count} response={response_id}")


def run_agent_evaluation(project, judge, questions, agent, poll_seconds=10, timeout_seconds=1500, progress=print):
    """Have Foundry call the agent on each question and grade the answers. Only works for an agent
    Foundry can run by itself, which is the portal agent."""
    from azure.ai.projects.models import AzureAIAgentTargetParam, TargetCompletionEvalRunDataSource
    client = project.get_openai_client()
    evaluation = client.evals.create(
        name=f"Northstar agent evaluation: {agent}",
        data_source_config={"type": "custom", "include_sample_schema": True, "item_schema": {
            "type": "object", "properties": {"query": {"type": "string"}, "ground_truth": {"type": "string"}}, "required": ["query"]}},
        testing_criteria=criteria(judge, "{{sample.output_text}}"))
    source = TargetCompletionEvalRunDataSource(
        type="azure_ai_target_completions",
        source={"type": "file_content", "content": [{"item": {"query": q["question"], "ground_truth": q["expected_answer"]}} for q in questions]},
        input_messages={"type": "template", "template": [
            {"type": "message", "role": "user", "content": {"type": "input_text", "text": "{{item.query}}"}}]},
        target=AzureAIAgentTargetParam(type="azure_ai_agent", name=agent))
    run = client.evals.runs.create(eval_id=evaluation.id, name=f"{agent} on policy questions ({len(questions)})", data_source=source)
    deadline = time.monotonic() + timeout_seconds
    while run.status not in ("completed", "failed", "canceled") and time.monotonic() < deadline:
        time.sleep(poll_seconds)
        run = client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        progress(f"  status: {run.status}")
    return evaluation.id, run


def run_dataset_evaluation(project, judge, rows, name, poll_seconds=10, timeout_seconds=1500, progress=print):
    """Have Foundry grade answers that were already collected. Only the judge model is called."""
    from azure.ai.projects.models import TestingCriterionAzureAIEvaluator
    client = project.get_openai_client()
    fields = ("query", "response", "context", "ground_truth")
    evaluation = client.evals.create(
        name=name,
        data_source_config={"type": "custom", "item_schema": {
            "type": "object", "properties": {field: {"type": "string"} for field in fields}, "required": list(fields)}},
        testing_criteria=[TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator", name=grader, evaluator_name=f"builtin.{grader}", initialization_parameters={"model": judge},
            data_mapping={field: "{{item." + field + "}}" for field in inputs}) for grader, inputs in DATASET_GRADERS.items()])
    run = client.evals.runs.create(eval_id=evaluation.id, name=f"{name} ({len(rows)} answers)", data_source={
        "type": "jsonl", "source": {"type": "file_content", "content": [{"item": {field: row[field] for field in fields}} for row in rows]}})
    deadline = time.monotonic() + timeout_seconds
    while run.status not in ("completed", "failed", "canceled") and time.monotonic() < deadline:
        time.sleep(poll_seconds)
        run = client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        progress(f"  status: {run.status}")
    return evaluation.id, run


def latest_answers(data_dir):
    """The most recent answers file written by evals/policy_agent.py."""
    files = sorted(data_dir.glob("eval/*/portal_dataset.jsonl"))
    if not files:
        raise ValueError("No saved answers found. Run python -m northstar.evals.policy_agent --confirm first, or pass --rows.")
    return files[-1]


def report(evaluation_id, result):
    print(f"Evaluation {evaluation_id}, run {result.id}: {result.status}")
    print(f"Result counts: {getattr(result, 'result_counts', None)}")
    for item in getattr(result, "per_testing_criteria_results", None) or []:
        print(f"  {item.testing_criteria}: passed {item.passed}, failed {item.failed}")
    print(f"Report: {getattr(result, 'report_url', None) or 'open Evaluations in the Foundry portal'}")
    return 0 if result.status == "completed" else 1


def status(project):
    return {"continuous_rules": [{"id": rule.id, "enabled": rule.enabled} for rule in project.evaluation_rules.list()
                                 if rule.id.startswith(RULE_PREFIX)],
            "agents": sorted(agent.name for agent in project.agents.list())}


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for name in ("continuous", "traffic", "agent-run", "dataset-run", "remove"):
        sub = commands.add_parser(name)
        sub.add_argument("--confirm", action="store_true", help="Required: this changes the project or makes billed calls")
        if name == "traffic":
            sub.add_argument("--count", type=int, default=len(TRAFFIC))
        if name == "dataset-run":
            sub.add_argument("--rows", help="Answers file (portal_dataset.jsonl). Default: the latest under data/eval")
            sub.add_argument("--limit", type=int)
        if name == "agent-run":
            sub.add_argument("--limit", type=int)
            sub.add_argument("--split", choices=("development", "test", "all"), default="development")
    args = parser.parse_args(argv)
    load_env_file()
    use_utf8_output()
    if args.command != "status" and not args.confirm:
        print(f"'{args.command}' changes the Foundry project or makes billed calls. Add --confirm.")
        return 2
    from azure.ai.projects import AIProjectClient
    settings, azure = Settings.from_env(), AzureSettings.from_env()
    judge = os.environ.get("EVALUATION_MODEL_DEPLOYMENT", azure.planning_deployment)
    project = AIProjectClient(endpoint=azure.project_endpoint, credential=azure_credential())
    if args.command == "status":
        print(json.dumps(status(project), indent=2))
    elif args.command == "continuous":
        evaluation_id, rule_id = setup_continuous(project, judge)
        print(f"Continuous evaluation {evaluation_id} (judge {judge}) is active for '{monitored_agent()}' (rule {rule_id}).")
        print("New responses are graded as they complete. See the agent's Monitor tab in the Foundry portal.")
    elif args.command == "traffic":
        print(f"Asking '{monitored_agent()}' {args.count} questions...")
        send_traffic(args.count)
    elif args.command == "agent-run":
        questions = [q for q in json.loads((settings.dataset_dir / "evals" / "policy_qa.json").read_text(encoding="utf-8"))
                     if args.split in ("all", q["split"])][:args.limit]
        agent = monitored_agent()
        print(f"Foundry is running '{agent}' on {len(questions)} questions and grading with {judge}...")
        evaluation_id, result = run_agent_evaluation(project, judge, questions, agent)
        return report(evaluation_id, result)
    elif args.command == "dataset-run":
        from pathlib import Path
        path = Path(args.rows) if args.rows else latest_answers(settings.dataset_dir.parent / "data")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][:args.limit]
        print(f"Foundry is grading {len(rows)} saved answers from {path} with {judge}...")
        return report(*run_dataset_evaluation(project, judge, rows, "Northstar policy agent: RAG metrics"))
    else:
        removed = []
        for rule in list(project.evaluation_rules.list()):
            if rule.id.startswith(RULE_PREFIX):
                project.evaluation_rules.delete(rule.id)
                removed.append(rule.id)
        print("Deleted: " + (", ".join(removed) or "nothing"))
    return 0


def main(argv=None):
    from .. import telemetry
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
