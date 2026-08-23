"""10-Point Trend Template validation (Mark Minervini SEPA criteria)."""

import numpy as np
import pandas as pd

from snipe.config import load_config


def compute_sma(prices: pd.Series, period: int) -> pd.Series:
    """Compute Simple Moving Average.

    Args:
        prices: Series of closing prices.
        period: Number of periods for SMA.

    Returns:
        Series with SMA values.
    """
    return prices.rolling(window=period, min_periods=period).mean()


def compute_relative_strength(
    stock_prices: pd.Series,
    index_prices: pd.Series,
    lookback: int = 126,
) -> float:
    """Compute 6-month relative strength of stock vs index.

    Args:
        stock_prices: Series of stock closing prices (at least 126 days).
        index_prices: Series of index closing prices (same period).
        lookback: Number of trading days (default 126 = 6 months).

    Returns:
        RS value (stock_6m_return / index_6m_return * 100).
    """
    if len(stock_prices) < lookback or len(index_prices) < lookback:
        return 0.0

    stock_return = (stock_prices.iloc[-1] / stock_prices.iloc[-lookback] - 1) * 100
    index_return = (index_prices.iloc[-1] / index_prices.iloc[-lookback] - 1) * 100

    if index_return == 0:
        return stock_return

    return (stock_return / index_return) * 100 if index_return != 0 else 0.0


def rank_relative_strength(
    stock_returns: dict[str, float],
) -> dict[str, float]:
    """Rank all stocks by relative strength and return percentiles.

    Args:
        stock_returns: Dict of symbol -> 12-month return.

    Returns:
        Dict of symbol -> RS percentile (0-100).
    """
    if not stock_returns:
        return {}

    sorted_symbols = sorted(stock_returns.keys(), key=lambda s: stock_returns[s])
    n = len(sorted_symbols)

    percentiles = {}
    for i, symbol in enumerate(sorted_symbols):
        percentiles[symbol] = round((i / (n - 1)) * 100, 1) if n > 1 else 50.0

    return percentiles


def check_trend_template(
    df: pd.DataFrame,
    rs_percentile: float,
    config: dict | None = None,
) -> dict:
    """Evaluate a stock against the 10-point Trend Template.

    Args:
        df: DataFrame with columns: date, close (sorted by date ascending).
            Must have at least 200 rows.
        rs_percentile: Stock's RS percentile rank (0-100).
        config: Optional config dict. If None, loads from file.

    Returns:
        Dict with:
        - criteria: dict of criterion_1..criterion_10 -> bool
        - values: dict of computed values for each criterion
        - score: int (0-10)
        - trend_template_pass: bool (True only if score == 10)
    """
    if config is None:
        config = load_config()

    tt_config = config["trend_template"]

    if len(df) < 200:
        return {
            "criteria": {f"criterion_{i}": None for i in range(1, 11)},
            "values": {},
            "score": 0,
            "trend_template_pass": False,
            "insufficient_data": True,
        }

    close = df["close"].astype(float)
    current_price = close.iloc[-1]

    # Compute moving averages
    sma_50 = compute_sma(close, 50)
    sma_150 = compute_sma(close, 150)
    sma_200 = compute_sma(close, 200)

    current_sma50 = sma_50.iloc[-1]
    current_sma150 = sma_150.iloc[-1]
    current_sma200 = sma_200.iloc[-1]

    # 52-week (252 trading days) high and low
    lookback_252 = close.tail(252)
    high_52w = lookback_252.max()
    low_52w = lookback_252.min()

    # Criterion 1: Price above 150-day MA
    c1 = current_price > current_sma150

    # Criterion 2: Price above 200-day MA
    c2 = current_price > current_sma200

    # Criterion 3: 150-day MA above 200-day MA
    c3 = current_sma150 > current_sma200

    # Criterion 4: 200-day MA trending up for at least 22 trading days
    min_rising_days = tt_config["ma200_rising_min_days"]
    sma200_recent = sma_200.tail(min_rising_days + 1).dropna()
    c4 = False
    if len(sma200_recent) >= min_rising_days + 1:
        c4 = sma200_recent.iloc[-1] > sma200_recent.iloc[0]

    # Criterion 5: 50-day MA above 150-day MA
    c5 = current_sma50 > current_sma150

    # Criterion 6: 50-day MA above 200-day MA
    c6 = current_sma50 > current_sma200

    # Criterion 7: Price above 50-day MA
    c7 = current_price > current_sma50

    # Criterion 8: Price at least 30% above 52-week low
    min_above_low = tt_config["min_above_52w_low_pct"]
    pct_above_low = ((current_price - low_52w) / low_52w) * 100 if low_52w > 0 else 0
    c8 = pct_above_low >= min_above_low

    # Criterion 9: Price within 25% of 52-week high
    max_below_high = tt_config["max_below_52w_high_pct"]
    pct_below_high = ((high_52w - current_price) / high_52w) * 100 if high_52w > 0 else 0
    c9 = pct_below_high <= max_below_high

    # Criterion 10: RS ranking in top 30%
    rs_threshold = 100 - tt_config["rs_top_percentile"]  # top 30% means percentile >= 70
    c10 = rs_percentile >= rs_threshold

    criteria = {
        "criterion_1": bool(c1),
        "criterion_2": bool(c2),
        "criterion_3": bool(c3),
        "criterion_4": bool(c4),
        "criterion_5": bool(c5),
        "criterion_6": bool(c6),
        "criterion_7": bool(c7),
        "criterion_8": bool(c8),
        "criterion_9": bool(c9),
        "criterion_10": bool(c10),
    }

    values = {
        "current_price": round(current_price, 2),
        "sma_50": round(current_sma50, 2),
        "sma_150": round(current_sma150, 2),
        "sma_200": round(current_sma200, 2),
        "price_vs_150dma_pct": round(((current_price / current_sma150) - 1) * 100, 2),
        "price_vs_200dma_pct": round(((current_price / current_sma200) - 1) * 100, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "pct_above_52w_low": round(pct_above_low, 2),
        "pct_below_52w_high": round(pct_below_high, 2),
        "rs_percentile": round(rs_percentile, 1),
    }

    score = sum(1 for v in criteria.values() if v)

    return {
        "criteria": criteria,
        "values": values,
        "score": score,
        "trend_template_pass": score == 10,
        "insufficient_data": False,
    }


def batch_trend_template(
    stocks_data: dict[str, pd.DataFrame],
    rs_percentiles: dict[str, float],
    config: dict | None = None,
) -> list[dict]:
    """Run Trend Template scan across multiple stocks.

    Args:
        stocks_data: Dict of symbol -> DataFrame with price data.
        rs_percentiles: Dict of symbol -> RS percentile.
        config: Optional config.

    Returns:
        List of dicts with symbol + trend template results, filtered to passing stocks.
    """
    if config is None:
        config = load_config()

    results = []
    for symbol, df in stocks_data.items():
        rs = rs_percentiles.get(symbol, 50.0)
        result = check_trend_template(df, rs, config)
        result["symbol"] = symbol
        results.append(result)

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
