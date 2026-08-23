## Purpose

Computes a multi-factor edge score for each stock candidate by combining technical pattern quality, volume signals, relative strength, and fundamental catalysts into a single actionable composite score that determines position sizing and trade priority.

## ADDED Requirements

### Requirement: Edge Factor Identification

The system SHALL evaluate each stock for the following edge factors, assigning 1 point per edge present:

1. **HV1 Edge**: Breakout on highest volume in 1 year (252 days)
2. **HVE Edge**: Breakout on highest volume ever in available history
3. **RS Edge**: Stock dual-timeframe RS (min of 3-month and 6-month) in top 10% of Nifty 500 AND making a new RS high simultaneously with price high
4. **N-Factor Edge**: Stock price at or within 5% of its 52-week high (new price high confirms momentum alignment)
5. **VCP Edge**: High-quality VCP pattern (quality score ≥8/10) with tight final contraction ≤8%
6. **Trend Template Edge**: Perfect 10/10 Trend Template score

**Alignment Bonus**: When all 4 core edges (HV1 + HVE + RS + N-Factor) align simultaneously, the system SHALL add +1 bonus point.

Maximum edge count: 7 (4 core + bonus + VCP + Trend Template; 5+ is exceptional and rare).

#### Scenario: Multi-edge breakout
- **WHEN** a stock breaks out with HV1 (highest volume in 1 year), RS in top 5%, price at 52-week high, and a high-quality VCP pattern, with perfect Trend Template
- **THEN** the system SHALL report edge_count=5, edges=["hv1","rs","n_factor","vcp","trend_template"], composite_score calculated accordingly

#### Scenario: Alignment bonus triggered
- **WHEN** a stock breaks out with HV1, HVE (all-time highest volume), RS in top 5%, AND price at 52-week high
- **THEN** the system SHALL report all 4 core edges plus alignment_bonus, giving edge_count=5 from volume/momentum alone

#### Scenario: Single-edge breakout
- **WHEN** a stock breaks out with adequate volume (not HV1), average RS rank (top 25%), and a medium-quality VCP
- **THEN** the system SHALL report edge_count=0 (no edges met their thresholds)

#### Scenario: HVE implies HV1
- **WHEN** a stock triggers HVE edge (highest volume ever)
- **THEN** the system SHALL count both hve_edge=true AND hv1_edge=true (HVE is a superset), giving 2 edge points from volume alone

### Requirement: Composite Edge Score Calculation

The system SHALL compute a composite edge score (0-100) using weighted factors:
- Edge count (0-6): 40% weight
- VCP quality score (0-10): 20% weight
- Trend Template score (0-10): 15% weight
- CANSLIM score (0-7): 15% weight
- Volume ratio on breakout: 10% weight

Formula: composite_score = (edge_count/6 × 40) + (vcp_quality/10 × 20) + (trend_template/10 × 15) + (canslim/7 × 15) + (min(volume_ratio, 3)/3 × 10)

#### Scenario: High composite score
- **WHEN** a stock has edge_count=4, vcp_quality=9, trend_template=10, canslim=6, volume_ratio=2.5
- **THEN** the system SHALL compute composite_score = (4/6×40) + (9/10×20) + (10/10×15) + (6/7×15) + (2.5/3×10) = 26.67 + 18 + 15 + 12.86 + 8.33 = 80.86, rounded to 81

#### Scenario: Low composite score
- **WHEN** a stock has edge_count=1, vcp_quality=4, trend_template=7, canslim=3, volume_ratio=1.2
- **THEN** the system SHALL compute a score in the 30-40 range, indicating a marginal candidate

### Requirement: Edge-Based Ranking

The system SHALL rank all qualifying stocks by composite_score in descending order. When two stocks have equal composite scores, the tiebreaker SHALL be edge_count (higher first), then volume_ratio (higher first).

#### Scenario: Ranking output
- **WHEN** the system has 12 stocks that passed the scanning phase
- **THEN** the system SHALL output a ranked list sorted by composite_score descending, with rank position 1 being the highest-scored candidate
