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

    Args:
        edge_count: Number of edges (1-6).
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

    # Determine risk percentage based on edge count
    if edge_count >= 4:
        risk_pct = ps_config["risk_4plus_edge_pct"]
    elif edge_count == 3:
        risk_pct = ps_config["risk_3_edge_pct"]
    elif edge_count == 2:
        risk_pct = ps_config["risk_2_edge_pct"]
    else:
        risk_pct = ps_config["risk_1_edge_pct"]

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

    # Edge-count-based position size cap (PDF: Score → Max % of equity)
    # Score 1: 8-10%, Score 2: 12-13%, Score 3: 15%, Score 4+: 18-20%
    edge_cap_map = {1: 10, 2: 13, 3: 15}
    edge_position_cap = edge_cap_map.get(edge_count, ps_config["max_position_pct_of_equity"])
    max_position_pct = min(edge_position_cap, ps_config["max_position_pct_of_equity"])

    if position_pct > max_position_pct:
        max_value = account_equity * (max_position_pct / 100)
        shares = int(max_value / entry_price)
        position_value = shares * entry_price
        position_pct = (position_value / account_equity) * 100

    # Portfolio risk limit check
    max_total_risk = ps_config["max_total_risk_pct"]
    new_total_risk = current_total_risk + adjusted_risk_pct
    portfolio_risk_warning = new_total_risk > max_total_risk

    # Max positions check
    max_positions = ps_config["max_open_positions"]
    positions_warning = current_positions >= max_positions

    # Targets (R-multiples)
    target_1 = entry_price + risk_per_share  # 1R
    target_2 = entry_price + 2 * risk_per_share  # 2R
    target_3 = entry_price + 3 * risk_per_share  # 3R

    # Risk:Reward to first meaningful target (2R)
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
