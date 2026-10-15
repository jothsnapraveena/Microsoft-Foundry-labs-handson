# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Tool discovery is empty | Check toolbox version, consumer endpoint, connection authentication and server transport. |
| Local server works but Foundry fails | Verify managed-service network reachability; localhost is not the hosted server. |
| Agent answers from memory | Inspect tool traces; tighten instructions and record the case as failed if no required call occurred. |
| Approval shown but state is wrong | Inspect server authorization and idempotency; do not rely on the language-model response. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
