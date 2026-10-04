# Implementation

1. Read `src/api/foundry_config.py`. Identify the four steps: initialize the runtime, check the cache, load the model, share one chat client.
2. Open each module in `src/api/agents`. Explain every agent's `PROMPT`, its `valid` contract and its entry point. In `product.py`, follow `find_products` and `keyword_search` against `catalog/products.json`.
3. Follow `Pipeline.stages` in `src/api/orchestrator.py`: triage, product search, draft, deterministic checks, model review and up to two revisions. Locate the global call budget in `invoke` and the escalation paths in `create`.
4. Run orchestration tests before loading a model:

```powershell
python -m unittest discover -s tests -v
```

5. Run the first fixture, watching each agent's progress and the streamed draft, then the complete dataset. The first command downloads the model if it is not cached yet:

```powershell
python scripts/multi_agent_lab.py run --alias phi-3.5-mini
python scripts/multi_agent_lab.py evaluate --offline --alias phi-3.5-mini --output artifacts/evaluation.json
```

6. Start the web service, open <http://127.0.0.1:8000> and submit each sample case. Watch the four agents advance, the draft stream in, and the reviewer approve it or send it back. Then send a case from a second terminal to see the raw messages the page consumes; each line of the response is one progress message:

```powershell
python -m uvicorn main:app --app-dir src/api --host 127.0.0.1 --port 8000
```

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/api/reply -H "Content-Type: application/json" -d '{\"id\":\"demo\",\"customer\":\"I ordered a blue backpack but received a green one.\",\"facts\":{\"order_id\":\"DEMO-1042\",\"ordered\":\"blue backpack\",\"received\":\"green backpack\"}}'
```

   The service reads `FOUNDRY_MODEL_ALIAS` and `FOUNDRY_RUNTIME_DIR`. It downloads the model on first start unless `FOUNDRY_OFFLINE=1`. Stop it with Ctrl+C before running the CLI again, because the CLI rejects an already-loaded model.

7. Inspect the report and manually compare accepted drafts against each fixture's trusted facts and catalog matches. Record hallucinations, omissions, appropriate refusals and reviewer mistakes.
8. Repeat with another prepared model and compare actual quality and latency. Use different output filenames to retain evidence.

The native SDK initializes in-process. The backend rejects an already-loaded model, loads its selected model and unloads it on exit. SDK logs go to `artifacts/runtime/logs`, configurable with `--runtime-dir`; the SDK's default data directory is used unchanged. The SDK keeps a separate model cache per application name, so this application downloads its own copy of the model to `~/.retail_support_agents/cache/models` the first time it runs without `--offline`. The latency gate measures completed calls and is not a hard inference deadline.

The web service loads the model once and handles one run at a time. A deployed service still needs supervised inference workers with hard deadlines, bounded queues, authentication, health-based restarts and shutdown recovery.
