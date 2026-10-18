"""Create a small private-markets portfolio database (SQLite) for the MCP server.

The data is synthetic. A few data-quality problems are planted on purpose
(a missing value, a duplicate cashflow, a stale NAV snapshot) so the
check_data_quality tool has something real to find.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "portfolio.db"


def seed(db_path: Path = DB_PATH) -> None:
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.executescript(
        """
        CREATE TABLE fund (
            fund_code     TEXT PRIMARY KEY,
            fund_name     TEXT NOT NULL,
            asset_class   TEXT NOT NULL,          -- Private Equity / Private Credit / Infrastructure
            vintage_year  INTEGER,
            base_currency TEXT NOT NULL
        );

        CREATE TABLE cashflow (
            cashflow_id   INTEGER PRIMARY KEY,
            fund_code     TEXT NOT NULL REFERENCES fund(fund_code),
            cashflow_date TEXT NOT NULL,          -- ISO date
            cashflow_type TEXT NOT NULL,          -- Contribution / Distribution
            amount_local  REAL,
            currency      TEXT NOT NULL,
            amount_cad    REAL,
            source_file   TEXT                    -- which fund-administrator file it came from
        );

        CREATE TABLE nav_snapshot (
            fund_code   TEXT NOT NULL REFERENCES fund(fund_code),
            as_of_date  TEXT NOT NULL,
            nav_local   REAL NOT NULL,
            nav_cad     REAL NOT NULL,
            PRIMARY KEY (fund_code, as_of_date)
        );
        """
    )

    funds = [
        ("PE-IV", "Northbridge Private Equity IV", "Private Equity", 2019, "USD"),
        ("PC-II", "Lakeshore Private Credit II", "Private Credit", 2021, "CAD"),
        ("INF-I", "Harbour Infrastructure I", "Infrastructure", 2018, "USD"),
    ]
    cur.executemany("INSERT INTO fund VALUES (?,?,?,?,?)", funds)

    cashflows = [
        (1, "PE-IV", "2025-03-31", "Contribution", -5_000_000, "USD", -6_850_000, "citco_2025Q1.csv"),
        (2, "PE-IV", "2025-06-30", "Contribution", -3_000_000, "USD", -4_110_000, "citco_2025Q2.csv"),
        (3, "PE-IV", "2025-12-31", "Distribution", 2_500_000, "USD", 3_450_000, "citco_2025Q4.csv"),
        (4, "PC-II", "2025-03-31", "Contribution", -8_000_000, "CAD", -8_000_000, "alterdomus_2025Q1.csv"),
        (5, "PC-II", "2025-09-30", "Distribution", 1_200_000, "CAD", 1_200_000, "alterdomus_2025Q3.csv"),
        # Planted issue: exact duplicate of cashflow 5 (same file loaded twice)
        (6, "PC-II", "2025-09-30", "Distribution", 1_200_000, "CAD", 1_200_000, "alterdomus_2025Q3.csv"),
        (7, "INF-I", "2025-06-30", "Contribution", -4_000_000, "USD", -5_480_000, "citco_2025Q2.csv"),
        # Planted issue: CAD amount missing (FX rate not available at load time)
        (8, "INF-I", "2026-03-31", "Distribution", 900_000, "USD", None, "citco_2026Q1.csv"),
    ]
    cur.executemany("INSERT INTO cashflow VALUES (?,?,?,?,?,?,?,?)", cashflows)

    navs = [
        ("PE-IV", "2026-06-30", 21_400_000, 29_318_000),
        ("PC-II", "2026-06-30", 15_800_000, 15_800_000),
        # Planted issue: INF-I has no NAV since 2025 (stale)
        ("INF-I", "2025-09-30", 18_200_000, 24_934_000),
    ]
    cur.executemany("INSERT INTO nav_snapshot VALUES (?,?,?,?)", navs)

    con.commit()
    con.close()
    print(f"Created {db_path}")


if __name__ == "__main__":
    seed()
