## Purpose

Implements the complete S.N.I.P.E. process map — reducing the Nifty 500 universe through 5 sequential stages to produce a final actionable watchlist of 5-7 highest-conviction candidates.

## ADDED Requirements

### Requirement: S.N.I.P.E. Pipeline Stage Definition

The system SHALL process stocks through the following stages matching the PDF Complete Process Map:

**S — SCAN: Cast a wide but structured net**
1. Universe: Nifty 500 constituents
2. Filter: Price > ₹50, Market Cap > ₹2,000 Cr, Avg Volume > 5L shares OR Turnover > ₹10 Cr
3. Dual-timeframe RS: Compute RS percentiles for BOTH 3-month AND 6-month (use min of both)
4. Sector rankings: Compute sector momentum (median 6-month return), identify leading sectors (top 25%)
5. Trend Template: Apply 10-point SEPA criteria (ALL must pass)

**N — NARROW: Shortlist top 5-7 only**
1. Leading sector filter: Remove stocks NOT in a leading sector (top 25% by sector RS)
2. Clean chart patterns: VCP/base detection + confirmed Stage 2
3. Not extended: If stock is >10% above its pivot, it's not tradeable (FOMO rule)
4. Fundamental qualification: CANSLIM score ≥ 3

**I — IDENTIFY EDGES: Score the setup quality**
1. 4 core edges: HV1 (52W high volume), HVE (all-time high volume), RS (top 10% + new high), N-Factor (52W new high on price)
2. Alignment bonus: +1 when all 4 core edges align simultaneously
3. VCP Edge: High-quality VCP (score ≥ 8/10)
4. Trend Template Edge: Perfect 10/10 score
5. Composite score: Weighted combination of edges + VCP + TT + CANSLIM + volume

**P — PLAN THE TRADE: Entry, SL, Target, Position size**
1. Rank by composite score
2. Sector diversification: max 2 per sector
3. Final watchlist: top 5-7 stocks
4. Position sizing: Based on edge count (0 edges = no trade, 1 = 10% max, 2 = 13%, 3 = 15%, 4+ = 20%)

**E — EXECUTE: Output for limit orders + journaling**
1. Store watchlist history for tracking
2. Output formatted for trade execution (entry, stop, targets, shares)

#### Scenario: Full pipeline execution
- **WHEN** the scanner runs on 500 stocks
- **THEN** the system SHALL output stage counts following S.N.I.P.E.: universe=500 → scan_trend_template=55 → narrow_sector=24 → narrow_patterns=8 → narrow_qualified=8 → identify_edges=8 → final_watchlist=5

#### Scenario: "Not extended" filter applied
- **WHEN** a stock has a VCP pivot at 500 but current price is 560 (12% above pivot)
- **THEN** the system SHALL remove it during the NARROW stage (>10% extended past pivot = not your trade)

#### Scenario: Sector NARROW filter applied
- **WHEN** 55 stocks pass trend template but only 24 are in leading sectors (top 25%)
- **THEN** the system SHALL narrow to those 24 before checking chart patterns

#### Scenario: No stocks pass all filters
- **WHEN** no stocks pass the full S.N.I.P.E. pipeline
- **THEN** the system SHALL report an empty watchlist with stage counts showing where elimination occurred

### Requirement: Universe Filters (S — SCAN)

The system SHALL apply the following filters before Trend Template evaluation:
- **Price Floor**: Current price > ₹50 (avoid penny stocks — manipulation, wide spreads)
- **Market Cap Floor**: Market cap > ₹2,000 Cr (mid-cap and above — institutional participation)
- **Liquidity**: Average daily volume > 5 lakh shares OR average daily turnover > ₹10 Cr

#### Scenario: Penny stock filtered
- **WHEN** a Nifty 500 constituent is trading at ₹35
- **THEN** the system SHALL exclude it before any technical analysis

#### Scenario: Illiquid stock filtered
- **WHEN** a stock has 50-day average volume of only 80,000 shares and turnover of ₹2 Cr
- **THEN** the system SHALL exclude it (fails both volume AND turnover thresholds)

### Requirement: Dual-Timeframe Relative Strength

The system SHALL compute RS percentiles on BOTH 3-month (63 days) and 6-month (126 days) timeframes. The combined RS for each stock SHALL be the MINIMUM of its 3-month and 6-month percentiles, ensuring the stock is strong on both timeframes.

#### Scenario: Stock strong on both timeframes
- **WHEN** a stock has 6-month RS percentile of 85 and 3-month RS percentile of 78
- **THEN** the system SHALL assign combined RS = 78 (minimum of the two)

#### Scenario: Recent weakness despite long-term strength
- **WHEN** a stock has 6-month RS percentile of 90 but 3-month RS percentile of 45
- **THEN** the system SHALL assign combined RS = 45 (recent weakness disqualifies it from leadership)

### Requirement: Sector Diversification in Final List

The system SHALL enforce maximum 2 stocks from the same sector in the final 5-7 candidate list. If more than 2 top-ranked stocks are from the same sector, the system SHALL take the top 2 and fill remaining slots from next-best stocks in other sectors.

#### Scenario: Sector concentration override
- **WHEN** the top 5 stocks by composite score are all from Capital Goods
- **THEN** the system SHALL select the top 2 Capital Goods stocks and fill positions 3-7 from other sectors

### Requirement: Watchlist Output Format

The system SHALL output the final watchlist with for each stock:
- Rank (1-7)
- Symbol
- Sector and sector_trending flag (whether sector is in leading group)
- Sector rank (percentile: 100 = best performing sector)
- Current price
- Pivot price (entry trigger)
- Stop loss level (base_low or 8% below pivot, whichever is tighter)
- Composite edge score
- Edge count and which edges (including n_factor, alignment_bonus)
- Trend Template score (must be 10/10)
- VCP quality
- CANSLIM score and breakdown (C, A, N, S, L, I, M)
- Position sizing (shares, value, risk%, R:R)
- Stage (stage_2 or stage_2_early)
- Breakout status (breakout_detected, approaching_breakout)

The system SHALL also output sector_rankings metadata:
- leading_sectors: list of sector names in top 25% by 6-month median return
- sector_returns: median 6-month return per sector

### Requirement: Score 0 = No Trade

The system SHALL NOT generate position sizing for any stock with edge_count=0. Per the framework: "No edges = NO trade." Position sizing SHALL return valid=false with reason="no_edges".

#### Scenario: Zero edges
- **WHEN** a stock passes all filters but has 0 edges (volume is not HV1, RS not top 10%, not at 52W high, VCP not high quality, TT not 10/10)
- **THEN** the system SHALL include it in the watchlist for monitoring but position_sizing SHALL be invalid with reason="no_edges"
