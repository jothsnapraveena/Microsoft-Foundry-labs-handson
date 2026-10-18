# Running Session 15

Create an environment, install requirements.txt and run:

~~~powershell
python -m unittest discover -s tests -v
python lab.py plan
~~~

Copy .env.example to .env and set this session's project endpoint and three distinct deployment names. Use real Model Router for ROUTER_DEPLOYMENT; this implementation does not emulate routing.

See [the Azure setup plan](AZURE-SETUP.md) for the proposed project, verified deployment choices and shared-resource cleanup boundary.

## Deployment support

deployments.py can create a model deployment in an existing Foundry account. Set FOUNDRY_ACCOUNT_RESOURCE_ID to the account ARM ID. Discover currently supported model/router versions, SKU, capacity and region before using it; the lab does not invent these values.

~~~powershell
python deployments.py plan --name s15-router
python deployments.py create --name s15-router --model VERIFIED_MODEL_NAME --model-version VERIFIED_VERSION --sku VERIFIED_SKU --capacity VERIFIED_CAPACITY --confirm
python deployments.py status --name s15-router --confirm
~~~

Repeat with session-owned fixed-model deployments, or select existing ones. The helper refuses to overwrite an existing deployment. Successful submission is not readiness: check provisioning state and perform an inference smoke test.

## Benchmark

~~~powershell
python lab.py run --limit 1 --report artifacts/smoke.json --confirm
python lab.py run --repeats 1 --report artifacts/benchmark.json --confirm
python lab.py summarize --report artifacts/benchmark.json
~~~

One repetition attempts 24 requests: eight cases against three deployments, alternating target order by case. The SDK transport does not retry silently. Reports are checkpointed after every observation and preserve errors. Structured outputs are graded with exact keys, values and types; explanation cases remain ungraded for manual review. Grade counts are explicit.

The runner uses the Foundry project's Responses API and normalizes input/output token usage for the price calculator while preserving raw usage. Inspect the three-call smoke test before the full run. Calls are paced seven seconds apart by default; adjust `--request-interval` to the deployed rate limits. Each report preserves one run ID across checkpoints, records execution status, and retains HTTP status/error codes when available. A run with execution errors exits with code 1. Failed structured requests count as failures in the end-to-end grading metric; completed counts and errors remain visible separately.

The scorecard reports successful-response latency separately from errors. Repeat enough times for useful p95 estimates. No warm-up requests are hidden: if you want a warm-up, run a separate unreported trial and document it.

## Pricing

Copy data/prices.example.json to a private artifact file and enter dated official prices. Match response-model keys only when you have independently verified they identify the applicable Azure billing. Set verified_billing_match only after that check.

~~~powershell
python lab.py run --prices artifacts/prices.json --confirm
~~~

Cached input tokens use their own configured rate. Missing rates/billing matches produce null cost, not free inference. These are token-price estimates, not a bill or complete infrastructure cost.

## Cleanup

~~~powershell
python deployments.py delete --name s15-router --confirm
~~~

Repeat only for deployment IDs created by this session. The ledger protects unrecorded resources. Verify deletion in Azure; delete_requested is not a final absence check.
