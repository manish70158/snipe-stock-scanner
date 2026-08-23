## Purpose

Calculates position size and risk allocation for each trade based on the number of edges identified, account equity, market regime, and maximum portfolio risk constraints.

## ADDED Requirements

### Requirement: Edge-Based Risk Allocation

The system SHALL determine the percentage of account equity to risk per trade based on edge count:
- 1 edge: 0.5% of account equity at risk
- 2 edges: 1.0% of account equity at risk
- 3 edges: 1.5% of account equity at risk
- 4+ edges: 2.0% of account equity at risk (maximum)

Risk at stake = (Entry Price - Stop Loss Price) × Number of Shares

#### Scenario: 2-edge position sizing
- **WHEN** a stock has 2 edges, account equity is 10,00,000, entry at 500, stop at 470 (6% risk per share)
- **THEN** the system SHALL calculate: risk_amount = 10,00,000 × 1% = 10,000; shares = 10,000 / (500-470) = 333 shares; position_value = 333 × 500 = 1,66,500

#### Scenario: 4-edge maximum allocation
- **WHEN** a stock has 5 edges, account equity is 10,00,000, entry at 200, stop at 185 (7.5% per share)
- **THEN** the system SHALL cap risk at 2% (4+ edges rule): risk_amount = 20,000; shares = 20,000 / 15 = 1,333 shares; position_value = 2,66,600

#### Scenario: Tight stop increases position size
- **WHEN** a stock has 3 edges, account equity 10,00,000, entry at 1000, stop at 970 (3% risk per share)
- **THEN** the system SHALL calculate: risk_amount = 15,000; shares = 15,000 / 30 = 500 shares; position_value = 5,00,000

### Requirement: Stop Loss Distance Validation

The system SHALL enforce a maximum stop loss distance of 8% from entry. If the natural stop (below base low) exceeds 8%, the system SHALL flag the trade as "stop_too_wide" and NOT generate a position size.

#### Scenario: Acceptable stop distance
- **WHEN** entry is at 500 and base low (stop) is at 468 (6.4% below entry)
- **THEN** the system SHALL accept the stop and compute position size normally

#### Scenario: Stop too wide
- **WHEN** entry is at 500 and the base low is at 440 (12% below entry)
- **THEN** the system SHALL reject the trade with reason="stop_too_wide" (exceeds 8% maximum) and suggest waiting for a tighter setup

### Requirement: Market Regime Adjustment

The system SHALL adjust position sizing based on the current market regime:
- GREEN regime: Use full edge-based allocation (100%)
- YELLOW regime: Reduce allocation by 50% (e.g., 2-edge goes from 1% to 0.5%)
- RED regime: No new positions (position size = 0)

#### Scenario: Yellow regime reduction
- **WHEN** a 3-edge stock is identified but market regime is "yellow"
- **THEN** the system SHALL reduce risk from 1.5% to 0.75% of equity and compute shares accordingly

#### Scenario: Red regime blocks entry
- **WHEN** a 4-edge stock is identified but market regime is "red"
- **THEN** the system SHALL output position_size=0 with reason="market_regime_red"

### Requirement: Portfolio Concentration Limits

The system SHALL enforce:
- Maximum 20% of equity in a single position
- Maximum 5% of equity at risk across all open positions combined
- Maximum 8-10 open positions at any time

#### Scenario: Position too large
- **WHEN** calculated position value exceeds 20% of account equity
- **THEN** the system SHALL cap position_value at 20% of equity and recalculate shares downward

#### Scenario: Portfolio risk limit reached
- **WHEN** total risk across existing open positions is already 4.5% of equity and a new 2-edge trade wants 1% risk
- **THEN** the system SHALL warn portfolio_risk_limit_approaching=true (4.5% + 1% = 5.5% would exceed 5% cap) and suggest reducing to 0.5% risk on the new trade

### Requirement: Position Sizing Output

The system SHALL output for each trade recommendation:
- edge_count and edges list
- risk_percent (of equity)
- risk_amount (absolute)
- entry_price, stop_price, stop_distance_pct
- shares (quantity to buy)
- position_value (total capital deployed)
- position_pct_of_equity
- regime_adjustment applied
- target_1 (entry + 1× risk, R:R 1:1)
- target_2 (entry + 2× risk, R:R 2:1)
- target_3 (entry + 3× risk, R:R 3:1)

#### Scenario: Complete position output
- **WHEN** all inputs are available for a 3-edge trade in green regime
- **THEN** the system SHALL output all fields listed above with computed values
