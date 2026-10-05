"""Catalog, ingestion planning and date-constrained retrieval. No Azure calls."""
from dataclasses import replace
from datetime import date
import json
import unittest

from fixtures import AS_OF, DATASET
from northstar.rag.azure import plan_ingestion
from northstar.rag.catalog import OPEN_ENDED, load_chunks
from northstar.rag.retrieval import (KnowledgeBaseRetriever, LocalKeywordRetriever, build_filter, check_citations,
                                     validate_references)

CHUNKS, PROBLEMS = load_chunks(DATASET)
CATALOG = {chunk.id: chunk for chunk in CHUNKS}
QUESTIONS = json.loads((DATASET / "evals" / "policy_qa.json").read_text(encoding="utf-8"))
V1_DAY, V2_DAY, BOUNDARY = date(2026, 8, 20), date(2026, 9, 20), date(2026, 9, 15)
MODEL = "text-embedding-3-small"


class FakeKnowledgeBase:
    """Returns whatever references it is given, like a service that ignored the filter."""
    def __init__(self, references, activity=()):
        self.references, self.activity, self.requests = references, list(activity), []

    def retrieve(self, request):
        self.requests.append(request)
        return {"references": self.references, "activity": self.activity}


def reference(chunk_id, text=None, score=3.0):
    return {"type": "searchIndex", "id": "0", "docKey": chunk_id, "rerankerScore": score,
            "sourceData": {"id": chunk_id, "page_chunk": CATALOG[chunk_id].text if text is None and chunk_id in CATALOG else text}}


class CatalogTests(unittest.TestCase):
    def test_dataset_chunks_are_valid(self):
        self.assertEqual(PROBLEMS, [])
        self.assertEqual(len(CHUNKS), 120)

    def test_document_shape_and_open_ended_date(self):
        v1 = CATALOG["electronics-returns-v1-chunk-1"].to_document(MODEL)
        v2 = CATALOG["electronics-returns-v2-chunk-1"].to_document(MODEL)
        self.assertEqual((v1["effective_from"], v1["effective_to"]), ("2026-01-01T00:00:00Z", "2026-09-15T00:00:00Z"))
        self.assertEqual(v2["effective_to"], OPEN_ENDED)
        self.assertEqual(v1["page_chunk"], CATALOG["electronics-returns-v1-chunk-1"].text)

    def test_interval_includes_start_and_excludes_end(self):
        v1, v2 = CATALOG["electronics-returns-v1-chunk-1"], CATALOG["electronics-returns-v2-chunk-1"]
        self.assertTrue(v1.in_effect(date(2026, 9, 14)))
        self.assertFalse(v1.in_effect(BOUNDARY))
        self.assertTrue(v2.in_effect(BOUNDARY))
        self.assertFalse(v2.in_effect(date(2026, 9, 14)))


class IngestionPlanTests(unittest.TestCase):
    def test_first_run_uploads_everything(self):
        plan = plan_ingestion(CHUNKS, {}, MODEL)
        self.assertEqual((len(plan.upload), len(plan.unchanged), plan.delete), (120, 0, []))

    def test_rerun_with_no_changes_uploads_nothing(self):
        plan = plan_ingestion(CHUNKS, {c.id: c.content_hash(MODEL) for c in CHUNKS}, MODEL)
        self.assertEqual((len(plan.upload), len(plan.unchanged), plan.delete), (0, 120, []))

    def test_changed_text_metadata_or_model_is_reuploaded_and_stale_ids_deleted(self):
        stored = {c.id: c.content_hash(MODEL) for c in CHUNKS}
        stored["removed-policy-v1-chunk-1"] = "old"
        changed = [replace(c, text=c.text + " Updated.") if c.id == "warranty-v2-chunk-1" else
                   replace(c, effective_to=date(2026, 12, 1)) if c.id == "cancellation-v2-chunk-1" else c for c in CHUNKS]
        plan = plan_ingestion(changed, stored, MODEL)
        self.assertEqual(sorted(c.id for c in plan.upload), ["cancellation-v2-chunk-1", "warranty-v2-chunk-1"])
        self.assertEqual(plan.delete, ["removed-policy-v1-chunk-1"])
        self.assertEqual(len(plan_ingestion(CHUNKS, stored, "text-embedding-3-large").upload), 120)


class FilterTests(unittest.TestCase):
    def test_filter_applies_each_date_to_its_own_policies(self):
        self.assertEqual(build_filter(V1_DAY, AS_OF, "US"),
                         "region eq 'US' and ((applies_by eq 'order_date' and effective_from le 2026-08-20T00:00:00Z and "
                         "effective_to gt 2026-08-20T00:00:00Z) or (applies_by eq 'event_date' and effective_from le "
                         "2026-10-03T00:00:00Z and effective_to gt 2026-10-03T00:00:00Z))")

    def test_region_cannot_inject_filter_syntax(self):
        with self.assertRaises(ValueError):
            build_filter(V1_DAY, AS_OF, "US' or region ne '")


class EvidenceValidationTests(unittest.TestCase):
    def validate(self, *ids, order=V1_DAY, event=AS_OF, **overrides):
        references = [{"doc_key": i, "text": None, "reranker_score": 1.0, **overrides} for i in ids]
        return validate_references(references, CATALOG, order, event, "US")

    def test_only_the_version_for_the_order_date_survives(self):
        evidence, rejected = self.validate("electronics-returns-v1-chunk-1", "electronics-returns-v2-chunk-1")
        self.assertEqual([e.chunk_id for e in evidence], ["electronics-returns-v1-chunk-1"])
        self.assertEqual(rejected, [{"chunk_id": "electronics-returns-v2-chunk-1", "reason": "not_in_effect"}])
        evidence, _ = self.validate("electronics-returns-v1-chunk-1", "electronics-returns-v2-chunk-1", order=V2_DAY)
        self.assertEqual([e.chunk_id for e in evidence], ["electronics-returns-v2-chunk-1"])

    def test_operational_policy_follows_the_event_date_not_the_order_date(self):
        evidence, rejected = self.validate("refund-timing-v1-chunk-2", "refund-timing-v2-chunk-2", order=V1_DAY, event=AS_OF)
        self.assertEqual([e.chunk_id for e in evidence], ["refund-timing-v2-chunk-2"])
        evidence, _ = self.validate("refund-timing-v1-chunk-2", "refund-timing-v2-chunk-2", order=V1_DAY, event=V1_DAY)
        self.assertEqual([e.chunk_id for e in evidence], ["refund-timing-v1-chunk-2"])

    def test_unknown_stale_and_duplicate_references(self):
        evidence, rejected = self.validate("made-up-v1-chunk-1")
        self.assertEqual((evidence, rejected[0]["reason"]), ([], "not_in_catalog"))
        evidence, rejected = self.validate("warranty-v1-chunk-1", text="Replacement guaranteed within 2 days.")
        self.assertEqual((evidence, rejected[0]["reason"]), ([], "index_text_differs_from_source"))
        evidence, rejected = self.validate("warranty-v1-chunk-1", "warranty-v1-chunk-1")
        self.assertEqual((len(evidence), rejected), (1, []))

    def test_evidence_text_comes_from_the_local_source(self):
        evidence, _ = self.validate("warranty-v1-chunk-1")
        self.assertEqual(evidence[0].text, CATALOG["warranty-v1-chunk-1"].text)
        self.assertEqual(evidence[0].source_path, "knowledge/warranty-v1.md")


class KnowledgeBaseRetrieverTests(unittest.TestCase):
    def test_request_carries_the_filter_and_wrong_version_is_dropped_anyway(self):
        service = FakeKnowledgeBase(
            [reference("electronics-returns-v2-chunk-1"), reference("electronics-returns-v1-chunk-1", score=2.5)],
            [{"type": "modelQueryPlanning", "inputTokens": 900, "outputTokens": 40, "elapsedMs": 700},
             {"type": "searchIndex", "elapsedMs": 120, "searchIndexArguments": {"search": "electronics return window"}}])
        result = KnowledgeBaseRetriever(service, "ks", CHUNKS).retrieve("How long to return headphones?", V1_DAY, AS_OF)
        params = service.requests[0]["knowledgeSourceParams"][0]
        self.assertEqual(params["filterAddOn"], build_filter(V1_DAY, AS_OF, "US"))
        self.assertEqual((params["knowledgeSourceName"], params["includeReferences"]), ("ks", True))
        self.assertEqual(service.requests[0]["outputMode"], "extractiveData")
        self.assertIn("messages", service.requests[0])
        self.assertEqual([e.chunk_id for e in result.evidence], ["electronics-returns-v1-chunk-1"])
        self.assertEqual(result.rejected[0]["reason"], "not_in_effect")
        self.assertEqual((result.input_tokens, result.output_tokens, result.elapsed_ms), (900, 40, 820))
        self.assertEqual(result.sub_queries, ["electronics return window"])

    def test_minimal_effort_sends_intents_and_dates_default_to_today(self):
        service = FakeKnowledgeBase([])
        result = KnowledgeBaseRetriever(service, "ks", CHUNKS, effort="minimal").retrieve("cancel order")
        self.assertEqual(service.requests[0]["intents"], [{"type": "semantic", "search": "cancel order"}])
        self.assertNotIn("messages", service.requests[0])
        self.assertEqual(result.order_date, str(date.today()))
        with self.assertRaises(ValueError):
            KnowledgeBaseRetriever(service, "ks", CHUNKS, effort="extreme")


class LocalFallbackTests(unittest.TestCase):
    def test_fallback_is_labeled_and_only_returns_policies_in_effect(self):
        retriever = LocalKeywordRetriever(CHUNKS)
        self.assertEqual(retriever.backend, "local-keyword-fallback")
        for question in QUESTIONS:
            reference_date = date.fromisoformat(question["reference_date"])
            order = reference_date if question["date_field"] == "order_date" else AS_OF
            event = reference_date if question["date_field"] == "event_date" else AS_OF
            for item in retriever.retrieve(question["question"], order, event).evidence:
                chunk = CATALOG[item.chunk_id]
                self.assertTrue(chunk.in_effect(order if chunk.applies_by == "order_date" else event), item.chunk_id)

    def test_expected_evidence_is_always_reachable_under_the_date_rule(self):
        """The question set and the retrieval date rule must agree, or no retriever could score well."""
        for question in QUESTIONS:
            reference_date = date.fromisoformat(question["reference_date"])
            order = reference_date if question["date_field"] == "order_date" else AS_OF
            event = reference_date if question["date_field"] == "event_date" else AS_OF
            references = [{"doc_key": i, "text": None, "reranker_score": None} for i in question["expected_chunk_ids"]]
            evidence, rejected = validate_references(references, CATALOG, order, event, "US")
            self.assertEqual(rejected, [], question["qa_id"])


class CitationTests(unittest.TestCase):
    def test_citations_must_come_from_the_retrieved_evidence(self):
        evidence, _ = validate_references([{"doc_key": "warranty-v2-chunk-1", "text": None}], CATALOG, V2_DAY, AS_OF, "US")
        answer = "It goes to warranty review [warranty-v2-chunk-1], and a replacement is guaranteed [warranty-v2-chunk-9]."
        self.assertEqual(check_citations(answer, evidence), (["warranty-v2-chunk-1", "warranty-v2-chunk-9"], ["warranty-v2-chunk-9"]))
        self.assertEqual(check_citations("No citations here.", evidence), ([], []))


if __name__ == "__main__":
    unittest.main()
