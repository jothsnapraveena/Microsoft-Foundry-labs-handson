"""Policy agent commands.

  python -m northstar.agent.cli create --confirm     Publish the agent definition to the Foundry project.
  python -m northstar.agent.cli ask "question"       One question; prints the answer, citations and evidence.
  python -m northstar.agent.cli chat                 Ask several questions in a row (each is independent).
  python -m northstar.agent.cli delete --confirm     Remove the agent from the project.

Portal agent: runs wholly inside Foundry, so it works in the playground. Current policies only.
  python -m northstar.agent.cli portal-create --confirm   Knowledge base, project connection and agent.
  python -m northstar.agent.cli portal-ask "question"
  python -m northstar.agent.cli portal-delete --confirm

Each question makes billed model and retrieval calls.
"""
import argparse
import json
import os
import sys

from .. import telemetry
from ..azure_login import SignInError, azure_credential, explain
from ..config import AzureSettings, Clock, Settings, load_env_file, use_utf8_output
from .policy_agent import PolicyAgent


def build_agent():
    from azure.ai.projects import AIProjectClient
    from ..rag.azure import SearchProvisioner
    settings, azure = Settings.from_env(), AzureSettings.from_env()
    credential = azure_credential()
    retriever = SearchProvisioner(azure, credential, settings.dataset_dir).retriever(region=settings.region)
    project = AIProjectClient(endpoint=azure.project_endpoint, credential=credential)
    destination = telemetry.configure(project)
    if destination:
        print(f"Tracing to {destination}.", file=sys.stderr)
    return PolicyAgent(project, retriever, os.environ.get("NORTHSTAR_POLICY_AGENT", "northstar-policy-agent"),
                       azure.agent_model, Clock(settings.fixed_date))


def build_portal_agent():
    from azure.ai.projects import AIProjectClient
    from ..rag.azure import SearchProvisioner
    from .portal_agent import PortalAgent
    settings, azure = Settings.from_env(), AzureSettings.from_env()
    resource_id = os.environ.get("PROJECT_RESOURCE_ID", "")
    if not resource_id.startswith("/subscriptions/"):
        raise ValueError("PROJECT_RESOURCE_ID is not set. Find it on the Foundry project's Properties page (docs/azure-setup.md).")
    credential = azure_credential()
    project = AIProjectClient(endpoint=azure.project_endpoint, credential=credential)
    return PortalAgent(project, SearchProvisioner(azure, credential, settings.dataset_dir), credential, resource_id,
                       os.environ.get("NORTHSTAR_PORTAL_AGENT", "northstar-portal-agent"), azure.agent_model, settings.region)


def show(result, as_json=False):
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return
    print(f"\n{result.answer}\n")
    print(f"Verified: {'yes' if result.verified else 'NO'} | citations: {', '.join(result.citations) or 'none'}"
          + (" | policies do not cover this" if result.not_covered else "")
          + (" | BLOCKED by the content filter" if result.blocked else ""))
    if result.invalid_citations:
        print(f"NOT RETRIEVED (invalid citations): {', '.join(result.invalid_citations)}")
    for call in result.retrievals:
        print(f"Search: \"{call['question']}\" | order date {call['order_date']}, event date {call['event_date']} | "
              f"{len(call['evidence_ids'])} passages, {call['service_ms']} ms")
    print(f"Agent tokens in/out: {result.input_tokens}/{result.output_tokens} | response {result.response_id}"
          + (f" | trace {result.trace_id}" if result.trace_id else ""))


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "delete", "portal-create", "portal-delete"):
        commands.add_parser(name).add_argument("--confirm", action="store_true", help="Required: this changes the Foundry project")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--json", action="store_true")
    commands.add_parser("chat")
    commands.add_parser("portal-ask").add_argument("question")
    args = parser.parse_args(argv)
    load_env_file()
    use_utf8_output()
    if args.command in ("create", "delete", "portal-create", "portal-delete") and not args.confirm:
        print(f"'{args.command}' changes the Foundry project. Add --confirm.")
        return 2
    if args.command.startswith("portal-"):
        portal = build_portal_agent()
        if args.command == "portal-create":
            version = portal.create()
            print(f"Knowledge base '{portal.knowledge_base_name}' (current policies only) and connection ready.")
            print(f"Agent '{portal.agent_name}' version {version} published (model {portal.model}). Try it in the Foundry playground.")
        elif args.command == "portal-delete":
            print("Deleted: " + (", ".join(portal.delete()) or "nothing"))
        else:
            answer, response_id = portal.ask(args.question)
            print(f"\n{answer}\n\nResponse {response_id}")
        return 0
    agent = build_agent()
    if args.command == "create":
        print(f"Agent '{agent.agent_name}' version {agent.create()} published (model {agent.model}).")
    elif args.command == "delete":
        agent.delete()
        print(f"Agent '{agent.agent_name}' deleted.")
    elif args.command == "ask":
        show(agent.ask(args.question), args.json)
    else:
        print("Ask a policy question. Empty line to quit.")
        while (question := input("\n> ").strip()):
            show(agent.ask(question))
    return 0


def main(argv=None):
    try:
        return run(argv)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        return 0
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
