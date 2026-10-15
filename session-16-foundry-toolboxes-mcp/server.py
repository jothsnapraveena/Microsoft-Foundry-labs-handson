"""Authenticated MCP server. Only synthetic data; bearer token binds a fixed demo actor."""
import os
import secrets
from support import ROOT, load_env, required
from inventory import Inventory

def create_server(database=None):
    from mcp.server.fastmcp import FastMCP
    from pydantic import Field
    from typing import Annotated
    # Avoid annotation forward-reference ambiguity in FastMCP schema generation.
    class InventoryMCP(FastMCP):
        async def call_tool(self, name, arguments):
            fields = {"get_stock": {"sku"}, "reserve_stock": {"sku", "quantity", "request_id", "idempotency_key"}}
            if name not in fields or set(arguments) != fields[name]:
                raise ValueError("unexpected_tool_arguments")
            return await super().call_tool(name, arguments)
    server = InventoryMCP("Juniper demo inventory", host=os.environ.get("MCP_BIND_HOST", "127.0.0.1"), stateless_http=True, json_response=True)
    db = Inventory(database or ROOT / "artifacts/inventory.sqlite", ROOT / "data/inventory.json")
    db.initialize()

    @server.tool()
    def get_stock(sku: str) -> dict:
        """Read exact synthetic stock for one J-xxx SKU. Unknown SKUs remain unknown."""
        return db.stock(sku)

    @server.tool()
    def reserve_stock(sku: str, quantity: Annotated[int, Field(strict=True, gt=0, le=1000)], request_id: str, idempotency_key: str) -> dict:
        """Create a MOCK reservation only for an operator-approved proposal. Cannot grant approval."""
        if os.environ.get("ENABLE_MOCK_WRITES") != "1":
            raise ValueError("mock_writes_disabled")
        return db.reserve(os.environ.get("MCP_ACTOR_ID", "lab-demo-user"),
                          sku, quantity, request_id, idempotency_key)

    return server


class BearerGuard:
    def __init__(self, app, token):
        if len(token) < 24:
            raise ValueError("Use a random MCP_API_TOKEN of at least 24 characters")
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            if not secrets.compare_digest(auth, "Bearer " + self.token):
                await send({"type": "http.response.start", "status": 401, "headers": [(b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--database")
    args = parser.parse_args()
    load_env()
    server = create_server(args.database)
    if args.stdio:
        server.run(transport="stdio")
        raise SystemExit(0)
    uvicorn.run(BearerGuard(server.streamable_http_app(), required("MCP_API_TOKEN")),
                host=os.environ.get("MCP_BIND_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "8000")))
