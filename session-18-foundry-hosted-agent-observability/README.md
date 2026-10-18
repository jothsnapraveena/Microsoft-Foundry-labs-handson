# Session 18: Hosted Agent Deployment and Observability

A fictional Willow equipment assistant looks up a synthetic device checklist through a tiny read-only function. One test device deliberately triggers a controlled tool failure.

The session investigates: **Can we deploy a versioned agent and use traces to explain a failed request from the user's symptom to the failing component?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry hosted agents, agent versions and OpenTelemetry tracing.

Foundry hosts the agent and provides supported deployment and observability integrations. Our handler implements the equipment lookup, correlation attributes and honest failure responses. An ordinary FastAPI endpoint is not automatically a Foundry hosted-agent protocol implementation.

## What learners will demonstrate

- Deploy a small agent using a supported hosted-agent protocol/sample.
- Distinguish local execution from an active Foundry deployment.
- Trace a request through model and tool spans without recording credentials.
- Introduce, diagnose and fix a controlled failure using versioned evidence.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md).

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo. Verify current hosting availability, protocol libraries and deployment path. This package includes the protocol host and image build helper; no deployed Azure container is claimed.

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

- [Deploy hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent)
- [Agent tracing setup](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup)
- [Hosted-agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
