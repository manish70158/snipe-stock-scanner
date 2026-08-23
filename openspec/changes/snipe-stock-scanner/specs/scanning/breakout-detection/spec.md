## Purpose

Detects price breakouts from consolidation patterns with volume confirmation, identifying high-probability entry points where stocks emerge from bases on institutional-quality volume. Also detects the HV1 and HVE edge signals.

## ADDED Requirements

### Requirement: Breakout Detection

The system SHALL identify a breakout when:
1. Price closes above the pivot point (base high or VCP pivot) by at least 1%
2. Volume on the breakout day is at least 50% above the 50-day average volume (≥1.5× 50DMA)
3. The stock is in confirmed Stage 2
4. The breakout occurs from a recognized base pattern (VCP, flat base, cup-with-handle)

#### Scenario: Valid breakout with volume
- **WHEN** a stock closes 2% above its VCP pivot on volume that is 180% of the 50-day average
- **THEN** the system SHALL flag breakout_detected=true with volume_ratio=1.8 and breakout_strength="strong"

#### Scenario: Breakout without volume confirmation
- **WHEN** a stock closes above its pivot but volume is only 90% of the 50-day average
- **THEN** the system SHALL flag breakout_detected=true but volume_confirmed=false, marking it as "unconfirmed_breakout"

#### Scenario: False breakout (fail)
- **WHEN** a stock breaks above pivot but closes back below it within the same session (intraday reversal)
- **THEN** the system SHALL NOT flag a breakout (uses closing price, not intraday high)

### Requirement: HV1 Edge Detection (Highest Volume in 50 Days)

The system SHALL detect when a breakout day's volume is the highest in the past 50 trading days AND the price closes in the upper 60% of the day's range. This constitutes the HV1 Edge — an institutional entry signal.

Per the MD framework:
- "The stock prints its HIGHEST volume in 50+ days on a single day"
- "Price closing in the upper 60% of the day's range"
- "HV1 is valid for 10 trading days. If no base forms within 10 days, ignore."

#### Scenario: HV1 breakout
- **WHEN** a stock breaks out above its pivot, the day's volume exceeds all volumes in the prior 50 days, and the close is above low + 0.6 × (high - low)
- **THEN** the system SHALL flag hv1_edge=true

#### Scenario: High volume but close in lower range
- **WHEN** a stock has highest volume in 50 days but closes in the lower 40% of the day's range (selling into strength)
- **THEN** the system SHALL flag hv1_edge=false (close must be in upper 60%)

#### Scenario: High volume but not 50-day highest
- **WHEN** a stock breaks out on volume 200% of average but not the highest in 50 days
- **THEN** the system SHALL flag hv1_edge=false but still report the volume ratio

### Requirement: HVE Edge Detection (High Volume Earnings)

The system SHALL detect when a stock surges ≥5% in a single day with volume ≥ 2× the 50-day average. This constitutes the HVE Edge — a post-result momentum signal indicating institutional repricing.

Per the MD framework:
- "Stock gaps up or surges 5%+ on earnings day with volume ≥ 2x 50DMA volume"
- "Creates a new 'floor' — stock rarely returns below earnings gap"
- "Wait 3-5 days after HVE for a pullback to the gap zone. Don't chase the spike."

Note: HVE is INDEPENDENT of HV1. They are separate edges that can occur together or independently.

#### Scenario: HVE post-earnings gap
- **WHEN** a stock gaps up 8% from previous close with volume 2.5× the 50-day average
- **THEN** the system SHALL flag hve_edge=true

#### Scenario: Small gap with high volume
- **WHEN** a stock gaps up only 3% with volume 2.5× average
- **THEN** the system SHALL flag hve_edge=false (gap must be ≥5%)

#### Scenario: Large gap with normal volume
- **WHEN** a stock gaps up 7% but volume is only 1.3× average
- **THEN** the system SHALL flag hve_edge=false (volume must be ≥2× 50DMA)

### Requirement: Breakout Proximity Alert

The system SHALL identify stocks that are within 3% of their pivot point and have not yet broken out, as "approaching breakout" candidates for the watchlist.

#### Scenario: Stock approaching pivot
- **WHEN** a VCP pivot is identified at 500 and the stock is currently trading at 490 (2% below pivot)
- **THEN** the system SHALL flag approaching_breakout=true with distance_to_pivot_pct=2.0

#### Scenario: Stock too far from pivot
- **WHEN** a VCP pivot is identified at 500 and the stock is at 460 (8% below)
- **THEN** the system SHALL NOT flag approaching_breakout (distance exceeds 3% threshold)

### Requirement: "Not Extended" Filter (MD Framework)

The system SHALL exclude stocks that are more than 10% above their pivot price. Per the MD framework: "Not extended (price within 10% of pivot)."

MD also states: "If already 20-30% above the last proper base = too risky. Pattern's R:R deteriorates dramatically when chased."

Entry rule: "If stock runs >3% past pivot without you, LET IT GO. Wait for next base."

#### Scenario: Stock too extended
- **WHEN** a stock has a VCP pivot at 500 and current price is 560 (12% above pivot)
- **THEN** the system SHALL exclude this stock (too extended, chasing risk)

#### Scenario: Stock within acceptable range
- **WHEN** a stock has a VCP pivot at 500 and current price is 540 (8% above pivot)
- **THEN** the system SHALL include it (within 10% limit, still tradeable)

#### Scenario: Stock below pivot (ideal)
- **WHEN** a stock has a VCP pivot at 500 and current price is 490 (2% below)
- **THEN** the system SHALL include it as approaching_breakout (optimal entry zone)
