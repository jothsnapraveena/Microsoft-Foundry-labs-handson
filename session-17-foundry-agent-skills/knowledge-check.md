# Knowledge Check

1. Is a skill the same as an MCP function?
2. Does uploading a skill prove it changed behavior?
3. Why pin versions?

4. Which part of this lesson is a Microsoft-managed capability, and which part is our application content?
5. What evidence distinguishes an expected result from an executed result?

## Answer key

1. No. A skill carries reusable instructions/resources; a function executes a tool operation.
2. No. Verify consumption and evaluate outcomes against the baseline.
3. To reproduce the exact procedure being tested without silently following a changed default.
4. Foundry manages skill artifacts and versions. Skill-capable clients/harnesses load the instructions; our fixtures and evaluators determine whether behavior improved. Registering a skill alone does not prove an agent consumed it. Instructions cannot authorize privileged actions.
5. Actual response/error data linked to target versions, fixture IDs and service/run identifiers. Fixtures and blank templates are not execution evidence.
