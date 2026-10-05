"""Date-constrained policy retrieval.

The knowledge base ranks; it does not know which policy version applies. Fifteen topics
have identical text in both versions, so the version is selected here: by an OData filter
on the request, and again by checking every returned reference against the local catalog.
A prompt instruction would guarantee neither.
"""
from dataclasses import asdict, dataclass, field
from datetime import date
import re

EFFORTS = ("minimal", "low", "medium")


@dataclass(frozen=True)
class Evidence:
    chunk_id: str               # stable citation id
    policy_id: str
    topic: str
    version: str
    section: str
    title: str
    text: str                   # from the local source document, not from the index
    effective_from: str
    effective_to: str | None
    source_path: str
    reranker_score: float | None = None


@dataclass
class RetrievalResult:
    backend: str
    question: str
    order_date: str
    event_date: str
    filter: str
    evidence: list = field(default_factory=list)
    rejected: list = field(default_factory=list)       # returned by the service but failed validation
    sub_queries: list = field(default_factory=list)
    activity: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed_ms: int = 0

    def to_dict(self):
        return asdict(self)


def applicable_date(chunk, order_date, event_date):
    return order_date if chunk.applies_by == "order_date" else event_date


def build_filter(order_date, event_date, region):
    """Each policy must be in effect on the date its applies_by rule names. End dates are exclusive."""
    def window(applies_by, on):
        stamp = f"{on}T00:00:00Z"
        return f"(applies_by eq '{applies_by}' and effective_from le {stamp} and effective_to gt {stamp})"
    if not re.fullmatch(r"[A-Za-z]{2,10}", region):
        raise ValueError("invalid region")
    return f"region eq '{region}' and ({window('order_date', order_date)} or {window('event_date', event_date)})"


def validate_references(references, catalog, order_date, event_date, region):
    """Keep references that exist locally, are in effect, and whose indexed text matches the source."""
    evidence, rejected, seen = [], [], set()
    for reference in references:
        chunk_id = reference.get("doc_key")
        chunk = catalog.get(chunk_id)
        if chunk is None:
            reason = "not_in_catalog"
        elif chunk_id in seen:
            continue
        elif chunk.region != region:
            reason = "wrong_region"
        elif not chunk.in_effect(applicable_date(chunk, order_date, event_date)):
            reason = "not_in_effect"
        elif reference.get("text") is not None and reference["text"].strip() != chunk.text.strip():
            reason = "index_text_differs_from_source"      # the index is stale; re-run ingestion
        else:
            seen.add(chunk_id)
            evidence.append(Evidence(chunk.id, chunk.policy_id, chunk.topic, chunk.version, chunk.section, chunk.title,
                                     chunk.text, str(chunk.effective_from), str(chunk.effective_to) if chunk.effective_to else None,
                                     chunk.source_path, reference.get("reranker_score")))
            continue
        rejected.append({"chunk_id": chunk_id, "reason": reason})
    return evidence, rejected


def pick(record, *names):
    """Read a field that may be snake_case or camelCase depending on the SDK serializer."""
    for name in names:
        if isinstance(record, dict) and record.get(name) is not None:
            return record[name]
    return None


class KnowledgeBaseRetriever:
    """Azure AI Search agentic retrieval through the knowledge base, with the date filter applied."""
    backend = "azure-ai-search-knowledge-base"

    def __init__(self, client, knowledge_source_name, catalog, region="US", effort="low", top=6):
        if effort not in EFFORTS:
            raise ValueError(f"effort must be one of {EFFORTS}")
        self.client, self.knowledge_source_name = client, knowledge_source_name
        self.catalog, self.region, self.effort, self.top = {chunk.id: chunk for chunk in catalog}, region, effort, top

    def retrieve(self, question, order_date=None, event_date=None, effort=None, top=None):
        event_date = event_date or date.today()
        order_date = order_date or event_date
        effort = effort or self.effort
        odata = build_filter(order_date, event_date, self.region)
        request = {"knowledgeSourceParams": [{"knowledgeSourceName": self.knowledge_source_name, "kind": "searchIndex",
                                              "filterAddOn": odata, "includeReferences": True,
                                              "includeReferenceSourceData": True, "alwaysQuerySource": True}],
                   "includeActivity": True, "outputMode": "extractiveData",
                   "retrievalReasoningEffort": {"kind": effort}}
        if effort == "minimal":
            # Minimal effort skips model query planning and takes the search text directly.
            request["intents"] = [{"type": "semantic", "search": question}]
        else:
            request["messages"] = [{"role": "user", "content": [{"type": "text", "text": question}]}]
        response = self.client.retrieve(request)
        payload = response.as_dict() if hasattr(response, "as_dict") else response
        references = []
        for reference in payload.get("references") or []:
            source = pick(reference, "source_data", "sourceData") or {}
            references.append({"doc_key": pick(reference, "doc_key", "docKey") or source.get("id"),
                               "text": source.get("page_chunk"),
                               "reranker_score": pick(reference, "reranker_score", "rerankerScore")})
        evidence, rejected = validate_references(references, self.catalog, order_date, event_date, self.region)
        # The service returns every candidate; keep the best-ranked ones so weak matches do not dilute the answer.
        evidence.sort(key=lambda item: -(item.reranker_score or 0))
        evidence = evidence[:top or self.top]
        result = RetrievalResult(self.backend, question, str(order_date), str(event_date), odata, evidence, rejected)
        for record in payload.get("activity") or []:
            result.activity.append(record)
            result.input_tokens += pick(record, "input_tokens", "inputTokens") or 0
            result.output_tokens += pick(record, "output_tokens", "outputTokens") or 0
            result.elapsed_ms += pick(record, "elapsed_ms", "elapsedMs") or 0
            arguments = pick(record, "search_index_arguments", "searchIndexArguments") or {}
            if arguments.get("search"):
                result.sub_queries.append(arguments["search"])
        return result


class LocalKeywordRetriever:
    """LOCAL FALLBACK, NOT AZURE AI SEARCH. Plain keyword overlap over the catalog.

    For running the application without cloud configuration. It applies the same date rule,
    but its ranking says nothing about how the real knowledge base behaves.
    """
    backend = "local-keyword-fallback"

    def __init__(self, catalog, region="US", top=5):
        self.catalog, self.region, self.top = list(catalog), region, top

    def retrieve(self, question, order_date=None, event_date=None, effort=None, top=None):
        event_date = event_date or date.today()
        order_date = order_date or event_date
        words = set(re.findall(r"[a-z0-9]+", question.lower()))
        scored = []
        for chunk in self.catalog:
            if chunk.region == self.region and chunk.in_effect(applicable_date(chunk, order_date, event_date)):
                overlap = len(words & set(re.findall(r"[a-z0-9]+", f"{chunk.title} {chunk.section} {chunk.text}".lower())))
                if overlap:
                    scored.append((overlap, chunk.id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        references = [{"doc_key": chunk_id, "text": None, "reranker_score": None} for _, chunk_id in scored[:top or self.top]]
        evidence, rejected = validate_references(references, {c.id: c for c in self.catalog}, order_date, event_date, self.region)
        return RetrievalResult(self.backend, question, str(order_date), str(event_date),
                               build_filter(order_date, event_date, self.region), evidence, rejected, sub_queries=[question])


# Models sometimes write citations in the lenticular brackets used by other products; accept both.
CITATION = re.compile(r"[\[【]([a-z0-9-]+-v\d+-chunk-\d+)[\]】]")


def normalize_citations(answer):
    """Rewrite every citation as [id] so the customer sees one style."""
    return CITATION.sub(lambda match: f"[{match.group(1)}]", answer)


def check_citations(answer, evidence):
    """Citations must name evidence retrieved for this answer. Returns (cited ids, ids that were not retrieved)."""
    allowed = {item.chunk_id for item in evidence}
    cited = list(dict.fromkeys(CITATION.findall(answer)))
    return cited, [chunk_id for chunk_id in cited if chunk_id not in allowed]
