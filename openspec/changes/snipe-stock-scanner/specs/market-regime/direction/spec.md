## Purpose

Evaluates overall market health using breadth indicators, index trend, and institutional flow data to classify the market regime and gate entry signals appropriately.

## ADDED Requirements

### Requirement: Market Breadth Indicators

The system SHALL compute the following breadth indicators for the Nifty 500 universe:
1. **% Stocks above 50-DMA**: Percentage of Nifty 500 constituents trading above their 50-day moving average
2. **% Stocks above 200-DMA**: Percentage of Nifty 500 constituents trading above their 200-day moving average
3. **Advance-Decline Line**: Running cumulative sum of (advancing stocks - declining stocks) on daily basis

#### Scenario: Strong breadth
- **WHEN** 72% of Nifty 500 stocks are above their 50-DMA and 68% are above their 200-DMA
- **THEN** the system SHALL report breadth_50dma=72, breadth_200dma=68, breadth_status="healthy"

#### Scenario: Deteriorating breadth
- **WHEN** % above 50-DMA drops from 65% to 35% over 2 weeks while index remains near highs
- **THEN** the system SHALL flag breadth_divergence=true (index up but breadth declining — a warning)

#### Scenario: Weak breadth
- **WHEN** only 25% of stocks are above their 50-DMA
- **THEN** the system SHALL report breadth_status="weak" indicating a hostile environment for new longs

### Requirement: Index Trend Assessment

The system SHALL evaluate Nifty 500 index trend:
- Position relative to 150-day (30-week) MA
- 150-day MA slope direction (rising/flat/falling)
- Distance from 150-day MA in percentage

#### Scenario: Index in uptrend
- **WHEN** Nifty 500 is 4% above its rising 150-day MA
- **THEN** the system SHALL report index_trend="uptrend", index_vs_150dma_pct=+4, ma_slope="rising"

#### Scenario: Index breakdown
- **WHEN** Nifty 500 crosses below its 150-day MA and the MA starts to flatten
- **THEN** the system SHALL report index_trend="breakdown", triggering regime change to "yellow" or "red"

### Requirement: FII/DII Flow Assessment

The system SHALL track net FII and DII daily cash market flows (buy - sell) and compute:
- Rolling 5-day net FII flow
- Rolling 20-day net FII flow
- Whether FII is in net buying or selling mode (20-day rolling)

#### Scenario: FII net buying
- **WHEN** 20-day rolling FII net flow is positive (+5000 crore cumulative)
- **THEN** the system SHALL report fii_flow_20d="net_buying", fii_net_20d=5000

#### Scenario: Heavy FII selling
- **WHEN** 20-day rolling FII net flow is negative (-15000 crore) and accelerating
- **THEN** the system SHALL report fii_flow_20d="heavy_selling", fii_net_20d=-15000

### Requirement: Market Regime Classification

The system SHALL classify the market into one of three regimes based on the combined signals:

- **GREEN (Full Offense)**: Nifty 500 above rising 150-day MA AND breadth_50dma ≥ 60% AND FII net buying (20-day) → Deploy full position sizing, take all signals
- **YELLOW (Caution)**: One or two indicators negative but not all → Reduce position sizes by 50%, take only highest-edge signals (edge_count ≥ 3)
- **RED (Defense)**: Nifty 500 below declining 150-day MA AND breadth_50dma < 40% → No new buy signals, protect existing positions

#### Scenario: Green regime
- **WHEN** Nifty 500 is above rising 150-day MA, 65% stocks above 50-DMA, FII in net buying mode
- **THEN** the system SHALL classify regime="green" with full position sizing authorized

#### Scenario: Yellow regime
- **WHEN** Nifty 500 is above 150-day MA but breadth_50dma has dropped to 45% and FII turned to selling
- **THEN** the system SHALL classify regime="yellow" with position sizing reduced to 50%

#### Scenario: Red regime
- **WHEN** Nifty 500 is below declining 150-day MA and only 30% of stocks above 50-DMA
- **THEN** the system SHALL classify regime="red" and suppress all new buy signals

### Requirement: Regime Change Alerts

The system SHALL detect and report regime transitions (green→yellow, yellow→red, red→yellow, yellow→green) and timestamp them.

#### Scenario: Regime transition
- **WHEN** the market moves from green to yellow (breadth deterioration)
- **THEN** the system SHALL emit regime_change event with from="green", to="yellow", date, and trigger_reason
