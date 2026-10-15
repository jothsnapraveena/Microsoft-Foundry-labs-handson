# Prerequisites and Preparation

## Required access

- A Foundry project with toolbox access, a supported region/model and project permissions for toolbox management and runtime tool use.
- A demo MCP server reachable by Foundry over the supported transport; a local-only localhost URL is not reachable from the managed service.
- Choose the authenticated MCP connection pattern in the current guide. For the read-only first pass expose only synthetic data; enable the optional write path only after server-side validation is implemented.

## Rehearsal checklist

- Choose a session-specific resource prefix and record the subscription, resource group and project privately.
- Verify current capability availability and the selected model/version in the official references below.
- Record developer and runtime identities separately where relevant, including the roles actually needed. Request the required scope rather than assuming subscription-wide permissions.
- Prepare an isolated environment using the selected maintained sample's dependencies. Record package versions and its source commit; these content files do not prescribe an untested universal SDK pin.
- Confirm authentication without putting keys, tokens or connection strings in fixtures, screenshots or source control.
- Inventory which resources are shared and which this lab owns. Check estimated charges and plan cleanup before running cloud work.
- Read all eight fixture rows and confirm the expected outcomes agree with the supplied domain rules.

## Record before the live demo

| Item | Your value |
| --- | --- |
| Feature status and region | Not yet verified |
| Model and deployment versions | Not yet selected |
| SDK/sample commit | Not yet selected |
| Estimated budget and price date | Not yet recorded |
| Resource ownership list | Not yet recorded |
| Rehearsal run ID | Not yet executed |

Tool support varies by model/region. The write extension is optional and requires an implemented, authenticated demo server; no MCP server is deployed by these content files.

## Official setup references

- [Toolbox creation and management](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)
- [MCP tool integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)

Proceed with cloud execution only after the required access is available. A local mock is useful for preparation but does not demonstrate the named managed capability.
