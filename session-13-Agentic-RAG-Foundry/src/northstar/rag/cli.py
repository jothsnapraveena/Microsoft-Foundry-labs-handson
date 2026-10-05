"""Retrieval commands. Anything that creates, changes or deletes Azure objects needs --confirm.

  python -m northstar.rag.cli plan                 What provisioning would do. Reads only.
  python -m northstar.rag.cli provision --confirm  Create or update the index, documents, knowledge source and base.
  python -m northstar.rag.cli status               What exists now.
  python -m northstar.rag.cli ask "question" [--order-date YYYY-MM-DD] [--event-date YYYY-MM-DD] [--effort low]
  python -m northstar.rag.cli ask "question" --local    Keyword fallback, no Azure.
  python -m northstar.rag.cli teardown --confirm   Delete the knowledge base, knowledge source and index.
"""
import argparse
from datetime import date
import json
import sys

from ..azure_login import SignInError, azure_credential, explain
from ..config import AzureSettings, Settings, load_env_file, use_utf8_output
from .catalog import load_chunks
from .retrieval import EFFORTS, LocalKeywordRetriever


def provisioner():
    from .azure import SearchProvisioner
    return SearchProvisioner(AzureSettings.from_env(), azure_credential(), Settings.from_env().dataset_dir)


def show(result, as_json):
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return
    print(f"Backend: {result.backend}")
    print(f"Order date {result.order_date}, event date {result.event_date}")
    print(f"Filter: {result.filter}")
    if result.sub_queries:
        print("Sub-queries:", "; ".join(result.sub_queries))
    print(f"Tokens in/out: {result.input_tokens}/{result.output_tokens}, service time {result.elapsed_ms} ms")
    for item in result.evidence:
        score = f"{item.reranker_score:.2f}" if item.reranker_score is not None else "n/a"
        print(f"\n[{item.chunk_id}] score {score} | {item.title} / {item.section} | effective {item.effective_from} to {item.effective_to or 'open'}")
        print(f"  {item.text}")
    if not result.evidence:
        print("\nNo evidence passed validation.")
    for item in result.rejected:
        print(f"\nREJECTED {item['chunk_id']}: {item['reason']}")


def main(argv=None):
    try:
        return run(argv)
    except SignInError as error:
        print(error, file=sys.stderr)
        return 1
    except ValueError as error:           
        print(error, file=sys.stderr)
        return 2
    except Exception as error:
        try:
            explain(error)
        except SignInError as sign_in:
            print(sign_in, file=sys.stderr)
            return 1


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    commands.add_parser("status")
    for name in ("provision", "teardown"):
        commands.add_parser(name).add_argument("--confirm", action="store_true", help="Required: this changes Azure resources")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--order-date", type=date.fromisoformat)
    ask.add_argument("--event-date", type=date.fromisoformat)
    ask.add_argument("--effort", choices=EFFORTS, default="low")
    ask.add_argument("--top", type=int, default=6, help="Maximum evidence chunks to keep")
    ask.add_argument("--local", action="store_true", help="Use the local keyword fallback instead of Azure AI Search")
    ask.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    load_env_file()
    use_utf8_output()
    settings = Settings.from_env()

    if args.command == "ask":
        event_date = args.event_date or settings.fixed_date or date.today()
        if args.local:
            chunks, problems = load_chunks(settings.dataset_dir)
            if problems:
                raise SystemExit("\n".join(problems))
            retriever = LocalKeywordRetriever(chunks, settings.region)
        else:
            retriever = provisioner().retriever(args.effort, settings.region)
        show(retriever.retrieve(args.question, args.order_date, event_date, args.effort, args.top), args.json)
        return 0

    work = provisioner()
    azure = work.settings
    if args.command == "status":
        print(json.dumps(work.status(), indent=2))
    elif args.command == "plan":
        plan = work.plan()
        print(f"Search service:   {azure.search_endpoint}")
        print(f"Index:            {azure.index_name} ({'exists' if work.index_dimensions() else 'will be created'})")
        print(f"Knowledge source: {azure.knowledge_source_name}")
        print(f"Knowledge base:   {azure.knowledge_base_name} (query planning model: {azure.planning_deployment})")
        print(f"Embedding model:  {azure.embedding_deployment}")
        print(f"Documents:        {plan.summary()}")
        print("\nNothing was changed. Run 'provision --confirm' to apply. Embedding, indexing and later queries are billed by use.")
    elif not args.confirm:
        print(f"'{args.command}' changes Azure resources. Review with 'plan' or 'status', then add --confirm.")
        return 2
    elif args.command == "provision":
        dimensions = work.ensure_index()
        print(f"Index ready: {azure.index_name} ({dimensions} dimensions)")
        print(f"Documents: {work.ingest(dimensions).summary()}")
        work.ensure_knowledge_source()
        print(f"Knowledge source ready: {azure.knowledge_source_name}")
        work.ensure_knowledge_base()
        print(f"Knowledge base ready: {azure.knowledge_base_name}")
    elif args.command == "teardown":
        removed = work.teardown()
        print("Deleted: " + ", ".join(removed) if removed else "Nothing to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
