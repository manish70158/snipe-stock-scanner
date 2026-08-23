"""Composite edge scoring and ranking."""

from snipe.config import load_config


def identify_edges(
    hv1_edge: bool = False,
    hve_edge: bool = False,
    rs_percentile: float = 0,
    rs_new_high: bool = False,
    sector_leader: bool = False,
    vcp_quality_score: float = 0,
    trend_template_score: int = 0,
    config: dict | None = None,
) -> dict:
    """Identify which edges are present for a stock.

    Args:
        hv1_edge: Breakout on highest volume in 1 year.
        hve_edge: Breakout on highest volume ever.
        rs_percentile: Stock's RS percentile.
        rs_new_high: RS making new high simultaneously with price.
        sector_leader: Stock in leading sector/theme.
        vcp_quality_score: VCP quality (0-10).
        trend_template_score: Trend Template score (0-10).
        config: Optional config.

    Returns:
        Dict with edge_count, edges list, and individual edge booleans.
    """
    if config is None:
        config = load_config()

    es_config = config["edge_scoring"]
    vcp_config = config["vcp"]

    edges = []

    # HV1 Edge
    if hv1_edge:
        edges.append("hv1")

    # HVE Edge (counts separately from HV1)
    if hve_edge:
        edges.append("hve")
        if "hv1" not in edges:
            edges.append("hv1")  # HVE implies HV1

    # RS Edge: top 10% AND making new RS high
    rs_threshold = es_config["rs_edge_percentile"]
    rs_edge = rs_percentile >= rs_threshold and rs_new_high
    if rs_edge:
        edges.append("rs")

    # N-Factor Edge: sector leadership
    if sector_leader:
        edges.append("n_factor")

    # VCP Edge: high quality VCP (score >= 8)
    vcp_edge = vcp_quality_score >= vcp_config["high_quality_threshold"]
    if vcp_edge:
        edges.append("vcp")

    # Trend Template Edge: perfect 10/10
    tt_edge = trend_template_score == 10
    if tt_edge:
        edges.append("trend_template")

    return {
        "edge_count": len(edges),
        "edges": edges,
        "hv1_edge": "hv1" in edges,
        "hve_edge": "hve" in edges,
        "rs_edge": "rs" in edges,
        "n_factor_edge": "n_factor" in edges,
        "vcp_edge": "vcp" in edges,
        "trend_template_edge": "trend_template" in edges,
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
        edge_count: Number of edges (0-6).
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
    edge_norm = min(edge_count, 6) / 6
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
