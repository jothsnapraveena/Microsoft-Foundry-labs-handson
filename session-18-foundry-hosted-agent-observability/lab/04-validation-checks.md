# Validation and Interpretation

## Measurements

| Measurement | Definition |
| --- | --- |
| Remote request outcome | Expected answer, explicit unknown or honest controlled failure, matched by case ID. |
| Trace completeness | Expected model/tool spans and a correlation ID exist for each exercised request. |
| Latency | End-to-end and lookup duration with the same measurement boundary across versions. |
| Diagnostic correctness | The identified failure component matches the deliberately injected fault. |

## Controlled comparison

- Freeze the fixture revision and baseline configuration before measuring.
- Change one intended factor at a time and document unavoidable differences.
- Preserve errors and failed cases; report the number attempted, completed and graded.
- Repeat cases where output is stochastic. Report the sample count and spread rather than a single best result.
- Review disagreements and a sample of apparently passing outputs manually.
- Keep development cases separate from final held-out cases when making optimization decisions.

## Proposed teaching gates

These are starting criteria for a classroom exercise, not Microsoft guarantees or empirically calibrated production thresholds.

- Verify at least one healthy invocation of the remote active version.
- Correlate healthy and controlled-failure cases to their expected spans.
- No failed lookup is presented as a successful checklist retrieval.

The eight seed rows are enough to explain the method, not to estimate broad reliability. Expand and independently label the corpus before making a production recommendation.

## Evidence review

Use [proof of execution](07-proof-of-execution.md). Separate expected behavior, observed behavior and your interpretation. Report unavailable metrics as unknown, and include at least one failure analysis if a failure occurs.
