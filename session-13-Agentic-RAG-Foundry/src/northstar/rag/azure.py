"""Azure AI Search objects: index, documents, knowledge source and knowledge base.

Uses azure-search-documents 12.1.0b2 and REST API 2026-08-01-preview. The knowledge
source, knowledge base and per-request filter are PREVIEW features: no service-level
agreement, and their shape may change.
"""
from dataclasses import dataclass, field
import json
import time
import urllib.error
import urllib.request

from .catalog import load_chunks

VECTOR_FIELD, VECTOR_PROFILE, VECTORIZER, SEMANTIC_CONFIG = "page_embedding", "policy-hnsw", "policy-vectorizer", "policy-semantic"
MODEL_SCOPE = "https://cognitiveservices.azure.com/.default"
SOURCE_DATA_FIELDS = ("id", "policy_id", "topic", "version", "section", "title", "page_chunk", "effective_from",
                      "effective_to", "region", "applies_by", "source_path")


class Embedder:
    """Document embeddings from the Azure OpenAI deployment. Query-time vectorization does not cover uploads."""
    def __init__(self, endpoint, deployment, credential, batch_size=64, retries=5):
        self.url, self.deployment, self.credential = f"{endpoint}/openai/v1/embeddings", deployment, credential
        self.batch_size, self.retries = batch_size, retries

    def embed(self, texts):
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._batch(texts[start:start + self.batch_size]))
        return vectors

    def _batch(self, texts):
        body = json.dumps({"model": self.deployment, "input": texts}).encode("utf-8")
        for attempt in range(self.retries):
            request = urllib.request.Request(self.url, data=body, headers={
                "Authorization": f"Bearer {self.credential.get_token(MODEL_SCOPE).token}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = sorted(json.load(response)["data"], key=lambda item: item["index"])
                    return [item["embedding"] for item in data]
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == self.retries - 1:
                    raise RuntimeError(f"Embedding request failed with HTTP {error.code}: {error.read()[:200]!r}") from error
                time.sleep(min(2 ** attempt, 30))       # throttled or transient: back off and retry
        raise RuntimeError("Embedding request failed")


@dataclass
class IngestionPlan:
    upload: list = field(default_factory=list)       # new or changed chunks
    unchanged: list = field(default_factory=list)
    delete: list = field(default_factory=list)       # in the index but no longer in the dataset

    def summary(self):
        return f"{len(self.upload)} to embed and upload, {len(self.unchanged)} unchanged, {len(self.delete)} stale to delete"


def plan_ingestion(chunks, existing_hashes, embedding_model):
    """Compare the dataset with what the index holds. existing_hashes maps chunk id to its stored content hash."""
    plan = IngestionPlan()
    for chunk in chunks:
        (plan.unchanged if existing_hashes.get(chunk.id) == chunk.content_hash(embedding_model) else plan.upload).append(chunk)
    current = {chunk.id for chunk in chunks}
    plan.delete = sorted(chunk_id for chunk_id in existing_hashes if chunk_id not in current)
    return plan


def build_index(settings, dimensions):
    from azure.search.documents.indexes.models import (
        AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters, HnswAlgorithmConfiguration, SearchField, SearchIndex,
        SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch, VectorSearch, VectorSearchProfile)

    def text(name, **options):
        return SearchField(name=name, type="Edm.String", **options)

    fields = [
        text("id", key=True, filterable=True),
        text("policy_id", filterable=True, facetable=True),
        text("topic", filterable=True, facetable=True, searchable=True),
        text("version", filterable=True, facetable=True),
        text("section", searchable=True),
        text("title", searchable=True),
        text("page_chunk", searchable=True),
        SearchField(name="page_number", type="Edm.Int32", filterable=True, sortable=True),
        SearchField(name="effective_from", type="Edm.DateTimeOffset", filterable=True, sortable=True),
        SearchField(name="effective_to", type="Edm.DateTimeOffset", filterable=True, sortable=True),
        text("region", filterable=True, facetable=True),
        text("applies_by", filterable=True),
        text("source_path"),
        text("content_hash", filterable=True),
        SearchField(name=VECTOR_FIELD, type="Collection(Edm.Single)", searchable=True, stored=False,
                    vector_search_dimensions=dimensions, vector_search_profile_name=VECTOR_PROFILE),
    ]
    return SearchIndex(
        name=settings.index_name, fields=fields,
        vector_search=VectorSearch(
            profiles=[VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name="hnsw", vectorizer_name=VECTORIZER)],
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            # No key: the search service's managed identity calls the embedding deployment at query time.
            vectorizers=[AzureOpenAIVectorizer(vectorizer_name=VECTORIZER, parameters=AzureOpenAIVectorizerParameters(
                resource_url=settings.openai_endpoint, deployment_name=settings.embedding_deployment,
                model_name=settings.embedding_model))]),
        semantic_search=SemanticSearch(default_configuration_name=SEMANTIC_CONFIG, configurations=[SemanticConfiguration(
            name=SEMANTIC_CONFIG, prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"), content_fields=[SemanticField(field_name="page_chunk")],
                keywords_fields=[SemanticField(field_name="topic"), SemanticField(field_name="section")]))]))


class SearchProvisioner:
    """Creates, fills and removes the search objects. Every method is safe to run again."""
    def __init__(self, settings, credential, dataset_dir):
        from azure.search.documents import SearchClient
        from azure.search.documents.indexes import SearchIndexClient
        self.settings, self.credential, self.dataset_dir = settings, credential, dataset_dir
        self.index_client = SearchIndexClient(endpoint=settings.search_endpoint, credential=credential)
        self.search_client = SearchClient(endpoint=settings.search_endpoint, index_name=settings.index_name, credential=credential)
        self.embedder = Embedder(settings.openai_endpoint, settings.embedding_deployment, credential)

    def chunks(self):
        chunks, problems = load_chunks(self.dataset_dir)
        if problems:
            raise ValueError("Dataset validation failed:\n  " + "\n  ".join(problems[:20]))
        return chunks

    def index_dimensions(self):
        """Vector dimensions of the existing index, or None when there is no index."""
        from azure.core.exceptions import ResourceNotFoundError
        try:
            index = self.index_client.get_index(self.settings.index_name)
        except ResourceNotFoundError:
            return None
        return next(f.vector_search_dimensions for f in index.fields if f.name == VECTOR_FIELD)

    def existing_hashes(self):
        results = self.search_client.search(search_text="*", select=["id", "content_hash"], top=1000)
        return {doc["id"]: doc.get("content_hash") for doc in results}

    def plan(self):
        chunks = self.chunks()
        existing = self.existing_hashes() if self.index_dimensions() is not None else {}
        return plan_ingestion(chunks, existing, self.settings.embedding_model)

    def ensure_index(self):
        dimensions = len(self.embedder.embed(["dimension probe"])[0])      # ask the deployment, never assume
        existing = self.index_dimensions()
        if existing is not None and existing != dimensions:
            raise RuntimeError(f"Index has {existing}-dimension vectors but '{self.settings.embedding_deployment}' produces "
                               f"{dimensions}. Run teardown, then provision again.")
        self.index_client.create_or_update_index(build_index(self.settings, dimensions))
        return dimensions

    def ingest(self, dimensions):
        plan = self.plan()
        if plan.upload:
            vectors = self.embedder.embed([chunk.text for chunk in plan.upload])
            wrong = [chunk.id for chunk, vector in zip(plan.upload, vectors) if len(vector) != dimensions]
            if len(vectors) != len(plan.upload) or wrong:
                raise RuntimeError(f"Embedding output does not match the index: {wrong[:5]}")
            documents = [{**chunk.to_document(self.settings.embedding_model), VECTOR_FIELD: vector}
                         for chunk, vector in zip(plan.upload, vectors)]
            self._check(self.search_client.merge_or_upload_documents(documents), "upload")
        if plan.delete:
            # Stale chunks would otherwise stay retrievable after their policy was removed.
            self._check(self.search_client.delete_documents([{"id": chunk_id} for chunk_id in plan.delete]), "delete")
        expected = len(plan.upload) + len(plan.unchanged)
        for _ in range(20):                           # indexing is eventually consistent
            if self.search_client.get_document_count() == expected:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"Index holds {self.search_client.get_document_count()} documents, expected {expected}")
        return plan

    @staticmethod
    def _check(results, action):
        failed = [result.key for result in results if not result.succeeded]
        if failed:
            raise RuntimeError(f"{action} failed for {len(failed)} document(s): {failed[:5]}")

    def ensure_knowledge_source(self):
        from azure.search.documents.indexes.models import (
            SearchIndexFieldReference, SearchIndexKnowledgeSource, SearchIndexKnowledgeSourceParameters)
        self.index_client.create_or_update_knowledge_source(SearchIndexKnowledgeSource(
            name=self.settings.knowledge_source_name, description="Northstar Retail policy chunks, versioned by effective date",
            search_index_parameters=SearchIndexKnowledgeSourceParameters(
                search_index_name=self.settings.index_name, semantic_configuration_name=SEMANTIC_CONFIG,
                source_data_fields=[SearchIndexFieldReference(name=name) for name in SOURCE_DATA_FIELDS])))

    def ensure_knowledge_base(self):
        from azure.search.documents.indexes.models import (
            AzureOpenAIVectorizerParameters, KnowledgeBase, KnowledgeBaseAzureOpenAIModel, KnowledgeSourceReference)
        self.index_client.create_or_update_knowledge_base(KnowledgeBase(
            name=self.settings.knowledge_base_name, description="Policy evidence for the Northstar support agent",
            knowledge_sources=[KnowledgeSourceReference(name=self.settings.knowledge_source_name)],
            # The planning model is used for low and medium reasoning effort; minimal effort does not call it.
            models=[KnowledgeBaseAzureOpenAIModel(azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                resource_url=self.settings.openai_endpoint, deployment_name=self.settings.planning_deployment,
                model_name=self.settings.planning_model))],
            output_mode="extractiveData"))

    def status(self):
        from azure.core.exceptions import ResourceNotFoundError
        report = {"index": None, "documents": None, "knowledge_source": False, "knowledge_base": False}
        dimensions = self.index_dimensions()
        if dimensions is not None:
            report.update(index=f"{self.settings.index_name} ({dimensions} dimensions)", documents=self.search_client.get_document_count())
        for key, getter, name in (("knowledge_source", self.index_client.get_knowledge_source, self.settings.knowledge_source_name),
                                  ("knowledge_base", self.index_client.get_knowledge_base, self.settings.knowledge_base_name)):
            try:
                getter(name)
                report[key] = True
            except ResourceNotFoundError:
                pass
        return report

    def teardown(self):
        """Delete in dependency order. Missing objects are skipped."""
        from azure.core.exceptions import ResourceNotFoundError
        removed = []
        for label, delete, name in (("knowledge base", self.index_client.delete_knowledge_base, self.settings.knowledge_base_name),
                                    ("knowledge source", self.index_client.delete_knowledge_source, self.settings.knowledge_source_name),
                                    ("index", self.index_client.delete_index, self.settings.index_name)):
            try:
                delete(name)
                removed.append(f"{label} {name}")
            except ResourceNotFoundError:
                pass
        return removed

    def retriever(self, effort="low", region="US"):
        from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
        from .retrieval import KnowledgeBaseRetriever
        client = KnowledgeBaseRetrievalClient(endpoint=self.settings.search_endpoint, credential=self.credential,
                                              knowledge_base_name=self.settings.knowledge_base_name)
        return KnowledgeBaseRetriever(client, self.settings.knowledge_source_name, self.chunks(), region, effort)
