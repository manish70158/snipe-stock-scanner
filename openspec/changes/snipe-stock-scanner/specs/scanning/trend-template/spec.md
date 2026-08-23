## Purpose

Validates whether a stock meets the Mark Minervini 10-point Trend Template criteria, confirming it is in a confirmed Stage 2 uptrend suitable for momentum entry.

## ADDED Requirements

### Requirement: SEPA Trend Template Validation (PDF Page 19)

The system SHALL evaluate each stock against the 10-point SEPA Trend Template from the framework. "Every Criterion Must Be Met Before Any Entry."

**Technical Criteria (1-10, implemented as code checks C1-C10):**

Per PDF Page 19, the 10 criteria map to:
1. Price above both 150-DMA (30W MA) and 200-DMA (40W MA) — Non-negotiable [code: C1 + C2]
2. 150-DMA is ABOVE the 200-DMA — MAs in bullish order [code: C3]
3. 200-DMA trending UP for at least 1 month (ideally 4-5 months) [code: C4]
4. 50-DMA (10W MA) above both 150-DMA and 200-DMA [code: C5 + C6]
5. Current price above 50-DMA [code: C7]
6. Price at least 30% above 52-week low [code: C8]
7. Price within 25% of 52-week high [code: C9]
8. RS Rank: Top 30% minimum (dual-timeframe: min of 3-month and 6-month) [code: C10]

**Additional PDF Criteria (enforced via pipeline stages):**
9. EPS growth ≥20% QoQ for at least 2 consecutive quarters — Fundamental strength driving institutional buying [enforced when data available via CANSLIM C criterion]
10. Stock is in a leading sector (sector RS in top 25%) — Sector leadership multiplies individual stock's odds [enforced via NARROW sector filter]

The system SHALL classify a stock as "Trend Template PASS" when all 10 technical criteria (C1-C10) are satisfied. Criteria 9 and 10 from the PDF are enforced at subsequent pipeline stages (NARROW) to allow graceful handling when EPS data is unavailable.

Code implementation: 10 individual boolean checks (C1-C10), pass requires score=10.

#### Scenario: Stock passes all 10 technical criteria
- **WHEN** a stock's price is above 50/150/200 DMA, all MAs are properly stacked and rising, price is ≥30% above 52W low, within 25% of 52W high, and dual-timeframe RS is top 30%
- **THEN** the system SHALL return trend_template_score=10 and trend_template_pass=true
- **NOTE**: PDF criteria 9 (EPS) and 10 (sector) are additionally checked in the NARROW stage

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
