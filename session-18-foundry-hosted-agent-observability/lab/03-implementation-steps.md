# Implementation and Live Demonstration

Use [the executable command guide](../RUNNING.md) for this session's implementation. The steps below explain the experiment; SDK/API references remain useful for checking current service availability.

## 1. Choose a maintained starter

Use the official hosted-agent quickstart/sample linked below. Record its commit and SDK versions. Select a simple supported Responses protocol path. Keep the model client independent of any prior session; do not use Northstar or its tool service.

## 2. Add the equipment function

Implement ../assets/tool-contracts.md against ../data/equipment.json. The get_checklist function returns known checklist items, returns unknown for missing devices and raises a controlled error for DEMO-FAIL. Add ../assets/baseline-instructions.md to the agent. This function is local to the hosted agent; no separate MCP server is required.

## 3. Verify locally

Start the sample through its documented host entry point. Run the healthy, unknown and failing-device fixtures using its supported request protocol. Verify that an error does not become a fabricated checklist. Capture the response outcome and correlation ID.

## 4. Deploy a named version

Follow the official deployment guide for the selected path. Record the image/source artifact, agent version and endpoint. Wait for active/readiness status, invoke the remote endpoint and verify the observed version. A successful image build alone is not a successful agent deployment.

## 5. Instrument and inspect

Enable supported tracing and add a lookup span with device_id, lookup outcome and a safe error code. Keep prompt content collection off for the first run. Find the healthy and failing requests by correlation ID and inspect parent/child relationships and tool duration.

## 6. Diagnose from evidence

Ask learners to identify whether the failure occurred before model invocation, during tool execution or during deployment. Use the DEMO-FAIL trace, safe error code and actual returned response. Explain the difference between telemetry diagnostics and a durable business audit record.

## 7. Deploy a fix and compare

Create a new version that handles the controlled tool error with a useful fallback message. Repeat the same fixtures; verify successful answers remain unchanged and the failure is honestly surfaced. Demonstrate rollback/version selection only through the current documented management path; retain both version identifiers in the scorecard.

## Capture the experiment

Start with [the blank scorecard](../evidence/scorecard-template.csv). Record one observation per input, variant and attempt. Keep raw synthetic outputs in an ignored local `artifacts/` directory and link reviewed excerpts in the evidence document. Never put expected labels into the tested request.

## Maintained implementation references

- [Deploy hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent)
- [Agent tracing setup](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup)
- [Hosted-agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

Use the named Microsoft capability for the relevant exercise and record the configuration and outputs in your run report.
