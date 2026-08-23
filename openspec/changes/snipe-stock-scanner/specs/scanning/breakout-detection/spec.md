## Purpose

Detects price breakouts from consolidation patterns with volume confirmation, identifying high-probability entry points where stocks emerge from bases on institutional-quality volume.

## ADDED Requirements

### Requirement: Breakout Detection

The system SHALL identify a breakout when:
1. Price closes above the pivot point (base high or VCP pivot) by at least 1%
2. Volume on the breakout day is at least 50% above the 50-day average volume
3. The stock is in confirmed Stage 2
4. The breakout occurs from a recognized base pattern (VCP, flat base, cup-with-handle, or high-tight-flag)

#### Scenario: Valid breakout with volume
- **WHEN** a stock closes 2% above its VCP pivot on volume that is 180% of the 50-day average
- **THEN** the system SHALL flag breakout_detected=true with volume_ratio=1.8 and breakout_strength="strong"

#### Scenario: Breakout without volume confirmation
- **WHEN** a stock closes above its pivot but volume is only 90% of the 50-day average
- **THEN** the system SHALL flag breakout_detected=true but volume_confirmed=false, marking it as "unconfirmed_breakout"

#### Scenario: False breakout (fail)
- **WHEN** a stock breaks above pivot but closes back below it within the same session (intraday reversal)
- **THEN** the system SHALL NOT flag a breakout (uses closing price, not intraday high)

### Requirement: HV1 Edge Detection (Highest Volume in 1 Year)

The system SHALL detect when a breakout occurs on the highest volume traded in the past 252 trading days (1 year). This constitutes the HV1 Edge — a strong institutional accumulation signal.

#### Scenario: HV1 breakout
- **WHEN** a stock breaks out above its pivot and the breakout day volume exceeds all daily volumes in the prior 252 trading days
- **THEN** the system SHALL flag hv1_edge=true and report the volume as a multiple of the 50-day average

#### Scenario: High volume but not HV1
- **WHEN** a stock breaks out on volume that is 200% of average but not the highest in 1 year (there was one higher volume day 3 months ago)
- **THEN** the system SHALL flag hv1_edge=false but still report the volume ratio

### Requirement: HVE Edge Detection (Highest Volume Ever)

The system SHALL detect when a breakout occurs on the highest volume ever recorded for that stock in available history. This constitutes the HVE Edge — the strongest institutional accumulation signal.

#### Scenario: HVE breakout
- **WHEN** a stock breaks out and the breakout day volume exceeds all daily volumes in the entire available price history
- **THEN** the system SHALL flag hve_edge=true (which also implies hv1_edge=true)

### Requirement: Breakout Proximity Alert

The system SHALL identify stocks that are within 3% of their pivot point and have not yet broken out, as "approaching breakout" candidates for the watchlist.

#### Scenario: Stock approaching pivot
- **WHEN** a VCP pivot is identified at 500 and the stock is currently trading at 490 (2% below pivot)
- **THEN** the system SHALL flag approaching_breakout=true with distance_to_pivot_pct=2.0

#### Scenario: Stock too far from pivot
- **WHEN** a VCP pivot is identified at 500 and the stock is at 460 (8% below)
- **THEN** the system SHALL NOT flag approaching_breakout (distance exceeds 3% threshold)
