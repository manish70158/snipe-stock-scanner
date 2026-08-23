## Purpose

Detects Volatility Contraction Patterns (VCP) in stock price action — identifying bases with progressively tightening price contractions and declining volume that precede high-probability breakouts.

## ADDED Requirements

### Requirement: VCP Pattern Identification

The system SHALL identify a Volatility Contraction Pattern when:
1. At least 2 successive contractions (T1, T2, ...) are detected within a base
2. Each successive contraction is shallower than the previous (T2 < T1, T3 < T2)
3. The maximum first contraction (T1) SHALL NOT exceed 35% from the base high
4. Volume declines progressively through each contraction
5. The base duration is between 3 weeks minimum and 65 weeks maximum

The system SHALL report the number of contractions, their depths, and the overall base characteristics.

#### Scenario: Classic 3-contraction VCP
- **WHEN** a stock forms a base with contractions of 25%, 15%, 8% over 12 weeks with declining volume at each contraction low
- **THEN** the system SHALL identify a VCP with contractions=3, depths=[25,15,8], base_weeks=12, vcp_quality="high"

#### Scenario: Contraction not tightening
- **WHEN** a stock forms a base where the second contraction (20%) is deeper than the first (15%)
- **THEN** the system SHALL NOT classify this as a VCP pattern

#### Scenario: Base too shallow for first contraction
- **WHEN** a stock corrects only 5% from its high before forming a tight range
- **THEN** the system SHALL classify this as a "flat base" rather than a VCP (minimum T1 correction of 10% required for VCP classification)

### Requirement: Pivot Point Detection

The system SHALL identify the VCP pivot point (buy point) as the price level at the top of the last contraction before breakout. The pivot price SHALL be the highest high within the final contraction zone.

#### Scenario: Pivot identified at final contraction high
- **WHEN** a VCP has formed with the last contraction's highest price at 450
- **THEN** the system SHALL report pivot_price=450 as the breakout trigger level

#### Scenario: Price approaching pivot
- **WHEN** a stock with identified VCP pivot at 450 is currently trading at 445 (within 2% of pivot)
- **THEN** the system SHALL flag this stock as "approaching_pivot" in scan results

### Requirement: VCP Quality Scoring

The system SHALL assign a VCP quality score based on:
- Number of contractions (more = higher quality, max benefit at 4)
- Tightness of final contraction (tighter = higher quality)
- Volume dry-up at pivot (lower relative volume = higher quality)
- Base duration appropriateness (5-25 weeks optimal)

Quality levels: "high" (score ≥8/10), "medium" (5-7), "low" (3-4)

#### Scenario: High quality VCP
- **WHEN** a stock has 3+ contractions, final contraction ≤8%, volume at pivot is 40% below 50-day average volume, and base is 8 weeks
- **THEN** the system SHALL assign vcp_quality="high" with score ≥8

#### Scenario: Low quality VCP
- **WHEN** a stock has only 2 contractions, final contraction is 15%, and volume shows no dry-up
- **THEN** the system SHALL assign vcp_quality="low" with score ≤4
