# Hands-on lab: long-term memory in Microsoft Foundry Agent Service

Give a Foundry prompt agent a real long-term memory — no vector DB to provision,
no extraction pipeline to maintain. This lab creates a managed memory store,
attaches it to an agent, and runs the two-conversation "amnesia test" that proves
memory works across sessions.

Part of the [AgenticAI-on-Azure](https://github.com/jothsnapraveena/AgenticAI-on-Azure)
hands-on series. The visual explainer lives on LinkedIn; this repo holds the lab.

> **Preview note:** Memory in Foundry Agent Service is in public preview. Pin your
> SDK version (`azure-ai-projects>=2.3.0`) and check the
> [Learn doc](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage)
> before upgrading — consolidation behavior and schemas can change.

## What you'll build

```
Conversation 1 (fresh thread)          Conversation 2 (fresh thread, no shared history)
┌─────────────────────────┐           ┌──────────────────────────────────┐
│ you: I prefer dark      │  extract  │ you: Please order my usual       │
│ roast coffee.           │ ────────▶ │ coffee.                          │
│                         │ consolidate│                                  │
│                         │  memory   │ agent: On it — dark roast,       │
│                         │   store   │ like you prefer.                 │
└─────────────────────────┘           └──────────────────────────────────┘
```

## Prerequisites

- A Microsoft Foundry project
- A chat model deployment (e.g. `gpt-5.2`)
- An embedding model deployment (e.g. `text-embedding-3-small`)
- The **Foundry User** role on your project (or key-based auth)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your endpoint + deployment names
az login
```

## Run the lab

```bash
python memory_lab.py
```

The script walks through five steps:

| Step | What happens | Key API |
|------|--------------|---------|
| 1. Create store | Managed memory store with user profile, chat summaries, and procedural memory; 30-day TTL; privacy-safe extraction instructions | `project_client.beta.memory_stores.create(...)` with `MemoryStoreDefaultOptions` |
| 2. Attach tool | Memory search tool on a prompt agent; static lab scope; `update_delay=1` so writes land fast | `MemorySearchPreviewTool(memory_store_name, scope, update_delay)` |
| 3. Amnesia test | Teach "dark roast" in conversation 1, wait out the debounce, recall it in a fresh conversation 2 | `openai_client.responses.create(...)` with `agent_reference` |
| 4. Inspect | List raw memory items — compare what you *thought* would be remembered vs what *was* | `beta.memory_stores.list_memories(name, scope)` |
| 5. Cleanup | Delete the lab scope (uncomment to also delete the store) | `delete_scope(...)` / `delete(...)` |

## The three decisions that matter

1. **`user_profile_details`** — the Customize phase made concrete. Write it as an
   exclusion list first ("avoid age, financials, precise location, credentials"),
   then add inclusions for your domain. Cheapest privacy control you have.
2. **`scope`** — your isolation boundary. Per-user: `scope="{{$userId}}"` plus the
   `x-memory-user-id` header on each response call (falls back to Entra TID+OID
   without it). Static scope only if you truly don't need isolation.
3. **`update_delay`** — the write debounce. Low = pay for extraction on every
   pause; high (default 300s) = a user who closes the tab fast loses the last
   turn's memories.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Auth errors | Missing role | Assign **Foundry User** to your identity on the project |
| No memories after conversation 1 | Debounce still processing | Wait longer; the lab already waits ~65s |
| Memory search returns nothing | Scope mismatch | Use the same scope for write and read |
| Agent ignores stored memory | Tool not attached / wrong store name | Check the agent definition includes `memory_search_preview` |

## Going further

- Flip `scope` to `"{{$userId}}"` and pass `x-memory-user-id` per request for real multi-user isolation.
- Coach the agent once on a repeated workflow (e.g. PR review order) and watch **procedural memory** replay it weeks later.
- Add item-level CRUD (`get_memory` / `update_memory` / `delete_memory`) behind a user-facing "forget me" flow.
