# Implementation and Live Demonstration

Use [the executable command guide](../RUNNING.md) for this session's implementation. The steps below explain the experiment; SDK/API references remain useful for checking current service availability.

## 1. Define stable labels

Read ../assets/label-policy.md and the seed cases. Label billing, access and delivery independently from urgency. Identify ambiguous cases and resolve label policy before generating more data. The same policy must govern prompts, training labels and evaluation.

## 2. Curate independent splits

Expand seed examples into a representative dataset meeting the chosen model's requirements. Split by scenario/template family before writing paraphrases. Keep a final test set sealed; do not train on ../data/cases.jsonl, which serves as the teaching holdout. Check near-duplicates, label balance and accidental identifiers.

## 3. Run two prompt baselines

Use ../assets/baseline-instructions.md and ../assets/hardened-instructions.md against the same base-model deployment. Record exact prompts, model/version, outputs, token usage and request latency. Grade structured fields exactly; select the stronger baseline using development data only.

## 4. Prepare and validate training files

Convert the curated training/validation rows to the selected model's supported fine-tuning JSONL chat schema. ../data/training-seed.jsonl illustrates the schema only; it is intentionally too small to establish model eligibility or quality. Check required roles, encoding, label values and non-overlap before uploading.

## 5. Submit a small eligible training job

Follow the current supervised fine-tuning guide for your selected model and region. Record file identifiers, base-model version, training settings and job ID. Inspect validation results and failures. Do not report a submitted job as completed training.

## 6. Deploy and run held-out evaluation

After successful training, deploy an eligible checkpoint with the documented custom-model deployment path. Verify endpoint availability. Run the same held-out requests against the chosen base prompt and tuned deployment; record both prompts. Keep sampling/output limits comparable where supported.

## 7. Interpret the trade-offs

Report exact-match accuracy, per-label errors, schema failures, latency and cost assumptions. Include training and any ongoing deployment charges separately from inference estimates. If tuning does not improve the held-out result, publish that finding and prefer the simpler solution.

## Capture the experiment

Start with [the blank scorecard](../evidence/scorecard-template.csv). Record one observation per input, variant and attempt. Keep raw synthetic outputs in an ignored local `artifacts/` directory and link reviewed excerpts in the evidence document. Never put expected labels into the tested request.

## Maintained implementation references

- [Supervised fine-tuning guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning)
- [Fine-tuning considerations](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/fine-tuning-considerations)

If a capability is unavailable in your subscription, keep the corresponding step explicitly unexecuted. Describe the access limitation rather than substituting a local implementation under the Microsoft feature's name.
