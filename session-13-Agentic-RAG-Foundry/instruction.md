# Build instructions: Northstar Retail enterprise agentic RAG

## Goal and working style
Build a runnable customer support agent using Microsoft Foundry and Azure AI Search. Use synthetic data, but implement production-style retrieval, authorization, transactional workflows, evaluations and observability. The user develops in VS Code and wants to inspect evaluation results and traces in Foundry. Explain each build stage clearly so the user can learn the implementation. Proceed with local implementation and meaningful tests. Ask only for missing Azure resource details or decisions that materially block progress. Do not claim deployment or portal verification without actually completing it.

This is a fictional Amazon-style retail support application, not an Amazon integration. No actual payments, carrier labels or customer communications are authorized. Return processing means persisted mock return authorizations. Keep Azure provisioning and chargeable evaluation runs explicit and reviewable before execution. Never request secrets in chat or commit them.

## Existing deliverable
The dataset is in the `northstar-dataset` directory next to this file. Its `README.md` documents every file, the policy rules and the limitations; read it first. Regenerate with `python generate.py` and check with `python validate.py`. Do not edit generated files by hand.

Dataset counts (see `manifest.json`):
- 40 Markdown policy documents: 20 topics, each with v1 and v2, three sections each.
- 120 policy chunks, one per section, without embeddings.
- 100 products and 200 fictional customers.
- 1,000 orders and 2,000 order items.
- 771 shipments, 88 historical returns, 39 refunds (pending, submitted and paid).
- 144 labeled return cases: 117 development and 27 held-out.
- 33 policy questions with expected answers and evidence chunks: 27 development and 6 held-out.
- Six adversarial/failure specifications, not yet executable tests.

Important files:
- `knowledge/*.md` and `knowledge/policies.json`: policy documents, effective-date metadata, the `applies_by` rule and machine-readable rule `parameters`.
- `search/policy_chunks.json`: pre-chunked records WITHOUT embeddings.
- `operational/*.json`: linked customers, products, orders, order_items, shipments, returns and refunds.
- `northstar.sqlite`: local relational store with keys, constraints and indexes.
- `evals/cases.json`: return request fixtures with expected outcomes, policy references, fees and a `version_sensitive` flag.
- `evals/policy_qa.json`: policy questions for retrieval and answer-quality evaluation.
- `evals/adversarial_cases.json`: failure and security scenario specifications.
- `observability/trace_contract.json`: proposed trace/audit fields, not recorded telemetry.
- `generate.py`, `validate.py`, `README.md`, `manifest.json`.

Dataset is deterministic, seed 42, fixed date 2026-10-03, US region, USD prices in integer cents. Policy v2 takes effect on 2026-09-15. Use a configurable server clock; tests use the fixed date. Using today's date changes eligibility. Product variety is deliberately limited to generic electronics and standard goods, and there is a single region, so region filtering cannot be tested with this data.

`validate.py` checks SQLite integrity, policy intervals, chronology, refund timing against policy and coverage, and recomputes every return-case label with an implementation separate from the generator's. That catches coding slips, but both implementations encode the same reading of the rules and neither is human ground truth. Do not describe the labels as independently validated. The policy engine built for this project must be a third implementation, driven by `policies.json`, and must agree with the fixtures.

## Reference architecture
Follow and adapt Microsoft's tutorial:
https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-pipeline

Read the CURRENT official documentation before selecting packages, APIs and model deployments. The previously viewed tutorial used preview SDK/API surfaces. Do not assume its old pinned package versions remain correct, and do not silently mix Foundry classic/new experiences. Document any preview dependency and version-pin the implementation.

Concepts:
- Raw documents are original policy files.
- A search index stores searchable policy chunks, metadata and real embedding vectors.
- A search-index knowledge source wraps that index.
- A knowledge base references sources and orchestrates retrieval.
- The Foundry agent accesses the knowledge base using the tutorial's supported MCP integration.
- Order and return tools access the transactional database separately.

Data flow:
1. Policy files -> validated chunks -> embeddings -> Azure AI Search index.
2. Index -> knowledge source -> knowledge base -> Foundry agent retrieval tool.
3. Agent -> authorized backend order/eligibility/action tools -> transactional store.
4. Instrumented execution -> Application Insights connected to Foundry -> traces and monitoring.
5. Evaluation runner -> registered Foundry evaluation results plus local deterministic test reports.

Keep private orders out of the shared policy index. RAG explains rules with evidence; a deterministic backend authorizes business actions.

## Implementation choices
Use Python unless the existing project clearly requires another language. Prefer a simple FastAPI tool service and SQLite for the initial runnable build. Isolate persistence behind a repository interface so Azure SQL/PostgreSQL can replace SQLite later. Do not call SQLite itself a production deployment. A minimal CLI/chat client is sufficient initially; no elaborate UI is needed. Use environment-based configuration and an `.env.example` with placeholders. Provide a supported tool adapter for the chosen Foundry SDK/API. Tool descriptions alone do not register tools.

## Retrieval and ingestion requirements
- Preserve policy ID, topic, version, section, effective_from, effective_to, region, applies_by and source_path on every chunk.
- Intervals include effective_from and exclude effective_to; null end means open-ended.
- Eligibility policies apply by ORDER DATE, per this fictional business's rules. Operational policies apply by the date of the event they describe (for example refund timing by warehouse receipt date); each policy's `applies_by` field states which. Never blindly retrieve only the latest version for old orders.
- Five topics differ between versions: electronics window (14 then 15 days), change-of-mind return fee (700 then 500 cents), refund posting time (5-7 then 3-5 business days), delivered-not-received report window (7 then 14 days) and support response time (3 then 2 business days). The other fifteen topics have identical text in both versions, so their chunks are exact duplicates and only a date filter can select the right one.
- Support keyword/vector hybrid retrieval and semantic reranking through the selected knowledge-base configuration, verifying available capabilities.
- Generate document embeddings explicitly. Query-time vectorization does not embed uploaded documents. Match index dimensions to the deployment configuration.
- Make ingestion idempotent and incremental with stable chunk IDs and content/version hashes. Prevent stale deleted chunks from remaining active.
- Validate schema, dates, vector lengths and upload failures. Preserve stable citation IDs and resolve source references to actual policy text. Do not fabricate public URLs for local files.
- If the chosen knowledge-base surface cannot enforce required date/region filters, implement a supported constrained retrieval adapter or backend evidence validation. Prompt instructions alone do not guarantee policy applicability.
- Missing, overlapping or contradictory applicable policies trigger review, not invented rules.

## Tools and business workflows
Implement:
1. `get_order(order_id)` with server-derived authenticated customer identity.
2. `check_return_eligibility(order_id, item_id, quantity, reason, condition, accessories_present, original_packaging)` returning eligible/ineligible/review_required, reasons, policy IDs/version and proposed fees.
3. `create_return(...)` with action-bound confirmation token and idempotency key.
4. `get_return_status(return_id)` with ownership checks, including the refund record and its pending/submitted/paid state when one exists.
5. `cancel_order(...)` only for processing orders, after confirmation.
6. `create_support_ticket(...)` after confirmation, with persistent ticket storage.

Required enforcement:
- Trusted authenticated identity comes from server context. IDs typed in chat do not authenticate a customer.
- For local demos, clearly label any identity stub and keep it disabled in deployed configuration. Implement a real Entra-compatible access-token validation path for deployment, verifying issuer/audience/signature and mapping identity to customer ownership.
- Unauthorized lookup must not reveal whether another customer's order exists or disclose its contents.
- Delivery day is day zero. Undelivered orders cannot enter return processing.
- Company standard change-of-mind: <=30 days, unused and original packaging. Packaging is an explicit input (`original_packaging`); do not infer it.
- Company electronics change-of-mind: <=14/15 days by applicable version, undamaged and accessories present; opened packaging allowed.
- Company defects: <=30 days, except marketplace/final-sale claims need review. Beyond the window, warranty review.
- Final-sale change-of-mind is ineligible. Marketplace requests require seller review.
- Positive quantities cannot exceed purchased minus active/completed return reservations. Define rejected/cancelled states explicitly.
- Defect return shipping is free; the eligible change-of-mind fee is 700 cents for orders placed under v1 and 500 cents under v2, disclosed before confirmation and not deducted from the refund.
- Never issue a refund merely because a return was created.
- Recheck ownership, eligibility, current status and quantities in the write transaction.
- Idempotency is persistent: same key and payload returns original result; mismatched payload fails. Handle retry after response timeout and concurrent attempts.
- Confirmation tokens bind actor, order, item, quantity, action and relevant proposal details, with expiry. A bare boolean controlled by the model is insufficient.
- Audit attempted/successful actions and failures, avoiding sensitive raw data.

## Evaluations
Use three complementary layers:
1. Independent deterministic backend tests for policy boundaries, ownership, quantities, confirmations, concurrency, state transitions and idempotency.
2. Agent workflow tests checking expected tools, arguments, evidence and actual side effects.
3. Answer/retrieval evaluations for Recall@k, ranking quality, groundedness, citation correctness, relevance and completeness.

The 144 return cases are single-turn fixtures built per scenario and contain no confirmation, so no write should occur. Six of them change outcome depending on the policy version and many more change fee; report results on the `version_sensitive` cases separately. The 33 policy questions carry expected answers and evidence chunk IDs for the answer and retrieval layer. Build adapters to the current Foundry evaluation schema. Keep the generated fixtures separate from any enriched versions and document changes. Retain held-out separation; never include evaluation answers in the RAG corpus or agent prompts.

The fixtures already cover the 14/15/16 and 29/30/31-day boundaries, both policy versions, original packaging, damaged items, partial and already-returned quantities, and access by another real customer. Extend with missing fields, multi-turn confirmed writes, refund status, cancellations, delivery disputes (the data has overdue shipments), policy conflicts, prompt injection and backend outages. The policy question set is small and author-written; add human-reviewed questions before treating its scores as more than a smoke test. Turn the six adversarial specifications into executable tests. Use model graders for answer quality, not as the only check for authorization or eligibility. Human-review a sample. Document judge model, rubric, prompt and dataset versions.

Publish supported evaluation runs to Foundry so the user can inspect results. Do not claim a local JSON report automatically appears in the portal. Document which deterministic results can be registered through the chosen evaluation API and keep additional CI reports available locally.

Release gates: no unauthorized data disclosure, unconfirmed writes, quantity over-return or duplicate side effects in the covered tests. Set quality/latency/cost targets only after baseline measurements; do not invent achieved metrics. Synthetic success does not prove real-traffic quality.

## Observability
Connect Application Insights to the Foundry project, enable supported agent tracing, and instrument custom application/tool logic with OpenTelemetry. Propagate trace context across agent and tool boundaries.

Record redacted attributes for model deployment, prompt version, policy/chunk IDs, retrieval and tool durations, token usage, errors/retries and decision outcomes. Token/cost fields may depend on available provider telemetry; estimated cost must be labeled and use configurable pricing. Do not log credentials, payment data or unrestricted prompts/order payloads by default.

Link business-action audit records to trace IDs. Audit persistence is separate from diagnostic trace sampling. Add dashboards/queries for latency percentiles, tool errors, retrieval failures, escalations, tokens and estimated cost. Add alerts and retention/sampling configuration. Document how to inspect traces and registered evaluations in the selected Foundry portal experience. Verify a real trace/evaluation run when Azure access exists; otherwise clearly mark pending cloud verification.

Official starting references, recheck current versions:
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard

## Build stages and acceptance
The stages are large. Treat each as its own deliverable with its own review, and do not start a stage until the previous one runs and its tests pass.

1. Inspect existing repo and dataset; run integrity checks; document architecture and dependencies.
2. Build a local policy engine, repository and tool service with meaningful deterministic tests.
3. Implement ingestion and Foundry knowledge-source/knowledge-base/agent integration. Validate cited policy-only answers against real indexed data.
4. Attach operational tools and demonstrate authenticated lookup, eligibility, confirmed mock authorization, cancellation and escalation.
5. Run local workflow evaluations and register supported results in Foundry.
6. Enable tracing, demonstrate correlated model/retrieval/tool spans, and provide monitoring queries.
7. Add reproducible infrastructure/deployment configuration, CI checks, dependency/secret scanning, rollback instructions and setup documentation. Deployment remains conditional on available Azure access and user authorization.

Keep a runnable local mode when cloud configuration is unavailable. Mocks must be explicitly labeled and must not masquerade as a successful Foundry integration.

Deliver source code, pinned dependencies, `.env.example`, setup instructions, ingestion commands, local demo commands, test/evaluation commands, architecture documentation, threat/permission assumptions and a concise status of implemented versus pending cloud verification. Main successful demo: lookup an owned delivered order, retrieve applicable policy, explain return eligibility with evidence, obtain confirmation, persist exactly one authorization, and inspect its trace and evaluation results.
