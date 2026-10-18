# Session 14 Azure setup

Status: provisioned after subscription reactivation on 2026-10-18 UTC (2026-10-17 Chicago time). The two-call live smoke test completed successfully. Earlier `ReadOnlyDisabledSubscription` failures cleared after short propagation waits. Local resource details are retained in ignored `artifacts/provisioning.json`; paired-test responses are in [the execution evidence](evidence/fixed-2026-10-18.json).

This session runs independently of Northstar. Use a new Microsoft Foundry resource and project, rather than a hub-based project.

## Provisioned target

| Setting | Value |
| --- | --- |
| Subscription | The currently selected Azure CLI subscription; verify before provisioning |
| Resource group | `rg-foundry-session14` |
| Resource and project region | `eastus2` |
| Foundry resource | `foundry-s14-f15256c9` |
| Project | `session14-security` |
| Deployment name | `s14-gpt41-mini` |
| Model and version | `gpt-4.1-mini`, `2025-04-14` |
| Deployment type | `GlobalStandard` |
| Initial deployment capacity | 10 capacity units; service reported 10 requests/minute and 10,000 tokens/minute |

The deployment uses `Microsoft.DefaultV2` filtering and `OnceNewDefaultVersionAvailable` upgrades. The signed-in user has Foundry User access scoped to the project. The session's ignored `.env` is configured, and both prompt agents exist as version `1`. The resources remain deployed for subsequent validation.

Read-only discovery on 2026-10-17 confirmed that the active subscription had no visible Cognitive Services accounts, and had both available quota and service capacity for this model/type in East US 2. Capacity can change before provisioning. The quota catalog names this model `gpt4.1-mini` even though deployment uses `gpt-4.1-mini`.

Global Standard inference can be processed outside the resource's region. Select a suitable regional deployment instead if the demonstration requires regional processing.

## Provision and configure

1. Verify the selected subscription with `az account show`. Create the resource group, Foundry resource, and project using the proposed names. Keep hosted-agent infrastructure disabled for this prompt-agent lab.
2. Deploy the model with the name, version, type, and capacity above. Confirm that the signed-in identity has the required project data-plane permissions; subscription ownership alone does not prove agent invocation access.
3. Copy the project's actual endpoint from Foundry. Copy `.env.example` to `.env` in this session directory and fill in:

   ```dotenv
   AZURE_AI_PROJECT_ENDPOINT=<actual-project-endpoint>
   MODEL_DEPLOYMENT=s14-gpt41-mini
   ```

   The fixed-test comparison uses this one deployment for both instruction variants.
4. From this session directory, use the isolated environment:

   ```powershell
   .venv/Scripts/python.exe lab.py create --confirm
   .venv/Scripts/python.exe lab.py fixed --limit 1 --report artifacts/smoke.json --confirm
   ```

5. Inspect both saved responses and execution status before running the full corpus. Record the actual resource region, deployed model/version, run identifiers, and outcomes with the saved test report.

The initial live validation consists of creating two prompt-agent versions and making two target inference calls. A successful smoke test establishes connectivity and execution only.

## Cost and cleanup

Global Standard inference is metered. Deployment capacity is a throughput allocation, not a spending cap. Check current pricing and usage; this plan does not promise a fixed dollar cost.

`lab.py cleanup --confirm` removes the recorded agents and evaluations. It does not delete the model deployment, project, or resource group. After preserving sanitized evidence, explicitly remove the dedicated resource group when it is no longer needed, after checking that it contains no shared resources.

References: [create a Foundry project](https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects), [deployment types](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/deployment-types), [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/).
