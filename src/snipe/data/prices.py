"""Daily OHLCV price data fetcher using Yahoo Finance."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from snipe.config import load_config
from snipe.database import get_db, init_db


def fetch_stock_prices(
    symbol: str,
    period: str = "1y",
    suffix: str = ".NS",
) -> pd.DataFrame:
    """Fetch daily OHLCV data for a single stock from Yahoo Finance.

    Args:
        symbol: NSE stock symbol (e.g., "RELIANCE").
        period: Data period (default "1y" for 1 year).
        suffix: Yahoo Finance suffix for exchange (default ".NS" for NSE).

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, adj_close.
    """
    ticker = yf.Ticker(f"{symbol}{suffix}")
    df = ticker.history(period=period, auto_adjust=False)

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "Adj Close": "adj_close",
    })

    # Ensure date is string format (YYYY-MM-DD)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = symbol

    return df[["symbol", "date", "open", "high", "low", "close", "volume", "adj_close"]]


def store_prices(df: pd.DataFrame, db_path: Path | None = None) -> int:
    """Store price data in the database.

    Args:
        df: DataFrame with price data (symbol, date, open, high, low, close, volume, adj_close).
        db_path: Optional database path.

    Returns:
        Number of rows stored.
    """
    if df.empty:
        return 0

    conn = init_db(db_path)

    rows = df.to_dict("records")
    for row in rows:
        conn.execute(
            """INSERT OR REPLACE INTO daily_prices
               (symbol, date, open, high, low, close, volume, adj_close)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["symbol"], row["date"], row["open"], row["high"],
             row["low"], row["close"], row["volume"], row.get("adj_close")),
        )

    conn.commit()
    conn.close()
    return len(rows)


def fetch_and_store_prices(
    symbols: list[str],
    period: str = "1y",
    db_path: Path | None = None,
    progress_callback=None,
) -> dict:
    """Fetch and store prices for multiple symbols.

    Args:
        symbols: List of NSE stock symbols.
        period: Data period.
        db_path: Optional database path.
        progress_callback: Optional callable(symbol, i, total) for progress.

    Returns:
        Dict with counts: {"success": N, "failed": N, "total_rows": N}
    """
    config = load_config()
    suffix = config["data"]["yfinance_suffix"]
    success = 0
    failed = 0
    total_rows = 0

    for i, symbol in enumerate(symbols):
        try:
            df = fetch_stock_prices(symbol, period=period, suffix=suffix)
            if not df.empty:
                rows = store_prices(df, db_path)
                total_rows += rows
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        if progress_callback:
            progress_callback(symbol, i + 1, len(symbols))

    return {"success": success, "failed": failed, "total_rows": total_rows}


def get_stock_prices(
    symbol: str,
    days: int = 252,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Get stored price data for a stock from the database.

    Args:
        symbol: Stock symbol.
        days: Number of most recent trading days to retrieve.
        db_path: Optional database path.

    Returns:
        DataFrame with price data, sorted by date ascending.
    """
    conn = init_db(db_path)
    query = """
        SELECT symbol, date, open, high, low, close, volume, adj_close
        FROM daily_prices
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(symbol, days))
    conn.close()

    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)

    return df
