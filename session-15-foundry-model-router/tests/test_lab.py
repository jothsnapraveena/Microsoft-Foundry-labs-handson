import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
from lab import benchmark, estimate_cost, summarize, main
from support import exact_json

class BenchmarkTests(unittest.TestCase):
    def test_boolean_does_not_match_number(self):
        self.assertFalse(exact_json('{"amount":true}', {"amount": 1}))

    def test_extra_fields_fail_contract(self):
        self.assertFalse(exact_json('{"category":"billing","extra":1}', {"category": "billing"}))

    def test_cost_unknown_without_verified_rates(self):
        self.assertIsNone(estimate_cost({"prompt_tokens": 5, "completion_tokens": 2}, "model", {}))

    def test_cached_tokens_use_their_own_price(self):
        rates = {"price_date": "2026-10-15", "models": {"x": {"verified_billing_match": True,
            "input_per_million": 10, "output_per_million": 20, "cached_input_per_million": 1}}}
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "prompt_tokens_details": {"cached_tokens": 50}}
        self.assertAlmostEqual(estimate_cost(usage, "x", rates), .00075)

    def test_errors_remain_visible_and_ungraded_explanations_are_not_passes(self):
        cases = [{"id": "a", "category": "classification", "input": "x", "expected": {"label": "a"}},
                 {"id": "b", "category": "explanation", "input": "y", "expected": "manual rubric"}]
        def response(client, deployment, instructions, prompt):
            if prompt == "x":
                raise TimeoutError()
            return {"answer": "looks good", "response_model": "m", "response_id": "r", "usage": None}
        with patch("lab.chat", side_effect=response):
            result = benchmark(object(), ["target"], cases, "instructions")
        summary = summarize(result)["target"]
        self.assertEqual(summary["attempted"], 2)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["graded"], 1)
        self.assertEqual(summary["pass_rate_graded"], 0)

    def test_alternating_target_order(self):
        cases = [{"id": "a", "category": "x", "input": "a", "expected": {}},
                 {"id": "b", "category": "x", "input": "b", "expected": {}}]
        with patch("lab.chat", return_value={"answer": "{}", "response_model": "m", "response_id": "r", "usage": None}):
            result = benchmark(object(), ["small", "router"], cases, "instructions")
        self.assertEqual([r["deployment"] for r in result], ["small", "router", "router", "small"])

    def test_guard(self):
        with patch("sys.argv", ["lab.py", "run"]), patch("lab.project") as factory:
            with self.assertRaises(SystemExit):
                main()
            factory.assert_not_called()

if __name__ == "__main__":
    unittest.main()
