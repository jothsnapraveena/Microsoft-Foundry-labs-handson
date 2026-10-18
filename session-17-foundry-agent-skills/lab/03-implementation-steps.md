# Implementation and Live Demonstration

Use [the executable command guide](../RUNNING.md) for this session's implementation. The steps below explain the experiment; SDK/API references remain useful for checking current service availability.

## 1. Read the skill package

Open ../assets/skills/v1/ticket-triage/SKILL.md. Explain the name/description front matter, when the skill applies, output schema and escalation rules. Keep examples and labels separate from evaluation cases; no tool or account actions are granted.

## 2. Create a no-skill baseline

Create a standalone Maple agent using ../assets/baseline-instructions.md with the chosen supported consumer. Run all ../data/cases.jsonl rows. Save the agent configuration and confirm that neither inline instructions nor a cached session already include the skill.

## 3. Register version 1

Follow the official Skills API guide to upload the v1 package. Record skill name, actual immutable version identifier and project. Confirm the service can return its content. Do not assume folder names v1/v2 equal service-assigned versions.

## 4. Attach and verify consumption

Pin the registered version using the documented consumer integration. Start fresh conversations and obtain loading evidence from the consumer trace/configuration. For toolbox discovery, use a client supporting MCP Resources and the skills discovery extension; ordinary tools/list alone is insufficient.

## 5. Evaluate version 1

Repeat the frozen cases with the same model. Parse each JSON response and compare category, priority and escalate fields against labels. Do not accept a convincing explanation that contradicts a required field. Report the security-related cases separately.

## 6. Create and test version 2

Upload ../assets/skills/v2/ticket-triage/SKILL.md as a new version. Pin a new consumer/agent version to it and rerun all cases. Record whether the added account-compromise rule improves escalation and whether routine billing/delivery cases regress.

## 7. Demonstrate reproducibility

Invoke the version-1-pinned consumer again after the version-2 upload. Explain the difference between a default skill selection, resolution at agent-version creation and a pinned immutable artifact. Promote defaults only after recording the comparison; do not assume existing agents hot-reload skill changes.

## Capture the experiment

Start with [the blank scorecard](../evidence/scorecard-template.csv). Record one observation per input, variant and attempt. Keep raw synthetic outputs in an ignored local `artifacts/` directory and link reviewed excerpts in the evidence document. Never put expected labels into the tested request.

## Maintained implementation references

- [Use skills in Foundry (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/skills)
- [Toolbox skill integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)

Use the named Microsoft capability for the relevant exercise and record the configuration and outputs in your run report.
