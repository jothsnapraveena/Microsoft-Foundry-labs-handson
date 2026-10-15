import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import tempfile
import unittest
from unittest.mock import patch
from inventory import Inventory
from support import ROOT

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Inventory(Path(self.temp.name) / "inventory.sqlite", ROOT / "data/inventory.json")
        self.db.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_stays_unknown(self):
        self.assertEqual(self.db.stock("J-999")["status"], "unknown_sku")

    def test_no_approval_no_mutation(self):
        with self.assertRaisesRegex(ValueError, "approval_required"):
            self.db.reserve("alice", "J-101", 1, "r1", "key1")
        self.assertEqual(self.db.stock("J-101")["available_quantity"], 12)

    def test_approval_is_bound_to_actor(self):
        self.db.approve("r1", "alice", "J-101", 1)
        with self.assertRaisesRegex(ValueError, "approval_required"):
            self.db.reserve("bob", "J-101", 1, "r1", "key1")

    def test_overstock_rolls_back(self):
        self.db.approve("r1", "alice", "J-101", 20)
        with self.assertRaisesRegex(ValueError, "insufficient"):
            self.db.reserve("alice", "J-101", 20, "r1", "key1")
        self.assertEqual(self.db.stock("J-101")["available_quantity"], 12)

    def test_concurrent_duplicate_has_one_effect_and_audit(self):
        self.db.approve("r1", "alice", "J-101", 1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.db.reserve("alice", "J-101", 1, "r1", "key1"), range(4)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(self.db.stock("J-101")["available_quantity"], 11)
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit").fetchone()[0], 1)

    def test_conflicting_key_is_rejected(self):
        self.db.approve("r1", "alice", "J-101", 1)
        self.db.reserve("alice", "J-101", 1, "r1", "key1")
        with self.assertRaisesRegex(ValueError, "idempotency_conflict"):
            self.db.reserve("alice", "J-101", 2, "r1", "key1")

    def test_boolean_and_negative_quantity_rejected(self):
        for quantity in (True, -3, 1.5, 0):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.db.reserve("alice", "J-101", quantity, "r1", "k")

    def test_initialization_does_not_reset_stock(self):
        self.db.approve("r1", "alice", "J-101", 1)
        self.db.reserve("alice", "J-101", 1, "r1", "k")
        self.db.initialize()
        self.assertEqual(self.db.stock("J-101")["available_quantity"], 11)


class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_protocol_over_stdio(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as temp:
            params = StdioServerParameters(command=sys.executable, args=[str(ROOT/"server.py"), "--stdio", "--database", str(Path(temp)/"inventory.sqlite")])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read,write) as client:
                    await client.initialize()
                    tools=await client.list_tools()
                    self.assertIn("get_stock",{tool.name for tool in tools.tools})
                    result=await client.call_tool("get_stock",{"sku":"J-101"})
                    self.assertFalse(result.isError)
                    payload = result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(payload["available_quantity"],12)

    async def test_mcp_tool_discovery_and_call(self):
        from server import create_server
        with tempfile.TemporaryDirectory() as temp:
            server = create_server(Path(temp) / "inventory.sqlite")
            tools = await server.list_tools()
            self.assertEqual({t.name for t in tools}, {"get_stock", "reserve_stock"})
            result = await server.call_tool("get_stock", {"sku": "J-101"})
            self.assertIn("12", str(result))

    async def test_extra_arguments_are_rejected(self):
        from server import create_server
        with tempfile.TemporaryDirectory() as temp:
            server = create_server(Path(temp) / "inventory.sqlite")
            with self.assertRaisesRegex(ValueError, "unexpected_tool_arguments"):
                await server.call_tool("get_stock", {"sku": "J-101", "override": True})

    async def test_protocol_rejects_boolean_quantity(self):
        from server import create_server
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {"ENABLE_MOCK_WRITES": "1"}):
            server = create_server(Path(temp) / "inventory.sqlite")
            with self.assertRaises(Exception):
                await server.call_tool("reserve_stock", {"sku": "J-101", "quantity": True, "request_id": "r1", "idempotency_key": "k"})

    async def test_bearer_guard_denies_unauthenticated_http(self):
        from server import BearerGuard
        invoked = []
        async def inner(*args):
            invoked.append(True)
        sent = []
        async def send(item):
            sent.append(item)
        await BearerGuard(inner, "x" * 24)({"type": "http", "headers": []}, None, send)
        self.assertEqual(sent[0]["status"], 401)
        self.assertFalse(invoked)

if __name__ == "__main__":
    unittest.main()
