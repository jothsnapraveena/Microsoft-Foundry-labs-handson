# Prerequisites and Preparation

## Required access

- A Foundry resource/project with a deployable Model Router version and two compatible fixed-model deployments; check regional capacity and access.
- Use an API and authentication path supported by all selected deployments. Confirm each deployment's accepted request parameters before testing.
- Record model-router version, routing configuration if exposed, deployment names, model versions and dated prices. The fixture set is a teaching seed, not a representative benchmark.

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

Router versions, underlying models, parameter support and region availability change. Confirm these for the selected deployment; no particular model family is required by this lab.

## Official setup references

- [Model Router guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router)
- [Evaluation overview](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent)

Proceed with cloud execution only after the required access is available. A local mock is useful for preparation but does not demonstrate the named managed capability.
