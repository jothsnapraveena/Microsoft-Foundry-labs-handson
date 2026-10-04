"""Shared test setup: a throwaway copy of the dataset store and a controllable clock."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from northstar.config import Clock
from northstar.eligibility import ReturnRequest
from northstar.policies import PolicyStore
from northstar.repository import SqliteRepository, bootstrap
from northstar.service import SupportService

DATASET = ROOT / "northstar-dataset"
AS_OF = date.fromisoformat(json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))["as_of"])
CASES = json.loads((DATASET / "evals" / "cases.json").read_text(encoding="utf-8"))


class TestClock(Clock):
    """Fixed business date and a wall clock the test can move."""
    def __init__(self):
        self.date, self.time = AS_OF, datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)

    def today(self):
        return self.date

    def now(self):
        return self.time

    def advance(self, **delta):
        self.time += timedelta(**delta)


class Environment:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = bootstrap(DATASET / "northstar.sqlite", Path(self.directory.name) / "app.sqlite")
        self.clock = TestClock()
        self.policies = PolicyStore.load(DATASET / "knowledge" / "policies.json")
        self.repository = SqliteRepository(self.db_path)
        self.service = SupportService(self.repository, self.policies, self.clock)

    def close(self):
        self.directory.cleanup()

    def query(self, sql, *args):
        connection = sqlite3.connect(self.db_path)
        try:
            return connection.execute(sql, args).fetchall()
        finally:
            connection.close()

    def execute(self, sql, *args):
        connection = sqlite3.connect(self.db_path)
        with connection:
            connection.execute(sql, args)
        connection.close()

    def count(self, table):
        return self.query(f"SELECT COUNT(*) FROM {table}")[0][0]


def case(scenario, outcome=None):
    """First fixture for a scenario, with its request and owner."""
    found = next(c for c in CASES if c["scenario"] == scenario and (outcome is None or c["expected_outcome"] == outcome))
    return found["authenticated_customer_id"], ReturnRequest(**found["inputs"]), found
