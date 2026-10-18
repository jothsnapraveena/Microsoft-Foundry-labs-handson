# Session 15: Model Router Evaluation

A fictional Birch service desk classifies tickets, extracts fields and explains short support policies. A mixed-task benchmark compares a router deployment with fixed-model baselines.

The session investigates: **For this workload, what quality, latency and estimated-cost trade-offs does routing produce?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry Model Router, model inference and evaluation.

Foundry provides routing and inference. Our benchmark labels, grading rules, measurement harness and supplied price table define the experiment. Report the response's available model metadata; never infer the hidden routing decision from answer style.

## What learners will demonstrate

- Design a mixed workload with expected outputs and a held-out split.
- Compare router and fixed deployments using identical requests.
- Measure quality, request latency, token usage and price-based estimates.
- Explain unsupported parameters, routing visibility and small-sample limits.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md).

Current validation: 10 local tests pass and the isolated environment passes `pip check`. East US 2 model availability, quota and capacity have been checked for [the proposed Azure setup](AZURE-SETUP.md).

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo. Router versions, underlying models, parameter support and region availability change. Confirm these for the selected deployment; no particular model family is required by this lab.

## Start here

1. Read [the lab overview](lab/README.md).
2. Review [prerequisites](lab/01-prerequisites.md) and rehearse the full Azure path before presenting.
3. Use [the presenter runbook](presenter-runbook.md) for a 60-minute session.
4. Record actual observations in [proof of execution](lab/07-proof-of-execution.md).
5. Complete [the knowledge check](knowledge-check.md) and use [the contribution kit](contribution-kit.md) to prepare a public write-up.

Allow 90?150 minutes for a learner lab, excluding provisioning, scan or training waits. A live talk should use a rehearsed deployment and clearly dated saved evidence for long-running operations.

## Included materials

| Path | Purpose |
| --- | --- |
| lab/ | Seven guides covering preparation through cleanup |
| assets/ | Session-specific instructions and supporting contracts/content |
| data/cases.jsonl | Eight synthetic seed cases with expected outcomes; not measured results |
| evidence/scorecard-template.csv | Blank observation rows for your actual runs |
| presenter-runbook.md | Talk sequence, demo beats and fallback plan |
| contribution-kit.md | Article outline, demo checklist and community exercise |

## Official references

- [Model Router guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router)
- [Evaluation overview](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
