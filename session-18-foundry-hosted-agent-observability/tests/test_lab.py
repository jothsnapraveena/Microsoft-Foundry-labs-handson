import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
from assistant import LookupFailure, answer, get_checklist
from lab import main

class HostedTests(unittest.TestCase):
    def test_known_device(self):
        self.assertEqual(get_checklist("W-101")["checklist"][0], "Check power cable")

    def test_unknown_does_not_synthesize(self):
        with patch("builtins.print"):
            def fail(_):
                self.fail("Unknown device must not invoke model synthesis")
            self.assertEqual(answer("Get W-999", synthesize=fail)["status"], "unknown")

    def test_baseline_fault_is_real(self):
        with self.assertRaises(LookupFailure):
            answer("Get DEMO-FAIL", "v1")

    def test_recovery_still_reports_fault(self):
        result = answer("Get DEMO-FAIL", "v2")
        self.assertEqual(result["status"], "error")
        self.assertIn("could not", result["answer"])

    def test_healthy_call_after_failure(self):
        answer("Get DEMO-FAIL")
        self.assertEqual(answer("Get W-102")["status"], "ok")

    def test_model_receives_only_successful_lookup(self):
        received = []
        result = answer("Get W-101", synthesize=lambda facts: received.append(facts) or "draft")
        self.assertEqual(received[0]["device_id"], "W-101")
        self.assertEqual(result["answer"], "draft")

    def test_sdk_protocol_server_imports(self):
        import server
        self.assertTrue(callable(server.handle))
        self.assertTrue(hasattr(server.app, "run"))

    def test_guard(self):
        with patch("sys.argv", ["lab.py", "deploy"]), patch("lab.project") as factory:
            with self.assertRaises(SystemExit):
                main()
            factory.assert_not_called()

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_responses_http_contract(self):
        import httpx
        import server
        with patch.dict("os.environ", {"MODEL_BACKEND": "local"}):
            async with server.app.router.lifespan_context(server.app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
                    response = await client.post("/responses", json={"input": "Get W-101", "stream": False, "store": False})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertIn("Check power cable", response.text)


if __name__ == "__main__":
    unittest.main()
