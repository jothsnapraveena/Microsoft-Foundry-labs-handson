# Northstar Retail synthetic dataset

Fictional data for building and evaluating a retail support agent with agentic retrieval. Every record and policy is invented. It is not data from any real retailer, and it contains no real customers, credentials or payment details.

The dataset is deterministic: seed 42, fixed clock **2026-10-03**, region US, prices in integer US cents. Every label is computed as of the fixed clock, so tests must use that date rather than today's.

```powershell
python generate.py    # rewrite every generated file
python validate.py    # integrity, chronology, policy and label checks
```

## Contents

| Path | What it holds |
|---|---|
| `knowledge/*.md` | 40 policy documents: 20 topics, each in versions v1 and v2, three sections per document |
| `knowledge/policies.json` | Policy metadata: effective interval, region, `applies_by`, and machine-readable rule `parameters` |
| `search/policy_chunks.json` | 120 chunks (one per section) with metadata and no embeddings |
| `operational/*.json` | 200 customers, 100 products, 1,000 orders, 2,000 order items, 771 shipments, 88 returns, 39 refunds |
| `northstar.sqlite` | The same tables with keys, constraints and indexes, for local tool development |
| `evals/cases.json` | 144 labeled return requests (117 development, 27 held-out) |
| `evals/policy_qa.json` | 33 policy questions with expected answers and evidence chunks (27 development, 6 held-out) |
| `evals/adversarial_cases.json` | Six failure and security scenarios, as specifications, not executable tests |
| `observability/trace_contract.json` | Proposed trace and audit fields; no recorded telemetry |
| `manifest.json` | Seed, clock, version boundary and row counts |

`README.md`, `evals/adversarial_cases.json` and `observability/trace_contract.json` are maintained by hand. Everything else is written by `generate.py`; edit the generator, not the output.

## Policy rules

Version v1 is in effect from 2026-01-01 and v2 from **2026-09-15**. An interval includes its start date and excludes its end date. Five topics differ between versions:

| Topic | v1 | v2 | Version chosen by |
|---|---|---|---|
| `electronics-returns` | 14-day window | 15-day window | Order date |
| `return-shipping` | 700-cent change-of-mind fee | 500-cent fee | Order date |
| `refund-timing` | Posts in 5–7 business days | Posts in 3–5 business days | Warehouse receipt date |
| `delivered-not-received` | Report within 7 days | Report within 14 days | Delivered date |
| `support-escalation` | Response in 3 business days | Response in 2 business days | Escalation date |

The other fifteen topics have the same text in both versions, so their v1 and v2 chunks are exact duplicates. Retrieval must filter on the effective interval; it cannot rank its way to the right version.

Each policy's `applies_by` field says which date selects the version: `order_date` for eligibility and fee topics, `event_date` for operational topics.

Return rules, in the order they are applied:

1. The signed-in customer must own the order, otherwise access is denied without revealing anything.
2. The order must be delivered. The delivery day is day zero.
3. Quantity must be at least one and no more than the quantity purchased. Units in an authorized, received or refunded return are reserved; rejected and cancelled returns reserve nothing.
4. Marketplace items always go to review. Final-sale items are ineligible for a change of mind and go to review for a defect.
5. A defect within 30 days is eligible with free return shipping; after 30 days it goes to warranty review.
6. Electronics change of mind: within the version's window, undamaged, all accessories present. Opened packaging is allowed.
7. Standard change of mind: within 30 days, unused, in original packaging.

An authorization is never a refund. A refund record exists only once the warehouse has received the item, and moves through pending, submitted and paid.

## Evaluation sets

**Return cases** are built per scenario, not sampled, so each rule and boundary is covered on purpose. Each case has a `scenario` name, the request `inputs` (including `condition` of unused, opened or damaged, `accessories_present` and `original_packaging`), the expected outcome, policy IDs and fee, and a `version_sensitive` flag that is true when applying the other policy version would change the outcome or the fee.

| Expected outcome | Cases |
|---|---|
| eligible | 52 |
| ineligible | 58 |
| review_required | 19 |
| access_denied | 15 |

Coverage includes days 13 to 16 for electronics under each version, days 29 to 31 for standard and defective returns, over-quantity and already-returned items, and access attempts by a real other customer. Six cases flip between eligible and ineligible depending on the version, so a system that always applies the latest policy fails them. No case includes a customer confirmation, so no write should occur.

**Policy questions** come in four types: single-topic, version-dependent (asked once per version with a date in the question), multi-topic, and unanswerable (the policies do not cover the subject). `expected_chunk_ids` lists the evidence, which supports recall and ranking metrics; `expected_answer` supports groundedness, relevance and completeness grading.

Keep the held-out split out of prompts, few-shot examples and the search index.

## Limitations

- Labels come from a rule oracle in `generate.py`. `validate.py` recomputes them with a separate implementation driven by `policies.json`, which catches coding slips but is not human review. Both encode the same reading of the rules.
- The corpus is small: 120 short chunks. Retrieval scores here say little about behaviour on a large corpus.
- There is one region, so region filtering cannot be tested.
- Two product categories and eight product names span the catalog.
- A shipment covers the whole order; there are no split shipments.
- Historical returns exist only for company-sold items that are not final sale.
- The question set is small and written by the dataset author. Treat scores as a smoke test, and add human-reviewed questions before relying on them.
- No tool APIs, Azure resources, embeddings or telemetry are included.
