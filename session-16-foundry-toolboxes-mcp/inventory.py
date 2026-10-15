"""Transactional synthetic inventory and approved, idempotent mock reservations."""
from contextlib import contextmanager
import json
import re
import sqlite3
from pathlib import Path

class Inventory:
    def __init__(self, database, catalog):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self):
        data = json.loads(Path(self.catalog).read_text())
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS stock(sku TEXT PRIMARY KEY,name TEXT,quantity INTEGER CHECK(quantity>=0),snapshot TEXT);
              CREATE TABLE IF NOT EXISTS approvals(request_id TEXT PRIMARY KEY,actor TEXT,sku TEXT,quantity INTEGER CHECK(quantity>0));
              CREATE TABLE IF NOT EXISTS reservations(key TEXT PRIMARY KEY,request_id TEXT UNIQUE,actor TEXT,sku TEXT,quantity INTEGER,result TEXT);
              CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,request_id TEXT,actor TEXT,action TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
            """)
            for item in data["products"]:
                db.execute("INSERT OR IGNORE INTO stock VALUES(?,?,?,?)",
                           (item["sku"], item["name"], item["available_quantity"], data["snapshot_utc"]))

    @staticmethod
    def validate(sku, quantity=None):
        if not isinstance(sku, str) or not re.fullmatch(r"J-\d{3}", sku):
            raise ValueError("invalid_sku")
        if quantity is not None and (type(quantity) is not int or not 0 < quantity <= 1000):
            raise ValueError("invalid_quantity")

    def stock(self, sku):
        self.validate(sku)
        with self.connect() as db:
            item = db.execute("SELECT * FROM stock WHERE sku=?", (sku,)).fetchone()
        return ({"status": "ok", "sku": item["sku"], "name": item["name"],
                 "available_quantity": item["quantity"], "snapshot_utc": item["snapshot"]}
                if item else {"status": "unknown_sku", "sku": sku})

    def approve(self, request_id, actor, sku, quantity):
        self.validate(sku, quantity)
        if not request_id or not actor:
            raise ValueError("missing_approval_binding")
        with self.connect() as db:
            # The approval command is an operator action, never an MCP tool.
            db.execute("INSERT INTO approvals VALUES(?,?,?,?)", (request_id, actor, sku, quantity))

    def reserve(self, actor, sku, quantity, request_id, key):
        self.validate(sku, quantity)
        if not all(isinstance(v, str) and 0 < len(v) <= 100 for v in (actor, request_id, key)):
            raise ValueError("invalid_request")
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT * FROM reservations WHERE key=? OR request_id=?", (key, request_id)).fetchone()
                if previous:
                    if (previous["key"], previous["request_id"], previous["actor"], previous["sku"], previous["quantity"]) != (key, request_id, actor, sku, quantity):
                        raise ValueError("idempotency_conflict")
                    db.commit()
                    return json.loads(previous["result"])
                approved = db.execute("SELECT * FROM approvals WHERE request_id=?", (request_id,)).fetchone()
                if not approved or (approved["actor"], approved["sku"], approved["quantity"]) != (actor, sku, quantity):
                    raise ValueError("approval_required")
                updated = db.execute("UPDATE stock SET quantity=quantity-? WHERE sku=? AND quantity>=?",
                                     (quantity, sku, quantity))
                if updated.rowcount != 1:
                    raise ValueError("insufficient_or_unknown_stock")
                result = {"status": "mock_reserved", "reservation_id": "demo-" + request_id, "sku": sku, "quantity": quantity}
                db.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?)",
                           (key, request_id, actor, sku, quantity, json.dumps(result)))
                db.execute("INSERT INTO audit(request_id,actor,action) VALUES(?,?,'mock_reserve')", (request_id, actor))
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
