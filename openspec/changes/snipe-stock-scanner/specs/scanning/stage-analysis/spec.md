## Purpose

Classifies stocks into Weinstein's four market stages (Basing, Advancing, Topping, Declining) and confirms Stage 2 status required for SNIPE framework entries.

## ADDED Requirements

### Requirement: Stage Classification

The system SHALL classify each stock into one of four stages:
- **Stage 1 (Basing)**: Price moving sideways, 30-week MA flattening after decline, volume sporadic
- **Stage 2 (Advancing)**: Price above rising 30-week MA, higher highs and higher lows, expanding volume on advances
- **Stage 3 (Topping)**: Price moving sideways near highs, 30-week MA flattening after advance, high volume with no progress
- **Stage 4 (Declining)**: Price below declining 30-week MA, lower highs and lower lows, expanding volume on declines

#### Scenario: Stock in Stage 2
- **WHEN** a stock's price is above a rising 150-day MA (30-week proxy), making higher swing highs and higher swing lows over the past 3 months, with volume expanding on up-weeks
- **THEN** the system SHALL classify stage="stage_2" with confidence_level based on how clearly the criteria are met

#### Scenario: Stage 3 topping pattern
- **WHEN** a stock's price is oscillating around a flattening 150-day MA with high volume churning (high volume, no price progress) over 4+ weeks
- **THEN** the system SHALL classify stage="stage_3" and flag a warning for existing holders

#### Scenario: Stage transition detected
- **WHEN** a stock previously classified as Stage 1 breaks above its 150-day MA on volume 50%+ above average
- **THEN** the system SHALL reclassify as stage="stage_2_early" indicating a potential Stage 1→2 transition

### Requirement: Stage 2 Confirmation for Entry

The system SHALL confirm Stage 2 status as a prerequisite for any SNIPE buy signal. A stock MUST be in Stage 2 (not Stage 2 early) to qualify for the final watchlist.

Stage 2 confirmation requires:
1. Price above rising 150-day MA for at least 4 weeks
2. 150-day MA slope is positive (rising)
3. At least one higher swing low established above the 150-day MA
4. 50-day MA above 150-day MA

#### Scenario: Stage 2 not confirmed
- **WHEN** a stock broke above its 150-day MA only 2 weeks ago and has not yet established a higher swing low
- **THEN** the system SHALL classify as stage="stage_2_early" and NOT include it in confirmed Stage 2 candidates

#### Scenario: Stage 2 confirmed
- **WHEN** a stock has been above a rising 150-day MA for 6 weeks, 50-day MA crossed above 150-day MA, and price pulled back and bounced forming a higher low above the 150-day MA
- **THEN** the system SHALL classify as stage="stage_2" with stage_2_confirmed=true

### Requirement: Stage Duration Tracking

The system SHALL track how long a stock has been in its current stage (in weeks) and report stage_duration_weeks in the output.

#### Scenario: Early Stage 2
- **WHEN** a stock has been in Stage 2 for 5 weeks
- **THEN** the system SHALL report stage_duration_weeks=5 indicating it is in early Stage 2 (higher risk/reward)

#### Scenario: Late Stage 2
- **WHEN** a stock has been advancing in Stage 2 for 40+ weeks with multiple bases
- **THEN** the system SHALL report stage_duration_weeks and flag late_stage_2=true as a caution indicator (higher base count increases failure rate)
