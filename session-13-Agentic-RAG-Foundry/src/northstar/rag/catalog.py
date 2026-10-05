"""The local chunk catalog: the source of truth that indexed and retrieved content is checked against."""
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path

OPEN_ENDED = "9999-12-31T00:00:00Z"      # stored for open-ended policies so a date filter needs no null test
REQUIRED = ("id", "policy_id", "topic", "version", "effective_from", "effective_to", "region", "applies_by",
            "source_path", "title", "section", "page_chunk", "page_number")


@dataclass(frozen=True)
class Chunk:
    id: str
    policy_id: str
    topic: str
    version: str
    effective_from: date
    effective_to: date | None       # exclusive
    region: str
    applies_by: str
    source_path: str
    title: str
    section: str
    text: str
    page_number: int

    def in_effect(self, on):
        return self.effective_from <= on and (self.effective_to is None or on < self.effective_to)

    def content_hash(self, embedding_model):
        """Changes when the text, metadata or embedding model changes, so only those chunks are re-embedded."""
        payload = [self.policy_id, self.topic, self.version, str(self.effective_from), str(self.effective_to), self.region,
                   self.applies_by, self.source_path, self.title, self.section, self.text, self.page_number, embedding_model]
        return hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()

    def to_document(self, embedding_model):
        """The search document, without its vector."""
        return {"id": self.id, "policy_id": self.policy_id, "topic": self.topic, "version": self.version,
                "effective_from": f"{self.effective_from}T00:00:00Z",
                "effective_to": f"{self.effective_to}T00:00:00Z" if self.effective_to else OPEN_ENDED,
                "region": self.region, "applies_by": self.applies_by, "source_path": self.source_path, "title": self.title,
                "section": self.section, "page_chunk": self.text, "page_number": self.page_number,
                "content_hash": self.content_hash(embedding_model)}


def load_chunks(dataset_dir):
    """Load and validate search/policy_chunks.json. Returns (chunks, problems)."""
    dataset_dir = Path(dataset_dir)
    records = json.loads((dataset_dir / "search" / "policy_chunks.json").read_text(encoding="utf-8"))
    chunks, problems, seen = [], [], set()
    for position, record in enumerate(records):
        label = record.get("id", f"record {position}")
        missing = [name for name in REQUIRED if name not in record]
        if missing:
            problems.append(f"{label}: missing {missing}")
            continue
        if record["id"] in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(record["id"])
        try:
            start = date.fromisoformat(record["effective_from"])
            end = date.fromisoformat(record["effective_to"]) if record["effective_to"] else None
        except (TypeError, ValueError):
            problems.append(f"{label}: invalid effective date")
            continue
        if end is not None and end <= start:
            problems.append(f"{label}: effective_to is not after effective_from")
        if record["applies_by"] not in ("order_date", "event_date"):
            problems.append(f"{label}: unknown applies_by")
        if not isinstance(record["page_chunk"], str) or not record["page_chunk"].strip():
            problems.append(f"{label}: empty text")
        source = dataset_dir / record["source_path"]
        if not source.is_file() or record["page_chunk"] not in source.read_text(encoding="utf-8"):
            problems.append(f"{label}: text not found in {record['source_path']}")
        chunks.append(Chunk(id=record["id"], policy_id=record["policy_id"], topic=record["topic"], version=record["version"],
                            effective_from=start, effective_to=end, region=record["region"], applies_by=record["applies_by"],
                            source_path=record["source_path"], title=record["title"], section=record["section"],
                            text=record["page_chunk"], page_number=record["page_number"]))
    return chunks, problems
