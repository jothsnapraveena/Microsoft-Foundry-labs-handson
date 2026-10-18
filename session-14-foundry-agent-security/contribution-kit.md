# Community Contribution Kit

## Suggested article title

Agent Security and Red Teaming in Microsoft Foundry: A Reproducible Experiment

## Session abstract

A fictional Cedar employee-policy assistant answers travel and expense questions from a bundled policy. It has no operational tools and cannot approve or pay expenses. In this hands-on session, participants investigate the question: can we reduce successful instruction overrides while preserving useful policy answers? The lesson separates Foundry hosting and inference from application responsibilities and uses synthetic fixtures, a controlled comparison and explicit evidence. Attendees leave with a repeatable method and an understanding of its limitations.

## Article structure

1. State the problem and why versioned Foundry prompt agents and controlled security testing are relevant.
2. Show the architecture and access requirements.
3. Explain the synthetic dataset, instructions and baseline.
4. Walk through the Microsoft capability with actual versioned evidence.
5. Publish the scorecard with sample counts, failures and cost assumptions.
6. Explain limitations, cleanup and a reproducible community challenge.

## Demonstration deliverables

- A repository link to this session's instructions and synthetic assets.
- A short recording of a healthy case and an edge case.
- A sanitized scorecard populated from actual runs.
- Official reference links, execution date and feature/preview status.
- A troubleshooting note about an observed issue, if any.

## Community challenge

Add four independently labeled edge cases to [the seed dataset](data/cases.jsonl), predict their outcomes, then compare actual behavior without changing labels after seeing responses. Share a sanitized failure analysis and propose one controlled improvement.

## Contribution record

Record the publication URL, presentation date, recording link, audience questions and substantive feedback. Keep these separate from technical quality measurements; publication volume does not establish Microsoft MVP eligibility.
