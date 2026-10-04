"""Persistence behind a small interface, so SQLite can be replaced by Azure SQL or PostgreSQL.

SQLite here is the local development store. It is not a production deployment.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Protocol

ACTIVE_RETURN_STATUSES = ("authorized", "received", "refunded")    # these reserve quantity

# Tables the application adds to the generated dataset.
APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS support_tickets (ticket_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  order_id TEXT REFERENCES orders(order_id), category TEXT NOT NULL, summary TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL,
  binding_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, confirmed_at TEXT, token_hash TEXT, consumed_at TEXT);
CREATE TABLE IF NOT EXISTS idempotency (actor_id TEXT NOT NULL, key_hash TEXT NOT NULL, action TEXT NOT NULL,
  payload_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (actor_id, key_hash));
CREATE TABLE IF NOT EXISTS audit_log (audit_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor_id TEXT NOT NULL,
  action TEXT NOT NULL, result TEXT NOT NULL, order_id TEXT, policy_ids TEXT, confirmation_id TEXT, idempotency_key_hash TEXT,
  trace_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS customer_identities (subject TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id));
"""


class UnitOfWork(Protocol):
    """One transaction. A relational implementation must give the same guarantees:
    writes are serialized and either all commit or none do."""
    def get_order(self, order_id): ...
    def get_items(self, order_id): ...
    def get_item(self, item_id): ...
    def get_product(self, product_id): ...
    def get_shipment(self, order_id): ...
    def reserved_quantity(self, item_id): ...
    def insert_return(self, record): ...
    def get_return(self, return_id): ...
    def get_refund(self, return_id): ...
    def set_order_cancelled(self, order_id, cancelled_at): ...
    def insert_ticket(self, record): ...
    def save_proposal(self, record): ...
    def get_proposal(self, proposal_id): ...
    def update_proposal(self, proposal_id, **fields): ...
    def get_idempotent(self, actor_id, key_hash): ...
    def save_idempotent(self, record): ...
    def add_audit(self, record): ...
    def customer_for_subject(self, subject): ...
    def customer_exists(self, customer_id): ...


def bootstrap(dataset_db, app_db, overwrite=False):
    """Copy the generated dataset store to a working database and add the application tables."""
    app_db = Path(app_db)
    if app_db.exists() and not overwrite:
        raise FileExistsError(f"{app_db} already exists; pass overwrite to reset it")
    app_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dataset_db, app_db)
    connection = sqlite3.connect(app_db)
    connection.executescript(APP_SCHEMA)
    connection.close()
    return app_db


class SqliteRepository:
    def __init__(self, path, timeout=30.0):
        self.path, self.timeout = str(path), timeout

    @contextmanager
    def transaction(self, write=False):
        connection = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        # IMMEDIATE takes the write lock up front, so concurrent writers queue instead of racing.
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield SqliteUnitOfWork(connection)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


class SqliteUnitOfWork:
    def __init__(self, connection):
        self.connection = connection

    def _one(self, sql, *args):
        row = self.connection.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _all(self, sql, *args):
        return [dict(row) for row in self.connection.execute(sql, args)]

    def _insert(self, table, record):
        columns = ", ".join(record)
        self.connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({', '.join('?' for _ in record)})", list(record.values()))

    def get_order(self, order_id):
        return self._one("SELECT * FROM orders WHERE order_id = ?", order_id)

    def get_items(self, order_id):
        return self._all("SELECT * FROM order_items WHERE order_id = ? ORDER BY item_id", order_id)

    def get_item(self, item_id):
        return self._one("SELECT * FROM order_items WHERE item_id = ?", item_id)

    def get_product(self, product_id):
        return self._one("SELECT * FROM products WHERE product_id = ?", product_id)

    def get_shipment(self, order_id):
        return self._one("SELECT * FROM shipments WHERE order_id = ?", order_id)

    def reserved_quantity(self, item_id):
        marks = ", ".join("?" for _ in ACTIVE_RETURN_STATUSES)
        return self.connection.execute(
            f"SELECT COALESCE(SUM(quantity), 0) FROM returns WHERE item_id = ? AND status IN ({marks})",
            (item_id, *ACTIVE_RETURN_STATUSES)).fetchone()[0]

    def insert_return(self, record):
        self._insert("returns", record)

    def get_return(self, return_id):
        return self._one("SELECT * FROM returns WHERE return_id = ?", return_id)

    def get_refund(self, return_id):
        return self._one("SELECT * FROM refunds WHERE return_id = ?", return_id)

    def set_order_cancelled(self, order_id, cancelled_at):
        self.connection.execute("UPDATE orders SET status = 'cancelled', cancelled_at = ? WHERE order_id = ?", (cancelled_at, order_id))

    def insert_ticket(self, record):
        self._insert("support_tickets", record)

    def save_proposal(self, record):
        self._insert("proposals", record)

    def get_proposal(self, proposal_id):
        return self._one("SELECT * FROM proposals WHERE proposal_id = ?", proposal_id)

    def update_proposal(self, proposal_id, **fields):
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.connection.execute(f"UPDATE proposals SET {assignments} WHERE proposal_id = ?", (*fields.values(), proposal_id))

    def get_idempotent(self, actor_id, key_hash):
        return self._one("SELECT * FROM idempotency WHERE actor_id = ? AND key_hash = ?", actor_id, key_hash)

    def save_idempotent(self, record):
        self._insert("idempotency", record)

    def add_audit(self, record):
        record = dict(record)
        if isinstance(record.get("policy_ids"), (list, tuple)):
            record["policy_ids"] = json.dumps(list(record["policy_ids"]))
        self._insert("audit_log", record)

    def customer_for_subject(self, subject):
        row = self._one("SELECT customer_id FROM customer_identities WHERE subject = ?", subject)
        return row["customer_id"] if row else None

    def customer_exists(self, customer_id):
        return self._one("SELECT 1 AS found FROM customers WHERE customer_id = ?", customer_id) is not None
