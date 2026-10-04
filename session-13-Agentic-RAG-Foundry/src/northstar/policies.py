"""Policy metadata and version selection by effective date."""
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path


class PolicyConflict(Exception):
    """No policy, or more than one, is in effect for a topic on a date."""


@dataclass(frozen=True)
class Policy:
    policy_id: str
    topic: str
    version: str
    effective_from: date
    effective_to: date | None      # exclusive; None means open-ended
    region: str
    applies_by: str                # "order_date" or "event_date"
    parameters: dict

    def in_effect(self, on):
        return self.effective_from <= on and (self.effective_to is None or on < self.effective_to)


class PolicyStore:
    def __init__(self, policies):
        self.policies = list(policies)

    @classmethod
    def load(cls, path):
        records = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(Policy(
            policy_id=r["policy_id"], topic=r["topic"], version=r["version"],
            effective_from=date.fromisoformat(r["effective_from"]),
            effective_to=date.fromisoformat(r["effective_to"]) if r["effective_to"] else None,
            region=r["region"], applies_by=r["applies_by"], parameters=r.get("parameters", {})) for r in records)

    def applicable(self, topic, on, region):
        """The single policy in effect. Zero or several is a conflict, never a guess."""
        found = [p for p in self.policies if p.topic == topic and p.region == region and p.in_effect(on)]
        if len(found) != 1:
            raise PolicyConflict(f"{len(found)} policies in effect for {topic} in {region} on {on}")
        return found[0]
