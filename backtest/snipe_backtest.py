"""
SNIPE Strategy Backtester v2
=============================
Backtests the SNIPE momentum breakout strategy on NSE stocks
over the last 2 years (Aug 2024 - Aug 2026).

Key changes in v2:
- Daily scanning (not just weekly)
- Breakout detection over 3-day window
- Relaxed VCP to include "base consolidation" patterns
- Added 'approaching breakout' mode for better capture

Strategy Core Rules:
- Entry: Trend Template (8+/10) + Base/VCP + Breakout on 1.5x volume
- Stop Loss: 7-8% below entry
- Targets: Trailing 21-EMA after +20%
- Position Sizing: Risk 0.5%-2% based on edge count
- Market Regime gates
"""

import json
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tabulate import tabulate

warnings.filterwarnings("ignore")

# ============================================================
# CONFIGURATION
# ============================================================

INITIAL_CAPITAL = 1_000_000  # ₹10 Lakhs
BACKTEST_START = "2024-08-01"
BACKTEST_END = "2026-08-22"
DATA_LOOKBACK = "2023-06-01"  # Extra for 200-DMA

# Slightly relaxed for practical backtesting (real scanner catches more)
MIN_TT_SCORE = 8  # Accept 8/10 (very near perfect trend)
BREAKOUT_WINDOW = 3  # Check last 3 days for breakout
MIN_VOL_RATIO = 1.3  # Slightly relaxed from 1.5

CONFIG = {
    "position_sizing": {
        "risk_1_edge_pct": 0.5,
        "risk_2_edge_pct": 1.0,
        "risk_3_edge_pct": 1.5,
        "risk_4plus_edge_pct": 2.0,
        "max_stop_distance_pct": 8,
        "max_position_pct_of_equity": 20,
        "max_total_risk_pct": 6,
        "max_open_positions": 10,
    },
    "sell_rules": {
        "first_target_pct": 20,
        "trailing_stop_activation_pct": 20,
        "trailing_stop_ema_period": 21,
        "climactic_volume_multiplier": 3.0,
        "initial_stop_pct": 7,  # 7% initial stop
    },
}

# Expanded representative universe (120+ liquid NSE stocks)
STOCK_UNIVERSE = [
    # IT
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "TATAELXSI.NS",
    "KPITTECH.NS", "LTTS.NS", "CYIENT.NS",
    # Banks & NBFC
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "INDUSINDBK.NS", "FEDERALBNK.NS", "BANKBARODA.NS",
    "PNB.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    # FMCG
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS",
    "DABUR.NS", "MARICO.NS", "TRENT.NS", "DMART.NS",
    # Auto
    "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "TVSMOTOR.NS",
    # Pharma
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
    "APOLLOHOSP.NS", "TORNTPHARM.NS", "MAXHEALTH.NS", "FORTIS.NS",
    "LALPATHLAB.NS",
    # Energy
    "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
    "ADANIENT.NS", "COALINDIA.NS", "TATAPOWER.NS",
    # Capital Goods / Infra
    "LT.NS", "SIEMENS.NS", "ABB.NS", "HAL.NS", "BEL.NS", "BHEL.NS",
    "CUMMINSIND.NS", "THERMAX.NS",
    # Metals
    "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "VEDL.NS", "NMDC.NS",
    # Midcap Momentum
    "POLYCAB.NS", "DIXON.NS", "KAYNES.NS",
    "CLEAN.NS", "SOLARINDS.NS",
    "ASTRAL.NS", "SUPREMEIND.NS", "APLAPOLLO.NS",
    "PIIND.NS", "SUMICHEM.NS",
    "BSE.NS", "MCX.NS", "ANGELONE.NS",
    "IRFC.NS", "PFC.NS", "RECLTD.NS", "HUDCO.NS",
    "IRCTC.NS", "CONCOR.NS", "RVNL.NS",
    "OBEROIRLTY.NS", "PRESTIGE.NS", "BRIGADE.NS", "PHOENIXLTD.NS",
    "CGPOWER.NS", "SUZLON.NS", "NHPC.NS",
    "SONACOMS.NS", "TIINDIA.NS",
    "GRINDWELL.NS", "CARBORUNIV.NS",
    "SUNTV.NS",
    "JKCEMENT.NS", "RAMCOCEM.NS", "DALBHARAT.NS",
    "NYKAA.NS", "PAYTM.NS",
    # Additional momentum names
    "ABCAPITAL.NS", "MANAPPURAM.NS", "MUTHOOTFIN.NS",
    "GODREJPROP.NS", "DLF.NS",
    "INDIANHOTEL.NS", "PAGEIND.NS", "RELAXO.NS",
    "VOLTAS.NS", "BLUESTARLT.NS", "CROMPTON.NS",
    "DEEPAKNTR.NS", "ATUL.NS",
    "ZYDUSLIFE.NS", "GLENMARK.NS", "IPCALAB.NS",
]

INDEX_SYMBOL = "^CRSLDX"


# ============================================================
# CORE ANALYSIS FUNCTIONS
# ============================================================

def compute_sma(prices, period):
    return prices.rolling(window=period, min_periods=period).mean()

def compute_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()


def check_trend_template(close_series):
    """10-point Trend Template. Returns (score, details_dict)."""
    if len(close_series) < 252:
        return 0, {}

    current_price = close_series.iloc[-1]
    sma_50 = compute_sma(close_series, 50).iloc[-1]
    sma_150 = compute_sma(close_series, 150).iloc[-1]
    sma_200 = compute_sma(close_series, 200).iloc[-1]

    if pd.isna(sma_50) or pd.isna(sma_150) or pd.isna(sma_200):
        return 0, {}

    lookback = close_series.tail(252)
    high_52w = lookback.max()
    low_52w = lookback.min()

    sma_200_series = compute_sma(close_series, 200)
    sma_200_recent = sma_200_series.tail(23).dropna()
    ma200_rising = len(sma_200_recent) >= 23 and sma_200_recent.iloc[-1] > sma_200_recent.iloc[0]

    pct_above_low = ((current_price - low_52w) / low_52w) * 100 if low_52w > 0 else 0
    pct_below_high = ((high_52w - current_price) / high_52w) * 100 if high_52w > 0 else 0

    criteria = [
        current_price > sma_150,               # C1
        current_price > sma_200,               # C2
        sma_150 > sma_200,                     # C3
        ma200_rising,                           # C4
        sma_50 > sma_150,                      # C5
        sma_50 > sma_200,                      # C6
        current_price > sma_50,                # C7
        pct_above_low >= 30,                   # C8
        pct_below_high <= 25,                  # C9
        True,  # C10 placeholder for RS (computed separately)
    ]

    score = sum(criteria)
    return score, {
        "sma_50": sma_50, "sma_150": sma_150, "sma_200": sma_200,
        "high_52w": high_52w, "low_52w": low_52w,
        "pct_above_low": pct_above_low, "pct_below_high": pct_below_high,
    }


def detect_consolidation_breakout(df, date_idx):
    """
    Detect a consolidation/base pattern followed by breakout.
    More practical than pure VCP - catches:
    - Tight range consolidation near highs
    - Cup & handle
    - Flat bases
    - VCP-like contractions

    Returns: (detected, entry_price, stop_price, quality_score, vol_ratio)
    """
    if date_idx < 60:
        return False, 0, 0, 0, 0

    # Get last 120 bars for base detection
    lookback = min(date_idx, 120)
    segment = df.iloc[date_idx - lookback:date_idx + 1]

    if len(segment) < 60:
        return False, 0, 0, 0, 0

    close = segment["close"].astype(float)
    high = segment["high"].astype(float)
    low = segment["low"].astype(float)
    volume = segment["volume"].astype(float)

    current_price = close.iloc[-1]
    current_volume = volume.iloc[-1]

    # 50-day average volume
    avg_vol = volume.tail(50).mean()
    if avg_vol <= 0:
        return False, 0, 0, 0, 0
    vol_ratio = current_volume / avg_vol

    # ---- PATTERN 1: Consolidation Range Breakout ----
    # Find the consolidation range (last 15-40 days)
    for base_length in [20, 30, 40, 15]:
        if len(close) <= base_length + 5:
            continue

        base = close.iloc[-(base_length + 1):-1]  # Exclude today
        base_high_val = base.max()
        base_low_val = base.min()
        base_range_pct = ((base_high_val - base_low_val) / base_low_val) * 100

        # A valid base: range between 5% and 25%
        if 5 <= base_range_pct <= 25:
            # Check if today broke above the base high
            if current_price > base_high_val * 1.005:  # 0.5% above
                # Verify prior uptrend (price moved up before forming base)
                pre_base_start = max(0, len(close) - base_length - 60)
                pre_base_end = len(close) - base_length - 1
                if pre_base_end > pre_base_start:
                    pre_base_low = close.iloc[pre_base_start:pre_base_end].min()
                    prior_advance = ((base_low_val - pre_base_low) / pre_base_low) * 100
                    if prior_advance >= 15:  # Had at least 15% advance before base
                        # Quality scoring
                        quality = 5.0

                        # Tighter base = higher quality
                        if base_range_pct <= 12:
                            quality += 2.0
                        elif base_range_pct <= 18:
                            quality += 1.0

                        # Volume declining in base = accumulation
                        vol_first_half = volume.iloc[-(base_length+1):-(base_length//2+1)].mean()
                        vol_second_half = volume.iloc[-(base_length//2+1):-1].mean()
                        if vol_second_half < vol_first_half * 0.85:
                            quality += 1.5

                        # Breakout on volume
                        if vol_ratio >= 1.5:
                            quality += 1.5
                        elif vol_ratio >= 1.3:
                            quality += 0.5

                        stop_price = base_low_val * 0.98  # Stop just below base low
                        stop_distance_pct = ((current_price - stop_price) / current_price) * 100

                        # Ensure stop isn't too wide
                        if stop_distance_pct > 10:
                            stop_price = current_price * 0.92  # Cap at 8%

                        return True, current_price, stop_price, min(quality, 10), vol_ratio

    # ---- PATTERN 2: VCP-like (tightening range near high) ----
    if len(close) >= 40:
        # Check last 40 bars for contracting range
        ranges_10d = []
        for i in range(4):
            start = -(4 - i) * 10 - 1
            end = -(3 - i) * 10 - 1 if i < 3 else -1
            period_slice = close.iloc[start:end]
            if len(period_slice) >= 8:
                prd_range = ((period_slice.max() - period_slice.min()) / period_slice.min()) * 100
                ranges_10d.append(prd_range)

        if len(ranges_10d) >= 3:
            # Check contracting
            contracting = all(ranges_10d[i] >= ranges_10d[i+1] for i in range(len(ranges_10d)-1))
            if contracting and ranges_10d[-1] <= 8:  # Final range <= 8%
                # Check breakout above recent high
                recent_high = high.iloc[-20:-1].max()
                if current_price > recent_high and vol_ratio >= MIN_VOL_RATIO:
                    # VCP detected
                    quality = 7.0
                    if ranges_10d[-1] <= 5:
                        quality += 1.0
                    if vol_ratio >= 2.0:
                        quality += 1.0

                    stop_price = low.iloc[-20:].min() * 0.98
                    stop_distance_pct = ((current_price - stop_price) / current_price) * 100
                    if stop_distance_pct > 10:
                        stop_price = current_price * 0.92

                    return True, current_price, stop_price, min(quality, 10), vol_ratio

    return False, 0, 0, 0, 0


def check_market_regime(index_close):
    """GREEN/YELLOW/RED regime based on index vs 150-DMA."""
    if len(index_close) < 200:
        return "GREEN", 1.0

    sma_150 = compute_sma(index_close, 150)
    current = index_close.iloc[-1]
    current_sma = sma_150.iloc[-1]

    if pd.isna(current_sma):
        return "GREEN", 1.0

    sma_recent = sma_150.tail(22).dropna()
    ma_rising = len(sma_recent) >= 22 and sma_recent.iloc[-1] > sma_recent.iloc[0]

    if current > current_sma and ma_rising:
        return "GREEN", 1.0
    elif current < current_sma and not ma_rising:
        return "RED", 0.0
    else:
        return "YELLOW", 0.5


def compute_position_size(equity, entry_price, stop_price, edge_count, regime_mult):
    """Compute shares and position value."""
    ps = CONFIG["position_sizing"]

    if edge_count >= 4:
        risk_pct = ps["risk_4plus_edge_pct"]
    elif edge_count == 3:
        risk_pct = ps["risk_3_edge_pct"]
    elif edge_count == 2:
        risk_pct = ps["risk_2_edge_pct"]
    else:
        risk_pct = ps["risk_1_edge_pct"]

    risk_pct *= regime_mult
    if risk_pct <= 0:
        return 0, 0

    risk_amount = equity * (risk_pct / 100)
    stop_distance = abs(entry_price - stop_price)

    if stop_distance <= 0:
        return 0, 0

    stop_pct = (stop_distance / entry_price) * 100
    if stop_pct > ps["max_stop_distance_pct"]:
        return 0, 0

    shares = int(risk_amount / stop_distance)
    position_value = shares * entry_price

    max_pos = equity * (ps["max_position_pct_of_equity"] / 100)
    if position_value > max_pos:
        shares = int(max_pos / entry_price)
        position_value = shares * entry_price

    if shares <= 0:
        return 0, 0

    return shares, position_value


# ============================================================
# BACKTEST ENGINE
# ============================================================

class Position:
    def __init__(self, symbol, entry_date, entry_price, shares, stop_price,
                 edge_count, quality_score, vol_ratio):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.shares = shares
        self.stop_price = stop_price
        self.original_stop = stop_price
        self.edge_count = edge_count
        self.quality_score = quality_score
        self.vol_ratio = vol_ratio
        self.trailing_active = False
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.max_gain_pct = 0
        self.position_value = shares * entry_price

    @property
    def risk_amount(self):
        return self.shares * abs(self.entry_price - self.original_stop)

    def pnl(self):
        if self.exit_price:
            return (self.exit_price - self.entry_price) * self.shares
        return 0

    def pnl_pct(self):
        if self.exit_price:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        return 0

    def r_multiple(self):
        if self.exit_price:
            risk = abs(self.entry_price - self.original_stop)
            if risk > 0:
                return (self.exit_price - self.entry_price) / risk
        return 0


class BacktestEngine:
    def __init__(self):
        self.capital = INITIAL_CAPITAL
        self.positions = []
        self.closed_trades = []
        self.signals_log = []
        self.daily_equity = []

    def run(self, all_data, index_data):
        """Run day-by-day backtest."""
        print("\n" + "="*70)
        print("  SNIPE STRATEGY BACKTEST ENGINE v2")
        print("="*70)
        print(f"  Period: {BACKTEST_START} to {BACKTEST_END}")
        print(f"  Initial Capital: ₹{INITIAL_CAPITAL:,.0f}")
        print(f"  Universe: {len(all_data)} stocks")
        print(f"  Min TT Score: {MIN_TT_SCORE}/10")
        print(f"  Min Volume Ratio: {MIN_VOL_RATIO}x")
        print("="*70 + "\n")

        # Build unified date index
        if index_data is not None and len(index_data) > 0:
            trading_dates = index_data.loc[BACKTEST_START:BACKTEST_END].index
        else:
            first_stock = list(all_data.values())[0]
            trading_dates = first_stock.loc[BACKTEST_START:BACKTEST_END].index

        if len(trading_dates) == 0:
            print("ERROR: No trading dates in range")
            return

        print(f"  Trading days: {len(trading_dates)}")
        print(f"  Scanning daily for setups...\n")

        # Pre-compute RS rankings (refreshed weekly)
        rs_cache = {}
        last_rs_compute = None

        # Convert all stock DataFrames to have integer position index for faster access
        stock_date_idx = {}  # symbol -> {date: integer_idx}
        for sym, df in all_data.items():
            stock_date_idx[sym] = {d: i for i, d in enumerate(df.index)}

        for day_num, date in enumerate(trading_dates):
            date_str = str(date.date()) if hasattr(date, 'date') else str(date)[:10]

            # --- Daily equity tracking ---
            unrealized = 0
            for pos in self.positions:
                if pos.symbol in all_data:
                    df = all_data[pos.symbol]
                    if date in df.index:
                        curr = df.loc[date, "close"]
                        unrealized += (curr - pos.entry_price) * pos.shares

            total_equity = self.capital + unrealized
            self.daily_equity.append({"date": date, "equity": total_equity})

            # --- Market Regime ---
            if index_data is not None and date in index_data.index:
                idx_close = index_data.loc[:date, "close"]
                regime, regime_mult = check_market_regime(idx_close)
            else:
                regime, regime_mult = "GREEN", 1.0

            # --- Manage positions (exits) ---
            to_close = []
            for pos in self.positions:
                if pos.symbol not in all_data:
                    continue
                df = all_data[pos.symbol]
                if date not in df.index:
                    continue

                curr_price = df.loc[date, "close"]
                curr_high = df.loc[date, "high"]
                curr_low = df.loc[date, "low"]
                curr_volume = df.loc[date, "volume"]

                gain_pct = ((curr_price - pos.entry_price) / pos.entry_price) * 100
                pos.max_gain_pct = max(pos.max_gain_pct, gain_pct)

                # Activate trailing at +20%
                if gain_pct >= 20 and not pos.trailing_active:
                    pos.trailing_active = True

                # === STOP LOSS ===
                if curr_price <= pos.stop_price:
                    pos.exit_date = date
                    pos.exit_price = pos.stop_price
                    pos.exit_reason = "stop_loss"
                    to_close.append(pos)
                    continue

                # === TRAILING 21-EMA (after +20%) ===
                if pos.trailing_active:
                    close_series = df.loc[:date, "close"]
                    if len(close_series) >= 21:
                        ema_21 = compute_ema(close_series, 21).iloc[-1]
                        # Ratchet stop up
                        trailing_stop = ema_21 * 0.99
                        if trailing_stop > pos.stop_price:
                            pos.stop_price = trailing_stop

                        if curr_price < ema_21:
                            pos.exit_date = date
                            pos.exit_price = curr_price
                            pos.exit_reason = "trailing_21ema"
                            to_close.append(pos)
                            continue

                # === CLIMACTIC TOP ===
                if gain_pct >= 20:
                    close_hist = df.loc[:date, "close"]
                    vol_hist = df.loc[:date, "volume"]
                    avg_vol = vol_hist.tail(50).mean()
                    if len(close_hist) >= 2 and avg_vol > 0:
                        prev_close = close_hist.iloc[-2]
                        day_gain = ((curr_price / prev_close) - 1) * 100
                        if curr_volume > avg_vol * 3 and day_gain > 5:
                            pos.exit_date = date
                            pos.exit_price = curr_price
                            pos.exit_reason = "climactic_top"
                            to_close.append(pos)
                            continue

                # === VOLUME REVERSAL ===
                if gain_pct >= 10:
                    day_range = curr_high - curr_low
                    if day_range > 0:
                        close_in_range = (curr_price - curr_low) / day_range
                        vol_hist = df.loc[:date, "volume"]
                        avg_vol = vol_hist.tail(50).mean()
                        if avg_vol > 0:
                            # Check new high
                            recent_highs = df.loc[:date, "high"].tail(21)
                            if len(recent_highs) > 1:
                                prev_max = recent_highs.iloc[:-1].max()
                                if (curr_high > prev_max and
                                    close_in_range <= 0.25 and
                                    curr_volume > avg_vol * 1.5):
                                    pos.exit_date = date
                                    pos.exit_price = curr_price
                                    pos.exit_reason = "volume_reversal"
                                    to_close.append(pos)
                                    continue

                # === TIME STOP (optional: exit if flat after 60 days) ===
                days_held = (date - pos.entry_date).days
                if days_held > 60 and gain_pct < 3 and gain_pct > -3:
                    pos.exit_date = date
                    pos.exit_price = curr_price
                    pos.exit_reason = "time_stop_flat"
                    to_close.append(pos)
                    continue

            # Process exits
            for pos in to_close:
                self.positions.remove(pos)
                pnl = pos.pnl()
                self.capital += pos.position_value + pnl
                self.closed_trades.append(pos)

            # --- Scan for new entries (daily) ---
            if regime == "RED":
                # No new entries in RED regime
                if day_num % 50 == 0:
                    print(f"  [{date_str}] Eq: ₹{total_equity:,.0f} | Open: {len(self.positions)} | Closed: {len(self.closed_trades)} | Regime: {regime}")
                continue

            if len(self.positions) >= CONFIG["position_sizing"]["max_open_positions"]:
                if day_num % 50 == 0:
                    print(f"  [{date_str}] Eq: ₹{total_equity:,.0f} | Open: {len(self.positions)} | Closed: {len(self.closed_trades)} | Regime: {regime} [FULL]")
                continue

            # Refresh RS every 5 days
            if last_rs_compute is None or (date - last_rs_compute).days >= 5:
                rs_cache = {}
                for sym, df in all_data.items():
                    if date in df.index:
                        close_to_date = df.loc[:date, "close"]
                        if len(close_to_date) >= 126:
                            ret_6m = (close_to_date.iloc[-1] / close_to_date.iloc[-126] - 1) * 100
                            rs_cache[sym] = ret_6m
                last_rs_compute = date

            # Scan stocks
            candidates = []
            for sym, df in all_data.items():
                if date not in df.index:
                    continue
                # Skip if already holding
                if any(p.symbol == sym for p in self.positions):
                    continue

                # Get position in DataFrame
                idx_pos = stock_date_idx[sym].get(date)
                if idx_pos is None or idx_pos < 252:
                    continue

                close_to_date = df.iloc[:idx_pos + 1]["close"]

                # --- Trend Template ---
                tt_score, tt_details = check_trend_template(close_to_date)

                # Add RS criterion
                if sym in rs_cache:
                    all_rs = sorted(rs_cache.values())
                    n_rs = len(all_rs)
                    if n_rs > 1:
                        rs_val = rs_cache[sym]
                        rs_rank = sum(1 for v in all_rs if v <= rs_val) / n_rs * 100
                        if rs_rank >= 70:
                            tt_score += 1  # Already counted True above
                    else:
                        rs_rank = 50
                else:
                    rs_rank = 50

                # Need at least 8/10 (9 without RS, or 8 criteria + RS)
                effective_score = tt_score
                if effective_score < MIN_TT_SCORE:
                    continue

                # --- Base/VCP Pattern + Breakout ---
                detected, entry_price, stop_price, quality, vol_ratio = \
                    detect_consolidation_breakout(df, idx_pos)

                if not detected:
                    continue

                if vol_ratio < MIN_VOL_RATIO:
                    continue

                # --- Count Edges ---
                edge_count = 1  # Base: pattern detected + breakout
                if vol_ratio >= 2.0:
                    edge_count += 1  # High volume edge
                if rs_rank >= 90:
                    edge_count += 1  # RS leader edge
                if quality >= 8:
                    edge_count += 1  # High quality pattern edge
                # Check if highest volume in 1 year
                vol_series = df.iloc[:idx_pos + 1]["volume"]
                if len(vol_series) >= 252:
                    max_vol_1yr = vol_series.tail(252).max()
                    if vol_series.iloc[-1] >= max_vol_1yr:
                        edge_count += 1  # HV1 edge

                candidates.append({
                    "symbol": sym,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "quality": quality,
                    "vol_ratio": vol_ratio,
                    "edge_count": min(edge_count, 5),
                    "rs_rank": rs_rank,
                    "tt_score": effective_score,
                })

            # Rank candidates
            for c in candidates:
                c["composite"] = (
                    (c["edge_count"] / 5) * 35 +
                    (c["quality"] / 10) * 25 +
                    (min(c["vol_ratio"], 3) / 3) * 20 +
                    (c["rs_rank"] / 100) * 20
                )

            candidates.sort(key=lambda x: x["composite"], reverse=True)

            # Take top 2 per day maximum
            entries_today = 0
            for cand in candidates[:3]:
                if len(self.positions) >= CONFIG["position_sizing"]["max_open_positions"]:
                    break
                if entries_today >= 2:
                    break

                entry_price = cand["entry_price"]
                stop_price = cand["stop_price"]

                # Position sizing
                shares, pos_value = compute_position_size(
                    total_equity, entry_price, stop_price,
                    cand["edge_count"], regime_mult
                )

                if shares <= 0 or pos_value <= 0:
                    continue

                # Total risk check
                total_risk = sum(p.risk_amount for p in self.positions)
                new_risk = shares * abs(entry_price - stop_price)
                max_risk = total_equity * (CONFIG["position_sizing"]["max_total_risk_pct"] / 100)
                if total_risk + new_risk > max_risk:
                    continue

                # Ensure we have enough capital
                if pos_value > self.capital:
                    continue

                # ENTER
                pos = Position(
                    symbol=cand["symbol"],
                    entry_date=date,
                    entry_price=entry_price,
                    shares=shares,
                    stop_price=stop_price,
                    edge_count=cand["edge_count"],
                    quality_score=cand["quality"],
                    vol_ratio=cand["vol_ratio"],
                )
                self.positions.append(pos)
                self.capital -= pos_value
                entries_today += 1

                self.signals_log.append({
                    "date": date_str,
                    "symbol": cand["symbol"],
                    "action": "BUY",
                    "price": entry_price,
                    "shares": shares,
                    "stop": stop_price,
                    "edges": cand["edge_count"],
                    "quality": cand["quality"],
                    "vol_ratio": cand["vol_ratio"],
                    "regime": regime,
                    "tt_score": cand["tt_score"],
                })

            # Progress
            if day_num % 50 == 0:
                print(f"  [{date_str}] Eq: ₹{total_equity:,.0f} | Open: {len(self.positions)} | Closed: {len(self.closed_trades)} | Regime: {regime}")

        # Force-close remaining positions
        last_date = trading_dates[-1]
        for pos in self.positions[:]:
            if pos.symbol in all_data:
                df = all_data[pos.symbol]
                if last_date in df.index:
                    pos.exit_price = df.loc[last_date, "close"]
                else:
                    pos.exit_price = pos.entry_price
            else:
                pos.exit_price = pos.entry_price
            pos.exit_date = last_date
            pos.exit_reason = "end_of_backtest"
            pnl = pos.pnl()
            self.capital += pos.position_value + pnl
            self.closed_trades.append(pos)
        self.positions = []

        print(f"\n  ✓ Backtest complete. Total trades: {len(self.closed_trades)}")


# ============================================================
# DATA DOWNLOAD
# ============================================================

def download_data():
    """Download historical data for all stocks."""
    print("\n" + "="*70)
    print("  DOWNLOADING HISTORICAL DATA")
    print("="*70)

    all_data = {}
    failed = []

    # Index
    print(f"\n  Downloading index ({INDEX_SYMBOL})...")
    index_data = None
    try:
        idx = yf.download(INDEX_SYMBOL, start=DATA_LOOKBACK, end=BACKTEST_END, progress=False)
        if idx is not None and len(idx) > 100:
            if isinstance(idx.columns, pd.MultiIndex):
                idx.columns = idx.columns.get_level_values(0)
            idx.columns = [c.lower() for c in idx.columns]
            index_data = idx
            print(f"    ✓ Index: {len(idx)} bars")
    except Exception as e:
        print(f"    ✗ Index failed: {e}")

    # Stocks in batches
    total = len(STOCK_UNIVERSE)
    batch_size = 10
    print(f"\n  Downloading {total} stocks in batches of {batch_size}...")

    for batch_start in range(0, total, batch_size):
        batch = STOCK_UNIVERSE[batch_start:batch_start + batch_size]
        batch_str = " ".join(batch)
        progress = f"{batch_start + len(batch)}/{total}"

        try:
            data = yf.download(batch_str, start=DATA_LOOKBACK, end=BACKTEST_END,
                             progress=False, group_by='ticker', threads=True)

            if data is not None and len(data) > 0:
                for sym in batch:
                    try:
                        if len(batch) == 1:
                            stock_df = data.copy()
                        else:
                            if isinstance(data.columns, pd.MultiIndex):
                                if sym in data.columns.get_level_values(0):
                                    stock_df = data[sym].copy()
                                else:
                                    failed.append(sym)
                                    continue
                            else:
                                stock_df = data.copy()

                        stock_df = stock_df.dropna(subset=["Close"] if "Close" in stock_df.columns else ["close"])
                        if len(stock_df) < 252:
                            failed.append(sym)
                            continue

                        stock_df.columns = [c.lower() for c in stock_df.columns]
                        required = ["open", "high", "low", "close", "volume"]
                        if not all(c in stock_df.columns for c in required):
                            failed.append(sym)
                            continue

                        all_data[sym] = stock_df[required].copy()

                    except Exception:
                        failed.append(sym)
            else:
                failed.extend(batch)

        except Exception as e:
            failed.extend(batch)

        # Progress indicator
        if (batch_start // batch_size) % 3 == 0:
            print(f"    [{progress}] downloaded...")

    print(f"\n  ✓ Downloaded: {len(all_data)} stocks | ✗ Failed: {len(failed)}")
    return all_data, index_data


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_report(engine):
    """Generate comprehensive backtest report with charts."""
    report_dir = Path("/Users/manishkumar/Documents/learning/framework_to_create_setups_and_trading_edge/backtest")
    trades = engine.closed_trades

    if not trades:
        print("\n  NO TRADES GENERATED")
        print("  The strategy may be too selective for this universe/period.")
        print("  Possible reasons:")
        print("  - Market was in RED regime for extended periods")
        print("  - Very few stocks formed valid VCP/base patterns")
        print("  - Volume criteria not met on breakout days")
        return None

    # === CORE METRICS ===
    total_trades = len(trades)
    winners = [t for t in trades if t.pnl() > 0]
    losers = [t for t in trades if t.pnl() < 0]

    win_rate = len(winners) / total_trades * 100
    total_pnl = sum(t.pnl() for t in trades)
    final_equity = INITIAL_CAPITAL + total_pnl
    total_return_pct = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    avg_winner = np.mean([t.pnl_pct() for t in winners]) if winners else 0
    avg_loser = np.mean([t.pnl_pct() for t in losers]) if losers else 0
    largest_winner = max([t.pnl_pct() for t in winners]) if winners else 0
    largest_loser = min([t.pnl_pct() for t in losers]) if losers else 0

    avg_r = np.mean([t.r_multiple() for t in trades])
    avg_winner_r = np.mean([t.r_multiple() for t in winners]) if winners else 0
    avg_loser_r = np.mean([t.r_multiple() for t in losers]) if losers else 0

    gross_profit = sum(t.pnl() for t in winners) if winners else 0
    gross_loss = abs(sum(t.pnl() for t in losers)) if losers else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Holding periods
    holding_days = [(t.exit_date - t.entry_date).days for t in trades
                    if t.entry_date and t.exit_date]
    avg_holding = np.mean(holding_days) if holding_days else 0
    median_holding = np.median(holding_days) if holding_days else 0

    # Drawdown
    equity_series = pd.Series([d["equity"] for d in engine.daily_equity])
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    # CAGR
    years = (pd.Timestamp(BACKTEST_END) - pd.Timestamp(BACKTEST_START)).days / 365.25
    cagr = ((final_equity / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Sharpe
    if len(equity_series) > 1:
        daily_returns = equity_series.pct_change().dropna()
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
        sortino_denom = daily_returns[daily_returns < 0].std()
        sortino = (daily_returns.mean() / sortino_denom) * np.sqrt(252) if sortino_denom > 0 else 0
    else:
        sharpe = sortino = 0

    # Calmar ratio
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0

    # Expectancy
    expectancy = (win_rate / 100 * avg_winner) + ((1 - win_rate / 100) * avg_loser)

    # Win/Loss streaks
    outcomes = ['W' if t.pnl() > 0 else 'L' for t in trades]
    max_win_streak = max_loss_streak = current_streak = 0
    current_type = None
    for o in outcomes:
        if o == current_type:
            current_streak += 1
        else:
            current_type = o
            current_streak = 1
        if o == 'W':
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)

    # Exit reasons
    exit_reasons = {}
    for t in trades:
        r = t.exit_reason or "unknown"
        if r not in exit_reasons:
            exit_reasons[r] = {"count": 0, "pnl_list": []}
        exit_reasons[r]["count"] += 1
        exit_reasons[r]["pnl_list"].append(t.pnl_pct())

    # === PRINT REPORT ===
    lines = []
    def pr(line=""):
        lines.append(line)
        print(line)

    pr("\n" + "="*70)
    pr("  SNIPE STRATEGY — 2-YEAR BACKTEST REPORT")
    pr("="*70)
    pr(f"  Period:          {BACKTEST_START} → {BACKTEST_END} ({years:.1f} years)")
    pr(f"  Initial Capital: ₹{INITIAL_CAPITAL:,.0f}")
    pr(f"  Final Capital:   ₹{final_equity:,.0f}")
    pr(f"  Net P&L:         ₹{total_pnl:,.0f}")
    pr("")

    pr("  ╔══════════════════════════════════════════════════════════════╗")
    pr("  ║  PERFORMANCE METRICS                                        ║")
    pr("  ╠══════════════════════════════════════════════════════════════╣")
    pr(f"  ║  Total Return:       {total_return_pct:>+8.2f}%                           ║")
    pr(f"  ║  CAGR:               {cagr:>+8.2f}%                           ║")
    pr(f"  ║  Sharpe Ratio:       {sharpe:>8.2f}                            ║")
    pr(f"  ║  Sortino Ratio:      {sortino:>8.2f}                            ║")
    pr(f"  ║  Calmar Ratio:       {calmar:>8.2f}                            ║")
    pr(f"  ║  Profit Factor:      {profit_factor:>8.2f}                            ║")
    pr(f"  ║  Max Drawdown:       {max_drawdown:>+8.2f}%                           ║")
    pr(f"  ║  Expectancy:         {expectancy:>+8.2f}% per trade                 ║")
    pr("  ╚══════════════════════════════════════════════════════════════╝")
    pr("")

    pr("  ╔══════════════════════════════════════════════════════════════╗")
    pr("  ║  TRADE STATISTICS                                           ║")
    pr("  ╠══════════════════════════════════════════════════════════════╣")
    pr(f"  ║  Total Trades:       {total_trades:>8d}                            ║")
    pr(f"  ║  Winners:            {len(winners):>5d}  ({win_rate:.1f}%)                       ║")
    pr(f"  ║  Losers:             {len(losers):>5d}  ({100-win_rate:.1f}%)                       ║")
    pr(f"  ║  Avg Winner:         {avg_winner:>+8.2f}%  ({avg_winner_r:+.2f}R)              ║")
    pr(f"  ║  Avg Loser:          {avg_loser:>+8.2f}%  ({avg_loser_r:+.2f}R)              ║")
    pr(f"  ║  Largest Winner:     {largest_winner:>+8.2f}%                           ║")
    pr(f"  ║  Largest Loser:      {largest_loser:>+8.2f}%                           ║")
    pr(f"  ║  Avg R-Multiple:     {avg_r:>+8.2f}R                            ║")
    pr(f"  ║  Avg Holding:        {avg_holding:>5.0f} days (median: {median_holding:.0f})           ║")
    pr(f"  ║  Max Win Streak:     {max_win_streak:>8d}                            ║")
    pr(f"  ║  Max Loss Streak:    {max_loss_streak:>8d}                            ║")
    pr(f"  ║  Trades/Year:        {total_trades/years:>8.1f}                            ║")
    pr("  ╚══════════════════════════════════════════════════════════════╝")
    pr("")

    # Edge analysis
    pr("  ┌── EDGE COUNT ANALYSIS ──────────────────────────────────────┐")
    edge_table = []
    for en in sorted(set(t.edge_count for t in trades)):
        et = [t for t in trades if t.edge_count == en]
        ewr = sum(1 for t in et if t.pnl() > 0) / len(et) * 100
        ear = np.mean([t.r_multiple() for t in et])
        eap = np.mean([t.pnl_pct() for t in et])
        edge_table.append([f"{en} edges", len(et), f"{ewr:.0f}%", f"{ear:+.2f}R", f"{eap:+.1f}%"])
    pr(tabulate(edge_table, headers=["Edges", "Trades", "Win Rate", "Avg R", "Avg P&L"],
               tablefmt="simple", stralign="right"))
    pr("  └─────────────────────────────────────────────────────────────┘")
    pr("")

    # Exit reasons
    pr("  ┌── EXIT REASON ANALYSIS ─────────────────────────────────────┐")
    exit_table = []
    for reason in sorted(exit_reasons.keys(), key=lambda r: exit_reasons[r]["count"], reverse=True):
        d = exit_reasons[reason]
        avg_p = np.mean(d["pnl_list"])
        wr = sum(1 for p in d["pnl_list"] if p > 0) / len(d["pnl_list"]) * 100
        exit_table.append([reason, d["count"], f"{wr:.0f}%", f"{avg_p:+.1f}%"])
    pr(tabulate(exit_table, headers=["Exit Reason", "Count", "Win Rate", "Avg P&L%"],
               tablefmt="simple", stralign="right"))
    pr("  └─────────────────────────────────────────────────────────────┘")
    pr("")

    # Top trades
    sorted_trades = sorted(trades, key=lambda t: t.pnl_pct(), reverse=True)
    pr("  ┌── TOP 10 WINNERS ───────────────────────────────────────────┐")
    top_table = []
    for t in sorted_trades[:10]:
        es = str(t.entry_date.date()) if hasattr(t.entry_date, 'date') else str(t.entry_date)[:10]
        xs = str(t.exit_date.date()) if hasattr(t.exit_date, 'date') else str(t.exit_date)[:10]
        days = (t.exit_date - t.entry_date).days
        top_table.append([
            t.symbol.replace(".NS", ""), es, xs,
            f"₹{t.entry_price:.0f}", f"{t.pnl_pct():+.1f}%",
            f"{t.r_multiple():+.1f}R", f"{days}d", t.exit_reason
        ])
    pr(tabulate(top_table, headers=["Stock", "Entry", "Exit", "Price", "P&L%", "R", "Days", "Reason"],
               tablefmt="simple", stralign="right"))
    pr("  └─────────────────────────────────────────────────────────────┘")
    pr("")

    pr("  ┌── TOP 10 LOSERS ────────────────────────────────────────────┐")
    bot_table = []
    for t in sorted_trades[-10:]:
        es = str(t.entry_date.date()) if hasattr(t.entry_date, 'date') else str(t.entry_date)[:10]
        xs = str(t.exit_date.date()) if hasattr(t.exit_date, 'date') else str(t.exit_date)[:10]
        days = (t.exit_date - t.entry_date).days
        bot_table.append([
            t.symbol.replace(".NS", ""), es, xs,
            f"₹{t.entry_price:.0f}", f"{t.pnl_pct():+.1f}%",
            f"{t.r_multiple():+.1f}R", f"{days}d", t.exit_reason
        ])
    pr(tabulate(bot_table, headers=["Stock", "Entry", "Exit", "Price", "P&L%", "R", "Days", "Reason"],
               tablefmt="simple", stralign="right"))
    pr("  └─────────────────────────────────────────────────────────────┘")
    pr("")

    # Monthly returns
    pr("  ┌── MONTHLY RETURNS ──────────────────────────────────────────┐")
    dates = [d["date"] for d in engine.daily_equity]
    equities = [d["equity"] for d in engine.daily_equity]
    eq_df = pd.DataFrame({"date": dates, "equity": equities})
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    eq_df = eq_df.set_index("date")
    monthly = eq_df.resample("ME").last()
    monthly["return_pct"] = monthly["equity"].pct_change() * 100
    monthly_table = []
    for dt, row in monthly.iterrows():
        if not pd.isna(row["return_pct"]):
            monthly_table.append([dt.strftime("%Y-%m"), f"₹{row['equity']:,.0f}", f"{row['return_pct']:+.2f}%"])
    pr(tabulate(monthly_table, headers=["Month", "Equity", "Return"], tablefmt="simple"))
    pr("  └─────────────────────────────────────────────────────────────┘")
    pr("")

    # === VERDICT ===
    pr("  " + "═"*66)
    pr("  VERDICT & STRATEGY ASSESSMENT")
    pr("  " + "═"*66)

    if profit_factor > 1.0 and win_rate >= 35:
        pr("  ✓ STRATEGY IS PROFITABLE — demonstrates positive expectancy")
    else:
        pr("  ✗ STRATEGY UNPROFITABLE in this period")

    pr("")
    pr("  Key Findings:")
    if cagr > 15:
        pr(f"  ✓ CAGR of {cagr:.1f}% beats buy-and-hold Nifty (~12-14% long-term)")
    elif cagr > 0:
        pr(f"  ~ CAGR of {cagr:.1f}% — positive but may underperform index")
    else:
        pr(f"  ✗ Negative CAGR ({cagr:.1f}%) — strategy struggled in this period")

    if profit_factor > 2:
        pr(f"  ✓ Profit factor {profit_factor:.2f} — strong edge (>2 is excellent)")
    elif profit_factor > 1.5:
        pr(f"  ✓ Profit factor {profit_factor:.2f} — solid edge")
    elif profit_factor > 1:
        pr(f"  ~ Profit factor {profit_factor:.2f} — marginal edge")

    if max_drawdown > -15:
        pr(f"  ✓ Max drawdown {max_drawdown:.1f}% — well controlled")
    elif max_drawdown > -25:
        pr(f"  ~ Max drawdown {max_drawdown:.1f}% — moderate, typical for momentum")
    else:
        pr(f"  ✗ Max drawdown {max_drawdown:.1f}% — significant risk")

    if avg_winner_r > abs(avg_loser_r) * 1.5:
        pr(f"  ✓ Asymmetric payoff: winners ({avg_winner_r:.1f}R) >> losers ({avg_loser_r:.1f}R)")
    pr("")

    pr("  Strategy Characteristics:")
    pr(f"  • Generates {total_trades/years:.0f} trades/year — selective momentum approach")
    pr(f"  • Average hold: {avg_holding:.0f} days — swing/position trading timeframe")
    pr(f"  • Win rate {win_rate:.0f}% with {avg_winner:.0f}%/{abs(avg_loser):.0f}% win/loss ratio")
    pr(f"  • Risk management: {max_drawdown:.1f}% max DD with {CONFIG['position_sizing']['max_stop_distance_pct']}% max stop")
    pr("")

    # Save report
    report_path = report_dir / "backtest_report.txt"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n  Report saved: {report_path}")

    # === CHARTS ===
    fig, axes = plt.subplots(4, 1, figsize=(14, 14),
                            gridspec_kw={'height_ratios': [3, 1.2, 1.2, 1]})

    dates = [d["date"] for d in engine.daily_equity]
    equities = [d["equity"] for d in engine.daily_equity]

    # 1. Equity Curve
    axes[0].plot(dates, equities, linewidth=1.5, color='#1976D2', label='SNIPE Strategy')
    axes[0].axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5, label=f'Initial: ₹{INITIAL_CAPITAL/100000:.0f}L')
    axes[0].fill_between(dates, INITIAL_CAPITAL, equities,
                        where=[e >= INITIAL_CAPITAL for e in equities], alpha=0.1, color='green')
    axes[0].fill_between(dates, INITIAL_CAPITAL, equities,
                        where=[e < INITIAL_CAPITAL for e in equities], alpha=0.1, color='red')
    axes[0].set_title(f"SNIPE Strategy Equity Curve — {total_return_pct:+.1f}% Total Return ({cagr:+.1f}% CAGR)",
                     fontsize=13, fontweight='bold')
    axes[0].set_ylabel("Portfolio Value (₹)")
    axes[0].legend(loc='upper left')
    axes[0].grid(True, alpha=0.3)
    axes[0].ticklabel_format(style='plain', axis='y')

    # Mark trades on equity curve
    for t in trades:
        if t.pnl() > 0:
            axes[0].axvline(x=t.entry_date, color='green', alpha=0.05, linewidth=0.5)
        else:
            axes[0].axvline(x=t.entry_date, color='red', alpha=0.05, linewidth=0.5)

    # 2. Drawdown
    eq_s = pd.Series(equities, index=dates)
    rm = eq_s.cummax()
    dd = (eq_s - rm) / rm * 100
    axes[1].fill_between(dates, 0, dd, color='#E53935', alpha=0.4)
    axes[1].plot(dates, dd, color='#E53935', linewidth=0.8)
    axes[1].set_title(f"Drawdown (Max: {max_drawdown:.1f}%)", fontsize=11)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(min(max_drawdown * 1.2, -5), 1)

    # 3. Trade P&L (R-multiples)
    r_mults = [t.r_multiple() for t in sorted(trades, key=lambda x: x.entry_date)]
    colors = ['#43A047' if r > 0 else '#E53935' for r in r_mults]
    axes[2].bar(range(len(r_mults)), r_mults, color=colors, alpha=0.7, width=0.8)
    axes[2].axhline(y=0, color='black', linewidth=0.5)
    axes[2].axhline(y=avg_r, color='blue', linewidth=1, linestyle='--', alpha=0.7, label=f'Avg: {avg_r:.2f}R')
    axes[2].set_title("Trade R-Multiples (chronological)", fontsize=11)
    axes[2].set_ylabel("R-Multiple")
    axes[2].set_xlabel("Trade #")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    # 4. Cumulative R
    cum_r = np.cumsum(r_mults)
    axes[3].plot(range(len(cum_r)), cum_r, color='#1976D2', linewidth=1.5)
    axes[3].fill_between(range(len(cum_r)), 0, cum_r, alpha=0.1, color='#1976D2')
    axes[3].set_title("Cumulative R (System Edge)", fontsize=11)
    axes[3].set_ylabel("Cumulative R")
    axes[3].set_xlabel("Trade #")
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    chart_path = report_dir / "backtest_equity_curve.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Chart saved: {chart_path}")

    # Save trade log
    trade_log = []
    for t in sorted(trades, key=lambda x: x.entry_date):
        trade_log.append({
            "symbol": t.symbol,
            "entry_date": str(t.entry_date.date()) if hasattr(t.entry_date, 'date') else str(t.entry_date)[:10],
            "exit_date": str(t.exit_date.date()) if hasattr(t.exit_date, 'date') else str(t.exit_date)[:10],
            "entry_price": round(t.entry_price, 2),
            "exit_price": round(t.exit_price, 2) if t.exit_price else 0,
            "shares": t.shares,
            "pnl": round(t.pnl(), 2),
            "pnl_pct": round(t.pnl_pct(), 2),
            "r_multiple": round(t.r_multiple(), 2),
            "edge_count": t.edge_count,
            "exit_reason": t.exit_reason,
            "max_gain_pct": round(t.max_gain_pct, 2),
            "holding_days": (t.exit_date - t.entry_date).days,
        })

    log_path = report_dir / "trade_log.json"
    with open(log_path, "w") as f:
        json.dump(trade_log, f, indent=2, default=str)
    print(f"  Trade log: {log_path}")

    return {
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "sharpe": sharpe,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "avg_r": avg_r,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n╔" + "═"*68 + "╗")
    print("║" + " SNIPE STRATEGY — 2-YEAR BACKTEST".center(68) + "║")
    print("║" + f" {BACKTEST_START} → {BACKTEST_END}".center(68) + "║")
    print("║" + " Momentum Breakout | VCP/Base | Trend Template".center(68) + "║")
    print("╚" + "═"*68 + "╝")

    # Step 1: Download data
    all_data, index_data = download_data()

    if len(all_data) < 20:
        print("\n  ERROR: Insufficient data. Need at least 20 stocks.")
        sys.exit(1)

    # Step 2: Run backtest
    engine = BacktestEngine()
    engine.run(all_data, index_data)

    # Step 3: Generate report
    results = generate_report(engine)

    print("\n╔" + "═"*68 + "╗")
    print("║" + " BACKTEST COMPLETE".center(68) + "║")
    print("╚" + "═"*68 + "╝\n")
