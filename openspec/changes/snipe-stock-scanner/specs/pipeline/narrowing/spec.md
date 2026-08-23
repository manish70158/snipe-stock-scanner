## Purpose

Reduces the initial scan universe (up to 500 stocks) through progressive filtering stages to produce a final actionable watchlist of 5-7 highest-conviction candidates ranked by composite edge score.

## ADDED Requirements

### Requirement: Pipeline Stage Definition

The system SHALL process stocks through the following sequential stages:

1. **Universe Filter**: Start with Nifty 500 constituents (or user-defined universe)
2. **Technical Pre-Screen**: Apply Trend Template (must pass all 10 points) → typically reduces to 50-80 stocks
3. **Pattern Detection**: Identify VCP/base patterns and proximity to pivot → typically reduces to 15-25 stocks
4. **Fundamental Screen**: Apply CANSLIM criteria (score ≥ 5) → typically reduces to 8-15 stocks
5. **Edge Scoring**: Compute composite edge score and rank
6. **Final Narrowing**: Select top 5-7 by composite score, ensuring sector diversification (max 2 per sector)

#### Scenario: Full pipeline execution
- **WHEN** the scanner runs on 500 stocks
- **THEN** the system SHALL output the count at each stage (e.g., 500 → 65 → 18 → 11 → ranked → top 7) and the final watchlist of 5-7 stocks

#### Scenario: No stocks pass all filters
- **WHEN** no stocks pass the Trend Template + VCP + CANSLIM combined criteria
- **THEN** the system SHALL report watchlist_empty=true with the stage at which all candidates were eliminated

### Requirement: Sector Diversification in Final List

The system SHALL enforce maximum 2 stocks from the same sector in the final 5-7 candidate list. If more than 2 top-ranked stocks are from the same sector, the system SHALL take the top 2 from that sector and fill remaining slots from the next-best stocks in other sectors.

#### Scenario: Sector concentration override
- **WHEN** the top 5 stocks by composite score are all from the IT sector
- **THEN** the system SHALL select the top 2 IT stocks and fill positions 3-7 from the next-best stocks in other sectors

#### Scenario: Diverse top list
- **WHEN** the top 7 stocks come from 5 different sectors
- **THEN** the system SHALL present all 7 without sector adjustment

### Requirement: Watchlist Output Format

The system SHALL output the final watchlist with for each stock:
- Rank (1-7)
- Symbol and company name
- Sector
- Current price
- Pivot price (entry trigger)
- Distance to pivot (%)
- Stop loss level and distance (%)
- Composite edge score
- Edge count and which edges
- Trend Template score
- VCP quality
- CANSLIM score
- Suggested position size (shares and value)
- Risk:Reward ratio to first target

#### Scenario: Watchlist display
- **WHEN** the pipeline completes with 6 qualifying stocks
- **THEN** the system SHALL output a formatted table/list with all fields above for each stock, sorted by composite score descending

### Requirement: Daily Scan Execution

The system SHALL support daily batch execution after market close (post 3:30 PM IST) to refresh the watchlist with latest price/volume data.

#### Scenario: Daily refresh
- **WHEN** the scan is triggered after market close
- **THEN** the system SHALL use end-of-day closing prices and volumes for all calculations and output an updated watchlist

#### Scenario: Intraday scan
- **WHEN** a user manually triggers a scan during market hours
- **THEN** the system SHALL use last traded price/current volume and flag results as "intraday_preliminary" (final confirmation requires EOD data)

### Requirement: Historical Candidate Tracking

The system SHALL maintain a log of stocks that appeared on the watchlist, including:
- Date first appeared
- Entry triggered (yes/no and date)
- Outcome if entered (hit target / hit stop / still open)

#### Scenario: Tracking a watchlist stock
- **WHEN** stock XYZ appears on the watchlist on Monday with pivot at 500
- **THEN** the system SHALL track whether price crossed 500 in subsequent days and log the outcome
