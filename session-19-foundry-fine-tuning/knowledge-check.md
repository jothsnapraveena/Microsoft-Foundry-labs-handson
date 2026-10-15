# Knowledge Check

1. Why use classification instead of changing product facts?
2. Why split before paraphrasing?
3. Does completed training imply deployment is available?

4. Which part of this lesson is a Microsoft-managed capability, and which part is our application content?
5. What evidence distinguishes an expected result from an executed result?

## Answer key

1. Stable label behavior fits supervised examples; changing facts usually need current context or retrieval.
2. Closely related templates across splits can inflate evaluation results.
3. No. Deployment support and capacity must be checked separately.
4. Foundry performs the training job and hosts the resulting deployment. We own data quality, label definitions, split hygiene, evaluation and price assumptions. This is a behavior/format task; fine-tuning is not a replacement for retrieving frequently changing facts.
5. Actual response/error data linked to target versions, fixture IDs and service/run identifiers. Fixtures and blank templates are not execution evidence.
