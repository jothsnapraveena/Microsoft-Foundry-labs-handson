# Validation and Interpretation

## Measurements

| Measurement | Definition |
| --- | --- |
| Discovery correctness | Expected tool names and input schemas actually returned through the toolbox. |
| Read accuracy | Answer quantity matches the recorded tool result for each SKU. |
| Rejected input behavior | Invalid arguments produce a structured tool error, with no state mutation. |
| Mock-write integrity | If enabled: one approved idempotent reservation, rejected unapproved/overstock requests, and audit record. |

## Controlled comparison

- Freeze the fixture revision and baseline configuration before measuring.
- Change one intended factor at a time and document unavoidable differences.
- Preserve errors and failed cases; report the number attempted, completed and graded.
- Repeat cases where output is stochastic. Report the sample count and spread rather than a single best result.
- Review disagreements and a sample of apparently passing outputs manually.
- Keep development cases separate from final held-out cases when making optimization decisions.

## Proposed teaching gates

These are starting criteria for a classroom exercise, not Microsoft guarantees or empirically calibrated production thresholds.

- All three catalog lookup outcomes match actual server results.
- Every required inventory answer has evidence of a tool call.
- If writes are enabled, no unapproved or invalid mutation and no duplicate effect on retry.

The eight seed rows are enough to explain the method, not to estimate broad reliability. Expand and independently label the corpus before making a production recommendation.

## Evidence review

Use [proof of execution](07-proof-of-execution.md). Separate expected behavior, observed behavior and your interpretation. Report unavailable metrics as unknown, and include at least one failure analysis if a failure occurs.
