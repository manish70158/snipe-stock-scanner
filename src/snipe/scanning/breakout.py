"""Breakout detection with volume confirmation, HV1/HVE edge detection."""

import numpy as np
import pandas as pd

from snipe.config import load_config
from snipe.scanning.trend_template import compute_sma


def detect_breakout(
    df: pd.DataFrame,
    pivot_price: float,
    config: dict | None = None,
) -> dict:
    """Detect if a stock has broken out above its pivot point.

    Args:
        df: DataFrame with columns: date, close, high, low, volume (sorted by date asc).
        pivot_price: The breakout trigger price level.
        config: Optional config dict.

    Returns:
        Dict with breakout detection results.
    """
    if config is None:
        config = load_config()

    bo_config = config["breakout"]

    if len(df) < 50 or pivot_price <= 0:
        return _empty_breakout_result()

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    current_price = close.iloc[-1]
    current_volume = volume.iloc[-1]

    # 50-day average volume
    avg_volume_50 = volume.tail(50).mean()
    volume_ratio = current_volume / avg_volume_50 if avg_volume_50 > 0 else 0

    # Check if price closed above pivot
    min_above = bo_config["min_above_pivot_pct"] / 100
    pct_above_pivot = (current_price - pivot_price) / pivot_price

    breakout_detected = pct_above_pivot >= min_above

    # Volume confirmation
    min_vol_ratio = bo_config["min_volume_ratio"]
    volume_confirmed = volume_ratio >= min_vol_ratio

    # Breakout strength
    if breakout_detected and volume_confirmed:
        if volume_ratio >= 2.5:
            strength = "very_strong"
        elif volume_ratio >= 2.0:
            strength = "strong"
        else:
            strength = "confirmed"
    elif breakout_detected:
        strength = "unconfirmed"
    else:
        strength = "none"

    # HV1 Edge: highest volume in 50 days AND close in upper 60% of range
    # MD says 50 days, not 252, and requires close in upper 60% of day's range
    hv1_lookback = 50
    hv1_edge = False
    hve_edge = False

    if breakout_detected and len(volume) >= hv1_lookback:
        max_vol_50d = volume.tail(hv1_lookback).max()
        day_range = float(high.iloc[-1]) - float(low.iloc[-1])
        close_in_upper_60 = (
            current_price > (float(low.iloc[-1]) + 0.6 * day_range)
            if day_range > 0
            else False
        )
        hv1_edge = current_volume >= max_vol_50d and close_in_upper_60

    # HVE Edge: Gap up ≥5% with volume ≥2x 50DMA (post-earnings momentum proxy)
    # MD defines HVE as: "Stock gaps up or surges 5%+ on earnings day with volume ≥ 2x 50DMA"
    # Since we can't detect earnings day automatically, use gap up ≥5% as proxy
    if len(close) >= 2:
        gap_pct = ((current_price - float(close.iloc[-2])) / float(close.iloc[-2])) * 100
        hve_edge = gap_pct >= 5 and volume_ratio >= 2.0

    # Approaching breakout detection
    approaching_pct = bo_config["approaching_pct"] / 100
    distance_to_pivot = (pivot_price - current_price) / pivot_price
    approaching_breakout = (
        not breakout_detected
        and 0 < distance_to_pivot <= approaching_pct
    )

    return {
        "breakout_detected": bool(breakout_detected),
        "volume_confirmed": bool(volume_confirmed),
        "breakout_strength": strength,
        "volume_ratio": round(float(volume_ratio), 2),
        "pct_above_pivot": round(float(pct_above_pivot * 100), 2),
        "hv1_edge": bool(hv1_edge),
        "hve_edge": bool(hve_edge),
        "approaching_breakout": bool(approaching_breakout),
        "distance_to_pivot_pct": round(float(distance_to_pivot * 100), 2),
        "pivot_price": pivot_price,
        "current_price": round(float(current_price), 2),
        "avg_volume_50d": round(float(avg_volume_50), 0),
        "current_volume": round(float(current_volume), 0),
    }


def _empty_breakout_result() -> dict:
    return {
        "breakout_detected": False,
        "volume_confirmed": False,
        "breakout_strength": "none",
        "volume_ratio": 0,
        "pct_above_pivot": 0,
        "hv1_edge": False,
        "hve_edge": False,
        "approaching_breakout": False,
        "distance_to_pivot_pct": 0,
        "pivot_price": 0,
        "current_price": 0,
        "avg_volume_50d": 0,
        "current_volume": 0,
    }
