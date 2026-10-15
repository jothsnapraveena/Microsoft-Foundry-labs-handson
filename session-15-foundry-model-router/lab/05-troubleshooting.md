# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Router unavailable | Check region, deployment version, model access and quota; do not replace it with handwritten routing and call that Model Router. |
| Parameter rejected | Use the documented supported contract and disclose any mismatch between comparison targets. |
| No selected-model metadata | Report unavailable; do not guess which model answered. |
| Timeouts distort results | Keep error rate and successful-response latency separate; publish the timeout threshold. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
