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


class Clock:
    """Business date and wall-clock time. Eligibility uses the date; expiry and audit use the time."""
    def __init__(self, fixed_date=None, now=None):
        self._fixed_date, self._now = fixed_date, now

    def today(self):
        return self._fixed_date or self.now().date()

    def now(self):
        return self._now() if self._now else datetime.now(timezone.utc)
