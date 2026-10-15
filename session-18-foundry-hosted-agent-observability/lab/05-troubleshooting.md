# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Local run succeeds but deployment fails | Inspect build/runtime logs, supported protocol, startup command, architecture and identity permissions. |
| Active agent cannot call the model | Check the agent runtime identity and model deployment configuration; local developer access is different. |
| No traces visible | Verify the connected telemetry resource, reader permissions, export configuration and ingestion delay. |
| Trace includes sensitive content | Review content capture settings and custom span attributes before sharing evidence. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
