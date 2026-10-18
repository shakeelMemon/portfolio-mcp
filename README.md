# Portfolio Data MCP Server

A Model Context Protocol (MCP) server that gives AI assistants **governed, read-only access** to a private-markets portfolio: a database of funds, cashflows and NAV snapshots, plus **searchable fund reports and policy PDFs (RAG retrieval with citations)**.

Built with the official MCP Python SDK **v2** (`MCPServer`).

## What it exposes

| Type | Name | What it does |
|---|---|---|
| Tool | `list_datasets` | Lists the datasets the AI is allowed to see, with descriptions and row counts |
| Tool | `describe_dataset` | Columns, types, keys and 3 sample rows for one dataset |
| Tool | `query_data` | Runs one read-only SQL `SELECT`, capped at 200 rows |
| Tool | `check_data_quality` | Nulls, duplicates and freshness (overall and per fund), with a PASS/FAIL result |
| Tool | `get_fund_cashflows` | A fund's cashflows with CAD totals, and a warning when CAD amounts are missing |
| Tool | `list_documents` | The ingested fund reports and policies, with page and chunk counts |
| Tool | `search_documents` | Ranked passages for a question, each with a citation (file and page); optional fund filter |
| Resource | `catalog://datasets` | The data catalog as Markdown |
| Prompt | `data_quality_review` | A ready-made "review this dataset's quality" request |

## Governance built in

1. **Read-only.** The database is opened in read-only mode.
2. **SQLite authorizer.** Every query is checked at the engine level. Only `SELECT` statements on allow-listed tables are permitted. `DELETE`, `DROP`, `PRAGMA`, `ATTACH` and system tables are blocked.
3. **Dataset allow-list.** The AI can only see `fund`, `cashflow` and `nav_snapshot`.
4. **One statement per call** and a **200-row limit**.
5. **Audit log.** Every tool call is written to `audit.log` as one JSON line: time, tool, arguments, status, row count and error.
6. **Clear errors.** Expected failures are raised as `ToolError`, so the AI gets the real reason ("Only SELECT queries are allowed") instead of a generic crash.

The sample data has three planted problems for the quality checks to find: a duplicated Alter Domus distribution, a cashflow missing its CAD amount, and a fund with a stale NAV.

## Document search (RAG retrieval)

```
PDF  ->  page text  ->  paragraph chunks  ->  SQLite (docs.db)  ->  BM25 search  ->  passages + citations
```

- **Ingestion is idempotent.** Each PDF is hashed (SHA-256). Unchanged files are skipped and changed files are re-chunked, so the job can run nightly.
- **Every chunk keeps its file and page**, so the AI can cite its sources.
- **Retrieval uses BM25**, a standard keyword-ranking method that needs no external service. `rag.search()` is the only function to change when moving to embeddings and a vector index (for example Azure OpenAI embeddings with Azure AI Search).
- **Prompt-injection guard.** The server tells the AI that document text is data, never instructions.

### Retrieval evaluation

`eval_retrieval.py` scores retrieval against 13 labelled questions, each with a known correct file and page:

| Metric | Result |
|---|---|
| Hit@1 (correct source ranked first) | 0.85 |
| Hit@3 (correct source in top 3) | 0.92 |
| MRR (mean reciprocal rank) | 0.87 |
| Hit@3, questions using the documents' own words | 1.00 |
| Hit@3, paraphrased questions | 0.80 |

The gap is the point. *"Who exceeded the borrowing ceiling agreed with lenders?"* is not found at all, because the report says "breached its maximum leverage covenant" and no words match. Keyword search cannot see that those mean the same thing. Embeddings (semantic search), usually combined with BM25 as **hybrid search**, close that gap. Rerun this script after any change to prove it helped.

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python seed_db.py          # creates portfolio.db
python make_sample_docs.py # creates the sample PDFs in docs/
python ingest_docs.py      # chunks the PDFs into docs.db
python eval_retrieval.py   # scores retrieval quality
python test_client.py      # starts the server and calls every tool
```

Run the server on its own:

```bash
python server.py          # stdio (for desktop AI apps)
python server.py --http   # Streamable HTTP at http://127.0.0.1:8000/mcp
```

### Deploy to Azure App Service

`startup.sh` builds the databases and starts the secured HTTP server. Required app settings: `MCP_API_TOKEN`, `ALLOWED_HOSTS`, `WEBSITES_PORT=8000`, `AUDIT_LOG=/home/LogFiles/portfolio-mcp-audit.log`. Startup command: `bash startup.sh`. Check a running server with `python test_http.py` (set `MCP_URL` and `MCP_API_TOKEN`). Every request except `/health` needs `Authorization: Bearer <token>`, and the server refuses to start on a public address without a token.

### Optional: try it in the MCP Inspector

The Inspector is a browser tool for clicking through an MCP server's tools (needs Node.js):

```bash
npx @modelcontextprotocol/inspector python server.py
```

### Optional: connect it to an AI app

Most MCP-capable desktop apps take a JSON config like this. Use the full paths on your machine:

```json
{
  "mcpServers": {
    "portfolio-data": {
      "command": "C:\\path\\to\\portfolio-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\portfolio-mcp\\server.py"]
    }
  }
}
```

## Moving to SQL Server

Only `_connect()` in `server.py` changes. Swap SQLite for `pyodbc` and connect with a **read-only database login** that has `SELECT` on approved views only. The database permissions then take over the job of the SQLite authorizer.

## Files

| File | Purpose |
|---|---|
| `server.py` | The MCP server |
| `seed_db.py` | Builds the sample portfolio database |
| `make_sample_docs.py` | Generates sample fund-report and policy PDFs |
| `rag.py` | Document ingestion (PDF to chunks) and BM25 retrieval |
| `ingest_docs.py` | Runs ingestion on `docs/` |
| `eval_retrieval.py` | Retrieval evaluation: Hit@1, Hit@3, MRR |
| `test_client.py` | End-to-end test over stdio, including blocked-query checks |
| `test_http.py` | Smoke test for a running HTTP server: health, token rejection, tools, governance |
| `startup.sh` | Azure App Service startup command |
| `requirements.txt` | Python dependencies |
