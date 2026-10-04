# Session 13: Enterprise Agentic RAG with Microsoft Foundry and Azure AI Search

A retail support agent for the fictional Northstar Retail. Azure AI Search agentic retrieval explains the policies with evidence; a deterministic backend decides and performs the business actions. All data is synthetic. No real payments, carrier labels or customer messages are involved, and a "return" is a stored mock authorization.

The build follows [instruction.md](instruction.md) in stages. This README states what exists now.

## Status

| Stage | What | State |
|---|---|---|
| 1 | Dataset, integrity checks, architecture | Done |
| 2 | Policy engine, repository, tool service, deterministic tests | Done, runs locally |
| 3 | Search index, knowledge source, knowledge base, Foundry agent | Not built |
| 4 | Agent with operational tools, chat client | Not built |
| 5 | Evaluations registered in Foundry | Not built |
| 6 | Tracing and monitoring | Not built |
| 7 | Infrastructure, CI, deployment | Not built |

Stages 3 onward need Azure resources and role assignments; [docs/azure-setup.md](docs/azure-setup.md) lists them. Nothing has been run against Azure yet. The Entra token path is tested with locally generated keys, not a live tenant.

## Layout

```text
instruction.md            Build specification
northstar-dataset/        Synthetic policies, orders, evaluation sets (see its README)
docs/architecture.md      Components, confirmation design, threat assumptions
docs/azure-setup.md       Azure resources, role assignments and troubleshooting
src/northstar/
  policies.py             Policy metadata and version selection by date
  eligibility.py          Return rules, driven by policies.json
  repository.py           Persistence interface and the SQLite implementation
  service.py              The tools: ownership, proposals, confirmed writes, idempotency, audit
  auth.py                 Caller identity: Entra token validation, and a local demo stub
  api.py                  FastAPI tool service
tests/                    34 tests, no model and no Azure required
```

## Run it locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Start the tool service against a working copy of the dataset:

```powershell
$env:PYTHONPATH = "src"
$env:NORTHSTAR_AUTH_MODE = "demo"
$env:NORTHSTAR_FIXED_DATE = "2026-10-03"
python -m northstar.setup_db
python -m uvicorn northstar.main:app --app-dir src --host 127.0.0.1 --port 8000
```

`demo` mode trusts the `X-Demo-Customer-Id` header and exists only for local use. Interactive API documentation is at <http://127.0.0.1:8000/docs>. `python -m northstar.setup_db --reset` restores the working database from the dataset.

## The tools

| Tool | Endpoint | Writes |
|---|---|---|
| `get_order` | `GET /orders/{order_id}` | No |
| `check_return_eligibility` | `POST /returns/eligibility` | No |
| `create_return` | `POST /returns` | Yes |
| `get_return_status` | `GET /returns/{return_id}` | No |
| `propose_cancel_order` | `POST /cancellations/proposal` | No |
| `cancel_order` | `POST /cancellations` | Yes |
| `propose_support_ticket` | `POST /tickets/proposal` | No |
| `create_support_ticket` | `POST /tickets` | Yes |

Every write needs a proposal from its read-only step, a confirmation token, and an `Idempotency-Key` header. The token comes from `POST /confirmations`, which only the customer-facing client may call and which is left out of the OpenAPI document so it is never registered as an agent tool. The agent can prepare an action but cannot confirm it.

## What the tests establish

- All 144 labeled return cases produce the expected outcome, policy IDs and fee through the service, and write nothing.
- Another customer's order is indistinguishable from a missing one.
- No write happens without a confirmation; a token for one action cannot drive another; confirmations expire.
- Eligibility, ownership and order status are re-checked inside the write transaction.
- A retried write with the same key returns the original result; concurrent attempts cannot return more units than were purchased.
- Overlapping or missing policies go to review instead of being decided.
- Entra tokens with a wrong signature, audience, issuer, expiry or an unlinked subject are rejected.

These are tests of the backend on synthetic data. They say nothing yet about retrieval or answer quality.
