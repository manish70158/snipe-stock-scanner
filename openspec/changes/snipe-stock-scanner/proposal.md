## Why

There is no automated system to scan NSE stocks using the SNIPE framework (Scan → Narrow → Inspect → Position → Execute) combined with SEPA methodology, CANSLIM fundamentals, VCP pattern detection, Trend Template validation, and edge-based position sizing. Currently, traders must manually run Chartink scans, cross-reference fundamentals, score edges, and track market regime — a process that takes hours daily and is prone to inconsistency. A unified scanning and scoring system would automate the entire pipeline from universe filtering to actionable trade candidates with position sizing.

## What Changes

- Introduce a stock scanner engine that filters the Nifty 500 universe through configurable technical criteria (Trend Template 10-point check, VCP detection, Stage 2 confirmation, breakout detection)
- Implement a fundamentals screening layer applying CANSLIM criteria adapted for Indian markets (QoQ EPS growth ≥20%, annual EPS CAGR ≥25%, FII/DII accumulation, RS ranking)
- Build an edge scoring system that assigns composite scores based on HV1 Edge, HVE Edge, RS Edge, N-Factor, VCP quality, and Trend Template compliance
- Create a market regime detector (% stocks above 50-DMA/200-DMA, Nifty 500 vs 30W MA, FII flows, A/D line) to gate entry signals
- Implement position sizing calculator based on edge count (1 edge = 0.5% risk through 4 edges = 2% risk)
- Build a narrowing pipeline that reduces scan results to 5-7 actionable candidates ranked by composite edge score
- Provide sell signal detection (stop-loss breach, pattern failure, volume reversal, climactic top, trailing stop)

## Capabilities

### New Capabilities
- `scanning/trend-template`: 10-point Trend Template validation (price vs moving averages, MA slopes, 52-week positioning)
- `scanning/vcp-detection`: Volatility Contraction Pattern identification (contracting ranges, declining volume, pivot point detection)
- `scanning/stage-analysis`: Weinstein Stage 2 confirmation and stage transition detection
- `scanning/breakout-detection`: Price breakout detection with volume confirmation (HV1 = highest volume in 1 year)
- `fundamentals/canslim-india`: CANSLIM criteria adapted for Indian markets (EPS growth, institutional holdings, RS ranking, market direction)
- `scoring/edge-composite`: Multi-factor edge scoring system (HV1, HVE, RS, N-Factor, VCP, Trend Template)
- `market-regime/direction`: Market health indicators and regime classification (green/yellow/red zones)
- `position-sizing/edge-based`: Position sizing and risk allocation based on edge count and account equity
- `pipeline/narrowing`: Candidate reduction pipeline from scan universe to actionable 5-7 stocks
- `signals/sell-rules`: Defensive and offensive sell signal detection

### Modified Capabilities
<!-- No existing capabilities to modify - this is a greenfield system -->

## Impact

- **Data Sources**: Requires integration with NSE market data (price/volume OHLCV), financial data APIs (quarterly results, EPS, institutional holdings), and index composition data (Nifty 500 constituents)
- **Dependencies**: Yahoo Finance or equivalent for price data; Screener.in/Trendlyne or similar for Indian fundamental data; BSE/NSE APIs for institutional holding patterns
- **Compute**: Daily batch processing of 500 stocks through technical + fundamental filters; real-time monitoring optional for breakout alerts
- **Output**: Ranked watchlist with edge scores, entry/stop/target levels, position sizing recommendations, and market regime status
- **User Interface**: CLI-based scanner with optional web dashboard; integration with existing Kite MCP for live price data
