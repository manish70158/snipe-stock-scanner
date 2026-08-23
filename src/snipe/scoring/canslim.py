"""CANSLIM scoring adapted for Indian markets."""

import pandas as pd
import numpy as np

from snipe.config import load_config
from snipe.scanning.trend_template import compute_sma


def score_c_criterion(
    eps_growth_qoq: float | None,
    revenue_growth_qoq: float | None = None,
    prev_eps_growth: float | None = None,
    config: dict | None = None,
) -> dict:
    """C — Current Quarterly Earnings (QoQ YoY ≥ 20%).

    Args:
        eps_growth_qoq: QoQ EPS growth percentage.
        revenue_growth_qoq: Optional revenue growth for supporting signal.
        prev_eps_growth: Previous quarter's growth for acceleration check.

    Returns:
        Dict with c_criterion, eps_growth_qoq, eps_decelerating.
    """
    if config is None:
        config = load_config()

    threshold = config["canslim"]["min_eps_growth_qoq_pct"]

    if eps_growth_qoq is None:
        return {"c_criterion": "data_unavailable", "eps_growth_qoq": None}

    passes = eps_growth_qoq >= threshold
    decelerating = (
        prev_eps_growth is not None
        and eps_growth_qoq < prev_eps_growth
    )

    return {
        "c_criterion": passes,
        "eps_growth_qoq": round(eps_growth_qoq, 1),
        "revenue_growth_qoq": round(revenue_growth_qoq, 1) if revenue_growth_qoq else None,
        "eps_decelerating": decelerating,
    }


def score_a_criterion(
    eps_cagr_3yr: float | None,
    roe: float | None,
    config: dict | None = None,
) -> dict:
    """A — Annual Earnings Growth (3yr CAGR ≥ 25%, ROE ≥ 17%).

    Args:
        eps_cagr_3yr: 3-year EPS CAGR percentage.
        roe: Return on Equity percentage.

    Returns:
        Dict with a_criterion result.
    """
    if config is None:
        config = load_config()

    cagr_threshold = config["canslim"]["min_eps_cagr_3yr_pct"]
    roe_threshold = config["canslim"]["min_roe_pct"]

    if eps_cagr_3yr is None:
        return {"a_criterion": "data_unavailable", "eps_cagr_3yr": None, "roe": roe}

    passes = eps_cagr_3yr >= cagr_threshold and (roe is None or roe >= roe_threshold)

    return {
        "a_criterion": passes,
        "eps_cagr_3yr": round(eps_cagr_3yr, 1),
        "roe": round(roe, 1) if roe else None,
    }


def score_n_criterion(
    current_price: float,
    high_52w: float,
    config: dict | None = None,
) -> dict:
    """N — New (52-week high as quantitative proxy).

    Args:
        current_price: Current stock price.
        high_52w: 52-week high price.

    Returns:
        Dict with n_criterion result.
    """
    if config is None:
        config = load_config()

    # Stock is at or near 52-week high (within 5% counts)
    pct_from_high = ((high_52w - current_price) / high_52w) * 100 if high_52w > 0 else 100
    passes = pct_from_high <= 5  # Within 5% of 52W high

    catalyst = "new_52w_high" if pct_from_high <= 1 else "near_52w_high" if passes else "none"

    return {
        "n_criterion": passes,
        "pct_from_52w_high": round(pct_from_high, 1),
        "catalyst": catalyst,
    }


def score_s_criterion(
    df: pd.DataFrame,
    shares_outstanding: float | None = None,
    config: dict | None = None,
) -> dict:
    """S — Supply/Demand (accumulation vs distribution days).

    Args:
        df: Price/volume DataFrame (last 50+ days).
        shares_outstanding: Float in crores (optional).

    Returns:
        Dict with s_criterion result.
    """
    if config is None:
        config = load_config()

    lookback = config["canslim"]["accum_dist_lookback_days"]

    if len(df) < lookback:
        return {"s_criterion": "data_unavailable"}

    recent = df.tail(lookback)
    close = recent["close"].astype(float)
    volume = recent["volume"].astype(float)

    # Count accumulation days (close up on above-avg volume) vs distribution
    avg_vol = volume.mean()
    price_change = close.diff()

    accum_days = ((price_change > 0) & (volume > avg_vol)).sum()
    dist_days = ((price_change < 0) & (volume > avg_vol)).sum()

    passes = accum_days > dist_days

    return {
        "s_criterion": bool(passes),
        "accumulation_days": int(accum_days),
        "distribution_days": int(dist_days),
        "float_crore": shares_outstanding,
    }


def score_l_criterion(
    rs_percentile: float,
    config: dict | None = None,
) -> dict:
    """L — Leader (RS rank in top 20%).

    Args:
        rs_percentile: Stock's RS percentile (0-100).

    Returns:
        Dict with l_criterion result.
    """
    if config is None:
        config = load_config()

    threshold = config["canslim"]["leader_rs_percentile"]
    passes = rs_percentile >= threshold

    return {
        "l_criterion": passes,
        "rs_rank_percentile": round(rs_percentile, 1),
    }


def score_i_criterion(
    fii_change: float | None,
    dii_change: float | None = None,
    mf_schemes_change: int | None = None,
) -> dict:
    """I — Institutional Sponsorship (FII+DII increasing).

    Args:
        fii_change: Change in FII holding (%) over 2 quarters.
        dii_change: Change in DII holding (%) over 2 quarters.
        mf_schemes_change: Change in number of MF schemes.

    Returns:
        Dict with i_criterion result.
    """
    if fii_change is None and dii_change is None:
        return {"i_criterion": "data_unavailable"}

    fii = fii_change or 0
    dii = dii_change or 0
    net_change = fii + dii

    passes = net_change > 0

    trend = "increasing" if passes else "declining"

    return {
        "i_criterion": passes,
        "fii_change": round(fii, 2) if fii_change else None,
        "dii_change": round(dii, 2) if dii_change else None,
        "mf_schemes_change": mf_schemes_change,
        "institutional_trend": trend,
    }


def score_m_criterion(
    index_prices: pd.DataFrame,
    config: dict | None = None,
) -> dict:
    """M — Market Direction (Nifty 500 above rising 150-day MA).

    Args:
        index_prices: DataFrame with 'close' column for Nifty 500 index.

    Returns:
        Dict with m_criterion result.
    """
    if config is None:
        config = load_config()

    if len(index_prices) < 150:
        return {"m_criterion": "data_unavailable"}

    close = index_prices["close"].astype(float)
    sma_150 = compute_sma(close, 150)

    current_price = close.iloc[-1]
    current_ma = sma_150.iloc[-1]

    # MA slope over 22 days
    ma_recent = sma_150.tail(23).dropna()
    ma_rising = ma_recent.iloc[-1] > ma_recent.iloc[0] if len(ma_recent) >= 2 else False

    above_ma = current_price > current_ma
    passes = above_ma and ma_rising

    return {
        "m_criterion": passes,
        "index_price": round(current_price, 2),
        "index_ma150": round(current_ma, 2),
        "index_above_ma": above_ma,
        "ma_rising": ma_rising,
    }


def compute_canslim_score(criteria: dict) -> dict:
    """Compute composite CANSLIM score (0-7).

    Args:
        criteria: Dict with all criterion results (c through m).

    Returns:
        Dict with canslim_score and fundamentally_qualified.
    """
    score = 0
    for key in ["c_criterion", "a_criterion", "n_criterion", "s_criterion",
                "l_criterion", "i_criterion", "m_criterion"]:
        val = criteria.get(key)
        if val is True:
            score += 1
        # "data_unavailable" does not count against

    return {
        "canslim_score": score,
        "fundamentally_qualified": score >= 5,
    }
