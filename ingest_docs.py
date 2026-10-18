"""Ingest the PDFs in docs/ into docs.db (idempotent: unchanged files are skipped)."""

from rag import ingest, list_documents

if __name__ == "__main__":
    stats = ingest()
    print(f"Added {stats['added']}, updated {stats['updated']}, skipped {stats['skipped']} "
          f"(unchanged); {stats['chunks']} new chunks.")
    for d in list_documents():
        print(f"  {d['file_name']:40} fund={d['fund_code'] or '-':6} pages={d['pages']} chunks={d['chunks']}")
