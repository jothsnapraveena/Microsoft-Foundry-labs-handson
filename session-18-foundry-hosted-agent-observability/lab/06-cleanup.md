# Cleanup and Cost Review

1. Export sanitized traces, version identifiers and the deployment verification checklist.
2. Stop/delete session-owned hosted-agent deployments and versions using the documented management path.
3. Remove unused session-only build artifacts/registry resources and telemetry resources after evidence retention; do not delete shared deployments.

## Verify completion

- Compare the final resource list with the ownership inventory from preparation.
- Verify the stopped/deleted state through the current portal or SDK, rather than relying on a command having returned.
- Check remaining model deployments, agent compute, storage, logs and training artifacts for continuing charges.
- Keep a minimal sanitized evidence set with an agreed retention period.
- Record retained shared resources and why they remain.

Cleanup steps are scoped to this session. Deleting a shared project is not part of the exercise.
