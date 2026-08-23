## Purpose

Evaluates stocks against CANSLIM criteria adapted for Indian markets, scoring current earnings growth, annual earnings consistency, new catalysts, supply/demand dynamics, market leadership, institutional sponsorship, and overall market direction.

## ADDED Requirements

### Requirement: C — Current Quarterly Earnings

The system SHALL evaluate quarterly EPS growth by comparing the most recent quarter's EPS to the same quarter one year ago (QoQ YoY comparison). A stock passes the C criterion when QoQ EPS growth is ≥20%.

The system SHALL also check:
- Revenue growth ≥20% QoQ (supporting criterion)
- EPS acceleration (current quarter growth > previous quarter growth) as a bonus signal

#### Scenario: Strong current earnings
- **WHEN** a stock's latest quarter EPS grew 35% vs the same quarter last year, with revenue up 28%
- **THEN** the system SHALL score c_criterion=true with eps_growth_qoq=35, revenue_growth_qoq=28

#### Scenario: Earnings deceleration warning
- **WHEN** a stock's EPS grew 25% this quarter but grew 40% in the prior quarter
- **THEN** the system SHALL score c_criterion=true (≥20%) but flag eps_decelerating=true as a caution

#### Scenario: Insufficient earnings data
- **WHEN** quarterly earnings data is not available for the required comparison periods
- **THEN** the system SHALL mark c_criterion="data_unavailable" and not fail the stock on this criterion alone

### Requirement: A — Annual Earnings Growth

The system SHALL evaluate whether annual EPS has grown at a CAGR of ≥25% over the past 3 fiscal years. Additionally, ROE should be ≥17%.

#### Scenario: Consistent annual growth
- **WHEN** a stock's annual EPS grew from 10 → 13 → 17 → 22 over 3 years (CAGR ~30%) with ROE of 22%
- **THEN** the system SHALL score a_criterion=true with eps_cagr_3yr=30, roe=22

#### Scenario: Volatile annual earnings
- **WHEN** annual EPS went 10 → 15 → 8 → 20 (not consistent despite high latest)
- **THEN** the system SHALL score a_criterion=false due to inconsistent growth pattern (one year of decline breaks the requirement)

### Requirement: N — New Products, Management, or Price Highs

The system SHALL identify the presence of "new" catalysts:
- Stock making a new 52-week high or all-time high
- Stock in a sector benefiting from government PLI scheme or policy tailwind
- Company with new product launches or management changes (when data available)

At minimum, the system SHALL check for new 52-week high status as a quantitative proxy.

#### Scenario: New 52-week high
- **WHEN** a stock's current price or recent price (within 5 days) touched a new 52-week high
- **THEN** the system SHALL score n_criterion=true with catalyst="new_52w_high"

#### Scenario: No new high, no identifiable catalyst
- **WHEN** a stock is 20% below its 52-week high and no sector catalyst data is available
- **THEN** the system SHALL score n_criterion=false

### Requirement: S — Supply and Demand

The system SHALL evaluate supply/demand dynamics through:
- Shares outstanding (smaller float preferred — under 50 crore shares for Indian midcaps)
- Volume patterns: up-days should show higher volume than down-days over recent weeks
- Accumulation/Distribution: count of up-volume days vs down-volume days over past 50 days

#### Scenario: Favorable supply/demand
- **WHEN** a stock has 10 crore shares outstanding, and over the past 50 days, 30 days showed up-volume exceeding down-volume
- **THEN** the system SHALL score s_criterion=true with accumulation_days=30, distribution_days=20, float_crore=10

#### Scenario: Distribution dominant
- **WHEN** over the past 50 days, 35 days showed higher volume on down-days
- **THEN** the system SHALL score s_criterion=false with distribution_dominant=true

### Requirement: L — Leader (Relative Strength)

The system SHALL rank all Nifty 500 stocks by Relative Strength (RS) — the stock's price performance over the past 12 months relative to the Nifty 500 index. A stock passes the L criterion when its RS rank is in the top 20% of the universe.

RS calculation: (Stock 12M return / Nifty 500 12M return) × 100, ranked percentile.

#### Scenario: Market leader
- **WHEN** a stock's 12-month return places it in the top 10% of Nifty 500 by relative performance
- **THEN** the system SHALL score l_criterion=true with rs_rank_percentile=90

#### Scenario: Laggard
- **WHEN** a stock's RS rank is at the 55th percentile
- **THEN** the system SHALL score l_criterion=false (requires top 20%, i.e., ≥80th percentile)

### Requirement: I — Institutional Sponsorship

The system SHALL evaluate institutional ownership trends:
- FII (Foreign Institutional Investor) holding change over last 2 quarters
- DII (Domestic Institutional Investor) / Mutual Fund holding change over last 2 quarters
- Number of mutual fund schemes holding the stock (increasing = positive)

A stock passes when institutional holdings are increasing (FII + DII net change positive over 2 quarters).

#### Scenario: Institutional accumulation
- **WHEN** FII holding increased from 12% to 15% and mutual fund schemes increased from 45 to 52 over 2 quarters
- **THEN** the system SHALL score i_criterion=true with fii_change=+3.0, mf_schemes_change=+7

#### Scenario: Institutional selling
- **WHEN** FII holding decreased from 18% to 14% and DII holding also decreased
- **THEN** the system SHALL score i_criterion=false with institutional_trend="declining"

### Requirement: M — Market Direction

The system SHALL evaluate overall market health (Nifty 500 index) to determine if conditions are favorable for buying. The M criterion passes when Nifty 500 is above its rising 30-week (150-day) moving average.

This criterion applies globally (same for all stocks) and acts as a gate: when M fails, no new buy signals are generated.

#### Scenario: Bull market confirmed
- **WHEN** Nifty 500 is 5% above its rising 150-day MA
- **THEN** the system SHALL score m_criterion=true (market direction favorable for entries)

#### Scenario: Market correction
- **WHEN** Nifty 500 is below its 150-day MA and the MA is declining
- **THEN** the system SHALL score m_criterion=false and suppress all new buy signals system-wide

### Requirement: CANSLIM Composite Score

The system SHALL compute a composite CANSLIM score (0-7) counting how many of the 7 criteria (C, A, N, S, L, I, M) pass. A stock with score ≥5 is considered "fundamentally qualified."

#### Scenario: High fundamental score
- **WHEN** a stock passes C, A, N, L, I, M but fails S
- **THEN** the system SHALL report canslim_score=6, fundamentally_qualified=true

#### Scenario: Marginal stock
- **WHEN** a stock passes only C, N, M (3 of 7)
- **THEN** the system SHALL report canslim_score=3, fundamentally_qualified=false
