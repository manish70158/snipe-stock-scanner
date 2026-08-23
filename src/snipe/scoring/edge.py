"""Composite edge scoring and ranking."""

from snipe.config import load_config


def identify_edges(
    hv1_edge: bool = False,
    hve_edge: bool = False,
    rs_correction_edge: bool = False,
    n_factor_catalyst: bool = False,
    config: dict | None = None,
) -> dict:
    """Identify which of the 4 edges are present (MD framework).

    The 4 Edges:
    1. HV1: Highest Volume Day 1 — Institutional entry signal
    2. HVE: High Volume Earnings — Post-result momentum
    3. RS Edge: Relative Strength — Outperforming in correction
    4. N-Factor: News Catalyst — Sector/policy tailwind

    Rule: Trade only setups with 2+ edges. 1 edge = watchlist only.

    Args:
        hv1_edge: HV1 edge present (50-day highest vol + upper 60% close).
        hve_edge: HVE edge present (gap up 5%+ with vol 2x).
        rs_correction_edge: RS Edge present (fell less than 50% of Nifty's decline).
        n_factor_catalyst: N-Factor edge present (sector/policy catalyst).
        config: Optional config.

    Returns:
        Dict with edge_count, edges list, tradeable flag, and individual bools.
    """
    if config is None:
        config = load_config()

    edges = []

    if hv1_edge:
        edges.append("hv1")
    if hve_edge:
        edges.append("hve")
    if rs_correction_edge:
        edges.append("rs")
    if n_factor_catalyst:
        edges.append("n_factor")

    edge_count = len(edges)
    tradeable = edge_count >= 2  # MD: "Trade only setups with 2+ edges"

    return {
        "edge_count": edge_count,
        "edges": edges,
        "tradeable": tradeable,
        "hv1_edge": "hv1" in edges,
        "hve_edge": "hve" in edges,
        "rs_edge": "rs" in edges,
        "n_factor_edge": "n_factor" in edges,
    }


def compute_composite_score(
    edge_count: int,
    vcp_quality_score: float,
    trend_template_score: int,
    canslim_score: int,
    volume_ratio: float,
    config: dict | None = None,
) -> float:
    """Compute the composite edge score (0-100).

    Formula: weighted combination of all factors.

    Args:
        edge_count: Number of edges (0-4).
        vcp_quality_score: VCP quality (0-10).
        trend_template_score: Trend Template score (0-10).
        canslim_score: CANSLIM score (0-7).
        volume_ratio: Breakout volume ratio vs 50-day avg.
        config: Optional config.

    Returns:
        Composite score (0-100).
    """
    if config is None:
        config = load_config()

    es = config["edge_scoring"]

    # Normalize each factor to 0-1 range, then apply weight
    edge_norm = min(edge_count, 4) / 4
    vcp_norm = min(vcp_quality_score, 10) / 10
    tt_norm = min(trend_template_score, 10) / 10
    canslim_norm = min(canslim_score, 7) / 7
    vol_cap = es["volume_ratio_cap"]
    vol_norm = min(volume_ratio, vol_cap) / vol_cap

    score = (
        edge_norm * es["weight_edge_count"]
        + vcp_norm * es["weight_vcp_quality"]
        + tt_norm * es["weight_trend_template"]
        + canslim_norm * es["weight_canslim"]
        + vol_norm * es["weight_volume_ratio"]
    )

    return round(score, 1)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Rank candidates by composite score with tiebreakers.

    Tiebreaker: edge_count (higher first), then volume_ratio (higher first).

    Args:
        candidates: List of dicts with composite_score, edge_count, volume_ratio.

    Returns:
        Sorted list with rank field added.
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (
            x.get("composite_score", 0),
            x.get("edge_count", 0),
            x.get("volume_ratio", 0),
        ),
        reverse=True,
    )

    for i, c in enumerate(sorted_candidates):
        c["rank"] = i + 1

    return sorted_candidates
