"""SNIPE Pipeline Orchestrator — follows the S.N.I.P.E. Complete Process Map.

S — SCAN: Cast wide net. Nifty 500 → Filter(Vol, EPS, RS) → Trend Template
N — NARROW: Shortlist top 5-7. Leading sectors → Clean chart patterns → Not extended
I — IDENTIFY EDGES: HV1, HVE, RS Edge → N-Factor → VCP quality
P — PLAN THE TRADE: Entry, SL, Target → Position size by edges
E — EXECUTE: Limit orders, respect stop, journal
"""

from datetime import datetime
from pathlib import Path

from snipe.config import load_config
from snipe.database import init_db, get_db
from snipe.data.prices import get_stock_prices
from snipe.data.universe import get_universe
from snipe.scanning.trend_template import (
    check_trend_template, rank_relative_strength
)
from snipe.scanning.vcp import detect_vcp
from snipe.scanning.stage_analysis import classify_stage
from snipe.scanning.breakout import detect_breakout
from snipe.scoring.canslim import (
    score_c_criterion, score_a_criterion, score_n_criterion,
    score_s_criterion, score_l_criterion, compute_canslim_score
)
from snipe.scoring.edge import identify_edges, compute_composite_score, rank_candidates
from snipe.scoring.regime import compute_sector_rankings
from snipe.scoring.position_sizing import compute_position_size


def run_pipeline(
    account_equity: float = 1000000,
    regime: str = "green",
    db_path: Path | None = None,
    config: dict | None = None,
    progress_callback=None,
) -> dict:
    """Run the full S.N.I.P.E. scan pipeline per framework PDF.

    S — SCAN:     Universe → Filters(Price, Vol, MCap) → RS ranking → Trend Template
    N — NARROW:   Leading sectors → Clean chart (VCP/base) → Not extended → Max 5-7
    I — IDENTIFY: Edge scoring (HV1, HVE, RS, N-Factor, Bonus) + VCP quality
    P — PLAN:     Entry/Stop/Target/Position sizing by edge count
    E — EXECUTE:  Output formatted for limit orders + journaling

    Args:
        account_equity: Account size for position sizing.
        regime: Current market regime ("green", "yellow", "red").
        db_path: Optional database path.
        config: Optional config.
        progress_callback: Optional callable(stage, count).

    Returns:
        Dict with pipeline results including watchlist and stage counts.
    """
    if config is None:
        config = load_config()

    # ═══════════════════════════════════════════════════════════════════════
    # S — SCAN: Cast a wide but structured net
    # ═══════════════════════════════════════════════════════════════════════

    # S.1: Get universe (Nifty 500)
    universe = get_universe(db_path)
    symbols = [s["symbol"] for s in universe]
    sector_map = {s["symbol"]: s["sector"] for s in universe}

    stage_counts = {"universe": len(symbols)}

    if progress_callback:
        progress_callback("universe", len(symbols))

    # S.2: Apply universe filters (PDF Page 5: Vol, EPS, RS)
    uni_config = config.get("universe", {})
    min_price = uni_config.get("min_price", 50)
    min_market_cap_cr = uni_config.get("min_market_cap_cr", 2000)
    min_avg_vol = uni_config.get("min_avg_daily_volume", 500000)
    min_avg_turnover_cr = uni_config.get("min_avg_daily_turnover_cr", 10)

    stocks_data = {}
    stock_returns = {}

    for symbol in symbols:
        df = get_stock_prices(symbol, days=260, db_path=db_path)
        if len(df) < 200:
            continue

        close = df["close"].astype(float)
        volume = df["volume"].astype(float)
        current_price = float(close.iloc[-1])

        # Filter: Price > ₹50 (avoid penny stocks — operator manipulation, wide spreads)
        if current_price < min_price:
            continue

        # Filter: Market Cap > ₹2,000 Cr (if available in DB)
        mcap_info = next((s for s in universe if s["symbol"] == symbol), None)
        if mcap_info and mcap_info.get("market_cap"):
            mcap_cr = mcap_info["market_cap"] / 1e7
            if mcap_cr < min_market_cap_cr:
                continue

        # Filter: Liquidity — avg daily volume > 5L shares OR avg turnover > ₹10 Cr
        avg_vol_50d = float(volume.tail(50).mean())
        avg_turnover_cr = (avg_vol_50d * current_price) / 1e7
        if avg_vol_50d < min_avg_vol and avg_turnover_cr < min_avg_turnover_cr:
            continue

        stocks_data[symbol] = df
        # 6-month return for RS ranking (126 trading days)
        if len(close) >= 126:
            ret_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
        else:
            ret_6m = (close.iloc[-1] / close.iloc[0] - 1) * 100
        stock_returns[symbol] = ret_6m

    # S.3: Compute dual-timeframe RS (PDF: must outperform BOTH 3-month AND 6-month)
    stock_returns_3m = {}
    for symbol, df in stocks_data.items():
        close = df["close"].astype(float)
        if len(close) >= 63:
            stock_returns_3m[symbol] = (close.iloc[-1] / close.iloc[-63] - 1) * 100
        else:
            stock_returns_3m[symbol] = stock_returns.get(symbol, 0)

    rs_percentiles_6m = rank_relative_strength(stock_returns)
    rs_percentiles_3m = rank_relative_strength(stock_returns_3m)

    # Combined RS: use the LOWER of the two percentiles (must be strong in BOTH)
    rs_percentiles = {}
    for symbol in stocks_data:
        rs_6m = rs_percentiles_6m.get(symbol, 50.0)
        rs_3m = rs_percentiles_3m.get(symbol, 50.0)
        rs_percentiles[symbol] = min(rs_6m, rs_3m)

    # S.4: Compute sector leadership (PDF Page 19: sector RS in top 25%)
    sector_top_pct = config.get("edge_scoring", {}).get("sector_leader_top_pct", 25)
    sector_rankings = compute_sector_rankings(stock_returns, sector_map, top_pct=sector_top_pct)
    leading_sectors = sector_rankings["leading_sectors"]

    # S.5: Trend Template (10-criteria SEPA check — ALL must pass)
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

    stage_counts["scan_trend_template"] = len(tt_passing)
    if progress_callback:
        progress_callback("scan_trend_template", len(tt_passing))

    # ═══════════════════════════════════════════════════════════════════════
    # N — NARROW: Shortlist top 5-7 only
    # ═══════════════════════════════════════════════════════════════════════

    # N.1: Leading sector filter (PDF Page 11 + Page 19 Criterion 10)
    # "Is it in a leading sector? NO → Remove"
    sector_filtered = [
        item for item in tt_passing
        if sector_map.get(item["symbol"], "") in leading_sectors
    ]
    stage_counts["narrow_sector"] = len(sector_filtered)

    # N.2: Clean chart patterns — VCP/base detection + Stage 2 confirmation
    pattern_candidates = []
    for item in sector_filtered:
        symbol = item["symbol"]
        df = stocks_data[symbol]

        # Stage analysis: must be Stage 2
        stage_result = classify_stage(df, config)
        if stage_result["stage"] not in ("stage_2", "stage_2_early"):
            continue

        # VCP detection: "Clean chart patterns"
        vcp_result = detect_vcp(df, config)

        # Determine pivot price
        pivot_price = vcp_result.get("pivot_price", 0)
        if pivot_price <= 0:
            # Use 52-week high as pivot if no VCP detected
            pivot_price = float(df["high"].astype(float).tail(252).max())

        # Breakout detection
        bo_result = detect_breakout(df, pivot_price, config)

        # Include if VCP detected OR approaching/breaking out of pivot
        if (vcp_result["vcp_detected"] or
                bo_result["breakout_detected"] or
                bo_result["approaching_breakout"]):

            # N.3: "Not extended" check (FOMO bias fix)
            # PDF: "If it's >10% extended past pivot, it's not your trade"
            current_price = float(df["close"].astype(float).iloc[-1])
            pct_above_pivot = ((current_price - pivot_price) / pivot_price) * 100
            if pct_above_pivot > 10:
                continue  # Too extended — not tradeable

            pattern_candidates.append({
                **item,
                "stage_result": stage_result,
                "vcp_result": vcp_result,
                "breakout_result": bo_result,
                "pivot_price": pivot_price,
            })

    stage_counts["narrow_patterns"] = len(pattern_candidates)
    if progress_callback:
        progress_callback("narrow_patterns", len(pattern_candidates))

    # N.3: Fundamental qualification (CANSLIM — supports narrowing)
    narrowed_candidates = []
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

        # Score individual CANSLIM criteria
        c_result = score_c_criterion(
            dict(fund_row)["eps_growth_qoq"] if fund_row else None,
            config=config
        )
        a_result = score_a_criterion(
            None, dict(fund_row).get("roe") if fund_row else None, config=config
        )
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
            "m_criterion": regime != "red",
        }
        canslim = compute_canslim_score(all_criteria)

        item["canslim_result"] = {**all_criteria, **canslim}
        item["canslim_score"] = canslim["canslim_score"]

        # Minimum qualification: score >= 3 (lenient due to Indian data gaps)
        if canslim["canslim_score"] >= 3:
            narrowed_candidates.append(item)

    stage_counts["narrow_qualified"] = len(narrowed_candidates)
    if progress_callback:
        progress_callback("narrow_qualified", len(narrowed_candidates))

    # ═══════════════════════════════════════════════════════════════════════
    # I — IDENTIFY EDGES: HV1, HVE, RS Edge, N-Factor, VCP quality
    # ═══════════════════════════════════════════════════════════════════════

    scored_candidates = []
    for item in narrowed_candidates:
        bo = item["breakout_result"]
        vcp = item["vcp_result"]
        tt = item["tt_result"]

        # N-Factor: check if stock is at 52-week new high
        n_criterion = bool(item["canslim_result"].get("n_criterion", False))

        edge_result = identify_edges(
            hv1_edge=bo.get("hv1_edge", False),
            hve_edge=bo.get("hve_edge", False),
            rs_percentile=item["rs_percentile"],
            rs_new_high=item["rs_percentile"] >= 90,
            n_factor_new_high=n_criterion,
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

        stock_sector = sector_map.get(item["symbol"], "Unknown")
        sector_rank = sector_rankings["sector_ranks"].get(stock_sector, 50)

        scored_candidates.append({
            "symbol": item["symbol"],
            "sector": stock_sector,
            "sector_trending": stock_sector in leading_sectors,
            "sector_rank": sector_rank,
            "current_price": float(stocks_data[item["symbol"]]["close"].iloc[-1]),
            "pivot_price": item["pivot_price"],
            "stop_price": max(vcp.get("base_low", 0), item["pivot_price"] * 0.92) if vcp["vcp_detected"] else item["pivot_price"] * 0.92,
            "composite_score": composite,
            "edge_count": edge_result["edge_count"],
            "edges": edge_result["edges"],
            "volume_ratio": bo.get("volume_ratio", 1.0),
            "trend_template_score": tt.get("score", 0),
            "vcp_quality": vcp.get("quality_score", 0),
            "canslim_score": item["canslim_score"],
            "canslim_detail": {
                "C": item["canslim_result"].get("c_criterion"),
                "A": item["canslim_result"].get("a_criterion"),
                "N": item["canslim_result"].get("n_criterion"),
                "S": item["canslim_result"].get("s_criterion"),
                "L": item["canslim_result"].get("l_criterion"),
                "I": item["canslim_result"].get("i_criterion"),
                "M": item["canslim_result"].get("m_criterion"),
            },
            "stage": item["stage_result"]["stage"],
            "breakout_detected": bo.get("breakout_detected", False),
            "approaching_breakout": bo.get("approaching_breakout", False),
        })

    stage_counts["identify_edges"] = len(scored_candidates)

    # ═══════════════════════════════════════════════════════════════════════
    # P — PLAN THE TRADE: Entry, SL, Target, Position size by edges
    # ═══════════════════════════════════════════════════════════════════════

    # Rank by composite score and apply sector diversification (max 5-7 final)
    ranked = rank_candidates(scored_candidates)
    watchlist = _apply_sector_diversification(ranked, config)

    stage_counts["final_watchlist"] = len(watchlist)
    if progress_callback:
        progress_callback("final_watchlist", len(watchlist))

    # Position sizing for each watchlist item
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

    # ═══════════════════════════════════════════════════════════════════════
    # E — EXECUTE: Store history + output for journaling
    # ═══════════════════════════════════════════════════════════════════════

    _store_watchlist_history(watchlist, datetime.now().strftime("%Y-%m-%d"), db_path)

    return {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "stage_counts": stage_counts,
        "watchlist": watchlist,
        "regime": regime,
        "account_equity": account_equity,
        "sector_rankings": {
            "leading_sectors": leading_sectors,
            "sector_returns": sector_rankings["sector_returns"],
        },
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
                0,
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
