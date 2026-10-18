# Session 17: Reusable Agent Skills and Versioning

A fictional Maple help desk applies a reusable ticket-triage procedure. The skill produces category, priority and an escalation flag. A second skill version adds an explicit account-compromise escalation rule.

The session investigates: **Does a versioned skill improve procedural consistency, and can we reproduce behavior after a skill update?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry Skills API and compatible skill consumption (preview).

Foundry manages skill artifacts and versions. Skill-capable clients/harnesses load the instructions; our fixtures and evaluators determine whether behavior improved. Registering a skill alone does not prove an agent consumed it. Instructions cannot authorize privileged actions.

## What learners will demonstrate

- Author a skill package with front matter and focused instructions.
- Register two immutable versions and distinguish pinned from default references.
- Use a supported consumer and record evidence of skill loading.
- Compare baseline, version 1 and version 2 using unchanged cases.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md).

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo. Skills and some consumption paths are preview. The example SKILL.md packages are Foundry teaching assets, not instructions for the coding assistant running this repository.

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

- [Use skills in Foundry (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/skills)
- [Toolbox skill integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
