# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Request rejected or rate limited | Record the HTTP status and error code; inspect content filtering or deployment quotas and adjust request pacing. Keep errors separate from graded answers. |
| Hardened variant refuses everything | Revisit legitimate-answer instructions and compare false refusals before claiming improvement. |
| Attack response looks harmless | Check the labeled objective; an unsupported approval may be a failure without harmful language. |
| Changing results across runs | Record run count and sampling settings; repeat paired trials rather than selecting the best screenshot. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
