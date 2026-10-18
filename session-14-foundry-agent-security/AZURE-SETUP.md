# Session 14 Azure setup

Use this guide to configure your own Foundry resource and project. Keep subscription IDs, resource names and project endpoints in your local configuration.

This session runs independently of Northstar. Use a new Microsoft Foundry resource and project, rather than a hub-based project.

## Example target

| Setting | Value |
| --- | --- |
| Subscription | `<subscription-id>`; verify your selection before provisioning |
| Resource group | `<resource-group-name>` |
| Resource and project region | `eastus2` |
| Foundry resource | `<foundry-account-name>` |
| Project | `<project-name>` |
| Deployment name | `s14-gpt41-mini` |
| Model and version | `gpt-4.1-mini`, `2025-04-14` |
| Deployment type | `GlobalStandard` |
| Initial deployment capacity | 10 capacity units; service reported 10 requests/minute and 10,000 tokens/minute |

Use `Microsoft.DefaultV2` filtering and verify your model upgrade policy. Grant the signed-in identity the required project-scoped access, then configure this session's ignored `.env` with your own endpoint.

Check model availability, subscription quota and platform capacity in your selected region before provisioning. The quota catalog may name GPT-4.1 mini `gpt4.1-mini` even though deployment uses `gpt-4.1-mini`.

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
