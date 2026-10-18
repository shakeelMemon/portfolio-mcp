"""End-to-end test: start server.py over stdio (like a desktop AI app does)
and call every tool, the resource and the prompt.

Run first: python seed_db.py && python make_sample_docs.py && python ingest_docs.py
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, MCPError
from mcp.client.stdio import StdioServerParameters

SERVER = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).parent / "server.py")])


def show(title: str, result) -> None:
    print(f"\n=== {title} ===")
    data = result.structured_content or [getattr(c, "text", c) for c in result.content]
    print(json.dumps(data, indent=2, default=str)[:1500])


async def main() -> None:
    async with Client(SERVER) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools.tools])

        show("list_datasets", await client.call_tool("list_datasets", {}))
        show("describe_dataset(cashflow)", await client.call_tool("describe_dataset", {"dataset": "cashflow"}))
        show(
            "query_data: net cashflow by fund",
            await client.call_tool(
                "query_data",
                {"sql": "SELECT fund_code, SUM(amount_cad) AS net_cad FROM cashflow GROUP BY fund_code"},
            ),
        )
        show(
            "check_data_quality(cashflow)",
            await client.call_tool("check_data_quality", {"dataset": "cashflow", "date_column": "cashflow_date"}),
        )
        show(
            "check_data_quality(nav_snapshot)",
            await client.call_tool("check_data_quality", {"dataset": "nav_snapshot", "date_column": "as_of_date"}),
        )
        show("get_fund_cashflows(INF-I)", await client.call_tool("get_fund_cashflows", {"fund_code": "INF-I"}))

        show("list_documents", await client.call_tool("list_documents", {}))
        show(
            "search_documents: covenant breach (PC-II only)",
            await client.call_tool(
                "search_documents", {"query": "leverage covenant breach waiver", "top_k": 2, "fund_code": "PC-II"}
            ),
        )
        show(
            "search_documents: stale NAV policy",
            await client.call_tool("search_documents", {"query": "when is a NAV stale", "top_k": 2}),
        )

        print("\n=== Governance checks (all should be blocked) ===")
        for sql in [
            "DELETE FROM cashflow",
            "SELECT * FROM sqlite_master",
            "SELECT 1; DROP TABLE fund",
        ]:
            try:
                r = await client.call_tool("query_data", {"sql": sql})
                status = "BLOCKED" if r.is_error else "ALLOWED (!)"
                detail = r.content[0].text if r.content else ""
            except MCPError as e:
                status, detail = "BLOCKED", e.message
            print(f"{status:12} {sql!r} -> {detail[:110]}")

        res = await client.read_resource("catalog://datasets")
        print("\n=== resource catalog://datasets ===\n" + res.contents[0].text)

        prompt = await client.get_prompt("data_quality_review", {"dataset": "nav_snapshot"})
        print("\n=== prompt data_quality_review ===\n" + prompt.messages[0].content.text)


if __name__ == "__main__":
    asyncio.run(main())
