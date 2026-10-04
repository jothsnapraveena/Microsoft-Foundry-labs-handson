# Session 12: Foundry Local Multi-Agent Construction and Evaluation

Build a fictional retail support application from agent definitions to repeatable evaluation using only the native Foundry Local Python SDK for inference. [Session 10](../session-10-foundry-local/README.md) introduces the Foundry Local CLI and SDK; this session is self-contained and downloads its own model on first run.

You will build triage, product, writer and reviewer agents; validate JSON handoffs; retrieve products from a local catalog; bound revisions and model calls; stream agent progress from a web service; evaluate pressure and injection scenarios; and decide what evidence is still needed before production deployment.

The agents share one loaded model, while each call gets fresh instructions and messages. Successful outputs are drafts requiring human review. The application does not send replies or approve refunds.

This is a production foundation, not a production certification. The lab distinguishes orchestration correctness from model quality and identifies deployment controls still required.

## Start here

Read [the lab overview](lab/README.md), complete the three guides in order, and answer [the knowledge check](knowledge-check.md). Allow 90–120 minutes after model preparation.

```text
src/api/foundry_config.py    Shared model lifecycle and chat client for all agents
src/api/agents/              One module per agent: triage, product, writer, reviewer
src/api/orchestrator.py      Pipeline, feedback loop, call budget and progress messages
src/api/contracts.py         Shared instructions, case validation and rule checks
src/api/main.py              FastAPI service streaming newline-delimited JSON
ui/                          Browser page showing agent progress and the streamed draft
catalog/products.json        Local product catalog searched by the product agent
scripts/multi_agent_lab.py   Run and evaluation CLI
eval/cases.jsonl             Fictional adversarial evaluation cases
tests/test_multi_agent.py    Model-independent orchestration checks
requirements.txt             Native Foundry Local SDK and web service dependencies
lab/                         Implementation, validation and execution evidence
```

From this directory:

```powershell
python -m unittest discover -s tests -v
python scripts/multi_agent_lab.py run
python scripts/multi_agent_lab.py evaluate --offline --output artifacts/evaluation.json
python -m uvicorn main:app --app-dir src/api --host 127.0.0.1 --port 8000
```

With the service running, open <http://127.0.0.1:8000> for the browser UI.

This session uses `from foundry_local_sdk import Configuration, FoundryLocalManager` with native `model.get_chat_client()` inference: `complete_chat()` for most agents and `complete_streaming_chat()` for the writer. Agent roles, validated handoffs, catalog search, revision limits and evaluation gates are Python application code built on that SDK.

## Relationship to the Zava Creative Writer

The layout follows the [Zava Creative Writer](https://github.com/microsoft-foundry/Foundry-Local-Lab/tree/main/zava-creative-writer-local) capstone: a shared Foundry configuration, one module per agent, a product agent combining model-generated queries with keyword search over a local catalog, a streaming writer, a reviewer that can send work back at most twice, a FastAPI endpoint reporting each agent's progress, and a browser UI.

It differs deliberately. The domain is retail support, inference uses the native SDK instead of the OpenAI client, every handoff has a strict JSON contract, a call budget bounds each run, and rule checks can override the reviewer.

The existing [Foundry memory lab](../session-11-foundry-memory-lab/README.md) is a separate module and retains its current directory name.
