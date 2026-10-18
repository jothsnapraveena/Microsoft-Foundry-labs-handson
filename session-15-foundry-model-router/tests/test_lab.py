import sys
from pathlib import Path
import json
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch, MagicMock
from lab import benchmark, estimate_cost, summarize, main
from support import exact_json, chat

class BenchmarkTests(unittest.TestCase):
    def test_responses_api_preserves_raw_usage_and_normalizes_cost_inputs(self):
        client = MagicMock()
        usage = MagicMock()
        raw = {"input_tokens": 20, "output_tokens": 5, "input_tokens_details": {"cached_tokens": 7}}
        usage.model_dump.return_value = raw
        client.responses.create.return_value = SimpleNamespace(status="completed", output_text="{}",
            id="resp-1", model="reported-model", usage=usage)
        result = chat(client, "deployment", "instructions", "input")
        self.assertEqual(result["usage"]["prompt_tokens"], 20)
        self.assertEqual(result["usage"]["completion_tokens"], 5)
        self.assertEqual(result["usage"]["prompt_tokens_details"]["cached_tokens"], 7)
        self.assertEqual(result["raw_usage"], raw)
        self.assertFalse(client.responses.create.call_args.kwargs["store"])
        client.responses.create.return_value.status = "incomplete"
        with self.assertRaisesRegex(RuntimeError, "did not complete"):
            chat(client, "deployment", "instructions", "input")

    def test_failed_cloud_run_checkpoints_one_run_id_and_exits_nonzero(self):
        @contextmanager
        def fake_project():
            yield MagicMock(), MagicMock()
        saved = []
        def capture(path, report):
            saved.append(json.loads(json.dumps(report)))
        settings = {"AZURE_AI_PROJECT_ENDPOINT": "https://example.test", "ROUTER_DEPLOYMENT": "router",
                    "FIXED_SMALL_DEPLOYMENT": "small", "FIXED_LARGE_DEPLOYMENT": "large"}
        with tempfile.TemporaryDirectory() as temp, patch("lab.project", fake_project), \
             patch("lab.required", side_effect=settings.__getitem__), patch("lab.chat", side_effect=TimeoutError()), \
             patch("lab.save", side_effect=capture), \
             patch("sys.argv", ["lab.py", "run", "--limit", "1", "--request-interval", "0",
                                "--report", str(Path(temp)/"benchmark.json"), "--confirm"]):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(len({r["run_id"] for r in saved}), 1)
        self.assertEqual(saved[0]["execution_status"], "running")
        self.assertEqual(saved[-1]["execution_status"], "error")
        self.assertEqual(len(saved[-1]["results"]), 3)

    def test_request_pacing_keeps_error_identity_and_checkpoints(self):
        error = RuntimeError()
        error.code, error.status_code = "rate_limit_exceeded", 429
        cases = [{"id": "a", "category": "classification", "input": "x", "expected": {}}]
        checkpoints = []
        with patch("lab.chat", side_effect=error), patch("lab.sleep") as pause:
            result = benchmark(object(), ["small", "router"], cases, "instructions", request_interval=7,
                               checkpoint=lambda results: checkpoints.append(len(results)))
        pause.assert_called_once_with(7)
        self.assertEqual(checkpoints, [1, 2])
        self.assertEqual(result[0]["http_status"], 429)
        self.assertEqual(result[0]["error_code"], "rate_limit_exceeded")

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
