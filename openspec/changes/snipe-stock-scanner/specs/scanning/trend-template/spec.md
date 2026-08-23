## Purpose

Validates whether a stock meets the Mark Minervini 10-point Trend Template criteria, confirming it is in a confirmed Stage 2 uptrend suitable for momentum entry.

## ADDED Requirements

### Requirement: 10-Point Trend Template Validation

The system SHALL evaluate each stock against the following 10 criteria and report a pass/fail for each point plus an overall score (0-10):

1. Current price above the 150-day (30-week) moving average
2. Current price above the 200-day (40-week) moving average
3. 150-day MA above the 200-day MA
4. 200-day MA trending up for at least 1 month (22 trading days)
5. 50-day MA above the 150-day MA
6. 50-day MA above the 200-day MA
7. Current price above the 50-day MA
8. Current price at least 30% above the 52-week low
9. Current price within 25% of the 52-week high
10. Relative Strength ranking in the top 30% of the Nifty 500 universe

The system SHALL classify a stock as "Trend Template PASS" only when all 10 criteria are satisfied.

#### Scenario: Stock passes all 10 criteria
- **WHEN** a stock's price is above 50/150/200 DMA, all MAs are properly stacked and rising, price is ≥30% above 52W low, within 25% of 52W high, and RS is top 30%
- **THEN** the system SHALL return trend_template_score=10 and trend_template_pass=true

#### Scenario: Stock fails on MA slope criterion
- **WHEN** a stock's 200-day MA has been declining over the past 22 trading days
- **THEN** the system SHALL return criterion_4=false and trend_template_pass=false with the overall score reflecting the failure

#### Scenario: Stock near 52-week low
- **WHEN** a stock's current price is only 15% above its 52-week low
- **THEN** the system SHALL return criterion_8=false (requires ≥30% above 52W low)

### Requirement: Trend Template Score Output

The system SHALL output for each evaluated stock:
- Individual pass/fail for each of the 10 criteria
- Aggregate score (0-10)
- Boolean trend_template_pass (true only if score = 10)
- The computed values for each criterion (e.g., "price_vs_200dma_pct": +45%)

#### Scenario: Partial score output
- **WHEN** a stock passes 7 of 10 criteria
- **THEN** the system SHALL output score=7, trend_template_pass=false, and list which 3 criteria failed with their computed values

### Requirement: Moving Average Calculation

The system SHALL calculate moving averages using simple moving average (SMA) of daily closing prices. The 150-day MA SHALL be used as the proxy for 30-week MA, and the 200-day MA as the proxy for 40-week MA.

#### Scenario: MA calculation with insufficient data
- **WHEN** a stock has fewer than 200 trading days of price history available
- **THEN** the system SHALL mark the stock as "insufficient_data" and not evaluate it against the Trend Template
