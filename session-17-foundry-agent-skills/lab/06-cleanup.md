# Cleanup and Cost Review

1. Export content hashes, immutable service versions and sanitized load evidence.
2. Delete this session's agents/toolboxes that reference skills before deleting session-owned skill versions.
3. Retain the authored packages and comparison data; remove any session-only runtime resources.

## Verify completion

- Compare the final resource list with the ownership inventory from preparation.
- Verify the stopped/deleted state through the current portal or SDK, rather than relying on a command having returned.
- Check remaining model deployments, agent compute, storage, logs and training artifacts for continuing charges.
- Keep a minimal sanitized evidence set with an agreed retention period.
- Record retained shared resources and why they remain.

Cleanup steps are scoped to this session. Deleting a shared project is not part of the exercise.
