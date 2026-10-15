# Validation and Interpretation

## Measurements

| Measurement | Definition |
| --- | --- |
| Exact structured accuracy | All expected category, priority and escalate fields match / attempted cases. |
| Escalation recall | Security/outage cases correctly escalated / labeled escalation cases. |
| Unnecessary escalation | Routine cases incorrectly escalated / labeled non-escalation cases. |
| Version reproducibility | Recorded agent version, skill version and content hash for each response; compare repeated runs. |

## Controlled comparison

- Freeze the fixture revision and baseline configuration before measuring.
- Change one intended factor at a time and document unavoidable differences.
- Preserve errors and failed cases; report the number attempted, completed and graded.
- Repeat cases where output is stochastic. Report the sample count and spread rather than a single best result.
- Review disagreements and a sample of apparently passing outputs manually.
- Keep development cases separate from final held-out cases when making optimization decisions.

## Proposed teaching gates

These are starting criteria for a classroom exercise, not Microsoft guarantees or empirically calibrated production thresholds.

- Every compared skill condition has a recorded immutable skill version and loading evidence.
- All labeled compromise/outage cases escalate under the intended final procedure.
- No routine case escalates merely because of emphatic wording in the teaching corpus.

The eight seed rows are enough to explain the method, not to estimate broad reliability. Expand and independently label the corpus before making a production recommendation.

## Evidence review

Use [proof of execution](07-proof-of-execution.md). Separate expected behavior, observed behavior and your interpretation. Report unavailable metrics as unknown, and include at least one failure analysis if a failure occurs.
