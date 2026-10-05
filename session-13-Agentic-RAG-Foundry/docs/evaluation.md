# Evaluation

## Three layers

| Layer | What it checks | Model involved | Command |
|---|---|---|---|
| Backend tests | Eligibility rules, ownership, confirmation, idempotency, concurrency | No | `python -m unittest discover -s tests` |
| Retrieval | Whether the labeled evidence is retrieved, and how highly ranked | Only the knowledge base's query planner | `python -m northstar.evals.retrieval --confirm` |
| Policy agent | Citations, abstention, and answer quality | Agent and a judge model | `python -m northstar.evals.policy_agent --confirm` |

Authorization and eligibility are verified by the first layer only. A model grader never decides whether those are correct.

## Policy agent run

The runner asks the agent each question in `northstar-dataset/evals/policy_qa.json`, saves every answer with its evidence, grades the answers, and publishes the run to the Foundry project.

```powershell
python -m northstar.evals.policy_agent                      # what a run would do; free
python -m northstar.evals.policy_agent --confirm --limit 5  # small sample
python -m northstar.evals.policy_agent --confirm            # development split (27 questions)
python -m northstar.evals.policy_agent --confirm --from-rows data/eval/<run>/rows.jsonl   # re-grade saved answers
```

`--no-judges` skips the model grades; `--no-publish` keeps the run local. Without `--confirm` nothing is called.

### Deterministic metrics

Computed here from the dataset's labels. Each is between 0 and 1.

| Metric | Meaning |
|---|---|
| `citation_valid` | The answer passed the citation check: nothing cited that was not retrieved, and a policy answer cites something |
| `abstention_correct` | The agent said "not covered" exactly when the question is labeled unanswerable |
| `retrieval_recall` | Share of the labeled evidence passages among those retrieved |
| `retrieval_mrr` | Reciprocal rank of the first labeled passage |
| `retrieval_ndcg` | Ranking quality of the labeled passages |
| `citation_precision` | Share of cited passages that are labeled evidence |
| `citation_recall` | Share of labeled evidence that the answer cited |

The last five are undefined for unanswerable questions and are left out of their averages.

Low `citation_precision` is not necessarily an error. The labels list the minimum evidence for an answer; an agent that also cites a correct, related passage scores lower. Read it together with groundedness.

### Model-graded metrics

From the Azure AI Evaluation SDK (`azure-ai-evaluation` 1.18.7), using its built-in prompts and rubrics. Each scores 1 to 5, with 3 as the SDK's default pass mark.

| Metric | Inputs | Question it answers |
|---|---|---|
| Groundedness | answer, retrieved evidence | Is the answer supported by the evidence? |
| Relevance | question, answer | Does the answer address the question? |
| Response completeness | answer, expected answer | Does it contain what the expected answer contains? |
| Similarity | question, answer, expected answer | How close is it to the expected answer? |
| Retrieval | question, retrieved evidence | Is the evidence useful for the question? |
| Coherence | question, answer | Is it clearly written? |

The judge is the deployment named by `EVALUATION_MODEL_DEPLOYMENT`, defaulting to the knowledge base's planning model. Each run's `report.json` records the judge, the agent model, the prompt version and the dataset.

A judge from the same model family as the agent can share its blind spots. Use a different family for the judge if one is available, and review a sample of graded answers by hand.

### Release gates

These must hold on every answer, whatever the quality scores are. The command exits with status 1 if any fails.

| Gate | Fails when |
|---|---|
| `no_citation_of_unretrieved_passage` | Any answer cites a passage that was not retrieved |
| `every_answer_verified` | Any answer fails the citation check |
| `abstains_when_policies_do_not_cover` | An unanswerable question gets a policy answer |

No thresholds are set on the quality scores. Set them after several baseline runs, not before.

## What is published to Foundry

The run is sent through the SDK's `evaluate()` with the project endpoint, and the command prints a link. In the Foundry portal it appears under **Evaluations**.

Published: the six model-graded metrics per question and in aggregate, and the seven deterministic metrics, which are passed through the run as a custom evaluator so they sit beside the model grades.

Not published: the backend tests and the retrieval-only run. Those produce local reports. A local JSON report does not appear in the portal on its own.

Each run also writes to `data/eval/<run>/`, which is git-ignored:

| File | Contents |
|---|---|
| `rows.jsonl` | Every question, answer, evidence, citation result and trace ID |
| `evaluation_result.json` | The SDK's per-row scores and judge reasoning |
| `report.json` | Summary, gates, models, prompt version, Foundry link |

## Results so far

Baseline on the 27 development questions, run once on 2026-10-05. Agent and judge were both `gpt-5-mini`, prompt version `policy-v3`, top 6 passages, low retrieval reasoning effort.

All three release gates passed.

| Deterministic metric | All | Single-topic (9) | Version-dependent (8) | Multi-topic (7) |
|---|---|---|---|---|
| Citation valid | 1.00 | 1.00 | 1.00 | 1.00 |
| Abstention correct | 1.00 | | | |
| Retrieval recall | 0.85 | 0.94 | 1.00 | 0.57 |
| Citation recall | 0.85 | 0.94 | 1.00 | 0.57 |
| Retrieval MRR | 0.89 | | | |
| Retrieval nDCG | 0.83 | | | |
| Citation precision | 0.56 | | | |

All three unanswerable questions were correctly answered as not covered.

| Model-graded metric | Mean (1 to 5) | Share scoring 3 or more |
|---|---|---|
| Groundedness | 4.15 | 0.78 |
| Relevance | 4.56 | 1.00 |
| Response completeness | 4.67 | 0.96 |
| Similarity | 4.82 | 0.96 |
| Retrieval | 4.28 | 0.81 |
| Coherence | 4.22 | 1.00 |

Latency per question was 13.8 s at the median and 32.2 s at the 95th percentile. The run used about 47,000 input and 32,000 output tokens for the agent, and 26,000 input tokens for retrieval planning.

Reading these:

- Version selection works: recall is 1.0 on the questions that depend on the order or event date.
- Multi-topic questions are the weak spot. Citation recall equals retrieval recall there, so the agent cites what it is given; the missing evidence was never retrieved. Raising the passage limit or the retrieval reasoning effort is the first thing to try.
- Groundedness passes on 78% of answers, lower than the other grades. Those answers have not been reviewed by hand, so it is not yet known whether the agent overstated the evidence or the judge was strict.
- One run on 27 author-written questions, judged by the same model family as the agent. Treat it as a first baseline, not a quality claim.

## Limits

- The question set has 33 items written by the dataset's author. Scores are a smoke test until human-reviewed questions are added.
- Expected answers and evidence labels come from the same author as the policies.
- The held-out split has not been run. Keep it out of prompts and tuning, and use it once per candidate, not repeatedly.
- No human has reviewed a sample of graded answers.
- The agent with order and return tools (stage 4) does not exist yet, so there is no workflow evaluation of tool use and side effects. The backend's side effects are covered by the tests.
