# Cleanup and Cost Review

1. Export job/checkpoint lineage, split hashes, redacted evaluation outputs and cost assumptions.
2. Delete the custom deployment when finished to stop applicable hosting charges; deleting files alone does not stop a deployment.
3. Remove unneeded uploaded datasets and model artifacts through documented lifecycle operations; keep source teaching data and approved evidence.

## Verify completion

- Compare the final resource list with the ownership inventory from preparation.
- Verify the stopped/deleted state through the current portal or SDK, rather than relying on a command having returned.
- Check remaining model deployments, agent compute, storage, logs and training artifacts for continuing charges.
- Keep a minimal sanitized evidence set with an agreed retention period.
- Record retained shared resources and why they remain.

Cleanup steps are scoped to this session. Deleting a shared project is not part of the exercise.
