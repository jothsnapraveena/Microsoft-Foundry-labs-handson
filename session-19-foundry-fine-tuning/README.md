# Session 19: Fine-Tuning versus Prompt Engineering

A fictional Alder service desk needs consistent structured ticket classification. Compare a generic prompt, an explicit procedure prompt and a fine-tuned supported base model.

The session investigates: **Does supervised fine-tuning provide a measurable held-out benefit beyond a well-written prompt for this classification task?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry supervised fine-tuning, custom model deployment and evaluation.

Foundry performs the training job and hosts the resulting deployment. We own data quality, label definitions, split hygiene, evaluation and price assumptions. This is a behavior/format task; fine-tuning is not a replacement for retrieving frequently changing facts.

## What learners will demonstrate

- Choose a task where supervised examples can teach stable behavior.
- Prepare model-compatible JSONL with separated training, validation and held-out sets.
- Record training job, base model and checkpoint lineage.
- Compare three conditions without training on the final test set.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md).

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo. Model eligibility, dataset minimums, train/deploy regions and pricing must be checked for the selected model. Seed files are illustrative and are not a production or submission-ready training corpus.

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

- [Supervised fine-tuning guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning)
- [Fine-tuning considerations](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/fine-tuning-considerations)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
