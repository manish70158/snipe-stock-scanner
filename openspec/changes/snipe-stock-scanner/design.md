## Context

See proposal.md for motivation. This system targets Indian NSE stocks (Nifty 500 universe) and must integrate with freely available data sources for price/volume (Yahoo Finance, NSE APIs) and fundamental data (Screener.in, Trendlyne, or BSE/NSE quarterly filings). The user already has Kite MCP integration available for real-time quotes.

The framework is based on the SNIPE methodology combining Mark Minervini's SEPA (Specific Entry Point Analysis), William O'Neil's CANSLIM, and Stan Weinstein's Stage Analysis — all adapted for Indian market conditions.

## Goals / Non-Goals

**Goals:**
- Fully automated daily scan pipeline that runs post-market (after 3:30 PM IST)
- Produce 5-7 actionable candidates with complete entry/stop/target/position-size data
- Market regime detection to gate entries and adjust sizing
- Track open positions and generate sell signals
- Modular architecture so individual components (VCP detection, CANSLIM scoring) can be tested and improved independently
- CLI-first interface with structured JSON output for composability

**Non-Goals:**
- Real-time intraday execution or auto-trading (manual execution only)
- Options strategy integration (equity only)
- Backtesting engine (can be added later but not in scope)
- Mobile app or web frontend (CLI + optional simple dashboard)
- Coverage beyond Nifty 500 (index fund universe is fixed)
- Order placement automation (position sizing is advisory)

## Decisions

### Decision 1: Python as primary language

**Choice**: Python 3.11+

**Rationale**: Rich ecosystem for financial data (yfinance, pandas, numpy, ta-lib), readily available NSE data libraries (nsetools, jugaad-data, nsepy), strong data manipulation capabilities.

**Alternatives considered**:
- Node.js: Good for Kite MCP integration but weaker financial data ecosystem
- Go: Fast but immature financial library ecosystem for Indian markets

### Decision 2: Data sourcing strategy

**Choice**: Multi-source with fallback hierarchy

- **Price/Volume OHLCV**: Primary: Yahoo Finance (yfinance) for Nifty 500 daily data. Fallback: Kite MCP historical data API.
- **Fundamentals (EPS, Revenue, Holdings)**: Primary: Screener.in scraping or Trendlyne API. Fallback: BSE/NSE quarterly filing PDFs (manual update).
- **Institutional Holdings (FII/DII)**: NSDL/CDSL bulk shareholding data or Trendlyne quarterly shareholding API.
- **Market Breadth**: Computed from Nifty 500 constituent daily prices (derived, not sourced externally).
- **FII/DII Flows**: NSE daily FII/DII data (moneycontrol or NSDL provisional data).

**Rationale**: No single free API covers all data needs for Indian markets. Multi-source with caching provides resilience.

**Alternatives considered**:
- Paid APIs (Polygon, Alpha Vantage): Higher reliability but unnecessary cost for daily EOD scanning
- Chartink integration: Already provides scans but is a black box — building our own gives full control and customization

### Decision 3: Modular pipeline architecture

**Choice**: Each SNIPE stage as an independent module with defined input/output contracts

```
Universe → TrendTemplateFilter → VCPDetector → CANSLIMScorer → EdgeScorer → NarrowingPipeline → Watchlist
                                                                                      ↑
                                                                              MarketRegimeGate
```

Each module:
- Takes a list of stock symbols + data as input
- Returns a filtered/scored list as output
- Can be run independently for testing
- Stores intermediate results in a local SQLite database for audit trail

**Rationale**: Allows incremental development and testing of each component. VCP detection logic is complex and benefits from isolation.

**Alternatives considered**:
- Monolithic script: Simpler but harder to debug and improve individual components
- Microservices: Over-engineering for a personal tool

### Decision 4: Local SQLite for state and history

**Choice**: SQLite database for:
- Nifty 500 constituent list (refreshed quarterly)
- Daily scan results and watchlist history
- Open position tracking with entry/stop/target data
- Market regime history

**Rationale**: Zero infrastructure, single file, portable, fast enough for 500 stocks daily. Python has built-in sqlite3 support.

**Alternatives considered**:
- PostgreSQL: Unnecessary complexity for single-user tool
- JSON files: Poor for querying historical data and position tracking
- CSV: Adequate for simple use but fragile for relational data

### Decision 5: Configuration-driven thresholds

**Choice**: YAML configuration file for all tunable parameters:
- Trend Template thresholds (30% above 52W low, 25% within 52W high, etc.)
- CANSLIM cutoffs (20% EPS growth, 25% CAGR, etc.)
- Position sizing rules (risk percentages per edge count)
- Market regime boundaries (60% breadth threshold, etc.)
- Stop-loss maximum (8%)
- Portfolio limits (20% max position, 5% total risk, 10 max positions)

**Rationale**: The SNIPE framework has many calibrated parameters. Making them configurable allows tuning without code changes. User can adjust as experience grows.

### Decision 6: CLI interface with structured output

**Choice**: Click-based CLI with commands:
- `snipe scan` — Run full pipeline, output watchlist
- `snipe regime` — Show current market regime
- `snipe inspect <symbol>` — Deep-dive single stock
- `snipe positions` — Show open positions and sell signals
- `snipe history` — Show historical scan results and outcomes

Output: Rich console tables (using `rich` library) + JSON export option.

**Rationale**: CLI is composable, scriptable, and fast. Can be wrapped with a web UI later if needed.

## Risks / Trade-offs

**[Data reliability]** → Yahoo Finance occasionally has missing/delayed data for Indian stocks. Mitigation: Implement data validation checks, flag stocks with stale data, use Kite MCP as fallback for real-time quotes.

**[Fundamental data freshness]** → Quarterly results data lags 1-2 weeks after release. Mitigation: Accept lag for CANSLIM scoring; price action (Trend Template, VCP) is the primary filter and uses real-time data.

**[VCP detection accuracy]** → Algorithmic VCP identification is inherently approximate; visual pattern recognition is subjective. Mitigation: Use conservative detection (fewer false positives, may miss some patterns), allow manual override to add stocks to watchlist.

**[Nifty 500 rebalancing]** → Index constituents change semi-annually. Mitigation: Auto-refresh constituent list from NSE quarterly, cache previous constituents for continuity.

**[Rate limiting]** → Scraping multiple data sources for 500 stocks daily may hit rate limits. Mitigation: Implement respectful delays, cache data with TTL, only refresh fundamental data weekly (not daily).

**[Parameter overfitting]** → Many configurable thresholds could be over-tuned to recent data. Mitigation: Start with published values from the SNIPE framework PDF, only adjust after tracking outcomes over 50+ trades.

## Migration Plan

Not applicable — this is a greenfield system. Deployment is local (user's machine), no migration needed.

## Open Questions

- Should the system integrate directly with Kite for order placement assistance (pre-fill orders), or remain purely advisory? (Can be deferred — start advisory-only)
- Should Telegram/Discord notifications be added for breakout alerts and sell signals? (Deferred — can add notification module later)
