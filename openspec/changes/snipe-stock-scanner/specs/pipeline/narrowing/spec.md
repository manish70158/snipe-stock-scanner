## Purpose

Implements the complete S.N.I.P.E. process map from the MD framework — reducing the Nifty 500 universe through 5 sequential stages to produce a final actionable watchlist of maximum 5 stocks.

## ADDED Requirements

### Requirement: S.N.I.P.E. Pipeline Stage Definition (MD Framework)

The system SHALL process stocks through the following stages matching the MD Complete Process Map:

**S — SCAN: Filter the universe (500 → ~30)**
1. Universe: Nifty 500 constituents
2. Filter: Price > ₹50, Avg daily volume > ₹10 Cr turnover, Market Cap > ₹2,000 Cr
3. EPS growth ≥ 20% QoQ (when data available)
4. RS Rating: Top 20% vs Nifty 500 (dual-timeframe: min of 3-month and 6-month)
5. Stock in Stage 1 or 2 (Weinstein)
6. Trend Template: Apply 10-point SEPA criteria (ALL must pass)

**N — NARROW: Focus on the best (30 → 5)**
1. Leading sector: Top 3 sectors this month only (not percentage-based)
2. Clean base pattern visible on weekly chart (VCP, flat base, cup & handle)
3. Choppy chart rejection: Avg weekly range > 6% = avoid (V-shaped/wide-swinging action)
4. Institutional footprints: MF/FII increasing (low priority if weak, not hard filter)
5. Not extended: Price within 10% of pivot point
6. Fits timeframe: Swing/positional only (Stage 2 base breakouts)

**I — IDENTIFY EDGE: Score every setup (0-4 edges)**
1. HV1 Edge: Highest volume in 50 days + close in upper 60% of range (+1)
2. HVE Edge: Gap up ≥5% with volume ≥2x 50DMA (+1)
3. RS Edge: Outperformed during Nifty correction (+1)
4. N-Factor: Sector/policy catalyst (qualitative) (+1)
- Trade only with 2+ edges. 1 edge = watchlist only.

**P — PLAN THE TRADE: Define everything BEFORE entry**
1. Rank by composite score, enforce sector diversification (max 2/sector)
2. Final watchlist: Maximum 5 stocks (MD: "Never hold > 5 positions")
3. Position sizing: Edge count → risk% → shares (2e=0.5%, 3e=1%, 4e=1.5%)
4. Stop: Below C3 low (last contraction) or 8% below entry (whichever tighter)
5. Target: R:R ≥ 2:1 minimum (target_1 = entry + 2R)

**E — EXECUTE WITH DISCIPLINE**
1. Limit orders only (never market orders)
2. Store watchlist history for journaling
3. Output formatted for trade execution

### The Complete S.N.I.P.E. Process Map (Weekly Routine)

Per the MD:
```
Sunday Evening (30 minutes):
SCAN → Run scans → Get 20-40 stocks
  ↓
NARROW → Apply 5 qualitative filters → Pick TOP 5
  ↓
IDENTIFY → Score each stock (0-4 edges) → Rank by edge count
  ↓
PLAN → Write 7-field trade plan for top 2-3 → Set alerts
  ↓
(Wait for Monday)

Monday-Friday (10 minutes/day):
EXECUTE → Check if entry triggers hit → Execute EXACT plan
```

#### Scenario: Full pipeline execution
- **WHEN** the scanner runs on 500 stocks
- **THEN** the system SHALL output counts: universe=500 → scan_trend_template=~40 → narrow_sector=~10 → narrow_patterns=~3-5 → identify_edges → final_watchlist ≤ 5

#### Scenario: Strict sector filter (top 3 only)
- **WHEN** 40 stocks pass trend template with sectors across 15 industries
- **THEN** the system SHALL keep only stocks in the top 3 performing sectors by 6-month return

### Requirement: Universe Filters (S — SCAN)

The system SHALL apply per the MD "Universe Filter Rules":

| Rule | Criterion | Why |
|------|-----------|-----|
| 1 | Nifty 500 universe only | Liquidity + institutional coverage |
| 2 | Price > ₹50 | Avoid penny stock manipulation |
| 3 | Average daily volume > ₹10 Cr | Ensures you can exit when needed |
| 4 | EPS growth ≥ 20% QoQ | Fundamental momentum (CANSLIM C) |
| 5 | RS Rating top 20% vs Nifty 500 | Relative outperformance |
| 6 | Stock in Stage 1 or 2 (Weinstein) | Avoid Stage 3/4 |

### Requirement: Dual-Timeframe Relative Strength

The system SHALL compute RS on BOTH 3-month (63 days) and 6-month (126 days) timeframes. Combined RS = minimum of both percentiles (must be strong on both).

### Requirement: Sector Diversification

The system SHALL enforce:
- Maximum 2 stocks from the same sector in the final watchlist
- MD: "If 3+ stocks are from the same sector, you're making a sector bet, not diversifying"

### Requirement: Watchlist Output Format

The system SHALL output the final watchlist (max 5 stocks) with:
- Rank, Symbol, Sector
- Current price, Pivot price, Distance to pivot
- Stop loss (C3 low or 8% max), Stop distance %
- Edge count, Which edges, Tradeable flag
- Composite score, VCP quality, Trend Template score, CANSLIM score
- Position sizing (shares, value, risk%, R:R)
- Breakout status (detected, approaching, not yet)

### Requirement: Execution Checklist (10 Points — ALL Must Be YES)

Per the MD framework, before any trade the system SHALL validate:
1. Is the market in Stage 1 or 2? (Nifty 500 above 30W MA?)
2. Is the stock in my Top 5 this week?
3. Does it have 2+ edges confirmed?
4. Have I written all 7 plan fields?
5. Is my stop below a logical price level and ≤8%?
6. Is my R:R ≥ 2:1?
7. Is position size ≤ 1% risk rule?
8. Am I entering at the pivot (not chasing)?
9. Is volume confirming (≥1.5x 50DMA)?
10. Am I emotionally neutral?

**Rule: ALL 10 must be YES. Even one NO = NO TRADE.**
