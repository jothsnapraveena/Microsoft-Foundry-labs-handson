# Synthetic dataset card

The implementation corpus contains 160 training and 40 validation rows. Eight scenario templates have separate train/validation phrasing families; source rows record the family and split. The original eight cases remain a separate teaching holdout.

This deliberately small, templated corpus demonstrates the data pipeline and model training mechanics. It is not evidence of real-world generalization. Context substitutions within a family are correlated. Family metadata prevents that same generated template from crossing splits; it cannot prove semantic independence or remove all near-duplicates.

A human must review labels and examples before submitting a paid job. The CLI requires --data-reviewed and an actual measured baseline report matching the data hashes. Model-specific eligibility, minimums, quotas and quality requirements still apply. Add diverse independently authored examples and a larger sealed test set before making a production claim.

training-seed.jsonl is a legacy four-row format illustration. The prepare command consumes curated-tickets.jsonl instead and validates exact duplicates, family overlap, labels and holdout contamination.
