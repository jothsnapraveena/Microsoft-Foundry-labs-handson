# Session 15 Azure setup

This guide defines the Session 15 deployment configuration and benchmark sequence.

## Proposed target

Use your subscription `<subscription-id>`, region `<azure-region>`, Foundry account `<foundry-account-name>` and resource group `<resource-group-name>`. Create a separate project such as `session15-router` and grant the signed-in user Foundry User access scoped to that project. Session 15 requires no earlier application's agents or data. Keep actual identifiers and endpoints in the session's ignored `.env`.

| Deployment | Model | Version | Type | Initial capacity |
| --- | --- | --- | --- | --- |
| `s15-router` | `model-router` | `2025-11-18` | GlobalStandard | 10 |
| `s15-small` | `gpt-4.1-mini` | `2025-04-14` | GlobalStandard | 10 |
| `s15-large` | `gpt-4.1` | `2025-04-14` | GlobalStandard | 10 |

Model Router uses its default Balanced routing mode. The two fixed-model deployments are benchmark baselines; they are not prerequisites for Model Router's internal routing.

East US 2 is an example region. Check the listed model versions, deployment types, subscription quota and platform capacity for your own region before provisioning. Capacity controls throughput, not total spending. Global Standard processing is not restricted to the project's region.

## Validation sequence

1. Create the project and its scoped access, then create only the three deployments above. Record their exact versions, provisioning states, and rate limits.
2. Populate this session's ignored `.env` with the actual project endpoint, three deployment names, and account ARM ID. Use `.env.example` as the template.
3. Run a three-call smoke test from the session directory:

   ```powershell
   .venv/Scripts/python.exe lab.py run --limit 1 --report artifacts/smoke.json --confirm
   ```

4. Inspect the three outputs before running the full benchmark:

   ```powershell
   .venv/Scripts/python.exe lab.py run --repeats 1 --report artifacts/benchmark.json --confirm
   .venv/Scripts/python.exe lab.py summarize --report artifacts/benchmark.json
   ```

This sequence attempts 27 inference requests: three smoke requests followed by 24 benchmark requests. It captures response-model metadata, latency and token usage. It does not infer routing decisions from answer style. Structured cases have exact JSON grading; policy explanations need separate review. One repetition is a teaching demonstration and cannot establish a reliable latency ranking.

Leave cost estimates unknown until dated official rates and their billing mapping are verified. Metered inference is chargeable; neither this plan nor a throughput allocation promises a dollar cap.

## Cleanup boundary

Delete only the session-owned deployments recorded by `deployments.py`, verify their absence, and remove the Session 15 project when it is no longer needed. If the account or resource group is shared with another session, retain those shared resources during Session 15 cleanup.

References: [Model Router](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router), [create a Foundry project](https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects).
