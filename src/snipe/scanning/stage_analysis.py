"""Weinstein Stage Analysis - classify stocks into 4 market stages."""

import numpy as np
import pandas as pd

from snipe.config import load_config
from snipe.scanning.trend_template import compute_sma
from snipe.scanning.vcp import detect_swing_points


def classify_stage(
    df: pd.DataFrame,
    config: dict | None = None,
) -> dict:
    """Classify a stock into one of Weinstein's four stages.

    Args:
        df: DataFrame with columns: date, high, low, close, volume.
            Must have at least 200 rows.
        config: Optional config dict.

    Returns:
        Dict with:
        - stage: str ("stage_1", "stage_2_early", "stage_2", "stage_3", "stage_4")
        - stage_confirmed: bool (True for confirmed Stage 2)
        - stage_duration_weeks: int
        - late_stage_2: bool
        - ma_150_slope: str ("rising", "flat", "falling")
        - price_vs_ma150: str ("above", "below")
    """
    if config is None:
        config = load_config()

    stage_config = config["stage_analysis"]

    if len(df) < 200:
        return _empty_stage_result()

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # Compute 150-day MA (30-week proxy) and 50-day MA
    sma_150 = compute_sma(close, 150)
    sma_50 = compute_sma(close, 50)

    current_price = close.iloc[-1]
    current_ma150 = sma_150.iloc[-1]
    current_ma50 = sma_50.iloc[-1]

    # Determine MA slope (over last 22 days)
    ma150_slope = _compute_slope(sma_150, 22)

    # Price position relative to MA
    price_above_ma150 = current_price > current_ma150

    # Determine how long price has been above/below MA150
    weeks_above = _weeks_above_ma(close, sma_150)
    weeks_below = _weeks_below_ma(close, sma_150)

    # Detect swing structure (higher highs/lows vs lower highs/lows)
    swing_highs_idx, swing_lows_idx = detect_swing_points(close, order=10)
    price_structure = _analyze_swing_structure(close, swing_highs_idx, swing_lows_idx)

    # Stage classification logic
    if price_above_ma150 and ma150_slope == "rising":
        if price_structure == "higher_highs_lows":
            # Check Stage 2 confirmation criteria
            confirm_weeks = stage_config["stage2_confirm_weeks"]
            ma50_above_150 = current_ma50 > current_ma150

            if weeks_above >= confirm_weeks and ma50_above_150:
                # Check for higher swing low above MA150
                has_higher_low = _has_higher_low_above_ma(
                    close, low, sma_150, swing_lows_idx
                )
                if has_higher_low:
                    stage = "stage_2"
                    confirmed = True
                else:
                    stage = "stage_2_early"
                    confirmed = False
            else:
                stage = "stage_2_early"
                confirmed = False
        else:
            stage = "stage_2_early"
            confirmed = False
    elif price_above_ma150 and ma150_slope == "flat":
        if price_structure == "higher_highs_lows":
            stage = "stage_2_early"
        else:
            stage = "stage_3"
        confirmed = False
    elif not price_above_ma150 and ma150_slope == "flat":
        stage = "stage_1" if price_structure == "sideways" else "stage_3"
        confirmed = False
    elif not price_above_ma150 and ma150_slope == "falling":
        stage = "stage_4"
        confirmed = False
    elif not price_above_ma150 and ma150_slope == "rising":
        # Price temporarily below rising MA — could be pullback in Stage 2
        stage = "stage_2_early" if weeks_below < 3 else "stage_1"
        confirmed = False
    else:
        stage = "stage_1"
        confirmed = False

    # Duration tracking
    if stage in ("stage_2", "stage_2_early"):
        duration_weeks = weeks_above
    elif stage == "stage_4":
        duration_weeks = weeks_below
    else:
        duration_weeks = max(weeks_above, weeks_below)

    late_stage2 = (
        stage == "stage_2"
        and duration_weeks >= stage_config["late_stage2_weeks"]
    )

    return {
        "stage": stage,
        "stage_confirmed": confirmed,
        "stage_duration_weeks": duration_weeks,
        "late_stage_2": late_stage2,
        "ma_150_slope": ma150_slope,
        "price_vs_ma150": "above" if price_above_ma150 else "below",
        "weeks_above_ma150": weeks_above,
        "price_structure": price_structure,
    }


def _compute_slope(ma_series: pd.Series, lookback: int) -> str:
    """Determine if MA is rising, flat, or falling."""
    recent = ma_series.tail(lookback + 1).dropna()
    if len(recent) < lookback:
        return "flat"

    change_pct = ((recent.iloc[-1] / recent.iloc[0]) - 1) * 100
    if change_pct > 1.0:
        return "rising"
    elif change_pct < -1.0:
        return "falling"
    return "flat"


def _weeks_above_ma(close: pd.Series, ma: pd.Series) -> int:
    """Count consecutive weeks (5-day blocks) price has been above MA."""
    days_above = 0
    for i in range(len(close) - 1, -1, -1):
        if pd.isna(ma.iloc[i]):
            break
        if close.iloc[i] > ma.iloc[i]:
            days_above += 1
        else:
            break
    return days_above // 5


def _weeks_below_ma(close: pd.Series, ma: pd.Series) -> int:
    """Count consecutive weeks price has been below MA."""
    days_below = 0
    for i in range(len(close) - 1, -1, -1):
        if pd.isna(ma.iloc[i]):
            break
        if close.iloc[i] < ma.iloc[i]:
            days_below += 1
        else:
            break
    return days_below // 5


def _analyze_swing_structure(
    close: pd.Series,
    swing_highs: list[int],
    swing_lows: list[int],
) -> str:
    """Analyze if price is making higher highs/lows or lower highs/lows."""
    # Look at last 3 swing highs and 3 swing lows
    recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
    recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return "sideways"

    # Check highs
    high_values = [close.iloc[i] for i in recent_highs]
    higher_highs = all(high_values[i] < high_values[i + 1] for i in range(len(high_values) - 1))

    # Check lows
    low_values = [close.iloc[i] for i in recent_lows]
    higher_lows = all(low_values[i] < low_values[i + 1] for i in range(len(low_values) - 1))

    lower_highs = all(high_values[i] > high_values[i + 1] for i in range(len(high_values) - 1))
    lower_lows = all(low_values[i] > low_values[i + 1] for i in range(len(low_values) - 1))

    if higher_highs and higher_lows:
        return "higher_highs_lows"
    elif lower_highs and lower_lows:
        return "lower_highs_lows"
    return "sideways"


def _has_higher_low_above_ma(
    close: pd.Series,
    low: pd.Series,
    ma: pd.Series,
    swing_lows: list[int],
) -> bool:
    """Check if there's at least one higher swing low above the MA."""
    recent_lows = swing_lows[-5:]  # Check last 5 swing lows
    above_ma_lows = []

    for idx in recent_lows:
        if pd.isna(ma.iloc[idx]):
            continue
        if low.iloc[idx] > ma.iloc[idx]:
            above_ma_lows.append(low.iloc[idx])

    # Need at least one swing low above MA
    return len(above_ma_lows) >= 1


def _empty_stage_result() -> dict:
    return {
        "stage": "insufficient_data",
        "stage_confirmed": False,
        "stage_duration_weeks": 0,
        "late_stage_2": False,
        "ma_150_slope": "unknown",
        "price_vs_ma150": "unknown",
        "weeks_above_ma150": 0,
        "price_structure": "unknown",
    }
