"""Generate sample fund-report PDFs into docs/ (synthetic content).

Each document holds specific facts (rates, covenants, valuation notes) on
known pages, so retrieval can be evaluated against an answer key.
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

DOCS_DIR = Path(__file__).parent / "docs"

DOCUMENTS = {
    "PE-IV_Q2-2026_Quarterly_Report.pdf": (
        "Northbridge Private Equity IV - Q2 2026 Quarterly Report",
        [
            [
                "Fund overview. Northbridge Private Equity IV (fund code PE-IV) is a 2019 vintage buyout fund "
                "with USD 450 million of commitments. As of June 30, 2026 the fund is 82 percent called.",
                "Performance. Net IRR since inception is 14.2 percent and TVPI is 1.46x. DPI stands at 0.31x "
                "following the Q4 2025 distribution from the partial sale of Maple Logistics.",
            ],
            [
                "Portfolio update. The fund holds nine portfolio companies. Maple Logistics was written up by "
                "12 percent after a strong EBITDA quarter. Cedar Health Services was written down by 8 percent "
                "because of slower patient volumes in Ontario clinics.",
                "Outlook. The general partner expects one full exit in the first half of 2027 and does not "
                "plan further capital calls beyond management fees this year.",
            ],
        ],
    ),
    "PC-II_Q2-2026_Quarterly_Report.pdf": (
        "Lakeshore Private Credit II - Q2 2026 Quarterly Report",
        [
            [
                "Fund overview. Lakeshore Private Credit II (fund code PC-II) is a 2021 vintage senior secured "
                "lending fund with CAD 600 million of commitments, invested in 24 loans to mid-market borrowers.",
                "Income. The weighted average all-in yield on the portfolio is 10.8 percent, with loans priced "
                "at CORRA plus an average spread of 575 basis points.",
            ],
            [
                "Covenant monitoring. One borrower, Northern Fabrication Ltd, breached its maximum leverage "
                "covenant of 4.5x net debt to EBITDA, reporting 4.9x at quarter end. The fund granted a "
                "two-quarter waiver in exchange for a 50 basis point fee and tighter monthly reporting.",
                "Non-accruals. No loans are on non-accrual status. The watch list contains two borrowers, "
                "representing 6 percent of the portfolio.",
            ],
        ],
    ),
    "INF-I_Q3-2025_Quarterly_Report.pdf": (
        "Harbour Infrastructure I - Q3 2025 Quarterly Report",
        [
            [
                "Fund overview. Harbour Infrastructure I (fund code INF-I) is a 2018 vintage core-plus "
                "infrastructure fund with USD 380 million of commitments across toll roads, a regional port "
                "terminal and two renewable energy platforms.",
                "Valuation. The independent valuation of the port terminal has been delayed to Q2 2026 while "
                "the concession extension is negotiated. NAV for Q4 2025 and Q1 2026 will be carried forward "
                "at the Q3 2025 value until the valuation is complete.",
            ],
            [
                "Distributions. The fund paid a USD 900,000 distribution from toll road cash yield, scheduled "
                "for settlement on March 31, 2026. The CAD equivalent will be confirmed once the settlement "
                "FX rate is fixed by the administrator.",
            ],
        ],
    ),
    "Valuation_Policy_2026.pdf": (
        "Portfolio Valuation Policy - 2026",
        [
            [
                "Purpose. This policy sets out how private fund investments are valued for quarterly "
                "reporting to the investment committee and to plan members.",
                "Frequency. All fund NAVs must be updated at least quarterly. A NAV older than 120 days must "
                "be flagged as stale in reporting and escalated to the valuation committee.",
            ],
            [
                "Currency. Local-currency amounts are converted to CAD using the Bank of Canada daily exchange "
                "rate on the cashflow or NAV date. Missing FX rates must not be estimated; the record is held "
                "as pending until the official rate is available.",
                "Duplicates. If an administrator file is loaded twice, the duplicate cashflows must be removed "
                "before month-end reporting, and the incident logged in the data quality register.",
            ],
        ],
    ),
}


def build(out_dir: Path = DOCS_DIR) -> None:
    out_dir.mkdir(exist_ok=True)
    styles = getSampleStyleSheet()
    for filename, (title, pages) in DOCUMENTS.items():
        story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
        for i, paragraphs in enumerate(pages):
            if i:
                story.append(PageBreak())
            for p in paragraphs:
                story += [Paragraph(p, styles["BodyText"]), Spacer(1, 10)]
        SimpleDocTemplate(str(out_dir / filename), pagesize=letter, title=title).build(story)
        print(f"Created docs/{filename}")


if __name__ == "__main__":
    build()
