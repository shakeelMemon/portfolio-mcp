"""Document ingestion and retrieval for the Portfolio Data MCP server.

Pipeline:  PDF -> page text -> paragraph chunks -> SQLite (docs.db) -> BM25 search

* Ingestion is idempotent: each file is hashed (SHA-256) and skipped if unchanged,
  re-chunked if changed.
* Every chunk keeps its source file and page number, so answers can cite sources.
* Retrieval uses BM25, a standard lexical ranking. It runs with no external service.
  In production you would swap `search()` for embeddings + a vector index
  (e.g. Azure OpenAI embeddings + Azure AI Search) and keep the same contract.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
DOCS_DB = BASE_DIR / "docs.db"

MAX_CHUNK_CHARS = 700
FUND_CODE = re.compile(r"\b(PE-IV|PC-II|INF-I)\b")
STOPWORDS = set(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with "
    "what which who how when why does did do".split()
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    doc_id      INTEGER PRIMARY KEY,
    file_name   TEXT UNIQUE NOT NULL,
    title       TEXT,
    fund_code   TEXT,
    pages       INTEGER,
    sha256      TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunk (
    chunk_id  INTEGER PRIMARY KEY,
    doc_id    INTEGER NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
    page      INTEGER NOT NULL,
    chunk_no  INTEGER NOT NULL,
    text      TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- ingestion
def _chunk_page(text: str) -> list[str]:
    """Split a page into paragraph-sized chunks of at most MAX_CHUNK_CHARS."""
    text = re.sub(r"[ \t]+", " ", text)
    # pypdf returns wrapped lines; rebuild paragraphs from sentence ends.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|(?<=\.)\n(?=[A-Z][a-z-]+\.)", text) if p.strip()]
    chunks: list[str] = []
    for p in paragraphs:
        p = p.replace("\n", " ")
        while len(p) > MAX_CHUNK_CHARS:
            cut = p.rfind(". ", 0, MAX_CHUNK_CHARS) + 1 or MAX_CHUNK_CHARS
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            chunks.append(p)
    return chunks


def ingest(docs_dir: Path = DOCS_DIR, db_path: Path = DOCS_DB) -> dict[str, int]:
    """Ingest every PDF in docs_dir. Returns counts of added/updated/skipped files."""
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    stats = {"added": 0, "updated": 0, "skipped": 0, "chunks": 0}

    for pdf in sorted(docs_dir.glob("*.pdf")):
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        row = con.execute("SELECT doc_id, sha256 FROM document WHERE file_name = ?", (pdf.name,)).fetchone()
        if row and row[1] == digest:
            stats["skipped"] += 1
            continue

        reader = PdfReader(pdf)
        pages = [page.extract_text() or "" for page in reader.pages]
        title = (reader.metadata.title if reader.metadata else None) or pdf.stem
        fund = FUND_CODE.search(pdf.name) or FUND_CODE.search(" ".join(pages))
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if row:
            con.execute("DELETE FROM document WHERE doc_id = ?", (row[0],))
            stats["updated"] += 1
        else:
            stats["added"] += 1
        doc_id = con.execute(
            "INSERT INTO document (file_name, title, fund_code, pages, sha256, ingested_at) VALUES (?,?,?,?,?,?)",
            (pdf.name, title, fund.group(1) if fund else None, len(pages), digest, now),
        ).lastrowid

        for page_no, text in enumerate(pages, start=1):
            for chunk_no, chunk in enumerate(_chunk_page(text), start=1):
                if chunk.strip() == title.strip():
                    continue  # skip the bare title line
                con.execute(
                    "INSERT INTO chunk (doc_id, page, chunk_no, text) VALUES (?,?,?,?)",
                    (doc_id, page_no, chunk_no, chunk),
                )
                stats["chunks"] += 1

    con.commit()
    con.close()
    return stats


# ---------------------------------------------------------------- retrieval
def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()) if t not in STOPWORDS]


def _connect(db_path: Path = DOCS_DB) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError("docs.db not found. Run: python ingest_docs.py")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def list_documents(db_path: Path = DOCS_DB) -> list[dict[str, Any]]:
    with _connect(db_path) as con:
        return [
            dict(r)
            for r in con.execute(
                "SELECT d.file_name, d.title, d.fund_code, d.pages, d.ingested_at, COUNT(c.chunk_id) AS chunks "
                "FROM document d LEFT JOIN chunk c USING (doc_id) GROUP BY d.doc_id ORDER BY d.file_name"
            )
        ]


def search(
    query: str, top_k: int = 5, fund_code: str | None = None, db_path: Path = DOCS_DB, k1: float = 1.5, b: float = 0.75
) -> list[dict[str, Any]]:
    """BM25 search over chunks. Optional fund_code filter. Returns ranked chunks with citations."""
    sql = (
        "SELECT c.chunk_id, c.page, c.text, d.file_name, d.title, d.fund_code "
        "FROM chunk c JOIN document d USING (doc_id)"
    )
    params: tuple = ()
    if fund_code:
        sql += " WHERE d.fund_code = ?"
        params = (fund_code,)
    with _connect(db_path) as con:
        rows = [dict(r) for r in con.execute(sql, params)]
    if not rows:
        return []

    docs = [_tokens(r["text"]) for r in rows]
    n = len(docs)
    avgdl = sum(map(len, docs)) / n
    df = Counter(t for d in docs for t in set(d))
    q_terms = _tokens(query)

    scored = []
    for row, toks in zip(rows, docs):
        tf = Counter(toks)
        score = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(toks) / avgdl))
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "rank": i,
            "score": round(s, 3),
            "text": r["text"],
            "citation": {"file": r["file_name"], "page": r["page"], "title": r["title"], "fund_code": r["fund_code"]},
        }
        for i, (s, r) in enumerate(scored[:top_k], start=1)
    ]
