# Troubleshooting

| Symptom | What to inspect |
| --- | --- |
| Skill is registered but unused | Check consumer support, attached reference and evidence of loading; upload alone is not integration. |
| Client discovers tools but not skills | Verify MCP Resources and skills-extension support or select another documented consumer. |
| V2 change does not appear | Check pinned references and fresh agent/session versions; do not assume default changes mutate old versions. |
| Output varies | Separate stochastic output variation from version changes using repeated paired cases. |

## A useful diagnostic record

Record the case ID, target/agent/model version, timestamp, service run/correlation ID, safe error category and reproduction steps. Keep raw responses private until sanitized for publication.

Fix one variable, rerun the original failing case, then rerun a healthy control case. A successful retry alone does not establish the cause.

If access or capacity is unavailable, use saved evidence from an actual dated rehearsal or show a design walkthrough. Do not present expected fixture values as a live service result.
