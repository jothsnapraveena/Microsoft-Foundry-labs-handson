# Cleanup and Cost Review

1. Remove optional synthetic reservation records after exporting audit evidence.
2. Delete this session's consumer agents, toolbox versions and unused connections in dependency order.
3. Stop the demo MCP server and remove its session-only hosting resources; keep shared projects intact.

## Verify completion

- Compare the final resource list with the ownership inventory from preparation.
- Verify the stopped/deleted state through the current portal or SDK, rather than relying on a command having returned.
- Check remaining model deployments, agent compute, storage, logs and training artifacts for continuing charges.
- Keep a minimal sanitized evidence set with an agreed retention period.
- Record retained shared resources and why they remain.

Cleanup steps are scoped to this session. Deleting a shared project is not part of the exercise.
