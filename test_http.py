"""Smoke-test a running HTTP server (local or deployed).

Usage (PowerShell):
    $env:MCP_URL = "https://<your-app>.azurewebsites.net/mcp"
    $env:MCP_API_TOKEN = "<your token>"
    python test_http.py

Defaults to http://127.0.0.1:8000/mcp when MCP_URL is not set.
"""

import asyncio
import json
import os
import sys

import httpx2 as httpx
from mcp import Client, MCPError
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
TOKEN = os.environ.get("MCP_API_TOKEN", "")


async def main() -> int:
    base = URL.rsplit("/mcp", 1)[0]
    failures = 0

    # 1. Health check (no token needed)
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{base}/health")
        print(f"[{'PASS' if r.status_code == 200 else 'FAIL'}] health        {r.status_code} {r.text}")
        failures += r.status_code != 200

        # 2. A request without the token must be rejected
        r = await http.post(URL, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        ok = r.status_code == 401
        print(f"[{'PASS' if ok else 'FAIL'}] no-token      {r.status_code} (expected 401)")
        failures += not ok

    # 3. With the token: call real tools through MCP
    try:
        failures += await tool_checks()
    except Exception as e:  # connection errors arrive wrapped in an ExceptionGroup
        while isinstance(e, BaseExceptionGroup) and e.exceptions:
            e = e.exceptions[0]
        msg = e.message if isinstance(e, MCPError) else str(e)
        print(f"[FAIL] MCP call      {msg} (is MCP_API_TOKEN correct?)")
        failures += 1

    print("\nAll checks passed." if not failures else f"\n{failures} check(s) FAILED.")
    return 1 if failures else 0


async def tool_checks() -> int:
    failures = 0
    http_client = create_mcp_http_client(headers={"Authorization": f"Bearer {TOKEN}"})
    async with Client(streamable_http_client(URL, http_client=http_client)) as client:
        tools = [t.name for t in (await client.list_tools()).tools]
        print(f"[{'PASS' if len(tools) == 7 else 'FAIL'}] list_tools    {len(tools)} tools: {', '.join(tools)}")
        failures += len(tools) != 7

        r = await client.call_tool("check_data_quality", {"dataset": "cashflow", "date_column": "cashflow_date"})
        status = r.structured_content["status"]
        print(f"[PASS] data quality  cashflow -> {status}, issues: {len(r.structured_content['issues'])}")

        r = await client.call_tool("search_documents", {"query": "leverage covenant breach", "top_k": 1})
        top = r.structured_content["results"][0]["citation"]
        print(f"[PASS] doc search    top hit -> {top['file']} page {top['page']}")

        r = await client.call_tool("query_data", {"sql": "DELETE FROM cashflow"})
        print(f"[{'PASS' if r.is_error else 'FAIL'}] governance    DELETE blocked: {r.is_error}")
        failures += not r.is_error
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
