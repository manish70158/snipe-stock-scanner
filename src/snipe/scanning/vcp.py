"""Volatility Contraction Pattern (VCP) detection."""

import numpy as np
import pandas as pd

from snipe.config import load_config


def detect_swing_points(
    prices: pd.Series,
    order: int = 5,
) -> tuple[list[int], list[int]]:
    """Detect swing highs and swing lows in price data.

    Uses a local extrema approach: a point is a swing high if it's the
    highest in a window of 'order' bars on each side.

    Args:
        prices: Series of prices (typically close or high/low).
        order: Number of bars on each side to confirm swing.

    Returns:
        Tuple of (swing_high_indices, swing_low_indices).
    """
    highs = []
    lows = []

    values = prices.values
    n = len(values)

    for i in range(order, n - order):
        # Check if this is a local max
        window = values[i - order:i + order + 1]
        if values[i] == np.max(window):
            highs.append(i)
        # Check if this is a local min
        if values[i] == np.min(window):
            lows.append(i)

    return highs, lows


def detect_vcp(
    df: pd.DataFrame,
    config: dict | None = None,
) -> dict:
    """Detect Volatility Contraction Pattern in price data.

    Args:
        df: DataFrame with columns: date, high, low, close, volume.
            Should cover at least the base formation period.
        config: Optional config dict.

    Returns:
        Dict with:
        - vcp_detected: bool
        - contractions: int (number of contractions)
        - depths: list of contraction depths (%)
        - base_weeks: float
        - pivot_price: float (breakout trigger level)
        - vcp_quality: str ("high", "medium", "low")
        - quality_score: float (0-10)
        - approaching_pivot: bool
        - distance_to_pivot_pct: float
    """
    if config is None:
        config = load_config()

    vcp_config = config["vcp"]
    result = _empty_vcp_result()

    if len(df) < 20:
        return result

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # Find the base: look for the highest high in recent data as base start
    # Scan last 65 weeks (325 trading days) max
    max_bars = min(len(df), 325)
    recent = df.tail(max_bars).copy().reset_index(drop=True)
    recent_high = recent["high"].astype(float)
    recent_low = recent["low"].astype(float)
    recent_close = recent["close"].astype(float)
    recent_volume = recent["volume"].astype(float)

    # Find swing points
    swing_highs, swing_lows = detect_swing_points(recent_high, order=5)

    if len(swing_highs) < 2 or len(swing_lows) < 1:
        return result

    # Base high is the overall high in the lookback
    base_high_idx = recent_high.idxmax()
    base_high_price = recent_high.iloc[base_high_idx]

    # Find contractions after the base high
    # A contraction is: high → low → recovery toward high
    contractions = []
    current_high = base_high_price
    search_start = base_high_idx

    # Walk through swing lows after the base high
    relevant_lows = [i for i in swing_lows if i > search_start]
    relevant_highs = [i for i in swing_highs if i > search_start]

    if not relevant_lows:
        return result

    # Group into contractions: find pairs of (swing_low, next_swing_high)
    prev_high = base_high_price
    for i, low_idx in enumerate(relevant_lows):
        low_price = recent_low.iloc[low_idx]
        depth_pct = ((prev_high - low_price) / prev_high) * 100

        # Find next swing high after this low
        next_highs = [h for h in relevant_highs if h > low_idx]
        if next_highs:
            next_high_idx = next_highs[0]
            next_high_price = recent_high.iloc[next_high_idx]
        else:
            # Use current price area as the "recovery"
            next_high_price = recent_close.iloc[-1]
            next_high_idx = len(recent) - 1

        if depth_pct >= 3:  # Minimum meaningful contraction
            contractions.append({
                "depth_pct": round(depth_pct, 1),
                "low_idx": low_idx,
                "low_price": low_price,
                "high_idx": next_high_idx,
                "high_price": next_high_price,
            })
            prev_high = next_high_price

    if len(contractions) < vcp_config["min_contractions"]:
        return result

    # Validate contractions are tightening
    depths = [c["depth_pct"] for c in contractions]

    # Check T1 not too deep
    if depths[0] > vcp_config["max_t1_depth_pct"]:
        return result

    # Check T1 is deep enough (not a flat base)
    if depths[0] < vcp_config["min_t1_depth_pct"]:
        result["pattern_type"] = "flat_base"
        return result

    # Check each contraction is shallower than previous
    tightening = all(depths[i] > depths[i + 1] for i in range(len(depths) - 1))
    if not tightening:
        return result

    # Calculate base duration
    base_start_date = recent["date"].iloc[base_high_idx]
    base_end_date = recent["date"].iloc[-1]
    base_days = (pd.to_datetime(base_end_date) - pd.to_datetime(base_start_date)).days
    base_weeks = base_days / 7

    if base_weeks < vcp_config["min_base_weeks"] or base_weeks > vcp_config["max_base_weeks"]:
        return result

    # Check volume declining through contractions
    volume_declining = True
    for i in range(1, len(contractions)):
        prev_vol = recent_volume.iloc[
            contractions[i - 1]["low_idx"]:contractions[i - 1]["high_idx"]
        ].mean()
        curr_vol = recent_volume.iloc[
            contractions[i]["low_idx"]:max(contractions[i]["high_idx"], contractions[i]["low_idx"] + 1)
        ].mean()
        if curr_vol > prev_vol * 1.2:  # Allow 20% tolerance
            volume_declining = False

    # Pivot point: highest high in the final contraction
    last_contraction = contractions[-1]
    pivot_area = recent_high.iloc[last_contraction["low_idx"]:]
    pivot_price = float(pivot_area.max())

    # Current price distance to pivot
    current_price = float(recent_close.iloc[-1])
    distance_to_pivot = ((pivot_price - current_price) / pivot_price) * 100

    # Quality scoring
    quality_score = _compute_vcp_quality(
        contractions=len(contractions),
        final_depth=depths[-1],
        volume_declining=volume_declining,
        base_weeks=base_weeks,
        recent_volume=recent_volume,
        config=vcp_config,
    )

    if quality_score >= vcp_config["high_quality_threshold"]:
        quality = "high"
    elif quality_score >= vcp_config["low_quality_threshold"]:
        quality = "medium"
    else:
        quality = "low"

    approaching = 0 < distance_to_pivot <= vcp_config["approaching_pivot_pct"]

    return {
        "vcp_detected": True,
        "contractions": len(contractions),
        "depths": depths,
        "base_weeks": round(base_weeks, 1),
        "pivot_price": round(pivot_price, 2),
        "vcp_quality": quality,
        "quality_score": round(quality_score, 1),
        "approaching_pivot": approaching,
        "distance_to_pivot_pct": round(distance_to_pivot, 2),
        "volume_declining": volume_declining,
        "base_high": round(base_high_price, 2),
        "pattern_type": "vcp",
    }


def _compute_vcp_quality(
    contractions: int,
    final_depth: float,
    volume_declining: bool,
    base_weeks: float,
    recent_volume: pd.Series,
    config: dict,
) -> float:
    """Compute VCP quality score (0-10).

    Factors:
    - Number of contractions (more = better, max benefit at 4)
    - Tightness of final contraction (tighter = better)
    - Volume dry-up (lower recent volume vs avg = better)
    - Base duration (5-25 weeks optimal)
    """
    score = 0.0

    # Contractions: 2=4pts, 3=6pts, 4+=8pts (out of 10 contribution: 2.5 max)
    contraction_score = min(contractions, 4) / 4 * 2.5
    score += contraction_score

    # Final contraction tightness: <= 8% is ideal (2.5 max)
    tight_threshold = config["tight_final_contraction_pct"]
    if final_depth <= tight_threshold:
        tightness_score = 2.5
    elif final_depth <= tight_threshold * 2:
        tightness_score = 1.5
    else:
        tightness_score = 0.5
    score += tightness_score

    # Volume declining: 2.5 if yes, 0.5 if no
    score += 2.5 if volume_declining else 0.5

    # Base duration: optimal range 5-25 weeks (2.5 max)
    opt_min = config["optimal_base_min_weeks"]
    opt_max = config["optimal_base_max_weeks"]
    if opt_min <= base_weeks <= opt_max:
        duration_score = 2.5
    elif base_weeks < opt_min:
        duration_score = 1.0
    else:
        duration_score = 1.5
    score += duration_score

    return min(score, 10.0)


def _empty_vcp_result() -> dict:
    """Return empty VCP result."""
    return {
        "vcp_detected": False,
        "contractions": 0,
        "depths": [],
        "base_weeks": 0,
        "pivot_price": 0,
        "vcp_quality": "none",
        "quality_score": 0,
        "approaching_pivot": False,
        "distance_to_pivot_pct": 0,
        "volume_declining": False,
        "base_high": 0,
        "pattern_type": "none",
    }
