## Purpose

Scores every setup using the 4-edge system from the MD framework. Edge count determines whether to trade and how much to risk. Only setups with 2+ edges are tradeable.

## ADDED Requirements

### Requirement: The 4 Edges (MD Framework)

The system SHALL evaluate each stock for exactly 4 edge factors, assigning 1 point per edge present:

1. **HV1 — Highest Volume Day 1 (Institutional Entry Signal)**
   - Stock prints its highest volume in 50+ days on a single day
   - Price closes in the upper 60% of the day's range (close > low + 0.6 × (high - low))
   - HV1 is valid for 10 trading days. If no base forms within 10 days, ignore.

2. **HVE — High Volume Earnings (Post-Result Momentum)**
   - Stock gaps up or surges ≥5% on a single day with volume ≥ 2× the 50-day average
   - This signals institutional repricing after new fundamental information
   - Creates a new "floor" — stock rarely returns below the gap zone

3. **RS Edge — Relative Strength (Outperforming During Correction)**
   - While Nifty 500 corrects ≥5%, the stock corrects less than 50% of Nifty's decline (or stays flat/rises)
   - RS Ratio = Stock % Change (21-day) / Nifty 500 % Change (21-day) > 2.0 during Nifty decline
   - Automated proxy: stock RS percentile ≥ 80th percentile

4. **N-Factor — News Catalyst (Sector/Policy Tailwind)**
   - Stock is in one of the top 3 performing sectors by 6-month median returns
   - MD: "Stock in leading sector/theme"
   - Automated using sector momentum rankings (computed from constituent stock returns)
   - N-Factor ALONE is never enough — it must combine with HV1, HVE, or RS Edge

**Maximum edge count: 4. Minimum to trade: 2.**

**Rule:** "Trade only setups with 2+ edges. 3-4 edges = maximum confidence = larger size."

#### Scenario: 3-edge high-conviction setup
- **WHEN** a stock breaks out with HV1 (highest volume in 50 days, close in upper 60%), RS Edge (outperformed during last correction), and N-Factor (PLI sector tailwind)
- **THEN** the system SHALL report edge_count=3, edges=["hv1","rs","n_factor"], tradeable=true

#### Scenario: 1-edge watchlist-only
- **WHEN** a stock has only RS Edge (outperformed during correction) but no HV1, HVE, or N-Factor
- **THEN** the system SHALL report edge_count=1, tradeable=false (watchlist only, do not trade)

#### Scenario: HVE post-earnings signal
- **WHEN** a stock gaps up 7% on result day with volume 2.5× the 50-day average
- **THEN** the system SHALL flag hve_edge=true. Note: HVE does NOT imply HV1 — they are independent edges

#### Scenario: No edges present
- **WHEN** a stock passes technical filters but has no volume signal, no RS edge, and no catalyst
- **THEN** the system SHALL report edge_count=0, tradeable=false, reason="no_edges"

### Requirement: Edge-Based Position Sizing (Linked to Edge Count)

Per the MD framework's position size table:

| Edge Count | Risk per Trade | Max Position Size | Action |
|-----------|----------------|-------------------|--------|
| 0 | 0% | 0% | No trade — skip |
| 1 | 0% | 0% | Watchlist only — wait for more edges |
| 2 | 0.5% of capital | 5% of portfolio | Trade with 50% of max size |
| 3 | 1.0% of capital | 8% of portfolio | Trade with 75% of max size |
| 4 | 1.5% of capital | 12% of portfolio | Trade with 100% of max size (rare) |

### Requirement: Composite Edge Score Calculation

The system SHALL compute a composite edge score (0-100) using weighted factors for ranking purposes:
- Edge count (0-4): 40% weight
- VCP quality score (0-10): 20% weight
- Trend Template score (0-10): 15% weight
- CANSLIM score (0-7): 15% weight
- Volume ratio on breakout: 10% weight

Note: VCP quality and Trend Template contribute to the composite RANKING score but are NOT counted as separate "edges" in the 4-edge system.

#### Scenario: High composite score
- **WHEN** a stock has edge_count=3, vcp_quality=9, trend_template=10, canslim=6, volume_ratio=2.5
- **THEN** the system SHALL compute a high composite score for ranking priority

#### Scenario: Low composite score
- **WHEN** a stock has edge_count=2, vcp_quality=4, trend_template=7, canslim=3, volume_ratio=1.2
- **THEN** the system SHALL compute a lower score — still tradeable (2+ edges) but lower priority

### Requirement: Edge-Based Ranking

The system SHALL rank all qualifying stocks by composite_score in descending order. When two stocks have equal composite scores, the tiebreaker SHALL be edge_count (higher first), then volume_ratio (higher first).
