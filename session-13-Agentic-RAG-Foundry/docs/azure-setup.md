# Azure setup and permissions

Everything to configure in Azure before stage 3 (indexing, the knowledge base and the agent) can run. Stages 1 and 2 need none of it.

Replace the placeholders with your own names:

| Placeholder | Meaning |
|---|---|
| `<subscription>` | Your Azure subscription |
| `<resource-group>` | The resource group holding the resources below |
| `<foundry-resource>` | The Microsoft Foundry resource (the project's parent) |
| `<project>` | The Foundry project |
| `<search-service>` | The Azure AI Search service |
| `<app-insights>` | The Application Insights resource |

You need **Owner** or **User Access Administrator** on the subscription or resource group to assign roles, and **Contributor** or **Owner** on the subscription to register resource providers.

## What you will have at the end

| Resource | Purpose |
|---|---|
| Foundry resource and project | Hosts the model deployments and the agent |
| Chat model deployment | The agent's model |
| Embedding model deployment | Vectors for the policy index (`text-embedding-3-large`) |
| Azure AI Search service | Index, knowledge source and knowledge base |
| Application Insights (with a Log Analytics workspace) | Traces and monitoring |

Search, model calls, evaluations and Application Insights are billed by use. Delete what you no longer need.

## 1. Install the Azure CLI and sign in

The code authenticates with your Azure sign-in instead of API keys.

```powershell
winget install -e --id Microsoft.AzureCLI
```

Reopen the terminal, then:

```powershell
az login
az account set --subscription "<subscription>"
```

## 2. Register resource providers

A subscription that has never used Log Analytics or Application Insights cannot create them until their providers are registered. Without this, connecting Application Insights fails with:

> MissingSubscriptionRegistration: The subscription is not registered to use namespace 'Microsoft.OperationalInsights'.

Register both. Registration is free and happens once per subscription.

**Azure portal:** Subscriptions → `<subscription>` → Settings → Resource providers. Search for each provider, select its row, then **Register**. Refresh until the status is **Registered**.

- `Microsoft.OperationalInsights`
- `Microsoft.Insights`

**Or with the CLI:**

```powershell
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights
az provider show --namespace Microsoft.OperationalInsights --query registrationState -o tsv
```

## 3. Deploy the models

In the Foundry portal, open `<project>` → **Models** → **Deploy model**, and deploy:

- A chat model for the agent. Microsoft's tutorial uses `gpt-5-mini`; a larger model works but costs more.
- `text-embedding-3-large` for embeddings.

Note the deployment names; they go in `.env`.

## 4. Connect Application Insights to the project

In the Foundry portal, open an agent in `<project>` → **Monitor** → settings (or **Traces** → **Connect**):

1. Choose **Create new resource**, or select an existing Application Insights resource.
2. Leave **Auth Type** as **API Key**. The key is stored in the project connection; you never handle it.
3. Select **Create** (or **Connect**).

If creation fails with the registration error above, complete step 2 and retry.

Traces can contain prompts, tool arguments and customer content. Anyone with read access to the Application Insights resource can see them.

## 5. Configure the search service

Open `<search-service>` in the Azure portal.

- **Settings → Keys:** set API access control to **Role-based access control** or **Both**. With "API keys" only, the role assignments below have no effect.
- **Settings → Identity:** set **System assigned** to **On** and save. This gives the search service an identity that can call the models.

The service must be in a [region that supports agentic retrieval](https://learn.microsoft.com/azure/search/search-region-support).

## 6. Assign roles

Add each assignment from the resource's **Access control (IAM)** → **Add** → **Add role assignment**.

On the **Members** tab, the **Assign access to** choice decides which kind of identity you can pick:

- **User, group, or service principal** for your own account.
- **Managed identity** for a resource's identity, such as the Foundry project or the search service.

One assignment can hold only one kind, so a role that goes to both you and a managed identity takes two passes. Giving a role to your own account does not give it to the project; they are separate identities.

### On the Application Insights resource

| Role | Assign to | Why |
|---|---|---|
| Log Analytics Reader | Your user account | View traces in the portal |
| Log Analytics Reader | Foundry project managed identity (`<foundry-resource>/<project>`) | Lets Foundry read traces for Insights and monitoring |

Without the second row, the agent's Insights page shows "Setup incomplete: The project managed identity needs access to the Application Insights resource". The **Resolve** button on that banner attempts the same assignment.

### On the search service

| Role | Assign to | Why |
|---|---|---|
| Search Service Contributor | Your user account | Create indexes, knowledge sources and knowledge bases |
| Search Index Data Contributor | Your user account | Upload documents |
| Search Index Data Reader | Your user account | Query the index |
| Search Index Data Reader | Foundry project managed identity | Lets the agent read indexed content |

### On the Foundry resource

| Role | Assign to | Why |
|---|---|---|
| Foundry User | Your user account | Use model deployments and create agents |
| Foundry Project Manager | Your user account | Create the project connection and use the MCP tool in agents |
| Cognitive Services User | Search service managed identity | Lets the knowledge base call the models |

The Foundry roles were recently renamed. You may still see **Azure AI User** and **Azure AI Project Manager**; they are the same roles.

The search service's identity only appears in the member picker after step 5 has switched it on.

Being **Owner** of the subscription lets you create these assignments, but does not by itself grant data access to the search index, so the search data roles still have to be assigned.

Role assignments can take several minutes to take effect.

## 7. Check the result

- **Application Insights IAM → Role assignments:** Log Analytics Reader appears twice, once with type User and once with type Foundry project.
- **Search service IAM → Role assignments:** three roles for your user, and Search Index Data Reader for the project identity.
- **Foundry resource IAM → Role assignments:** two roles for your user, and Cognitive Services User for the search service.
- **Foundry portal → agent → Traces:** opens without a prompt to connect a resource.
- **Foundry portal → agent → Insights:** no "Setup incomplete" banner.

## 8. Fill in `.env`

Copy `.env.example` to `.env` and set the endpoints and deployment names. `.env` is git-ignored; do not commit it or share its contents.

| Variable | Where to find it |
|---|---|
| `AZURE_SEARCH_ENDPOINT` | Search service → Overview → Url |
| `PROJECT_ENDPOINT` | Foundry project → Endpoints |
| `AZURE_OPENAI_ENDPOINT` | Foundry resource → Endpoints |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | The embedding deployment name from step 3 |
| `AGENT_MODEL` | The chat deployment name from step 3 |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `az` is not recognized | The Azure CLI is not installed, or the terminal was not reopened after installing. |
| MissingSubscriptionRegistration when creating Application Insights | Register the providers in step 2, wait for **Registered**, retry. |
| Insights still says the project identity needs access | The role went to your user, not the managed identity. Repeat with **Assign access to: Managed identity**. Allow a few minutes. |
| The project or search service is missing from the managed identity picker | Its system-assigned identity is off. Turn it on under the resource's **Identity** page. |
| Search calls return 403 despite the roles | API access control is still "API keys" only (step 5), or the assignment has not propagated yet. |
| A Foundry role was assigned on the search service by mistake | It has no effect there. Delete it and assign it on the Foundry resource. |

## Sources and limits

The search and Foundry role tables follow Microsoft's tutorial, [Build an agentic retrieval solution](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-pipeline). The Application Insights steps follow [Set up tracing for AI agents](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup).

This project's own setup has confirmed steps 2 and 4 and the Application Insights and search service assignments. Stage 3 has not been run yet, so the full set has not been exercised end to end; if a later stage needs another permission, it will be added here.

Several features used later are in preview, including the knowledge base's MCP endpoint and the project connection type that reaches it. Preview features have no service-level agreement and can change.
