"""Environment-based settings and the server clock."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    dataset_dir: Path
    db_path: Path
    fixed_date: date | None
    region: str
    proposal_ttl_seconds: int
    auth_mode: str                  # "entra" or "demo"
    entra_tenant_id: str | None
    entra_audience: str | None
    entra_confirm_scope: str
    entra_customer_claim: str

    @classmethod
    def from_env(cls, env=os.environ):
        fixed = env.get("NORTHSTAR_FIXED_DATE")
        return cls(
            dataset_dir=Path(env.get("NORTHSTAR_DATASET_DIR", PROJECT_ROOT / "northstar-dataset")),
            db_path=Path(env.get("NORTHSTAR_DB_PATH", PROJECT_ROOT / "data" / "app.sqlite")),
            fixed_date=date.fromisoformat(fixed) if fixed else None,
            region=env.get("NORTHSTAR_REGION", "US"),
            proposal_ttl_seconds=int(env.get("NORTHSTAR_PROPOSAL_TTL_SECONDS", "900")),
            # Defaults to real token validation so an unconfigured deployment cannot fall back to the stub.
            auth_mode=env.get("NORTHSTAR_AUTH_MODE", "entra"),
            entra_tenant_id=env.get("ENTRA_TENANT_ID"),
            entra_audience=env.get("ENTRA_AUDIENCE"),
            entra_confirm_scope=env.get("ENTRA_CONFIRM_SCOPE", "Returns.Confirm"),
            entra_customer_claim=env.get("ENTRA_CUSTOMER_CLAIM", "oid"),
        )


def load_env_file(path=PROJECT_ROOT / ".env"):
    """Read KEY=VALUE lines into the environment without overriding variables already set."""
    path = Path(path)
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"'))
    return True


def use_utf8_output():
    """Model answers contain characters the default Windows console encoding cannot print."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class AzureSettings:
    """Azure resources for retrieval. Endpoints and names only; sign-in is by Azure credential, never keys."""
    search_endpoint: str
    openai_endpoint: str
    project_endpoint: str
    embedding_deployment: str
    embedding_model: str
    planning_deployment: str        # model the knowledge base uses to plan queries
    planning_model: str
    agent_model: str
    index_name: str
    knowledge_source_name: str
    knowledge_base_name: str

    @classmethod
    def from_env(cls, env=os.environ):
        def required(name):
            value = env.get(name, "").strip().rstrip("/")
            if not value or "<" in value:
                raise ValueError(f"{name} is not set. Fill it in .env (see docs/azure-setup.md).")
            return value
        embedding = required("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        agent = required("AGENT_MODEL")
        planning = env.get("KNOWLEDGE_BASE_MODEL_DEPLOYMENT", agent)
        return cls(
            search_endpoint=required("AZURE_SEARCH_ENDPOINT"), openai_endpoint=required("AZURE_OPENAI_ENDPOINT"),
            project_endpoint=required("PROJECT_ENDPOINT"), embedding_deployment=embedding,
            embedding_model=env.get("AZURE_OPENAI_EMBEDDING_MODEL", embedding),
            planning_deployment=planning, planning_model=env.get("KNOWLEDGE_BASE_MODEL", planning), agent_model=agent,
            index_name=env.get("AZURE_SEARCH_INDEX", "northstar-policies"),
            knowledge_source_name=env.get("AZURE_SEARCH_KNOWLEDGE_SOURCE", "northstar-policies-ks"),
            knowledge_base_name=env.get("AZURE_SEARCH_KNOWLEDGE_BASE", "northstar-policies-kb"))


class Clock:
    """Business date and wall-clock time. Eligibility uses the date; expiry and audit use the time."""
    def __init__(self, fixed_date=None, now=None):
        self._fixed_date, self._now = fixed_date, now

    def today(self):
        return self._fixed_date or self.now().date()

    def now(self):
        return self._now() if self._now else datetime.now(timezone.utc)
