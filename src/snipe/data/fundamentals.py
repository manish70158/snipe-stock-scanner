"""Fundamental data fetcher for CANSLIM criteria (EPS, ROE, institutional holdings)."""

from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from snipe.database import get_db, init_db


def fetch_fundamentals_screener(symbol: str) -> dict | None:
    """Fetch fundamental data from Screener.in for a stock.

    Args:
        symbol: NSE stock symbol.

    Returns:
        Dict with quarterly EPS, annual EPS history, ROE, holdings data.
        None if fetch fails.
    """
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            # Try standalone (non-consolidated)
            url = f"https://www.screener.in/company/{symbol}/"
            resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    data = {}

    # Extract quarterly results table
    try:
        quarters_section = soup.find("section", {"id": "quarters"})
        if quarters_section:
            table = quarters_section.find("table")
            if table:
                data["quarterly"] = _parse_screener_table(table)
    except Exception:
        data["quarterly"] = {}

    # Extract annual profit & loss
    try:
        pl_section = soup.find("section", {"id": "profit-loss"})
        if pl_section:
            table = pl_section.find("table")
            if table:
                data["annual"] = _parse_screener_table(table)
    except Exception:
        data["annual"] = {}

    # Extract ratios (ROE)
    try:
        ratios = soup.find("section", {"id": "ratios"})
        if ratios:
            table = ratios.find("table")
            if table:
                data["ratios"] = _parse_screener_table(table)
    except Exception:
        data["ratios"] = {}

    # Extract shareholding
    try:
        sh_section = soup.find("section", {"id": "shareholding"})
        if sh_section:
            table = sh_section.find("table")
            if table:
                data["shareholding"] = _parse_screener_table(table)
    except Exception:
        data["shareholding"] = {}

    return data if data else None


def _parse_screener_table(table) -> dict:
    """Parse an HTML table from screener.in into dict format."""
    result = {}
    rows = table.find_all("tr")

    # First row may be headers (dates/periods)
    headers = []
    header_row = rows[0] if rows else None
    if header_row:
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        row_label = cells[0].get_text(strip=True)
        values = []
        for cell in cells[1:]:
            text = cell.get_text(strip=True).replace(",", "")
            try:
                values.append(float(text))
            except (ValueError, TypeError):
                values.append(text)
        result[row_label] = values

    if headers:
        result["_headers"] = headers

    return result


def extract_eps_growth(data: dict) -> dict:
    """Extract EPS and growth metrics from raw screener data.

    Returns:
        Dict with:
        - quarterly_eps: list of recent quarterly EPS values
        - annual_eps: list of recent annual EPS values
        - eps_growth_qoq: latest QoQ growth %
        - eps_cagr_3yr: 3-year EPS CAGR %
        - roe: latest ROE %
    """
    result = {
        "quarterly_eps": [],
        "annual_eps": [],
        "eps_growth_qoq": None,
        "eps_cagr_3yr": None,
        "roe": None,
    }

    # Extract quarterly EPS
    quarterly = data.get("quarterly", {})
    eps_row = quarterly.get("EPS in Rs", quarterly.get("EPS (in Rs)", []))
    if isinstance(eps_row, list) and len(eps_row) >= 5:
        result["quarterly_eps"] = eps_row[:8]
        # QoQ growth: compare latest quarter to same quarter last year (4 quarters back)
        if len(eps_row) >= 5 and eps_row[4] and eps_row[4] != 0:
            latest = eps_row[0] if isinstance(eps_row[0], (int, float)) else None
            year_ago = eps_row[4] if isinstance(eps_row[4], (int, float)) else None
            if latest is not None and year_ago is not None and year_ago > 0:
                result["eps_growth_qoq"] = ((latest - year_ago) / year_ago) * 100

    # Extract annual EPS for CAGR
    annual = data.get("annual", {})
    ann_eps = annual.get("EPS in Rs", annual.get("EPS (in Rs)", []))
    if isinstance(ann_eps, list) and len(ann_eps) >= 4:
        result["annual_eps"] = ann_eps[:5]
        # 3-year CAGR: compare most recent to 3 years ago
        latest_ann = ann_eps[0] if isinstance(ann_eps[0], (int, float)) else None
        three_yr = ann_eps[3] if isinstance(ann_eps[3], (int, float)) else None
        if latest_ann and three_yr and three_yr > 0:
            result["eps_cagr_3yr"] = ((latest_ann / three_yr) ** (1 / 3) - 1) * 100

    # Extract ROE
    ratios = data.get("ratios", {})
    roe_row = ratios.get("Return on Equity", ratios.get("ROE", []))
    if isinstance(roe_row, list) and len(roe_row) > 0:
        latest_roe = roe_row[0]
        if isinstance(latest_roe, (int, float)):
            result["roe"] = latest_roe

    return result


def extract_holdings(data: dict) -> dict:
    """Extract institutional holding data from raw screener data.

    Returns:
        Dict with fii_holding_pct, dii_holding_pct, promoter_holding_pct.
    """
    result = {
        "fii_holding_pct": None,
        "dii_holding_pct": None,
        "promoter_holding_pct": None,
        "fii_change": None,
    }

    shareholding = data.get("shareholding", {})

    # FII/FPI holdings
    for key in ["FIIs", "FII / FPI", "Foreign Institutions"]:
        if key in shareholding:
            vals = shareholding[key]
            if isinstance(vals, list) and len(vals) >= 1:
                result["fii_holding_pct"] = vals[0] if isinstance(vals[0], (int, float)) else None
                if len(vals) >= 2 and isinstance(vals[1], (int, float)):
                    result["fii_change"] = vals[0] - vals[1] if result["fii_holding_pct"] else None
            break

    # DII holdings
    for key in ["DIIs", "DII", "Domestic Institutions"]:
        if key in shareholding:
            vals = shareholding[key]
            if isinstance(vals, list) and len(vals) >= 1:
                result["dii_holding_pct"] = vals[0] if isinstance(vals[0], (int, float)) else None
            break

    # Promoter holdings
    for key in ["Promoters", "Promoter"]:
        if key in shareholding:
            vals = shareholding[key]
            if isinstance(vals, list) and len(vals) >= 1:
                result["promoter_holding_pct"] = vals[0] if isinstance(vals[0], (int, float)) else None
            break

    return result


def store_fundamentals(
    symbol: str,
    eps_data: dict,
    holdings_data: dict,
    db_path: Path | None = None,
) -> None:
    """Store fundamental data in the database.

    Args:
        symbol: Stock symbol.
        eps_data: EPS and growth data from extract_eps_growth.
        holdings_data: Institutional holdings from extract_holdings.
        db_path: Optional database path.
    """
    conn = init_db(db_path)
    now = datetime.now().isoformat()
    quarter = datetime.now().strftime("%Y-Q%q").replace(
        "%q", str((datetime.now().month - 1) // 3 + 1)
    )

    conn.execute(
        """INSERT OR REPLACE INTO fundamentals
           (symbol, quarter, eps_growth_qoq, eps_cagr_3yr, roe, fii_holding_pct,
            dii_holding_pct, promoter_holding_pct, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            symbol, quarter,
            eps_data.get("eps_growth_qoq"),
            eps_data.get("eps_cagr_3yr"),
            eps_data.get("roe"),
            holdings_data.get("fii_holding_pct"),
            holdings_data.get("dii_holding_pct"),
            holdings_data.get("promoter_holding_pct"),
            now,
        ),
    )
    conn.commit()
    conn.close()


def fetch_and_store_fundamentals(
    symbols: list[str],
    db_path: Path | None = None,
    progress_callback=None,
) -> dict:
    """Fetch and store fundamentals for multiple symbols.

    Returns:
        Dict with success/failed counts.
    """
    success = 0
    failed = 0

    for i, symbol in enumerate(symbols):
        try:
            raw = fetch_fundamentals_screener(symbol)
            if raw:
                eps_data = extract_eps_growth(raw)
                holdings_data = extract_holdings(raw)
                store_fundamentals(symbol, eps_data, holdings_data, db_path)
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        if progress_callback:
            progress_callback(symbol, i + 1, len(symbols))

    return {"success": success, "failed": failed}
