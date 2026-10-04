#!/usr/bin/env python3
"""
Hands-on lab: long-term memory in Microsoft Foundry Agent Service.

What this lab does
------------------
1. Creates a managed memory store (user profile + chat summaries + procedural memory,
   30-day TTL, privacy-safe extraction instructions).
2. Attaches the memory search tool to a prompt agent with per-user scope isolation.
3. Runs the two-conversation "amnesia test": teach a preference in conversation 1,
   recall it in a brand-new conversation 2 with no shared thread.
4. Inspects the raw memory items so you can see what the extractor actually captured.
5. Cleans up (delete scope / store).

Prerequisites
-------------
- A Microsoft Foundry project with a chat model deployment (e.g. gpt-5.2)
  and an embedding model deployment (e.g. text-embedding-3-small).
- ``pip install -r requirements.txt``
- Copy ``.env.example`` to ``.env`` and fill in your values.
- ``az login`` (DefaultAzureCredential), with the Foundry User role on the project.

Memory is in public preview: pin your SDK version and expect API/schema changes.
Reference: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage
"""

import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    MemorySearchPreviewTool,
    MemoryStoreDefaultDefinition,
    MemoryStoreDefaultOptions,
    PromptAgentDefinition,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
CHAT_MODEL = os.environ["MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME"]
EMBEDDING_MODEL = os.environ["MEMORY_STORE_EMBEDDING_MODEL_DEPLOYMENT_NAME"]

STORE_NAME = "lab_memory_store"
AGENT_NAME = "MemoryLabAgent"
SCOPE = "lab_user_001"  # one stable scope per end user

project_client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential(),
)
openai_client = project_client.get_openai_client()


def step1_create_store():
    """Create the memory store: the interesting decisions live in `options`."""
    options = MemoryStoreDefaultOptions(
        chat_summary_enabled=True,
        user_profile_enabled=True,
        procedural_memory_enabled=True,  # agent learns *how* to do the work
        default_ttl_seconds=30 * 24 * 60 * 60,  # 30 days; 0 = no expiration
        # Customize phase: tell the extractor what to care about / avoid.
        user_profile_details=(
            "Avoid irrelevant or sensitive data, such as age, financials, "
            "precise location, and credentials. "
            "Do capture: coffee preferences, food preferences, communication style."
        ),
    )
    definition = MemoryStoreDefaultDefinition(
        chat_model=CHAT_MODEL,
        embedding_model=EMBEDDING_MODEL,
        options=options,
    )
    store = project_client.beta.memory_stores.create(
        name=STORE_NAME,
        definition=definition,
        description="Lab memory store: user profile + summaries + procedural memory",
    )
    print(f"[1] Created memory store: {store.name}")
    return store


def step2_create_agent():
    """Attach the memory search tool to a prompt agent.

    scope: isolation boundary. Each scope holds an isolated collection of
    memory items. Use "{{$userId}}" + the x-memory-user-id header for real
    per-user isolation; a static scope is fine for the lab.

    update_delay: write debounce. After each agent response the service calls
    update_memories internally, but the write only completes after this many
    seconds of conversation inactivity. 1s for the lab; default is 300s.
    """
    tool = MemorySearchPreviewTool(
        memory_store_name=STORE_NAME,
        scope=SCOPE,
        update_delay=1,  # demo value; use ~300 in production
    )
    agent = project_client.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=CHAT_MODEL,
            instructions=(
                "You are a helpful assistant. Use the user's stored memories "
                "to personalize your answers."
            ),
            tools=[tool],
        ),
    )
    print(f"[2] Created agent: {agent.name} (version {agent.version})")
    return agent


def _respond(agent, conversation_id, user_message):
    response = openai_client.responses.create(
        input=user_message,
        conversation=conversation_id,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        # For real per-user isolation with scope="{{$userId}}", pass:
        # extra_headers={"x-memory-user-id": "<stable-user-id>"},
    )
    return response.output_text


def step3_amnesia_test(agent):
    """Two conversations, one memory. Conversation 2 shares no thread with 1."""
    # --- Conversation 1: teach the preference ---
    conv1 = openai_client.conversations.create()
    print(f"[3] Conversation 1: {conv1.id}")
    reply1 = _respond(agent, conv1.id, "I prefer dark roast coffee.")
    print(f"    agent: {reply1}")

    # Wait out the debounce + extraction. The Learn doc's own sample waits ~65s.
    print("    Waiting for extraction + consolidation to land in the store...")
    time.sleep(65)

    # --- Conversation 2: brand-new thread, test recall ---
    conv2 = openai_client.conversations.create()
    print(f"[3] Conversation 2: {conv2.id} (fresh thread, no shared history)")
    reply2 = _respond(agent, conv2.id, "Please order my usual coffee.")
    print(f"    agent: {reply2}")
    return reply2


def step4_inspect_memories():
    """Read back what the extractor actually captured.

    This is the most educational step: compare what you *thought* the agent
    would remember against what it *did*. Note the preview schema: memory
    items live in a `memories` collection (not the legacy `results` field).
    """
    print("[4] Memory items in the store:")
    count = 0
    for item in project_client.beta.memory_stores.list_memories(
        name=STORE_NAME, scope=SCOPE
    ):
        count += 1
        print(f"    - {item.memory_id} [{item.kind}]: {item.content}")
    print(f"    Total memories: {count}")


def step5_cleanup(delete_store=False):
    """Delete the lab scope. Optionally delete the whole store."""
    project_client.beta.memory_stores.delete_scope(name=STORE_NAME, scope=SCOPE)
    print(f"[5] Deleted memories for scope: {SCOPE}")
    if delete_store:
        resp = project_client.beta.memory_stores.delete(STORE_NAME)
        print(f"[5] Deleted memory store: {resp.deleted}")


if __name__ == "__main__":
    step1_create_store()
    agent = step2_create_agent()
    step3_amnesia_test(agent)
    step4_inspect_memories()
    # step5_cleanup(delete_store=False)  # uncomment when you're done poking around
    print("\nDone. Re-run step4 any time to watch memories evolve across runs.")
