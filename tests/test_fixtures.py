"""Test fixtures with synthetic price data for deterministic testing."""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from snipe.scanning.trend_template import check_trend_template, rank_relative_strength
from snipe.scanning.vcp import detect_vcp
from snipe.scanning.stage_analysis import classify_stage
from snipe.scanning.breakout import detect_breakout
from snipe.scoring.edge import identify_edges, compute_composite_score
from snipe.scoring.position_sizing import compute_position_size
from snipe.scoring.canslim import score_c_criterion, score_a_criterion, compute_canslim_score
from snipe.signals.sell_rules import (
    check_defensive_signals, check_offensive_signals, compute_position_status
)


def make_stage2_uptrend(days=260, start_price=100, end_price=200):
    """Create synthetic Stage 2 uptrend data."""
    np.random.seed(42)
    prices = start_price + np.linspace(0, end_price - start_price, days)
    prices += np.random.normal(0, 2, days)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=days).strftime("%Y-%m-%d"),
        "open": prices - 1,
        "high": prices + 3,
        "low": prices - 3,
        "close": prices,
        "volume": np.random.randint(500000, 2000000, days),
    })


def make_stage4_downtrend(days=260, start_price=200, end_price=100):
    """Create synthetic Stage 4 downtrend data."""
    np.random.seed(43)
    prices = start_price - np.linspace(0, start_price - end_price, days)
    prices += np.random.normal(0, 2, days)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=days).strftime("%Y-%m-%d"),
        "open": prices + 1,
        "high": prices + 3,
        "low": prices - 3,
        "close": prices,
        "volume": np.random.randint(500000, 2000000, days),
    })


def make_vcp_pattern(days=80, base_high=200):
    """Create synthetic VCP with 3 tightening contractions."""
    np.random.seed(10)
    prices = []
    volumes = []

    # T1: drop 25% to 150, recover
    for i in range(20):
        prices.append(base_high - (50 * i / 20))
        volumes.append(1500000 - i * 20000)
    for i in range(15):
        prices.append(150 + (45 * i / 15))
        volumes.append(1000000 - i * 15000)

    # T2: drop 15%, recover
    for i in range(12):
        prices.append(195 - (29 * i / 12))
        volumes.append(800000 - i * 10000)
    for i in range(10):
        prices.append(166 + (26 * i / 10))
        volumes.append(600000 - i * 8000)

    # T3: drop 8%, recover toward pivot
    for i in range(8):
        prices.append(192 - (15 * i / 8))
        volumes.append(500000 - i * 10000)
    for i in range(15):
        prices.append(177 + (13 * i / 15))
        volumes.append(400000 - i * 5000)

    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=len(prices)).strftime("%Y-%m-%d"),
        "open": [p - 1 for p in prices],
        "high": [p + 2 for p in prices],
        "low": [p - 2 for p in prices],
        "close": prices,
        "volume": volumes[:len(prices)],
    })


class TestTrendTemplate:
    def test_stage2_passes_all(self):
        df = make_stage2_uptrend()
        result = check_trend_template(df, rs_percentile=85)
        assert result["trend_template_pass"] is True
        assert result["score"] == 10

    def test_stage4_fails(self):
        df = make_stage4_downtrend()
        result = check_trend_template(df, rs_percentile=15)
        assert result["trend_template_pass"] is False
        assert result["score"] < 5

    def test_rs_ranking(self):
        returns = {"A": 80, "B": 50, "C": 20, "D": -10, "E": 100}
        pcts = rank_relative_strength(returns)
        assert pcts["E"] == 100.0
        assert pcts["D"] == 0.0


class TestVCP:
    def test_vcp_detected(self):
        df = make_vcp_pattern()
        result = detect_vcp(df)
        assert result["vcp_detected"] is True
        assert result["contractions"] >= 2
        assert result["quality_score"] >= 7

    def test_random_no_vcp(self):
        np.random.seed(99)
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=100).strftime("%Y-%m-%d"),
            "open": np.random.normal(100, 10, 100),
            "high": np.random.normal(105, 10, 100),
            "low": np.random.normal(95, 10, 100),
            "close": np.random.normal(100, 10, 100),
            "volume": [500000] * 100,
        })
        result = detect_vcp(df)
        assert result["vcp_detected"] is False


class TestStageAnalysis:
    def test_stage2_classified(self):
        df = make_stage2_uptrend()
        result = classify_stage(df)
        assert result["stage"] in ("stage_2", "stage_2_early")

    def test_stage4_classified(self):
        df = make_stage4_downtrend()
        result = classify_stage(df)
        assert result["stage"] == "stage_4"


class TestBreakout:
    def test_breakout_on_volume(self):
        df = make_stage2_uptrend()
        # Set last day volume very high and pivot below current close
        df.loc[df.index[-1], "volume"] = 5000000
        pivot = float(df["close"].iloc[-1]) * 0.95  # 5% below current
        result = detect_breakout(df, pivot)
        assert result["breakout_detected"] == True
        assert result["volume_confirmed"] == True

    def test_no_breakout_below_pivot(self):
        df = make_stage2_uptrend()
        df.loc[df.index[-1], "volume"] = 100000  # Very low
        pivot = float(df["close"].iloc[-1]) * 1.05  # 5% above current
        result = detect_breakout(df, pivot)
        assert result["breakout_detected"] == False


class TestEdgeScoring:
    def test_composite_score_spec_example(self):
        # From spec: edge=4, vcp=9, tt=10, canslim=6, vol=2.5 → ~81
        score = compute_composite_score(4, 9, 10, 6, 2.5)
        assert 79 <= score <= 82

    def test_edge_identification(self):
        result = identify_edges(
            hv1_edge=True, rs_percentile=95, rs_new_high=True,
            vcp_quality_score=9, trend_template_score=10
        )
        assert result["edge_count"] >= 3


class TestPositionSizing:
    def test_2_edge_sizing(self):
        result = compute_position_size(2, 500, 470, 1000000)
        assert result["valid"] is True
        assert result["shares"] == 333
        assert result["risk_percent"] == 1.0

    def test_stop_too_wide(self):
        result = compute_position_size(2, 500, 440, 1000000)
        assert result["valid"] is False
        assert result["reason"] == "stop_too_wide"

    def test_red_regime_blocks(self):
        result = compute_position_size(3, 500, 470, 1000000, regime="red")
        assert result["valid"] is False
        assert result["reason"] == "market_regime_red"

    def test_yellow_halves(self):
        green = compute_position_size(2, 500, 470, 1000000, regime="green")
        yellow = compute_position_size(2, 500, 470, 1000000, regime="yellow")
        assert yellow["shares"] < green["shares"]
        assert yellow["risk_percent"] == green["risk_percent"] / 2


class TestSellSignals:
    def test_stop_loss_hit(self):
        prices = np.linspace(500, 460, 20)
        df = pd.DataFrame({
            "date": pd.date_range("2025-08-01", periods=20).strftime("%Y-%m-%d"),
            "high": prices + 5, "low": prices - 5,
            "close": prices, "volume": [1000000] * 20,
        })
        signals = check_defensive_signals(df, 500, 465)
        assert any(s["type"] == "stop_loss_hit" for s in signals)

    def test_first_target(self):
        prices = np.linspace(500, 620, 30)
        df = pd.DataFrame({
            "date": pd.date_range("2025-07-01", periods=30).strftime("%Y-%m-%d"),
            "high": prices + 3, "low": prices - 3,
            "close": prices, "volume": [800000] * 30,
        })
        signals = check_offensive_signals(df, 500, 24, 30)
        assert any(s["type"] == "first_target" for s in signals)

    def test_r_multiple(self):
        status = compute_position_status(500, 465, 570, "2025-07-01")
        assert abs(status["r_multiple"] - 2.0) < 0.01


if __name__ == "__main__":
    # Run all tests
    import sys
    pytest.main([__file__, "-v"] + sys.argv[1:])
