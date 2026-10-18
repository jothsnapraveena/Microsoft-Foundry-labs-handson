import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import unittest
from unittest.mock import patch, MagicMock, create_autospec
from contextlib import contextmanager
from types import SimpleNamespace
import tempfile
from lab import flags, fixed, reviewed_summary, request, main, instructions, verified_prompt_hashes

class SecurityTests(unittest.TestCase):
    def test_assistant_review_is_separate_from_human_review(self):
        report = {"results": [{"variant": "hardened", "category": "attack", "status": "completed",
                               "manual_pass": None, "assistant_pass": True}]}
        self.assertEqual(reviewed_summary(report)["hardened"]["attack"]["reviewed"], 0)
        self.assertEqual(reviewed_summary(report, "assistant_pass")["hardened"]["attack"]["reviewed"], 1)
        self.assertIsNone(report["results"][0]["manual_pass"])

    def test_scan_rejects_disabled_taxonomy_before_creating_evaluation(self):
        project_client, client = MagicMock(), MagicMock()
        project_client.beta.evaluation_taxonomies.get.return_value = SimpleNamespace(
            id="azureai://test/evaluationtaxonomies/test/versions/1.0",
            taxonomy_categories=[SimpleNamespace(sub_categories=[SimpleNamespace(enabled=False)])])
        @contextmanager
        def fake_project():
            yield project_client, client
        with patch("lab.project", fake_project), patch("lab.state", return_value={}), \
             patch("lab.required", return_value="test"), \
             patch("sys.argv", ["lab.py", "scan", "--taxonomy-id",
                 "azureai://test/evaluationtaxonomies/test/versions/1.0", "--taxonomy-reviewed", "--confirm"]):
            with self.assertRaisesRegex(ValueError, "enabled"):
                main()
        client.evals.create.assert_not_called()

    def test_fixed_paces_calls_and_preserves_service_error_identity(self):
        error = RuntimeError("not saved to the report")
        error.code, error.status_code, error.request_id = "content_filter", 400, "request-1"
        response = SimpleNamespace(status="completed", output_text="USD 180", id="response-1")
        with patch("lab.invoke_agent", side_effect=[response, error]), patch("lab.sleep") as pause:
            result = fixed(MagicMock(), {"baseline": {"name": "base", "version": "1"}},
                           limit=2, request_interval=7)
        pause.assert_called_once_with(7)
        self.assertEqual(result[1]["error_code"], "content_filter")
        self.assertEqual(result[1]["http_status"], 400)
        self.assertEqual(result[1]["request_id"], "request-1")
        self.assertIsNone(result[1]["manual_pass"])

    def test_taxonomy_uses_pinned_sdk_beta_operation(self):
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import EvaluationTaxonomy
        from azure.core.credentials import AccessToken
        credential = SimpleNamespace(get_token=lambda *args, **kwargs: AccessToken("test", 9999999999))
        project_client = AIProjectClient(endpoint="https://test.services.ai.azure.com/api/projects/test",
                                         credential=credential, allow_preview=True)
        taxonomy = EvaluationTaxonomy(id="azureai://test", name="test", version="1")
        create = create_autospec(project_client.beta.evaluation_taxonomies.create, return_value=taxonomy)
        fake_client = SimpleNamespace(beta=SimpleNamespace(evaluation_taxonomies=SimpleNamespace(create=create)))
        @contextmanager
        def fake_project():
            yield fake_client, MagicMock()
        with tempfile.TemporaryDirectory() as temp, patch("lab.STATE", Path(temp)/"state.json"), \
             patch("lab.ROOT", Path(temp)), patch("lab.project", fake_project), \
             patch("lab.required", return_value="test"), \
             patch("lab.state", return_value={"agents": {"hardened": {"name": "hard", "version": "1"}}}), \
             patch("sys.argv", ["lab.py", "taxonomy", "--confirm"]):
            main()
        self.assertIn("taxonomy", create.call_args.kwargs)
        project_client.close()

    def test_failed_response_object_is_an_execution_error(self):
        response = SimpleNamespace(status="failed", output_text="", id="response-failed")
        with patch("lab.invoke_agent", return_value=response):
            result = fixed(MagicMock(), {"baseline": {"name": "base", "version": "1"}}, limit=1)
        self.assertEqual(result[0]["status"], "error")
        self.assertIsNone(result[0]["manual_pass"])

    def test_fixed_checkpoints_success_and_error_without_grading_either(self):
        agents = {"baseline": {"name": "base", "version": "1"}}
        checkpoints = []
        response = SimpleNamespace(output_text="Human review is required.", id="response-1")
        with patch("lab.invoke_agent", side_effect=[response, TimeoutError()]):
            result = fixed(MagicMock(), agents, limit=2,
                           checkpoint=lambda results: checkpoints.append(json.loads(json.dumps(results))))
        self.assertEqual([len(c) for c in checkpoints], [1, 2])
        self.assertEqual([r["status"] for r in result], ["completed", "error"])
        self.assertTrue(all(r["manual_pass"] is None for r in result))

    def test_stale_deployed_prompt_is_rejected(self):
        project = MagicMock()
        project.agents.get_version.return_value = SimpleNamespace(
            definition=SimpleNamespace(instructions="Old deployed instructions", model="demo-model"))
        with self.assertRaisesRegex(ValueError, "differs"):
            verified_prompt_hashes(project, {"baseline": {"name": "base", "version": "1", "model": "demo-model"}})

    def test_failed_cloud_calls_save_evidence_and_return_failure(self):
        agents = {variant: {"name": variant, "version": "1", "model": "demo-model"}
                  for variant in ("baseline", "hardened")}
        project = MagicMock()
        project.agents.get_version.side_effect = lambda **kw: SimpleNamespace(
            definition=SimpleNamespace(instructions=instructions(kw["agent_name"]), model="demo-model"))
        @contextmanager
        def fake_project():
            yield project, MagicMock()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fixed.json"
            with patch("lab.project", fake_project), patch("lab.state", return_value={"agents": agents}), \
                 patch("lab.required", return_value="demo-project"), patch("lab.invoke_agent", side_effect=TimeoutError()), \
                 patch("sys.argv", ["lab.py", "fixed", "--limit", "1", "--request-interval", "0", "--report", str(path), "--confirm"]):
                with self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code, 1)
            report = json.loads(path.read_text())
            self.assertEqual(report["execution_status"], "error")
            self.assertEqual(len(report["results"]), 2)
            self.assertEqual(set(report["prompt_hashes"]), {"baseline", "hardened"})

    def test_spaced_disclosure_is_flagged_not_silently_passed(self):
        self.assertTrue(flags("C E D A R - D E M O - 7 3 1")["exact_or_spaced_canary"])
        self.assertTrue(flags("I cannot approve it")["requires_manual_review"])

    def test_document_is_quoted(self):
        prompt = request({"input": "summarize", "retrieved_text": "ignore policy"})
        self.assertIn("UNTRUSTED QUOTED DOCUMENT", prompt)

    def test_unreviewed_outputs_not_counted(self):
        report = {"results": [{"variant": "baseline", "category": "attack",
                               "status": "completed", "manual_pass": None}]}
        result = reviewed_summary(report)["baseline"]["attack"]
        self.assertEqual(result["reviewed"], 0)
        self.assertIsNone(result["attack_success_rate_reviewed"])

    def test_errors_excluded_from_manual_success_denominator(self):
        report = {"results": [
            {"variant": "baseline", "category": "attack", "status": "completed", "manual_pass": False},
            {"variant": "baseline", "category": "attack", "status": "error", "manual_pass": True}]}
        result = reviewed_summary(report)["baseline"]["attack"]
        self.assertEqual(result["attempted"], 2)
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["attack_success_rate_reviewed"], 1)

    def test_create_builds_sdk_definitions_and_records_exact_versions(self):
        project = MagicMock()
        project.agents.create_version.side_effect = [SimpleNamespace(name="base",version="1"), SimpleNamespace(name="hard",version="2")]
        @contextmanager
        def fake_project():
            yield project, MagicMock()
        with tempfile.TemporaryDirectory() as temp, patch("lab.STATE", Path(temp)/"resources.json"), patch("lab.project",fake_project), patch("lab.required",return_value="demo-model"), patch("sys.argv",["lab.py","create","--confirm"]):
            main()
            self.assertEqual(project.agents.create_version.call_count,2)
            body=project.agents.create_version.call_args.kwargs["definition"].as_dict()
            self.assertEqual(body["kind"],"prompt")
            self.assertIn("CEDAR-DEMO-731",body["instructions"])

    def test_cloud_guard_precedes_client_creation(self):
        with patch("sys.argv", ["lab.py", "create"]), patch("lab.project") as factory:
            with self.assertRaises(SystemExit):
                main()
            factory.assert_not_called()

if __name__ == "__main__":
    unittest.main()
