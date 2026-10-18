# Session 14: Agent Security and Red Teaming

A fictional Cedar employee-policy assistant answers travel and expense questions from a bundled policy. It has no operational tools and cannot approve or pay expenses.

The session investigates: **Can we reduce successful instruction overrides while preserving useful policy answers?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry Agent Service prompt agents, versioned definitions, model inference and content filtering.

Microsoft supplies agent hosting, model inference and available safety controls. Our policy text, attack labels, disclosure checks and acceptance criteria are application content. A system-prompt marker is a teaching canary, never a place to store a real secret.

## What learners will demonstrate

- Define direct and document-borne instruction attacks and the trust boundary they cross.
- Create a standalone prompt agent and record a legitimate-answer baseline.
- Run the fixed legitimate and adversarial cases against both agent variants.
- Compare mitigations using attack outcomes and false refusals.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md). The recorded paired run attempted 16 requests: 14 responses completed and two requests were blocked by content filtering. Assistant review is labeled separately from pending human grading; see [the execution evidence](evidence/fixed-2026-10-18.json).

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo.

## Start here

1. Read [the lab overview](lab/README.md).
2. Review [prerequisites](lab/01-prerequisites.md) and rehearse the full Azure path before presenting.
3. Use [the presenter runbook](presenter-runbook.md) for a 60-minute session.
4. Review actual observations in [the execution evidence](evidence/fixed-2026-10-18.json).
5. Complete [the knowledge check](knowledge-check.md) and use [the contribution kit](contribution-kit.md) to prepare a public write-up.

Allow 90?150 minutes for a learner lab, excluding provisioning waits. A live talk should use a rehearsed deployment and clearly dated saved evidence for long-running operations.

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

- [Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
