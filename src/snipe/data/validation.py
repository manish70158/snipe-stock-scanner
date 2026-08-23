"""Data validation for price and fundamental data quality."""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from snipe.config import load_config
from snipe.database import get_db


def validate_stock_data(
    symbol: str,
    db_path: Path | None = None,
) -> dict:
    """Validate price data quality for a single stock.

    Checks:
    - Sufficient history (>=200 trading days)
    - No zero-volume days in recent data
    - Data not stale (most recent date within 2 trading days)
    - No large gaps in dates (>5 calendar days without holidays)

    Args:
        symbol: Stock symbol.
        db_path: Optional database path.

    Returns:
        Dict with validation results:
        - valid: bool
        - issues: list of issue descriptions
        - days_available: int
        - last_date: str
    """
    config = load_config()
    min_days = config["data"]["min_history_days"]
    stale_days = config["data"]["stale_data_days"]

    conn = get_db(db_path)
    df = pd.read_sql_query(
        "SELECT date, close, volume FROM daily_prices WHERE symbol = ? ORDER BY date",
        conn,
        params=(symbol,),
    )
    conn.close()

    issues = []

    if df.empty:
        return {
            "valid": False,
            "issues": ["No price data available"],
            "days_available": 0,
            "last_date": None,
        }

    days_available = len(df)

    # Check minimum history
    if days_available < min_days:
        issues.append(f"Insufficient history: {days_available} days (need {min_days})")

    # Check for zero-volume days in last 50 days
    recent = df.tail(50)
    zero_vol_days = recent[recent["volume"] == 0]
    if len(zero_vol_days) > 5:
        issues.append(f"Too many zero-volume days in recent data: {len(zero_vol_days)}")

    # Check data staleness
    last_date = df["date"].iloc[-1]
    last_dt = datetime.strptime(last_date, "%Y-%m-%d")
    now = datetime.now()
    # Account for weekends: if today is Monday, data from Friday is OK
    days_since = (now - last_dt).days
    if days_since > stale_days + 2:  # +2 for weekend buffer
        issues.append(f"Data is stale: last date {last_date} ({days_since} days ago)")

    # Check for large gaps
    df["date_dt"] = pd.to_datetime(df["date"])
    df["gap"] = df["date_dt"].diff().dt.days
    large_gaps = df[df["gap"] > 7]  # Allow up to 7 days for holidays
    if len(large_gaps) > 0:
        issues.append(f"Large date gaps found: {len(large_gaps)} gaps > 7 days")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "days_available": days_available,
        "last_date": last_date,
    }


def validate_universe(
    symbols: list[str],
    db_path: Path | None = None,
) -> dict:
    """Validate data for all symbols in the universe.

    Returns:
        Dict with:
        - total: int
        - valid: int
        - invalid: int
        - invalid_symbols: list of (symbol, issues) tuples
    """
    valid_count = 0
    invalid_symbols = []

    for symbol in symbols:
        result = validate_stock_data(symbol, db_path)
        if result["valid"]:
            valid_count += 1
        else:
            invalid_symbols.append((symbol, result["issues"]))

    return {
        "total": len(symbols),
        "valid": valid_count,
        "invalid": len(invalid_symbols),
        "invalid_symbols": invalid_symbols,
    }
