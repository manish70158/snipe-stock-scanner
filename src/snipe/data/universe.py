"""Nifty 500 constituent fetcher and universe management."""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from snipe.database import get_db, init_db


NIFTY500_CSV_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
CACHED_CSV_PATH = Path(__file__).parent.parent.parent.parent / "data" / "nifty500.csv"


def fetch_nifty500_from_nse() -> list[dict]:
    """Fetch Nifty 500 constituents from NSE India website.

    Returns:
        List of dicts with symbol, name, sector, industry fields.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "text/csv,text/plain,*/*",
    }

    try:
        resp = requests.get(NIFTY500_CSV_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        reader = csv.DictReader(lines)
        stocks = []
        for row in reader:
            stocks.append({
                "symbol": row.get("Symbol", "").strip(),
                "name": row.get("Company Name", "").strip(),
                "sector": row.get("Industry", "").strip(),
                "industry": row.get("Industry", "").strip(),
            })
        return [s for s in stocks if s["symbol"]]
    except Exception as e:
        print(f"Failed to fetch from NSE: {e}. Trying cached CSV...")
        return fetch_nifty500_from_cache()


def fetch_nifty500_from_cache() -> list[dict]:
    """Load Nifty 500 from cached CSV file.

    Returns:
        List of dicts with symbol, name, sector fields.
    """
    if not CACHED_CSV_PATH.exists():
        raise FileNotFoundError(
            f"No cached Nifty 500 list at {CACHED_CSV_PATH}. "
            "Please download from https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        )

    stocks = []
    with open(CACHED_CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            stocks.append({
                "symbol": row.get("Symbol", "").strip(),
                "name": row.get("Company Name", "").strip(),
                "sector": row.get("Industry", "").strip(),
                "industry": row.get("Industry", "").strip(),
            })
    return [s for s in stocks if s["symbol"]]


def store_universe(stocks: list[dict], db_path: Path | None = None) -> int:
    """Store stock universe in the database.

    Args:
        stocks: List of stock dicts with symbol, name, sector, industry.
        db_path: Optional database path.

    Returns:
        Number of stocks stored.
    """
    conn = init_db(db_path)
    now = datetime.now().isoformat()

    for stock in stocks:
        conn.execute(
            """INSERT OR REPLACE INTO stocks (symbol, name, sector, industry, added_date, last_updated)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (stock["symbol"], stock["name"], stock["sector"],
             stock.get("industry", ""), now, now),
        )

    conn.commit()
    conn.close()
    return len(stocks)


def get_universe(db_path: Path | None = None) -> list[dict]:
    """Get current stock universe from database.

    Returns:
        List of stock dicts.
    """
    conn = get_db(db_path)
    cursor = conn.execute("SELECT symbol, name, sector, industry FROM stocks ORDER BY symbol")
    stocks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return stocks


def refresh_universe(db_path: Path | None = None) -> int:
    """Fetch and store the latest Nifty 500 universe.

    Returns:
        Number of stocks in the refreshed universe.
    """
    stocks = fetch_nifty500_from_nse()
    if not stocks:
        stocks = fetch_nifty500_from_cache()
    return store_universe(stocks, db_path)
