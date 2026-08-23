"""SNIPE Pipeline Orchestrator — full scan from universe to watchlist."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from snipe.config import load_config
from snipe.database import init_db, get_db
from snipe.data.prices import get_stock_prices
from snipe.data.universe import get_universe
from snipe.scanning.trend_template import (
    check_trend_template, rank_relative_strength, compute_sma
)
from snipe.scanning.vcp import detect_vcp
from snipe.scanning.stage_analysis import classify_stage
from snipe.scanning.breakout import detect_breakout
from snipe.scoring.canslim import (
    score_c_criterion, score_a_criterion, score_n_criterion,
    score_s_criterion, score_l_criterion, compute_canslim_score
)
from snipe.scoring.edge import identify_edges, compute_composite_score, rank_candidates
from snipe.scoring.position_sizing import compute_position_size


def run_pipeline(
    account_equity: float = 1000000,
    regime: str = "green",
    db_path: Path | None = None,
    config: dict | None = None,
    progress_callback=None,
) -> dict:
    """Run the full SNIPE scan pipeline.

    Stages:
    1. Universe Filter (Nifty 500)
    2. Technical Pre-Screen (Trend Template pass)
    3. Pattern Detection (VCP + proximity to pivot)
    4. Fundamental Screen (CANSLIM score >= 5)
    5. Edge Scoring
    6. Final Narrowing (top 5-7, sector diversification)

    Args:
        account_equity: Account size for position sizing.
        regime: Current market regime.
        db_path: Optional database path.
        config: Optional config.
        progress_callback: Optional callable(stage, count).

    Returns:
        Dict with pipeline results including watchlist and stage counts.
    """
    if config is None:
        config = load_config()

    # Stage 1: Get universe
    universe = get_universe(db_path)
    symbols = [s["symbol"] for s in universe]
    sector_map = {s["symbol"]: s["sector"] for s in universe}

    stage_counts = {"universe": len(symbols)}

    if progress_callback:
        progress_callback("universe", len(symbols))

    # Load all price data and compute RS percentiles
    stocks_data = {}
    stock_returns = {}

    for symbol in symbols:
        df = get_stock_prices(symbol, days=260, db_path=db_path)
        if len(df) >= 200:
            stocks_data[symbol] = df
            # 6-month return for RS ranking (126 trading days)
            close = df["close"].astype(float)
            if len(close) >= 126:
                ret = (close.iloc[-1] / close.iloc[-126] - 1) * 100
            else:
                ret = (close.iloc[-1] / close.iloc[0] - 1) * 100
            stock_returns[symbol] = ret

    rs_percentiles = rank_relative_strength(stock_returns)

    # Stage 2: Trend Template Pre-Screen
    tt_passing = []
    for symbol, df in stocks_data.items():
        rs = rs_percentiles.get(symbol, 50.0)
        result = check_trend_template(df, rs, config)
        if result["trend_template_pass"]:
            tt_passing.append({
                "symbol": symbol,
                "tt_result": result,
                "rs_percentile": rs,
            })

    stage_counts["trend_template"] = len(tt_passing)
    if progress_callback:
        progress_callback("trend_template", len(tt_passing))

    # Stage 3: VCP/Pattern Detection
    pattern_candidates = []
    for item in tt_passing:
        symbol = item["symbol"]
        df = stocks_data[symbol]

        # Stage analysis
        stage_result = classify_stage(df, config)
        if stage_result["stage"] not in ("stage_2", "stage_2_early"):
            continue

        # VCP detection
        vcp_result = detect_vcp(df, config)

        # Breakout detection
        pivot_price = vcp_result.get("pivot_price", 0)
        if pivot_price > 0:
            bo_result = detect_breakout(df, pivot_price, config)
        else:
            # Use 52-week high as pivot if no VCP
            pivot_price = df["high"].astype(float).tail(252).max()
            bo_result = detect_breakout(df, pivot_price, config)

        # Include if VCP detected OR approaching/breaking out
        if (vcp_result["vcp_detected"] or
            bo_result["breakout_detected"] or
            bo_result["approaching_breakout"]):
            pattern_candidates.append({
                **item,
                "stage_result": stage_result,
                "vcp_result": vcp_result,
                "breakout_result": bo_result,
                "pivot_price": pivot_price,
            })

    stage_counts["pattern_detection"] = len(pattern_candidates)
    if progress_callback:
        progress_callback("pattern_detection", len(pattern_candidates))

    # Stage 4: CANSLIM Fundamental Screen
    fundamental_candidates = []
    for item in pattern_candidates:
        symbol = item["symbol"]
        df = stocks_data[symbol]
        close = df["close"].astype(float)
        current_price = close.iloc[-1]
        high_52w = close.tail(252).max()

        # Get fundamental data from DB
        conn = get_db(db_path)
        fund_row = conn.execute(
            "SELECT * FROM fundamentals WHERE symbol = ? ORDER BY quarter DESC LIMIT 1",
            (symbol,)
        ).fetchone()
        conn.close()

        # Score individual criteria
        c_result = score_c_criterion(
            dict(fund_row)["eps_growth_qoq"] if fund_row else None,
            config=config
        )
        a_result = score_a_criterion(None, dict(fund_row).get("roe") if fund_row else None, config=config)
        n_result = score_n_criterion(current_price, high_52w, config=config)
        s_result = score_s_criterion(df, config=config)
        l_result = score_l_criterion(item["rs_percentile"], config=config)
        i_result = {"i_criterion": "data_unavailable"}
        if fund_row:
            fii = dict(fund_row).get("fii_holding_pct")
            i_result = {"i_criterion": fii is not None and fii > 0}

        # Aggregate criteria
        all_criteria = {
            "c_criterion": c_result.get("c_criterion"),
            "a_criterion": a_result.get("a_criterion"),
            "n_criterion": n_result.get("n_criterion"),
            "s_criterion": s_result.get("s_criterion"),
            "l_criterion": l_result.get("l_criterion"),
            "i_criterion": i_result.get("i_criterion"),
            "m_criterion": regime != "red",  # Market direction based on regime
        }
        canslim = compute_canslim_score(all_criteria)

        item["canslim_result"] = {**all_criteria, **canslim}
        item["canslim_score"] = canslim["canslim_score"]

        # Don't filter on fundamentals too strictly — include if score >= 3
        # (many Indian stocks lack full data)
        if canslim["canslim_score"] >= 3:
            fundamental_candidates.append(item)

    stage_counts["fundamental_screen"] = len(fundamental_candidates)
    if progress_callback:
        progress_callback("fundamental_screen", len(fundamental_candidates))

    # Stage 5: Edge Scoring
    scored_candidates = []
    for item in fundamental_candidates:
        bo = item["breakout_result"]
        vcp = item["vcp_result"]
        tt = item["tt_result"]

        edge_result = identify_edges(
            hv1_edge=bo.get("hv1_edge", False),
            hve_edge=bo.get("hve_edge", False),
            rs_percentile=item["rs_percentile"],
            rs_new_high=item["rs_percentile"] >= 90,
            vcp_quality_score=vcp.get("quality_score", 0),
            trend_template_score=tt.get("score", 0),
            config=config,
        )

        composite = compute_composite_score(
            edge_count=edge_result["edge_count"],
            vcp_quality_score=vcp.get("quality_score", 0),
            trend_template_score=tt.get("score", 0),
            canslim_score=item["canslim_score"],
            volume_ratio=bo.get("volume_ratio", 1.0),
            config=config,
        )

        scored_candidates.append({
            "symbol": item["symbol"],
            "sector": sector_map.get(item["symbol"], "Unknown"),
            "current_price": float(stocks_data[item["symbol"]]["close"].iloc[-1]),
            "pivot_price": item["pivot_price"],
            "stop_price": vcp.get("base_high", 0) * 0.92 if vcp["vcp_detected"] else item["pivot_price"] * 0.92,
            "composite_score": composite,
            "edge_count": edge_result["edge_count"],
            "edges": edge_result["edges"],
            "volume_ratio": bo.get("volume_ratio", 1.0),
            "trend_template_score": tt.get("score", 0),
            "vcp_quality": vcp.get("quality_score", 0),
            "canslim_score": item["canslim_score"],
            "stage": item["stage_result"]["stage"],
            "breakout_detected": bo.get("breakout_detected", False),
            "approaching_breakout": bo.get("approaching_breakout", False),
        })

    stage_counts["edge_scoring"] = len(scored_candidates)

    # Stage 6: Final Narrowing
    ranked = rank_candidates(scored_candidates)
    watchlist = _apply_sector_diversification(ranked, config)

    stage_counts["final_watchlist"] = len(watchlist)
    if progress_callback:
        progress_callback("final_watchlist", len(watchlist))

    # Add position sizing to watchlist items
    for item in watchlist:
        entry = item["pivot_price"]
        stop = item["stop_price"]
        if entry > 0 and stop > 0:
            sizing = compute_position_size(
                edge_count=item["edge_count"],
                entry_price=entry,
                stop_price=stop,
                account_equity=account_equity,
                regime=regime,
                config=config,
            )
            item["position_sizing"] = sizing

    # Store watchlist history
    _store_watchlist_history(watchlist, datetime.now().strftime("%Y-%m-%d"), db_path)

    return {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "stage_counts": stage_counts,
        "watchlist": watchlist,
        "regime": regime,
        "account_equity": account_equity,
    }


def _store_watchlist_history(watchlist: list[dict], scan_date: str, db_path: Path | None = None):
    """Store watchlist to history table for tracking."""
    if not watchlist:
        return

    conn = init_db(db_path)
    for item in watchlist:
        conn.execute(
            """INSERT INTO watchlist_history
               (scan_date, rank, symbol, sector, current_price, pivot_price,
                distance_to_pivot_pct, stop_price, stop_distance_pct,
                composite_score, edge_count, edges, trend_template_score,
                vcp_quality, canslim_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scan_date,
                item.get("rank", 0),
                item["symbol"],
                item.get("sector", ""),
                item.get("current_price", 0),
                item.get("pivot_price", 0),
                0,  # distance computed elsewhere
                item.get("stop_price", 0),
                0,
                item.get("composite_score", 0),
                item.get("edge_count", 0),
                ",".join(item.get("edges", [])),
                item.get("trend_template_score", 0),
                item.get("vcp_quality", 0),
                item.get("canslim_score", 0),
            ),
        )
    conn.commit()
    conn.close()


def _apply_sector_diversification(ranked: list[dict], config: dict) -> list[dict]:
    """Apply max-per-sector limit to final watchlist."""
    max_size = config["pipeline"]["max_watchlist_size"]
    max_per_sector = config["pipeline"]["max_per_sector"]

    watchlist = []
    sector_counts = {}

    for item in ranked:
        sector = item.get("sector", "Unknown")
        count = sector_counts.get(sector, 0)

        if count < max_per_sector:
            watchlist.append(item)
            sector_counts[sector] = count + 1

        if len(watchlist) >= max_size:
            break

    return watchlist
