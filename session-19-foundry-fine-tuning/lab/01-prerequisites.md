# Prerequisites and Preparation

## Required access

- Access to a currently fine-tunable base model, training region, quota and permissions, plus capacity to deploy its custom model.
- Training and deployment budgets, including any ongoing hosting charges. Review current model-specific minimums and file-format requirements before submission.
- A curated representative dataset beyond the small teaching seeds included here. There is no universal minimum or guaranteed benefit asserted by this lab.

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

Model eligibility, dataset minimums, train/deploy regions and pricing must be checked for the selected model. Seed files are illustrative and are not a production or submission-ready training corpus.

## Official setup references

- [Supervised fine-tuning guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning)
- [Fine-tuning considerations](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/fine-tuning-considerations)

Proceed with cloud execution only after the required access is available. A local mock is useful for preparation but does not demonstrate the named managed capability.
