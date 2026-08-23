"""FII/DII daily cash market flow data fetcher."""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from snipe.database import get_db, init_db


def fetch_fii_dii_flows(days: int = 30) -> pd.DataFrame:
    """Fetch FII/DII daily cash market flows from MoneyControl or NSDL.

    Args:
        days: Number of days of flow data to fetch.

    Returns:
        DataFrame with columns: date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net.
    """
    # Try MoneyControl FII/DII data page
    url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/data.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.moneycontrol.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return _parse_moneycontrol_fii(data, days)
    except Exception:
        pass

    # Fallback: try NSDL provisional data
    try:
        return _fetch_nsdl_fii_dii(days)
    except Exception:
        pass

    # Return empty if both fail
    return pd.DataFrame(columns=["date", "fii_buy", "fii_sell", "fii_net",
                                  "dii_buy", "dii_sell", "dii_net"])


def _parse_moneycontrol_fii(data: dict, days: int) -> pd.DataFrame:
    """Parse MoneyControl JSON response for FII/DII data."""
    records = []

    if isinstance(data, dict) and "data" in data:
        entries = data["data"][:days]
        for entry in entries:
            records.append({
                "date": entry.get("date", ""),
                "fii_buy": float(entry.get("fii_buy", 0)),
                "fii_sell": float(entry.get("fii_sell", 0)),
                "fii_net": float(entry.get("fii_net", 0)),
                "dii_buy": float(entry.get("dii_buy", 0)),
                "dii_sell": float(entry.get("dii_sell", 0)),
                "dii_net": float(entry.get("dii_net", 0)),
            })

    return pd.DataFrame(records)


def _fetch_nsdl_fii_dii(days: int) -> pd.DataFrame:
    """Fetch FII/DII data from NSDL (fallback source)."""
    # NSDL provides FPI (FII) data
    url = "https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "dvDaily"})

    if not table:
        return pd.DataFrame()

    records = []
    rows = table.find_all("tr")[1:]  # Skip header

    for row in rows[:days]:
        cells = row.find_all("td")
        if len(cells) >= 5:
            try:
                records.append({
                    "date": cells[0].get_text(strip=True),
                    "fii_buy": float(cells[1].get_text(strip=True).replace(",", "")),
                    "fii_sell": float(cells[2].get_text(strip=True).replace(",", "")),
                    "fii_net": float(cells[3].get_text(strip=True).replace(",", "")),
                    "dii_buy": 0,
                    "dii_sell": 0,
                    "dii_net": 0,
                })
            except (ValueError, IndexError):
                continue

    return pd.DataFrame(records)


def store_fii_dii_flows(df: pd.DataFrame, db_path: Path | None = None) -> int:
    """Store FII/DII flow data in the database.

    Args:
        df: DataFrame with flow data.
        db_path: Optional database path.

    Returns:
        Number of rows stored.
    """
    if df.empty:
        return 0

    conn = init_db(db_path)

    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO fii_dii_flows
               (date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (row["date"], row.get("fii_buy", 0), row.get("fii_sell", 0),
             row.get("fii_net", 0), row.get("dii_buy", 0),
             row.get("dii_sell", 0), row.get("dii_net", 0)),
        )

    conn.commit()
    conn.close()
    return len(df)


def get_fii_flows(days: int = 20, db_path: Path | None = None) -> pd.DataFrame:
    """Get stored FII/DII flow data from database.

    Args:
        days: Number of most recent days.
        db_path: Optional database path.

    Returns:
        DataFrame with flow data.
    """
    conn = get_db(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM fii_dii_flows ORDER BY date DESC LIMIT ?",
        conn,
        params=(days,),
    )
    conn.close()
    return df.sort_values("date").reset_index(drop=True) if not df.empty else df


def compute_rolling_fii_flow(db_path: Path | None = None) -> dict:
    """Compute rolling 5-day and 20-day FII net flow.

    Returns:
        Dict with fii_net_5d, fii_net_20d, fii_flow_status.
    """
    df = get_fii_flows(20, db_path)

    if df.empty or len(df) < 5:
        return {"fii_net_5d": 0, "fii_net_20d": 0, "fii_flow_status": "no_data"}

    fii_net_5d = df.tail(5)["fii_net"].sum()
    fii_net_20d = df["fii_net"].sum()

    if fii_net_20d > 0:
        status = "net_buying"
    elif fii_net_20d < -10000:
        status = "heavy_selling"
    else:
        status = "net_selling"

    return {
        "fii_net_5d": round(fii_net_5d, 2),
        "fii_net_20d": round(fii_net_20d, 2),
        "fii_flow_status": status,
    }
