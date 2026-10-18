# Implementation and Live Demonstration

Use [the executable command guide](../RUNNING.md) for this session's implementation. The steps below explain the experiment; SDK/API references remain useful for checking current service availability.

## 1. Define the tool contracts

Read ../assets/tool-contracts.md and ../data/inventory.json. Build or adapt a maintained MCP server exposing get_stock(sku). Validate SKU strings and return only catalog fields. Keep writes disabled initially; the contract is implemented by inventory.py and the MCP server.

## 2. Verify MCP independently

Using an MCP-capable inspector/client, call tools/list and get_stock for J-101, J-102 and an unknown SKU. Save the discovered JSON schema and actual results. Verify invalid types are rejected by the server rather than normalized by a model.

## 3. Create the toolbox

Follow the linked toolbox guide to create a new version containing the MCP server and its appropriate project connection. Give each tool a concise description and save version-specific and default consumer endpoints. Verify tool discovery through the toolbox endpoint, not just directly against the server.

## 4. Attach the first consumer

Create a standalone stock assistant with ../assets/baseline-instructions.md. Use the current supported toolbox integration from the Microsoft guide and ask the fixture questions. Save the actual get_stock arguments and returned quantity as well as the final answer.

## 5. Demonstrate reuse

Create a second independent agent with different wording but the same pinned toolbox version. Repeat a stock lookup. Explain that the shared tool endpoint enables reuse; it does not make the two agents share conversation memory.

## 6. Exercise validation and optional approval

Run unknown-SKU and invalid-quantity cases. If implementing reserve_stock, keep it a synthetic write with caller identity, an idempotency key, sufficient-stock validation and an explicit approval step. Reject an unapproved request in the backend even if the model claims a manager authorized it.

## 7. Version and retest

Change a tool description or add a harmless catalog field in a new toolbox/server version. Test against the version-specific endpoint before promoting a default. Repeat a pinned-version call and record what changed in toolbox configuration versus server implementation.

## Capture the experiment

Start with [the blank scorecard](../evidence/scorecard-template.csv). Record one observation per input, variant and attempt. Keep raw synthetic outputs in an ignored local `artifacts/` directory and link reviewed excerpts in the evidence document. Never put expected labels into the tested request.

## Maintained implementation references

- [Toolbox creation and management](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)
- [MCP tool integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)

Use the named Microsoft capability for the relevant exercise and record the configuration and outputs in your run report.
