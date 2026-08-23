# SNIPE Stock Scanner

A systematic stock scanning tool implementing the **SNIPE framework** (Scan → Narrow → Inspect → Position → Execute) for Indian NSE stocks. Combines Mark Minervini's SEPA methodology, William O'Neil's CANSLIM, Stan Weinstein's Stage Analysis, and Volatility Contraction Patterns (VCP) to identify high-probability momentum trade setups in the Nifty 500 universe.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Modules](#modules)
  - [Data Layer](#data-layer)
  - [Trend Template](#trend-template)
  - [VCP Detection](#vcp-detection)
  - [Stage Analysis](#stage-analysis)
  - [Breakout Detection](#breakout-detection)
  - [CANSLIM Scoring](#canslim-scoring)
  - [Market Regime](#market-regime)
  - [Edge Scoring](#edge-scoring)
  - [Position Sizing](#position-sizing)
  - [Pipeline Orchestrator](#pipeline-orchestrator)
  - [Sell Signals](#sell-signals)
- [CLI Commands](#cli-commands)
- [Configuration](#configuration)
- [Daily Workflow](#daily-workflow)
- [Understanding the Output](#understanding-the-output)
- [Testing](#testing)
- [Data Sources](#data-sources)

---

## Installation

```bash
# Clone or navigate to the project
cd /path/to/framework_to_create_setups_and_trading_edge

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Verify installation
snipe --help
```

Requirements: Python 3.11+

---

## Quick Start

```bash
# Activate environment
source .venv/bin/activate

# 1. Fetch price data (start small for testing)
snipe fetch --symbols 10

# 2. Inspect a single stock
snipe inspect RELIANCE

# 3. Fetch full Nifty 500 data (takes ~2-3 minutes)
snipe fetch --symbols 500

# 4. Run the full SNIPE scan
snipe scan

# 5. Get JSON output for programmatic use
snipe scan --json
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SNIPE PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Nifty 500 Universe (500 stocks)                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Trend Template  │  10-point check → ~50-80 pass              │
│  └────────┬────────┘                                            │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ VCP + Stage 2   │  Pattern + Stage confirmation → ~15-30     │
│  └────────┬────────┘                                            │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ CANSLIM Screen  │  Fundamental criteria → ~8-15              │
│  └────────┬────────┘                                            │
│           ▼                                                      │
│  ┌─────────────────┐     ┌──────────────────┐                  │
│  │ Edge Scoring    │◄────│ Market Regime    │                   │
│  └────────┬────────┘     │ (GREEN/YELLOW/   │                  │
│           ▼              │  RED gate)       │                   │
│  ┌─────────────────┐     └──────────────────┘                  │
│  │ Narrowing       │  Sector diversification → 5-7 stocks      │
│  └────────┬────────┘                                            │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Position Sizing │  Edge-based risk allocation                │
│  └─────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Project structure:**

```
src/snipe/
├── __init__.py           # Package init
├── __main__.py           # python -m snipe entry point
├── cli.py                # Click-based CLI with all commands
├── config.py             # YAML config loader and validator
├── database.py           # SQLite schema and connection management
├── pipeline.py           # Full SNIPE pipeline orchestrator
├── data/
│   ├── universe.py       # Nifty 500 constituent fetcher
│   ├── prices.py         # Yahoo Finance OHLCV data
│   ├── fundamentals.py   # Screener.in EPS/ROE/holdings scraper
│   ├── fii_dii.py        # FII/DII daily flow data
│   └── validation.py     # Data quality checks
├── scanning/
│   ├── trend_template.py # 10-point Trend Template
│   ├── vcp.py            # Volatility Contraction Pattern detection
│   ├── stage_analysis.py # Weinstein 4-stage classification
│   └── breakout.py       # Breakout + HV1/HVE edge detection
├── scoring/
│   ├── canslim.py        # CANSLIM criteria (C,A,N,S,L,I,M)
│   ├── edge.py           # Composite edge scoring and ranking
│   ├── regime.py         # Market regime (GREEN/YELLOW/RED)
│   └── position_sizing.py# Risk allocation and share calculation
└── signals/
    └── sell_rules.py     # Defensive and offensive sell signals
```

---

## Modules

### Data Layer

**Location:** `src/snipe/data/`

Handles all external data fetching and storage.

| File | Purpose |
|------|---------|
| `universe.py` | Fetches Nifty 500 constituents from NSE website. Falls back to cached CSV. Stores symbol, name, sector in SQLite. |
| `prices.py` | Fetches 1-year daily OHLCV from Yahoo Finance (`.NS` suffix). Stores in `daily_prices` table. |
| `fundamentals.py` | Scrapes quarterly EPS, annual EPS, ROE, and institutional holdings from Screener.in. |
| `fii_dii.py` | Fetches FII/DII daily cash market flows. Computes rolling 5-day and 20-day net flows. |
| `validation.py` | Validates data quality: checks for sufficient history (200+ days), zero volumes, stale data, date gaps. |

**Database tables:** `stocks`, `daily_prices`, `fundamentals`, `fii_dii_flows`

---

### Trend Template

**Location:** `src/snipe/scanning/trend_template.py`

Implements Mark Minervini's 10-point Trend Template — a checklist that confirms a stock is in a strong uptrend:

| # | Criterion | What It Checks |
|---|-----------|----------------|
| 1 | Price > 150-DMA | Stock above 30-week moving average |
| 2 | Price > 200-DMA | Stock above 40-week moving average |
| 3 | 150-DMA > 200-DMA | Shorter MA above longer MA (bullish stacking) |
| 4 | 200-DMA rising 22+ days | Long-term trend is up, not flat/falling |
| 5 | 50-DMA > 150-DMA | All MAs properly stacked |
| 6 | 50-DMA > 200-DMA | Confirms MA alignment |
| 7 | Price > 50-DMA | Short-term strength |
| 8 | Price ≥ 30% above 52W low | Stock has already shown strength |
| 9 | Price within 25% of 52W high | Near leadership territory |
| 10 | RS rank top 30% | Outperforming 70% of the universe |

A stock **must pass all 10** to qualify. Score: 0-10. Only 10/10 passes.

Also includes:
- **SMA calculation** (50, 150, 200-day simple moving averages)
- **Relative Strength ranking** — 12-month return percentile vs all Nifty 500 stocks

---

### VCP Detection

**Location:** `src/snipe/scanning/vcp.py`

Detects **Volatility Contraction Patterns** — the signature base pattern before breakouts:

```
Price
 ▲
 │    T1 (25% drop)
 │   /\          T2 (15%)
 │  /  \        /\      T3 (8%)
 │ /    \      /  \    /\     ← Tightening contractions
 │/      \    /    \  /  \
 │        \  /      \/    \_____ Pivot (buy point)
 │         \/
 │
 └──────────────────────────────▶ Time
```

**What it detects:**
- Swing highs and lows (local extrema algorithm)
- Contraction depths (% drop from each swing high to low)
- Tightening pattern (each contraction shallower than previous)
- Volume decline through contractions
- Pivot point (highest high in final contraction)
- Approaching-pivot alert (within 3% of breakout level)

**VCP Quality Score (0-10):**
- Number of contractions (more = better, max at 4)
- Final contraction tightness (≤8% = ideal)
- Volume dry-up at pivot
- Base duration (5-25 weeks optimal)

Quality levels: High (≥8), Medium (5-7), Low (≤4)

---

### Stage Analysis

**Location:** `src/snipe/scanning/stage_analysis.py`

Classifies stocks into **Weinstein's four market stages:**

| Stage | Name | Characteristics | Action |
|-------|------|-----------------|--------|
| 1 | Basing | Sideways, flat MA, sporadic volume | Watch |
| 2 | Advancing | Above rising MA, higher highs/lows | **Buy** |
| 3 | Topping | Sideways near highs, flattening MA | Sell |
| 4 | Declining | Below falling MA, lower highs/lows | Avoid |

**Stage 2 Confirmation requires all of:**
- Price above rising 150-DMA for 4+ weeks
- 50-DMA above 150-DMA
- At least one higher swing low established above the 150-DMA

Outputs: `stage_2_early` (not yet confirmed) vs `stage_2` (fully confirmed), plus `stage_duration_weeks` and `late_stage_2` warning for extended advances (40+ weeks).

---

### Breakout Detection

**Location:** `src/snipe/scanning/breakout.py`

Detects when a stock breaks above its pivot point with volume confirmation:

**Breakout criteria:**
- Price closes ≥1% above pivot
- Volume ≥150% of 50-day average

**Volume edges:**
- **HV1 Edge**: Breakout on highest volume in 252 trading days (1 year)
- **HVE Edge**: Breakout on highest volume in entire available history

**Breakout strength levels:**
- Very strong (volume ≥2.5x average)
- Strong (≥2.0x)
- Confirmed (≥1.5x)
- Unconfirmed (price broke out but volume insufficient)

Also detects **approaching breakout** — stocks within 3% of their pivot that haven't broken out yet (watchlist candidates).

---

### CANSLIM Scoring

**Location:** `src/snipe/scoring/canslim.py`

William O'Neil's CANSLIM adapted for Indian markets — 7 criteria scored individually:

| Letter | Criterion | Pass Condition |
|--------|-----------|----------------|
| **C** | Current Earnings | QoQ EPS growth ≥ 20% (vs same quarter last year) |
| **A** | Annual Earnings | 3-year EPS CAGR ≥ 25% AND ROE ≥ 17% |
| **N** | New (catalyst) | Stock at or within 5% of 52-week high |
| **S** | Supply/Demand | More accumulation days than distribution days (50-day) |
| **L** | Leader | RS percentile ≥ 80 (top 20% of universe) |
| **I** | Institutional | FII+DII holding increasing over 2 quarters |
| **M** | Market Direction | Nifty 500 above rising 150-day MA |

**Composite score:** 0-7. Stock is "fundamentally qualified" at score ≥ 5.

---

### Market Regime

**Location:** `src/snipe/scoring/regime.py`

Classifies overall market health into three zones that gate position sizing:

| Regime | Conditions | Action |
|--------|-----------|--------|
| **GREEN** | Index above rising 150-MA + breadth ≥60% + FII buying | Full sizing (100%) |
| **YELLOW** | Mixed signals (1-2 negative) | Half sizing (50%) |
| **RED** | Index below falling 150-MA + breadth <40% | No new buys (0%) |

**Breadth indicators computed:**
- % of Nifty 500 above their 50-DMA
- % of Nifty 500 above their 200-DMA
- Nifty 500 index position vs 150-DMA + MA slope
- FII 5-day and 20-day rolling net flow

Detects **breadth divergence** (index near highs but breadth declining — a warning sign).

---

### Edge Scoring

**Location:** `src/snipe/scoring/edge.py`

Identifies and counts favorable factors ("edges") present in each trade setup:

| Edge | Condition |
|------|-----------|
| HV1 | Breakout on highest volume in 1 year |
| HVE | Breakout on highest volume ever (implies HV1) |
| RS | RS percentile ≥ 90 AND making new RS high |
| N-Factor | Stock in leading sector/theme |
| VCP | High-quality VCP (quality score ≥ 8) |
| Trend Template | Perfect 10/10 Trend Template |

**Composite Score (0-100):**
```
Score = (edge_count/6 × 40) + (vcp_quality/10 × 20) + (TT/10 × 15)
      + (canslim/7 × 15) + (min(volume_ratio, 3)/3 × 10)
```

Candidates are ranked by composite score → edge count → volume ratio (tiebreaker).

---

### Position Sizing

**Location:** `src/snipe/scoring/position_sizing.py`

Calculates how many shares to buy based on edge count and risk parameters:

| Edge Count | Risk per Trade |
|-----------|---------------|
| 1 edge | 0.5% of equity |
| 2 edges | 1.0% of equity |
| 3 edges | 1.5% of equity |
| 4+ edges | 2.0% of equity (max) |

**Formula:**
```
Risk Amount = Account Equity × Risk %
Shares = Risk Amount / (Entry Price - Stop Price)
```

**Guardrails:**
- Maximum stop-loss distance: 8% (rejects setups with wider stops)
- Maximum single position: 20% of equity
- Maximum total portfolio risk: 5% across all positions
- Maximum open positions: 10
- Regime adjustment: GREEN=100%, YELLOW=50%, RED=0%

**Output includes:** Entry, stop, shares, position value, Target 1/2/3 (1R/2R/3R), R:R ratio.

---

### Pipeline Orchestrator

**Location:** `src/snipe/pipeline.py`

Runs the complete SNIPE scan in sequence:

1. **Universe** → 500 stocks (Nifty 500)
2. **Trend Template** → 50-80 pass (all 10 criteria met)
3. **Pattern Detection** → 15-30 (VCP + Stage 2 + breakout/approaching)
4. **Fundamental Screen** → 8-15 (CANSLIM score ≥ 3)
5. **Edge Scoring** → All scored and ranked
6. **Final Narrowing** → Top 5-7, max 2 per sector

Stores watchlist history in database for outcome tracking.

---

### Sell Signals

**Location:** `src/snipe/signals/sell_rules.py`

Monitors open positions and generates sell alerts:

**Defensive (protect capital):**

| Signal | Trigger | Urgency |
|--------|---------|---------|
| Stop-loss hit | Close below stop | Immediate |
| Pattern failure | Close below base low on heavy volume | Immediate |
| Volume reversal | New high + reversal close in bottom 25% + heavy volume | High |
| Three strikes | 3 closes below 10-DMA in 10 days | Consider exit |

**Offensive (lock profits):**

| Signal | Trigger | Action |
|--------|---------|--------|
| First target | +20-25% gain | Sell 1/3 to 1/2 |
| Climactic top | 3x volume + 5%+ gain after extended advance | Sell most/all |
| 3 weeks tight | <3% weekly range for 3 weeks at top | Tighten stop |
| Trailing stop | Close below 21-EMA after +20% gain | Confirm next day |

**Position tracking:** Computes gain%, R-multiple (gain / initial risk), days held, trailing stop activation status.

---

## CLI Commands

### `snipe scan`

Run the full pipeline and display the watchlist.

```bash
snipe scan                 # Rich table output
snipe scan --json          # JSON output
snipe scan --equity 2000000  # Custom account size (default 10L)
```

### `snipe inspect <SYMBOL>`

Deep-dive analysis of a single stock showing all scores and patterns.

```bash
snipe inspect TCS
snipe inspect BHEL --json
```

Output includes: Trend Template (10 criteria), VCP detection, Stage classification, Breakout status.

### `snipe regime`

Show current market regime assessment.

```bash
snipe regime
snipe regime --json
```

### `snipe positions`

Show open positions with P&L, R-multiples, and active sell signals.

```bash
snipe positions
snipe positions --json
```

### `snipe history`

Show historical scan results and trade outcomes.

```bash
snipe history
snipe history --json
```

### `snipe fetch`

Fetch/refresh price data from Yahoo Finance.

```bash
snipe fetch --symbols 5      # Quick test (5 stocks)
snipe fetch --symbols 500    # Full universe
```

### Global Options

- `--json` on any command outputs structured JSON instead of rich tables
- `--help` on any command shows usage

---

## Configuration

All thresholds are in `config.yaml` at the project root. Key sections:

```yaml
trend_template:
  min_above_52w_low_pct: 30    # Criterion 8 threshold
  max_below_52w_high_pct: 25   # Criterion 9 threshold
  rs_top_percentile: 30        # Criterion 10: top N%

vcp:
  min_contractions: 2          # Minimum contractions for VCP
  max_t1_depth_pct: 35         # Max first correction depth
  tight_final_contraction_pct: 8  # High-quality threshold

canslim:
  min_eps_growth_qoq_pct: 20   # C criterion
  min_eps_cagr_3yr_pct: 25     # A criterion
  leader_rs_percentile: 80     # L criterion (top 20%)

position_sizing:
  risk_1_edge_pct: 0.5         # 1 edge = 0.5% risk
  risk_4plus_edge_pct: 2.0     # 4+ edges = 2% risk
  max_stop_distance_pct: 8     # Reject setups > 8% stop
  max_position_pct_of_equity: 20
  max_total_risk_pct: 5
  max_open_positions: 10

market_regime:
  green_breadth_50dma_min: 60  # GREEN needs 60%+ above 50-DMA
  red_breadth_50dma_max: 40    # RED below 40%
```

Modify values as your experience grows. Start with published framework defaults.

---

## Daily Workflow

```bash
# Activate environment
source .venv/bin/activate

# 1. After market close (3:30 PM IST), refresh data
snipe fetch --symbols 500

# 2. Check market regime
snipe regime

# 3. Run full scan
snipe scan

# 4. Deep-dive top candidates
snipe inspect BHEL
snipe inspect NETWEB

# 5. If you have open positions, check for sell signals
snipe positions

# 6. Review past picks
snipe history
```

**Weekly routine:**
- Review which watchlist stocks triggered entries
- Update position stops if trailing stop activated
- Check regime for any transitions (GREEN→YELLOW, etc.)

---

## Understanding the Output

### Watchlist Table

```
# │ Symbol │ Sector │ Price │ Pivot │ Stop │ Score │ Edges │ TT    │ VCP │ CANSLIM
1 │ BHEL   │ CapGds │  413  │  436  │  411 │   60  │   3   │ 10/10 │  9  │  3/7
```

- **Rank**: By composite edge score (higher = better setup)
- **Pivot**: Price level to trigger entry (buy above this)
- **Stop**: Where to place stop-loss if entered
- **Score**: Composite edge score (0-100)
- **Edges**: Number of favorable factors present
- **TT**: Trend Template score (must be 10/10 to appear)
- **VCP**: VCP quality score (0-10, higher = tighter/cleaner pattern)
- **CANSLIM**: Fundamental score (0-7)

### Position Sizing

When a trade triggers, the system calculates:
- Exact number of shares to buy
- Total capital deployed
- Three profit targets (1R, 2R, 3R)
- Whether portfolio limits would be breached

### Regime Impact

| Regime | What It Means | Scanner Behavior |
|--------|--------------|------------------|
| GREEN | Market healthy | Full scans, full sizing |
| YELLOW | Caution | Scans run, sizing cut 50% |
| RED | Defensive | No new buy signals generated |

---

## Testing

```bash
# Run all unit tests
python -m pytest tests/ -v

# Quick module tests
python -c "from snipe.scanning.trend_template import check_trend_template; print('OK')"
python -c "from snipe.scanning.vcp import detect_vcp; print('OK')"
python -c "from snipe.scoring.edge import compute_composite_score; print('OK')"
```

18 tests cover: Trend Template (pass/fail), VCP detection (positive/negative), Stage Analysis, Breakout, Edge Scoring, Position Sizing (4 scenarios), Sell Signals (3 scenarios).

---

## Data Sources

| Data | Source | Refresh |
|------|--------|---------|
| Price/Volume OHLCV | Yahoo Finance (yfinance) | Daily after market close |
| Nifty 500 constituents | NSE India website | Quarterly |
| Quarterly EPS/ROE | Screener.in (scraping) | After results season |
| Institutional holdings | Screener.in shareholding | Quarterly |
| FII/DII flows | MoneyControl/NSDL | Daily (when available) |

**Storage:** Local SQLite database (`snipe.db`) — zero infrastructure, portable, fast.

---

## Key Concepts Reference

| Term | Meaning |
|------|---------|
| **SNIPE** | Scan → Narrow → Inspect → Position → Execute |
| **SEPA** | Specific Entry Point Analysis (Minervini) |
| **VCP** | Volatility Contraction Pattern — tightening base before breakout |
| **Trend Template** | 10-point checklist confirming strong uptrend |
| **Stage 2** | Weinstein's advancing stage — the only stage to buy in |
| **HV1** | Highest Volume in 1 year on breakout day |
| **HVE** | Highest Volume Ever on breakout day |
| **RS** | Relative Strength — stock performance vs the market |
| **Edge** | A favorable factor that increases trade probability |
| **R-Multiple** | Gain expressed as multiples of initial risk (1R = risk amount) |
| **Pivot** | The price level that triggers a buy (breakout point) |
