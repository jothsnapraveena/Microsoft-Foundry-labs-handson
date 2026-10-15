# Validation and Interpretation

## Measurements

| Measurement | Definition |
| --- | --- |
| Exact match | All requested category/priority fields correct / attempted held-out cases. |
| Per-label performance | Confusion counts and precision/recall by label, with class sample sizes. |
| Schema compliance | Valid JSON, exact required keys and allowed values / attempted cases. |
| Economic comparison | Training and hosting charges plus inference estimates; report break-even only with explicit workload and price assumptions. |

## Controlled comparison

- Freeze the fixture revision and baseline configuration before measuring.
- Change one intended factor at a time and document unavoidable differences.
- Preserve errors and failed cases; report the number attempted, completed and graded.
- Repeat cases where output is stochastic. Report the sample count and spread rather than a single best result.
- Review disagreements and a sample of apparently passing outputs manually.
- Keep development cases separate from final held-out cases when making optimization decisions.

## Proposed teaching gates

These are starting criteria for a classroom exercise, not Microsoft guarantees or empirically calibrated production thresholds.

- All train/validation/final-test splits are nonoverlapping by scenario family.
- No schema or evaluation errors are hidden in reported accuracy.
- Recommend the tuned model only if held-out benefit justifies the measured operational and economic trade-offs.

The eight seed rows are enough to explain the method, not to estimate broad reliability. Expand and independently label the corpus before making a production recommendation.

## Evidence review

Use [proof of execution](07-proof-of-execution.md). Separate expected behavior, observed behavior and your interpretation. Report unavailable metrics as unknown, and include at least one failure analysis if a failure occurs.
