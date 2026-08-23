"""Defensive and offensive sell signal detection."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from snipe.config import load_config
from snipe.scanning.trend_template import compute_sma
from snipe.database import get_db, init_db


def check_defensive_signals(
    df: pd.DataFrame,
    entry_price: float,
    stop_price: float,
    base_low: float | None = None,
    config: dict | None = None,
) -> list[dict]:
    """Check for defensive sell signals.

    Signals:
    1. Stop-loss hit (close below stop)
    2. Pattern failure (close below base low on volume)
    3. Volume reversal (new high + reversal on heavy volume)
    4. Three strikes (3 closes below 10-DMA in 10 days)

    Args:
        df: Recent price/volume data (last 20+ days).
        entry_price: Entry price of position.
        stop_price: Current stop-loss level.
        base_low: Base low from pattern (for pattern failure).
        config: Optional config.

    Returns:
        List of triggered signal dicts.
    """
    if config is None:
        config = load_config()

    sell_config = config["sell_rules"]
    signals = []

    if len(df) < 10:
        return signals

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    current_close = close.iloc[-1]
    current_volume = volume.iloc[-1]
    avg_volume = volume.tail(50).mean() if len(volume) >= 50 else volume.mean()

    # 1. Stop-loss hit
    if current_close < stop_price:
        signals.append({
            "type": "stop_loss_hit",
            "urgency": "immediate",
            "detail": f"Close {current_close:.2f} below stop {stop_price:.2f}",
            "action": "exit_immediately",
        })

    # 2. Pattern failure
    if base_low and current_close < base_low:
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        if vol_ratio > 1.5:  # Above-average volume confirms failure
            signals.append({
                "type": "pattern_failure",
                "urgency": "immediate",
                "detail": f"Close {current_close:.2f} below base low {base_low:.2f} on {vol_ratio:.1f}x volume",
                "action": "exit_immediately",
            })

    # 3. Volume reversal
    if len(df) >= 2:
        today_high = high.iloc[-1]
        today_close = close.iloc[-1]
        today_low = low.iloc[-1]
        today_range = today_high - today_low

        if today_range > 0:
            close_position_in_range = (today_close - today_low) / today_range
            threshold = sell_config["volume_reversal_close_pct"] / 100

            # New high + reversal close in bottom 25% + heavy volume
            prev_high = high.iloc[:-1].max() if len(high) > 1 else 0
            is_new_high = today_high > prev_high
            vol_heavy = current_volume > avg_volume * 1.5

            if is_new_high and close_position_in_range <= threshold and vol_heavy:
                signals.append({
                    "type": "volume_reversal",
                    "urgency": "high",
                    "detail": f"New high reversal, close in bottom {threshold*100:.0f}% on {current_volume/avg_volume:.1f}x volume",
                    "action": "exit_within_1_2_days",
                })

    # 4. Three strikes (3 closes below 10-DMA in window)
    window_days = sell_config["three_strikes_window_days"]
    ma_period = sell_config["three_strikes_ma_period"]

    if len(close) >= ma_period + window_days:
        sma_10 = compute_sma(close, ma_period)
        recent_window = close.tail(window_days)
        recent_ma = sma_10.tail(window_days)

        below_ma_count = (recent_window < recent_ma).sum()
        if below_ma_count >= 3:
            signals.append({
                "type": "three_strikes",
                "urgency": "consider_exit",
                "detail": f"{below_ma_count} closes below {ma_period}-DMA in {window_days} days",
                "action": "tighten_stop_or_reduce",
            })

    return signals


def check_offensive_signals(
    df: pd.DataFrame,
    entry_price: float,
    current_gain_pct: float,
    days_held: int,
    config: dict | None = None,
) -> list[dict]:
    """Check for offensive (profit-taking) sell signals.

    Signals:
    1. First target (+20-25%)
    2. Climactic volume top
    3. Three weeks tight at top
    4. Trailing stop (21-EMA)

    Args:
        df: Recent price/volume data.
        entry_price: Entry price.
        current_gain_pct: Current gain percentage.
        days_held: Days since entry.
        config: Optional config.

    Returns:
        List of triggered signal dicts.
    """
    if config is None:
        config = load_config()

    sell_config = config["sell_rules"]
    signals = []

    if len(df) < 21:
        return signals

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    volume = df["volume"].astype(float)

    current_close = close.iloc[-1]
    avg_volume = volume.tail(50).mean() if len(volume) >= 50 else volume.mean()

    # 1. First target hit (+20-25%)
    first_target_pct = sell_config["first_target_pct"]
    if current_gain_pct >= first_target_pct:
        signals.append({
            "type": "first_target",
            "urgency": "plan_exit",
            "detail": f"Gain {current_gain_pct:.1f}% reached first target {first_target_pct}%",
            "action": "partial_sell_33_to_50_pct",
        })

    # 2. Climactic volume top
    climactic_mult = sell_config["climactic_volume_multiplier"]
    if current_gain_pct >= 20:  # Only check after meaningful advance
        today_volume = volume.iloc[-1]
        today_gain = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0

        if today_volume > avg_volume * climactic_mult and today_gain > 5:
            # Largest single-day gain + highest volume = climactic
            signals.append({
                "type": "climactic_top",
                "urgency": "high",
                "detail": f"Volume {today_volume/avg_volume:.1f}x avg with {today_gain:.1f}% gain after +{current_gain_pct:.0f}% advance",
                "action": "sell_all_or_majority",
            })

    # 3. Three weeks tight at top
    tight_range_pct = sell_config["three_weeks_tight_range_pct"]
    if len(close) >= 15 and current_gain_pct >= 20:  # 3 weeks = 15 trading days
        # Check if last 3 weeks have tight ranges
        weeks_tight = 0
        for w in range(3):
            week_start = -(w + 1) * 5
            week_end = -w * 5 if w > 0 else None
            week_slice = close.iloc[week_start:week_end]
            if len(week_slice) >= 4:
                week_range = ((week_slice.max() - week_slice.min()) / week_slice.min()) * 100
                if week_range <= tight_range_pct:
                    weeks_tight += 1

        if weeks_tight >= 3:
            signals.append({
                "type": "three_weeks_tight",
                "urgency": "consider_exit",
                "detail": f"3 weeks with <{tight_range_pct}% range at top — potential distribution",
                "action": "tighten_stop_to_10dma",
            })

    # 4. Trailing stop (21-EMA)
    trailing_activation = sell_config["trailing_stop_activation_pct"]
    ema_period = sell_config["trailing_stop_ema_period"]

    if current_gain_pct >= trailing_activation and len(close) >= ema_period:
        ema_21 = close.ewm(span=ema_period, adjust=False).mean()
        current_ema = ema_21.iloc[-1]

        if current_close < current_ema:
            signals.append({
                "type": "trailing_stop_21ema",
                "urgency": "next_day_confirm",
                "detail": f"Close {current_close:.2f} below 21-EMA {current_ema:.2f} with +{current_gain_pct:.1f}% gain",
                "action": "exit_on_next_day_confirmation",
            })

    return signals


def compute_position_status(
    entry_price: float,
    stop_price: float,
    current_price: float,
    entry_date: str,
) -> dict:
    """Compute current position status metrics.

    Returns:
        Dict with gain_pct, r_multiple, days_held, trailing_stop_active.
    """
    gain_pct = ((current_price - entry_price) / entry_price) * 100
    initial_risk = abs(entry_price - stop_price)
    r_multiple = (current_price - entry_price) / initial_risk if initial_risk > 0 else 0

    entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
    days_held = (datetime.now() - entry_dt).days

    trailing_active = gain_pct >= 20  # Activates at +20%

    return {
        "current_price": round(current_price, 2),
        "gain_pct": round(gain_pct, 2),
        "r_multiple": round(r_multiple, 2),
        "days_held": days_held,
        "trailing_stop_active": trailing_active,
    }
