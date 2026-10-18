# Knowledge Check

1. Why keep legitimate questions?
2. Does the marker represent secret storage?
3. Can content-filter rejections count as successful agent refusals?

4. Which part of this lesson is a Microsoft-managed capability, and which part is our application content?
5. What evidence distinguishes an expected result from an executed result?

## Answer key

1. A blanket refusal strategy can reduce attacks while making the assistant unusable.
2. No. It is a synthetic disclosure canary; real credentials must never be placed in prompts.
3. No. A rejected request has no completed agent answer to grade; report it separately from completed responses.
4. Microsoft supplies agent hosting, model inference and available safety controls. Our policy text, attack labels, disclosure checks and acceptance criteria are application content. A system-prompt marker is a teaching canary, never a place to store a real secret.
5. Actual response/error data linked to target versions, fixture IDs and service/run identifiers. Fixtures and blank templates are not execution evidence.
