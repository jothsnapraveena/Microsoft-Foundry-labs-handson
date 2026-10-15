# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Training job rejected | Check model/region support, format, file limits, minimum examples and quota in the current guide. |
| Training loss improves but test accuracy does not | Inspect label noise, leakage, imbalance and mismatch between training and evaluation tasks. |
| Custom model cannot be deployed | Training capacity and deployment capacity are different; verify availability before scheduling the demo. |
| Perfect tiny-test result | Report sample count and uncertainty; expand independently labeled cases before making broad claims. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
