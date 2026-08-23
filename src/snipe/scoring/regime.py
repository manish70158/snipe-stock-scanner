"""Market regime detection and classification."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from snipe.config import load_config
from snipe.scanning.trend_template import compute_sma
from snipe.database import get_db, init_db


def compute_breadth(
    all_stocks_prices: dict[str, pd.DataFrame],
) -> dict:
    """Compute market breadth indicators for Nifty 500 universe.

    Args:
        all_stocks_prices: Dict of symbol -> DataFrame with 'close' column.

    Returns:
        Dict with breadth_50dma, breadth_200dma percentages.
    """
    above_50dma = 0
    above_200dma = 0
    total = 0

    for symbol, df in all_stocks_prices.items():
        if len(df) < 200:
            continue

        close = df["close"].astype(float)
        current = close.iloc[-1]

        sma_50 = compute_sma(close, 50).iloc[-1]
        sma_200 = compute_sma(close, 200).iloc[-1]

        if not pd.isna(sma_50) and not pd.isna(sma_200):
            total += 1
            if current > sma_50:
                above_50dma += 1
            if current > sma_200:
                above_200dma += 1

    if total == 0:
        return {"breadth_50dma": 0, "breadth_200dma": 0, "total_stocks": 0}

    return {
        "breadth_50dma": round((above_50dma / total) * 100, 1),
        "breadth_200dma": round((above_200dma / total) * 100, 1),
        "total_stocks": total,
        "above_50dma_count": above_50dma,
        "above_200dma_count": above_200dma,
    }


def assess_index_trend(index_prices: pd.DataFrame) -> dict:
    """Assess Nifty 500 index trend.

    Args:
        index_prices: DataFrame with 'close' column for the index.

    Returns:
        Dict with index trend assessment.
    """
    if len(index_prices) < 150:
        return {"index_trend": "unknown", "index_vs_150dma_pct": 0, "ma_slope": "unknown"}

    close = index_prices["close"].astype(float)
    sma_150 = compute_sma(close, 150)

    current = close.iloc[-1]
    current_ma = sma_150.iloc[-1]

    pct_from_ma = ((current - current_ma) / current_ma) * 100

    # Slope assessment
    ma_recent = sma_150.tail(23).dropna()
    if len(ma_recent) >= 2:
        slope_pct = ((ma_recent.iloc[-1] / ma_recent.iloc[0]) - 1) * 100
        if slope_pct > 1.0:
            ma_slope = "rising"
        elif slope_pct < -1.0:
            ma_slope = "falling"
        else:
            ma_slope = "flat"
    else:
        ma_slope = "unknown"

    # Trend classification
    if current > current_ma and ma_slope == "rising":
        trend = "uptrend"
    elif current > current_ma and ma_slope in ("flat", "falling"):
        trend = "weakening"
    elif current < current_ma and ma_slope in ("falling", "flat"):
        trend = "downtrend"
    else:
        trend = "breakdown"

    return {
        "index_trend": trend,
        "index_vs_150dma_pct": round(pct_from_ma, 2),
        "index_price": round(current, 2),
        "index_ma150": round(current_ma, 2),
        "ma_slope": ma_slope,
    }


def classify_regime(
    breadth: dict,
    index_trend: dict,
    fii_flow: dict,
    config: dict | None = None,
) -> dict:
    """Classify market into GREEN/YELLOW/RED regime.

    Args:
        breadth: Output from compute_breadth.
        index_trend: Output from assess_index_trend.
        fii_flow: Output from compute_rolling_fii_flow.
        config: Optional config.

    Returns:
        Dict with regime classification and supporting data.
    """
    if config is None:
        config = load_config()

    mr_config = config["market_regime"]

    breadth_50 = breadth.get("breadth_50dma", 0)
    trend = index_trend.get("index_trend", "unknown")
    ma_slope = index_trend.get("ma_slope", "unknown")
    fii_status = fii_flow.get("fii_flow_status", "no_data")

    # GREEN: Index above rising 150-MA AND breadth >= 60% AND FII buying
    index_bullish = trend in ("uptrend",) and ma_slope == "rising"
    breadth_healthy = breadth_50 >= mr_config["green_breadth_50dma_min"]
    fii_positive = fii_status == "net_buying"

    # RED: Index below declining 150-MA AND breadth < 40%
    index_bearish = trend in ("downtrend", "breakdown") and ma_slope == "falling"
    breadth_weak = breadth_50 < mr_config["red_breadth_50dma_max"]

    if index_bullish and breadth_healthy and fii_positive:
        regime = "green"
    elif index_bearish and breadth_weak:
        regime = "red"
    elif index_bearish or breadth_weak:
        regime = "red" if (index_bearish and breadth_weak) else "yellow"
    else:
        regime = "yellow"

    # Breadth divergence detection
    index_near_high = index_trend.get("index_vs_150dma_pct", 0) > 3
    breadth_divergence = index_near_high and breadth_50 < 50

    return {
        "regime": regime,
        "breadth_50dma": breadth_50,
        "breadth_200dma": breadth.get("breadth_200dma", 0),
        "index_trend": trend,
        "ma_slope": ma_slope,
        "fii_flow_status": fii_status,
        "fii_net_20d": fii_flow.get("fii_net_20d", 0),
        "breadth_divergence": breadth_divergence,
        "sizing_multiplier": mr_config[f"{regime}_sizing_multiplier"],
    }


def compute_sector_rankings(
    stock_returns: dict[str, float],
    sector_map: dict[str, str],
    top_pct: int = 30,
) -> dict:
    """Rank sectors by median 6-month return of constituent stocks.

    Args:
        stock_returns: Dict of symbol -> 6-month return (%).
        sector_map: Dict of symbol -> sector name.
        top_pct: Top N% of sectors considered "leading".

    Returns:
        Dict with:
        - sector_ranks: {sector_name: percentile_rank}
        - leading_sectors: list of sector names in top N%
        - sector_returns: {sector_name: median_return}
    """
    # Group returns by sector
    sector_stocks: dict[str, list[float]] = {}
    for symbol, ret in stock_returns.items():
        sector = sector_map.get(symbol, "Unknown")
        if sector not in sector_stocks:
            sector_stocks[sector] = []
        sector_stocks[sector].append(ret)

    # Compute median return per sector
    sector_returns = {}
    for sector, returns in sector_stocks.items():
        if returns:
            sector_returns[sector] = float(np.median(returns))

    if not sector_returns:
        return {
            "sector_ranks": {},
            "leading_sectors": [],
            "sector_returns": {},
        }

    # Rank sectors by median return (higher = better rank)
    sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
    total_sectors = len(sorted_sectors)

    sector_ranks = {}
    for i, (sector, _) in enumerate(sorted_sectors):
        # Percentile rank: 100 = best sector, 0 = worst
        sector_ranks[sector] = round((1 - i / max(total_sectors - 1, 1)) * 100, 1)

    # Leading sectors: top N%
    cutoff_idx = max(1, int(total_sectors * top_pct / 100))
    leading_sectors = [s for s, _ in sorted_sectors[:cutoff_idx]]

    return {
        "sector_ranks": sector_ranks,
        "leading_sectors": leading_sectors,
        "sector_returns": sector_returns,
    }


def detect_regime_change(
    current_regime: str,
    previous_regime: str | None,
    trigger_reason: str = "",
    db_path: Path | None = None,
) -> dict | None:
    """Detect and log a regime transition.

    Returns:
        Transition dict if regime changed, None if same.
    """
    if previous_regime is None or current_regime == previous_regime:
        return None

    transition = {
        "from": previous_regime,
        "to": current_regime,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "trigger_reason": trigger_reason,
    }

    # Log to database
    if db_path:
        conn = init_db(db_path)
        conn.execute(
            """INSERT INTO regime_history
               (date, regime, previous_regime, transition_reason)
               VALUES (?, ?, ?, ?)""",
            (transition["date"], current_regime, previous_regime, trigger_reason),
        )
        conn.commit()
        conn.close()

    return transition
