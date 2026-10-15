# Validation and Interpretation

## Measurements

| Measurement | Definition |
| --- | --- |
| Task pass rate | Structured cases passed / structured cases attempted, counting errors as failures; explanation cases remain ungraded pending review. |
| Schema error rate | Unparseable or contract-breaking outputs / attempted structured cases. |
| p50 and p95 latency | Client-observed request durations with sample size and warm-up policy. |
| Estimated cost | Sum applicable input/output token charges from a dated price sheet; mark unavailable billing dimensions unknown. |

## Controlled comparison

- Freeze the fixture revision and baseline configuration before measuring.
- Change one intended factor at a time and document unavoidable differences.
- Preserve errors and failed cases; report the number attempted, completed and graded.
- Repeat cases where output is stochastic. Report the sample count and spread rather than a single best result.
- Review disagreements and a sample of apparently passing outputs manually.
- Keep development cases separate from final held-out cases when making optimization decisions.

## Proposed teaching gates

These are starting criteria for a classroom exercise, not Microsoft guarantees or empirically calibrated production thresholds.

- At least 90% exact-match accuracy on an expanded structured-task set before recommending a target.
- No silent removal of errors, throttles or unknown cost fields.
- Choose acceptable latency and cost limits for the application before reading the scorecard.

The eight seed rows are enough to explain the method, not to estimate broad reliability. Expand and independently label the corpus before making a production recommendation.

## Evidence review

Use [proof of execution](07-proof-of-execution.md). Separate expected behavior, observed behavior and your interpretation. Report unavailable metrics as unknown, and include at least one failure analysis if a failure occurs.
