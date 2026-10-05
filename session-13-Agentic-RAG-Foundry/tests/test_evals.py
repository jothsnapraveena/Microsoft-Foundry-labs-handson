"""Evaluation metrics and gates, computed without any model or Azure call."""
import json
import math
import unittest

from fixtures import AS_OF, DATASET, TestClock
from northstar.agent.policy_agent import PolicyAgent
from northstar.evals.policy_agent import LabelChecks, collect, deterministic_metrics, summarize
from northstar.evals.retrieval import score
from test_policy_agent import FakeProject, RecordingRetriever, call, reply

QUESTIONS = {q["qa_id"]: q for q in json.loads((DATASET / "evals" / "policy_qa.json").read_text(encoding="utf-8"))}
ANSWERABLE = next(q for q in QUESTIONS.values() if q["type"] == "multi")
UNANSWERABLE = next(q for q in QUESTIONS.values() if not q["answerable"])


class RankingMetricTests(unittest.TestCase):
    def test_perfect_partial_and_missed_retrieval(self):
        self.assertEqual(score(["a", "b"], ["a", "b"], 6), {"recall": 1.0, "precision": 1.0, "hit": 1.0, "all_found": 1.0, "mrr": 1.0, "ndcg": 1.0})
        partial = score(["x", "a", "y"], ["a", "b"], 6)
        self.assertEqual((partial["recall"], partial["mrr"], partial["all_found"]), (0.5, 0.5, 0.0))
        self.assertAlmostEqual(partial["ndcg"], (1 / math.log2(3)) / (1 + 1 / math.log2(3)))
        self.assertEqual(score(["x", "y"], ["a"], 6)["mrr"], 0.0)
        self.assertEqual(score(["x", "a"], ["a"], 1)["recall"], 0.0)       # outside the cut-off


class DeterministicMetricTests(unittest.TestCase):
    def test_answerable_question(self):
        expected = ANSWERABLE["expected_chunk_ids"]
        metrics = deterministic_metrics(ANSWERABLE, expected + ["other"], [expected[0], "other"], [], True, False, 6)
        self.assertEqual((metrics["citation_valid"], metrics["abstention_correct"], metrics["retrieval_recall"]), (1.0, 1.0, 1.0))
        self.assertEqual(metrics["citation_precision"], 0.5)
        self.assertAlmostEqual(metrics["citation_recall"], 1 / len(expected))

    def test_wrong_abstention_and_invalid_citation_are_penalized(self):
        metrics = deterministic_metrics(ANSWERABLE, [], [], [], True, True, 6)
        self.assertEqual((metrics["abstention_correct"], metrics["citation_precision"], metrics["retrieval_recall"]), (0.0, 0.0, 0.0))
        metrics = deterministic_metrics(ANSWERABLE, [], ["made-up-v1-chunk-1"], ["made-up-v1-chunk-1"], False, False, 6)
        self.assertEqual(metrics["citation_valid"], 0.0)

    def test_unanswerable_question_scores_abstention_only(self):
        metrics = deterministic_metrics(UNANSWERABLE, ["a"], [], [], True, True, 6)
        self.assertEqual((metrics["abstention_correct"], metrics["retrieval_recall"], metrics["citation_recall"]), (1.0, None, None))
        self.assertEqual(deterministic_metrics(UNANSWERABLE, ["a"], ["a"], [], True, False, 6)["abstention_correct"], 0.0)

    def test_label_checks_pass_values_through_and_mark_undefined_as_nan(self):
        result = LabelChecks()(citation_valid=1, abstention_correct=0.0, retrieval_recall=None, citation_recall=0.5)
        self.assertEqual((result["citation_valid"], result["abstention_correct"], result["citation_recall"]), (1.0, 0.0, 0.5))
        self.assertTrue(math.isnan(result["retrieval_recall"]))


class CollectAndSummarizeTests(unittest.TestCase):
    def test_rows_summary_and_gates(self):
        good = "electronics-returns-v1-chunk-1"
        script = [reply(calls=[call({"question": "electronics return window days", "order_date": "2026-08-20"})]),
                  reply(f"You have 14 days [{good}]."),
                  reply(calls=[call({"question": "price match"})]),
                  reply("Yes, we match any price.")]                      # should have abstained, and cites nothing
        project = FakeProject(script)
        agent = PolicyAgent(project, RecordingRetriever(), "test-agent", "test-model", TestClock())
        version_question = next(q for q in QUESTIONS.values() if q["expected_chunk_ids"] == [good])
        rows = collect(agent, [version_question, UNANSWERABLE], AS_OF, progress=lambda line: None)
        self.assertEqual([row["citation_valid"] for row in rows], [1.0, 0.0])
        self.assertEqual((rows[0]["citation_recall"], rows[0]["citation_precision"]), (1.0, 1.0))
        self.assertEqual(rows[1]["abstention_correct"], 0.0)
        self.assertIn(good, rows[0]["context"])
        self.assertEqual(rows[0]["ground_truth"], version_question["expected_answer"])
        json.dumps(rows)
        summary = summarize(rows)
        self.assertEqual(summary["deterministic"]["citation_valid"], 0.5)
        self.assertEqual(summary["deterministic"]["citation_recall"], 1.0)      # undefined rows are left out of the mean
        self.assertEqual(summary["gates"], {"no_citation_of_unretrieved_passage": True, "every_answer_verified": False,
                                            "abstains_when_policies_do_not_cover": False})
        self.assertEqual(summary["tokens"]["agent_input_tokens"], 400)
        self.assertNotIn("estimated_cost_usd", summary)                         # no prices configured, so no estimate


if __name__ == "__main__":
    unittest.main()
