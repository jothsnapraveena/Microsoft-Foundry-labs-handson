# Implementation and Live Demonstration

Use [the executable command guide](../RUNNING.md) for this session's implementation. The steps below explain the experiment; SDK/API references remain useful for checking current service availability.

## 1. Define the workload

Read ../data/cases.jsonl. Classify each row by task family and difficulty before running it. Preserve labels and build a larger, nonduplicated workload representative of an intended application; reserve held-out cases that are not used while editing prompts.

## 2. Deploy the comparison targets

Follow the Model Router guide to create an available router deployment. Create or select two fixed-model deployments. Record the actual deployment identities and supported versions. Keep endpoint/auth settings separate from fixture files; do not hard-code keys into the workbook.

## 3. Freeze a request contract

Use ../assets/baseline-instructions.md for all three targets. Set the same output limits and sampling controls only when supported. Where a parameter differs or is unsupported, record the exception rather than silently changing the experiment.

## 4. Collect paired observations

Send each case to each target. Record raw answer, start/end time, error status, available response model identifier and token usage. Warm up separately; then alternate target order to reduce time-of-run bias. Keep retries, throttles and timeouts visible, with one row per attempt.

## 5. Grade independently

For classification/extraction, parse JSON and compare each expected field. Score unsupported keys and invalid labels explicitly. For explanations, use the row rubric and blind manual review or an independent judge; do not substitute fluent writing for correctness.

## 6. Compute the scorecard

Calculate pass rate by task family, invalid-schema rate, p50/p95 latency and mean token usage. Derive estimated cost only from applicable, dated prices for the billed model or router deployment. Mark cost unknown when billing metadata is insufficient; response model names alone do not establish a price.

## 7. Choose based on evidence

Compare all targets on held-out cases. A router win requires the intended quality threshold as well as acceptable latency and cost. Publish failures and sample counts. Explain why this workload may prefer a fixed model and why a tiny dataset cannot establish a universal cheapest deployment.

## Capture the experiment

Start with [the blank scorecard](../evidence/scorecard-template.csv). Record one observation per input, variant and attempt. Keep raw synthetic outputs in an ignored local `artifacts/` directory and link reviewed excerpts in the evidence document. Never put expected labels into the tested request.

## Maintained implementation references

- [Model Router guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router)
- [Evaluation overview](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent)

If a capability is unavailable in your subscription, keep the corresponding step explicitly unexecuted. Describe the access limitation rather than substituting a local implementation under the Microsoft feature's name.
