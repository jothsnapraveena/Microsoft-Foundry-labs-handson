# Session 16: Reusable Tools with Foundry Toolboxes and MCP

A fictional Juniper supply assistant checks a synthetic inventory catalog and optionally proposes a stock reservation. Inventory reads are real calls to a demo MCP server; reservations remain mock records.

The session investigates: **Can two independent agents reuse one managed tool endpoint while preserving input validation and approval boundaries?**

## Microsoft capability and application responsibility

**Microsoft capability:** Foundry Toolboxes and MCP tool integration.

Foundry supplies the toolbox resource and supported MCP integration. The MCP server must implement validation, stock constraints, authorization and idempotency. An agent approval prompt is not a substitute for backend authorization.

## What learners will demonstrate

- Explain the distinction between an MCP server, toolbox and consuming agent.
- Create and verify a versioned toolbox using a synthetic tool server.
- Inspect actual tool discovery and call results from two agents.
- Demonstrate rejected inputs and an explicitly approved mock write.

## Content and execution status

This session now includes a runnable implementation, pinned dependencies, local tests, configuration examples and explicit Azure commands. Start with [RUNNING.md](RUNNING.md). Local checks exercise application behavior and supported protocol libraries; no live Azure deployment, scan, model-quality result or training completion is claimed.

No Northstar agent or previous session is required. General Azure access is still required for the live Microsoft capability demo. Tool support varies by model/region. The write extension is optional and requires an implemented, authenticated demo server; the MCP implementation is included; no public server deployment is claimed.

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

- [Toolbox creation and management](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)
- [MCP tool integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)

Reference review date: 2026-10-15. Verify feature status, regional availability and package/API versions again before the live session.
