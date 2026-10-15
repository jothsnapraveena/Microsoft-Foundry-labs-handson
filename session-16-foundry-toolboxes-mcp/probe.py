"""Inspect MCP tools and call get_stock using the actual MCP protocol."""
import argparse
import asyncio
import os
from support import confirm, load_env, required, ROOT, save

async def probe(url, token, sku):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client(url, headers={"Authorization": "Bearer " + token}) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("get_stock", {"sku": sku})
            report = {"tools": tools.model_dump(mode="json"), "result": result.model_dump(mode="json")}
            save(ROOT / "artifacts/mcp-probe.json", report)
            print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--sku", default="J-101")
    parser.add_argument("--toolbox", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    load_env()
    if args.toolbox:
        confirm(args)
        from azure.identity import DefaultAzureCredential
        with DefaultAzureCredential() as credential:
            token = credential.get_token("https://ai.azure.com/.default").token
            asyncio.run(probe(required("TOOLBOX_MCP_URL"), token, args.sku))
    else:
        if not args.url.startswith(("http://127.0.0.1:", "http://localhost:")):
            confirm(args)
        asyncio.run(probe(args.url, required("MCP_API_TOKEN"), args.sku))
