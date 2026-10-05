"""Preflight check of the Azure setup in docs/azure-setup.md.

Signs in with your Azure CLI login and makes one small read or call per resource.
It creates and deletes nothing. The two model calls cost a fraction of a cent.

Run from the session folder:  python scripts/check_azure.py
"""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SEARCH_SCOPE = "https://search.azure.com/.default"
MODEL_SCOPE = "https://cognitiveservices.azure.com/.default"
KNOWLEDGE_BASE_API = "2026-08-01-preview"      # preview surface used by Microsoft's tutorial
results = []


def load_env(path):
    """Read KEY=VALUE lines from .env without overriding variables already set."""
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"'))
    return True


def setting(name):
    value = os.environ.get(name, "")
    return "" if "<" in value else value.rstrip("/")


def report(status, name, detail):
    results.append(status)
    print(f"[{status:4}] {name}: {detail}")


def call(url, token, body=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")[:300]
    except (urllib.error.URLError, TimeoutError) as error:
        return None, str(error)


HINTS = {401: "token rejected: check the endpoint, and that role-based access is enabled on the service",
         403: "signed in but not authorized: a role assignment is missing or has not propagated yet",
         404: "not found: check the endpoint and the deployment name", None: "could not connect: check the endpoint"}


def check(name, url, token, ok, body=None, role=""):
    status, payload = call(url, token, body)
    if status == 200:
        report("PASS", name, ok(payload))
    else:
        hint = HINTS.get(status, f"HTTP {status}")
        report("FAIL", name, f"{hint}{' (' + role + ')' if role and status in (401, 403) else ''}. {str(payload)[:160]}")
    return status == 200


def main():
    if not load_env(ROOT / ".env"):
        print("No .env file. Copy .env.example to .env and fill in the Azure values (docs/azure-setup.md, step 8).")
        return 2
    missing = [name for name in ("AZURE_SEARCH_ENDPOINT", "PROJECT_ENDPOINT", "AZURE_OPENAI_ENDPOINT",
                                 "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "AGENT_MODEL") if not setting(name)]
    if missing:
        print("These .env values are empty or still placeholders:", ", ".join(missing))
        return 2
    try:
        from northstar.azure_login import azure_credential
        credential = azure_credential()
    except ImportError:
        print("Install the Azure packages first: python -m pip install -r requirements.txt")
        return 2
    try:
        search_token = credential.get_token(SEARCH_SCOPE).token
        model_token = credential.get_token(MODEL_SCOPE).token
        report("PASS", "Sign-in", "obtained tokens for Azure AI Search and the model endpoint")
    except Exception as error:
        report("FAIL", "Sign-in", f"run 'az login' first. {str(error)[:200]}")
        return 1

    search, models = setting("AZURE_SEARCH_ENDPOINT"), setting("AZURE_OPENAI_ENDPOINT")
    check("Search service access", f"{search}/indexes?api-version=2024-07-01&$select=name", search_token,
          lambda p: f"{len(p['value'])} existing index(es)", role="Search Service Contributor or Search Index Data Reader")
    status, payload = call(f"{search}/knowledgebases?api-version={KNOWLEDGE_BASE_API}", search_token)
    if status == 200:
        report("PASS", "Agentic retrieval", f"{len(payload['value'])} existing knowledge base(s)")
    else:
        report("WARN", "Agentic retrieval", f"could not list knowledge bases with API {KNOWLEDGE_BASE_API} (HTTP {status}). "
               "The region or tier may not support it, or the API version has moved on.")
    embedding = setting("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    check(f"Embedding deployment '{embedding}'", f"{models}/openai/v1/embeddings", model_token,
          lambda p: f"returned a vector of {len(p['data'][0]['embedding'])} dimensions",
          {"model": embedding, "input": "return window"}, role="Foundry User")
    chat = setting("AGENT_MODEL")
    check(f"Chat deployment '{chat}'", f"{models}/openai/v1/chat/completions", model_token,
          lambda p: "responded", {"model": chat, "messages": [{"role": "user", "content": "Reply with OK."}],
                                  "max_completion_tokens": 200}, role="Foundry User")
    try:
        from azure.ai.projects import AIProjectClient
        agents = list(AIProjectClient(endpoint=setting("PROJECT_ENDPOINT"), credential=credential).agents.list())
        report("PASS", "Foundry project", f"reachable, {len(agents)} existing agent(s)")
    except Exception as error:
        report("FAIL", "Foundry project", f"check PROJECT_ENDPOINT and the Foundry User role. {type(error).__name__}: {str(error)[:200]}")

    print("\nNot covered here, because they only show up when the services call each other:")
    print(" - Cognitive Services User for the search service's identity (the knowledge base calling the models)")
    print(" - Search Index Data Reader for the project's identity (the agent reading the index)")
    print(" - Foundry Project Manager (creating the project connection)")
    print(" - Log Analytics Reader on Application Insights (reading traces)")
    print("Stage 3 exercises these. Check them in each resource's Access control (IAM) page meanwhile.")
    return 1 if "FAIL" in results else 0


if __name__ == "__main__":
    sys.exit(main())
