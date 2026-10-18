# Lab: Agent Security and Red Teaming

Can we reduce successful instruction overrides while preserving useful policy answers?

Complete the following sequence:

1. [Prerequisites and access](01-prerequisites.md)
2. [Architecture and trust boundaries](02-architecture-flow.md)
3. [Implementation and demonstration](03-implementation-steps.md)
4. [Validation and interpretation](04-validation-checks.md)
5. [Troubleshooting](05-troubleshooting.md)
6. [Cleanup](06-cleanup.md)
7. [Recorded execution evidence](../evidence/fixed-2026-10-18.json)

Use [the supplied fixtures](../data/cases.jsonl), [baseline instructions](../assets/baseline-instructions.md), and [comparison instructions](../assets/hardened-instructions.md). The latter filename means the second experimental condition; in some sessions the change is configuration or application behavior rather than a stronger prompt.

Success requires an actual Microsoft capability demonstration and independently reviewable observations. Reading this lesson or filling a scorecard with expected outputs does not establish execution. If access is unavailable, use a clearly labeled design walkthrough and leave live evidence unexecuted.
