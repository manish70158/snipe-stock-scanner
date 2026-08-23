"""Edge-based position sizing and risk allocation."""

from snipe.config import load_config


def compute_position_size(
    edge_count: int,
    entry_price: float,
    stop_price: float,
    account_equity: float,
    regime: str = "green",
    current_total_risk: float = 0,
    current_positions: int = 0,
    config: dict | None = None,
) -> dict:
    """Compute position size based on edge count and risk parameters.

    MD Edge Scoring:
    - 0-1 edges: NO TRADE (watchlist only)
    - 2 edges: 0.5% risk, 5% max position
    - 3 edges: 1.0% risk, 8% max position
    - 4 edges: 1.5% risk, 12% max position

    Args:
        edge_count: Number of edges (0-4).
        entry_price: Planned entry price.
        stop_price: Stop-loss price.
        account_equity: Total account equity.
        regime: Market regime ("green", "yellow", "red").
        current_total_risk: Current total risk across open positions (% of equity).
        current_positions: Number of currently open positions.
        config: Optional config.

    Returns:
        Dict with complete position sizing output.
    """
    if config is None:
        config = load_config()

    ps_config = config["position_sizing"]
    mr_config = config["market_regime"]

    # Validate stop distance
    stop_distance_pct = abs((entry_price - stop_price) / entry_price) * 100
    max_stop = ps_config["max_stop_distance_pct"]

    if stop_distance_pct > max_stop:
        return {
            "valid": False,
            "reason": "stop_too_wide",
            "stop_distance_pct": round(stop_distance_pct, 2),
            "max_allowed_pct": max_stop,
            "suggestion": "Wait for a tighter setup or use a closer stop.",
        }

    # Red regime blocks entry
    if regime == "red":
        return {
            "valid": False,
            "reason": "market_regime_red",
            "position_size": 0,
            "shares": 0,
        }

    # MD: 0-1 edges = NO TRADE (watchlist only)
    if edge_count < 2:
        return {
            "valid": False,
            "reason": "insufficient_edges",
            "edge_count": edge_count,
            "shares": 0,
        }

    # Determine risk percentage based on edge count (MD position size table)
    if edge_count >= 4:
        risk_pct = 1.5
    elif edge_count == 3:
        risk_pct = 1.0
    else:  # edge_count == 2
        risk_pct = 0.5

    # Apply regime adjustment
    sizing_multiplier = mr_config[f"{regime}_sizing_multiplier"]
    adjusted_risk_pct = risk_pct * sizing_multiplier

    # Calculate risk amount
    risk_amount = account_equity * (adjusted_risk_pct / 100)

    # Calculate shares
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share == 0:
        return {"valid": False, "reason": "zero_risk_per_share"}

    shares = int(risk_amount / risk_per_share)
    position_value = shares * entry_price
    position_pct = (position_value / account_equity) * 100

    # Edge-count-based position size cap (MD: 2 edges=5%, 3 edges=8%, 4 edges=12%)
    edge_cap_map = {2: 5, 3: 8, 4: 12}
    max_position_pct = edge_cap_map.get(edge_count, 12)

    if position_pct > max_position_pct:
        max_value = account_equity * (max_position_pct / 100)
        shares = int(max_value / entry_price)
        position_value = shares * entry_price
        position_pct = (position_value / account_equity) * 100

    # Portfolio risk limit check
    max_total_risk = ps_config["max_total_risk_pct"]
    new_total_risk = current_total_risk + adjusted_risk_pct
    portfolio_risk_warning = new_total_risk > max_total_risk

    # Max positions check (MD: max 5 positions)
    max_positions = ps_config["max_open_positions"]
    positions_warning = current_positions >= max_positions

    # Targets (R-multiples) - MD: Target 1 must be ≥ 2× stop distance (R:R ≥ 2:1)
    target_1 = entry_price + 2 * risk_per_share  # 2R
    target_2 = entry_price + 3 * risk_per_share  # 3R
    target_3 = entry_price + 4 * risk_per_share  # 4R

    # Risk:Reward to first meaningful target
    rr_ratio = 2.0

    return {
        "valid": True,
        "edge_count": edge_count,
        "edges_risk_pct": risk_pct,
        "regime_adjustment": sizing_multiplier,
        "risk_percent": round(adjusted_risk_pct, 2),
        "risk_amount": round(risk_amount, 2),
        "entry_price": entry_price,
        "stop_price": stop_price,
        "stop_distance_pct": round(stop_distance_pct, 2),
        "risk_per_share": round(risk_per_share, 2),
        "shares": shares,
        "position_value": round(position_value, 2),
        "position_pct_of_equity": round(position_pct, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "target_3": round(target_3, 2),
        "risk_reward_ratio": rr_ratio,
        "portfolio_risk_limit_approaching": portfolio_risk_warning,
        "max_positions_reached": positions_warning,
        "new_total_risk_pct": round(new_total_risk, 2),
    }
