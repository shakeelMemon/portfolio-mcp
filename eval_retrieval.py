"""Evaluate retrieval quality against a labelled question set.

Metrics:
  Hit@1 / Hit@3  share of questions whose correct source (file + page) is ranked 1st / in the top 3
  MRR            mean reciprocal rank: 1/rank of the first correct result (0 if not found)

Questions marked "paraphrase" deliberately use words that do NOT appear in the
documents. Lexical search (BM25) tends to miss those; that gap is the main
reason production RAG adds embeddings (semantic / hybrid search).
"""

from rag import search

# (question, expected file, expected page, style)
EVAL_SET = [
    ("Which borrower breached its leverage covenant?", "PC-II_Q2-2026_Quarterly_Report.pdf", 2, "keyword"),
    ("What is the net IRR and TVPI of PE-IV?", "PE-IV_Q2-2026_Quarterly_Report.pdf", 1, "keyword"),
    ("Why was the port terminal valuation delayed?", "INF-I_Q3-2025_Quarterly_Report.pdf", 1, "keyword"),
    ("When must a NAV be flagged as stale?", "Valuation_Policy_2026.pdf", 1, "keyword"),
    ("Which FX rate is used to convert amounts to CAD?", "Valuation_Policy_2026.pdf", 2, "keyword"),
    ("What spread over CORRA do the loans pay?", "PC-II_Q2-2026_Quarterly_Report.pdf", 1, "keyword"),
    ("Which portfolio company was written down?", "PE-IV_Q2-2026_Quarterly_Report.pdf", 2, "keyword"),
    ("When does the USD 900,000 distribution settle?", "INF-I_Q3-2025_Quarterly_Report.pdf", 2, "keyword"),
    ("What happens if an administrator file gets loaded two times?", "Valuation_Policy_2026.pdf", 2, "paraphrase"),
    ("Is any debt investment currently not paying interest?", "PC-II_Q2-2026_Quarterly_Report.pdf", 2, "paraphrase"),
    ("How much money has the buyout fund given back to investors so far?", "PE-IV_Q2-2026_Quarterly_Report.pdf", 1, "paraphrase"),
    ("Who exceeded the borrowing ceiling agreed with lenders?", "PC-II_Q2-2026_Quarterly_Report.pdf", 2, "paraphrase"),
    ("Which holding got marked lower because fewer people visited?", "PE-IV_Q2-2026_Quarterly_Report.pdf", 2, "paraphrase"),
]


def evaluate(top_k: int = 5) -> dict:
    rows, rr_total, hit1, hit3 = [], 0.0, 0, 0
    for question, file, page, style in EVAL_SET:
        results = search(question, top_k=top_k)
        rank = next(
            (r["rank"] for r in results if r["citation"]["file"] == file and r["citation"]["page"] == page), None
        )
        rr = 1 / rank if rank else 0.0
        rr_total += rr
        hit1 += rank == 1
        hit3 += bool(rank and rank <= 3)
        rows.append((style, rank, question))

    n = len(EVAL_SET)
    print(f"{'style':11} {'rank':>4}  question")
    for style, rank, q in rows:
        print(f"{style:11} {rank if rank else '-':>4}  {q}")
    summary = {"questions": n, "hit@1": round(hit1 / n, 2), "hit@3": round(hit3 / n, 2), "mrr": round(rr_total / n, 2)}
    for style in ("keyword", "paraphrase"):
        sub = [r for r in rows if r[0] == style]
        summary[f"hit@3_{style}"] = round(sum(1 for r in sub if r[1] and r[1] <= 3) / len(sub), 2)
    print("\nSummary:", summary)
    return summary


if __name__ == "__main__":
    evaluate()
