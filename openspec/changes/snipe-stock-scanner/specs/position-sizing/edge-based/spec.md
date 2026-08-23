## Purpose

Calculates position size and risk allocation for each trade based on edge count, stop distance, account equity, and market regime. Enforces the MD framework's strict rules: minimum 2 edges to trade, maximum 1.5% risk, maximum 12% position, maximum 5 positions.

## ADDED Requirements

### Requirement: Minimum 2 Edges to Trade

The system SHALL reject any position where edge_count < 2. Per the MD framework:
- "Trade only setups with 2+ edges. 3-4 edges = maximum confidence = larger size."
- 0 edges = "No trade — Skip"
- 1 edge = "Watchlist only — wait for more edges"

#### Scenario: Insufficient edges (0-1)
- **WHEN** a stock has 0 or 1 edge
- **THEN** the system SHALL return valid=false with reason="insufficient_edges" and shares=0

### Requirement: Edge-Based Risk Allocation (MD Position Size Table)

The system SHALL determine risk and position caps per the MD framework table:

| Edge Count | Risk per Trade | Max Position Size | Action |
|-----------|----------------|-------------------|--------|
| 0-1 | 0% | 0% | NO TRADE |
| 2 | 0.5% of capital | 5% of portfolio | Trade with reduced size |
| 3 | 1.0% of capital | 8% of portfolio | Trade with standard size |
| 4 | 1.5% of capital | 12% of portfolio | Trade with maximum size (rare) |

Risk Amount = Account Size × Risk%
Share Quantity = Risk Amount ÷ (Entry Price - Stop Price)
Position Value = Share Quantity × Entry Price

#### Scenario: 2-edge position sizing
- **WHEN** a stock has 2 edges, account equity ₹10,00,000, entry at ₹412, stop at ₹378
- **THEN** risk_amount = ₹10,00,000 × 0.5% = ₹5,000; shares = ₹5,000 ÷ ₹34 = 147; position_value = ₹60,564 (6%)
- **NOTE** position_value 6% > 5% cap → cap at 5% = ₹50,000 → shares = 121

#### Scenario: 3-edge position sizing
- **WHEN** a stock has 3 edges, account equity ₹10,00,000, entry at ₹412, stop at ₹378
- **THEN** risk_amount = ₹10,00,000 × 1% = ₹10,000; shares = ₹10,000 ÷ ₹34 = 294; position_value = ₹1,21,128 (12.1%)
- **NOTE** position_value 12.1% > 8% cap → cap at 8% = ₹80,000 → shares = 194

#### Scenario: 4-edge maximum allocation
- **WHEN** a stock has 4 edges, account equity ₹10,00,000, entry at ₹200, stop at ₹185
- **THEN** risk_amount = ₹15,000; shares = ₹15,000 ÷ ₹15 = 1,000; position_value = ₹2,00,000 (20%)
- **NOTE** position_value 20% > 12% cap → cap at 12% = ₹1,20,000 → shares = 600

### Requirement: Stop Loss Rules (MD Framework)

The system SHALL enforce stop placement per the MD:
- **VCP stop**: Below the low of C3 (the last/tightest contraction) — NOT below base_low (T1)
- **Maximum stop distance**: 8% from entry
- "If stop requires >8%, the entry is too late — skip the trade"
- "Stop MUST be below a logical price level (not arbitrary %)"
- "NEVER widen a stop after entry"

#### Scenario: Acceptable stop (C3 low)
- **WHEN** VCP has pivot at ₹412 and C3 low at ₹378 (8.2% below)
- **THEN** the system SHALL accept (within 8% tolerance) and compute position size

#### Scenario: Stop too wide
- **WHEN** entry at ₹500 and C3 low at ₹430 (14% below)
- **THEN** the system SHALL reject with reason="stop_too_wide" — entry is too late

### Requirement: Target Setting (Minimum R:R 2:1)

Per the MD framework:
- "Minimum R:R = 2:1"
- "Target 1 must be ≥ 2× your stop distance"
- Two-Tranche Exit: Sell 50% at Target 1 (+20-25%), trail remaining with 10-DMA

The system SHALL compute targets as:
- target_1 = entry + 2 × risk_per_share (R:R 2:1) — first profit exit
- target_2 = entry + 3 × risk_per_share (R:R 3:1) — trailing stop zone
- target_3 = entry + 4 × risk_per_share (R:R 4:1) — exceptional move

#### Scenario: Target calculation
- **WHEN** entry=₹412, stop=₹378, risk_per_share=₹34
- **THEN** target_1=₹480 (2R), target_2=₹514 (3R), target_3=₹548 (4R)

### Requirement: Market Regime Adjustment

The system SHALL adjust position sizing based on market regime:
- **Stage 2 confirmed (GREEN)**: Use full edge-based allocation (100%)
- **Stage 2 late / Stage 3 signs (YELLOW)**: Reduce allocation by 50%
- **Stage 3/4 (RED)**: No new positions (position size = 0)

MD Portfolio Exposure Rules:
| Market Stage | Max Portfolio Exposure | Max New Positions/Week |
|---|---|---|
| Stage 2 confirmed | 80-100% | 3-5 |
| Stage 2 late | 50-70% | 1-2 |
| Stage 3 | 20-40% | 0-1 |
| Stage 4 | 0-10% | 0 |

#### Scenario: Yellow regime reduction
- **WHEN** a 3-edge stock is identified but market regime is "yellow"
- **THEN** the system SHALL reduce risk from 1.0% to 0.5% of equity

#### Scenario: Red regime blocks entry
- **WHEN** any setup identified but market is in Stage 3/4 (red)
- **THEN** the system SHALL output valid=false with reason="market_regime_red"

### Requirement: Portfolio Risk Limits (MD "5 Non-Negotiable Rules")

The system SHALL enforce:
- "Never risk > 1% of account on a single trade" (max 1.5% at 4 edges is the exception)
- "Never hold > 5 positions simultaneously"
- Maximum 2 stocks from the same sector (correlation rule)
- "Cut total exposure to 50% if 3 stops hit in a row" (3-Strike Rule)

#### Scenario: Max positions reached
- **WHEN** trader already has 5 open positions
- **THEN** the system SHALL warn max_positions_reached=true and block new entries

### Requirement: Position Sizing Output

The system SHALL output for each trade recommendation:
- edge_count, edges list, tradeable flag
- risk_percent (of equity)
- risk_amount (absolute ₹)
- entry_price, stop_price, stop_distance_pct
- shares (quantity to buy)
- position_value (total capital deployed)
- position_pct_of_equity
- regime_adjustment applied
- target_1 (entry + 2R, minimum acceptable target)
- target_2 (entry + 3R)
- target_3 (entry + 4R)
- risk_reward_ratio (minimum 2.0)
