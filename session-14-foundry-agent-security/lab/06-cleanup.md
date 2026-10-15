# Cleanup and Cost Review

1. Export scan IDs, sanitized failure examples and the paired scorecard.
2. Delete only this session's agent versions and scan/evaluation objects when supported. Record any retained reports and their retention.
3. Remove unused model deployments only if created exclusively for this lab; do not delete a shared project.

## Verify completion

- Compare the final resource list with the ownership inventory from preparation.
- Verify the stopped/deleted state through the current portal or SDK, rather than relying on a command having returned.
- Check remaining model deployments, agent compute, storage, logs and training artifacts for continuing charges.
- Keep a minimal sanitized evidence set with an agreed retention period.
- Record retained shared resources and why they remain.

Cleanup steps are scoped to this session. Deleting a shared project is not part of the exercise.
