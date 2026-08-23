## 1. Project Setup

- [x] 1.1 Create Python project structure with `src/snipe/` package, `pyproject.toml`, and virtual environment. Verify: `python -m snipe --help` prints a usage message.
- [x] 1.2 Add dependencies: yfinance, pandas, numpy, click, rich, pyyaml, sqlite3 (stdlib), requests, beautifulsoup4. Verify: `pip install -e .` succeeds without errors.
- [x] 1.3 Create `config.yaml` with all configurable thresholds from the SNIPE framework (Trend Template values, CANSLIM cutoffs, position sizing rules, regime boundaries, stop-loss max 8%, portfolio limits). Verify: config loads and all expected keys are present via a test script.
- [x] 1.4 Create SQLite database schema with tables: `stocks` (universe), `daily_prices`, `scan_results`, `watchlist_history`, `positions`, `regime_history`, `fundamentals`. Verify: database initializes and schema matches expected table/column definitions.

## 2. Data Layer

- [x] 2.1 Implement Nifty 500 constituent fetcher (scrape NSE or use cached CSV). Store in `stocks` table with symbol, name, sector, market_cap. Verify: fetcher returns 500 symbols and stores them in DB.
- [x] 2.2 Implement daily OHLCV data fetcher using yfinance for all Nifty 500 stocks (with `.NS` suffix). Store in `daily_prices` table. Verify: fetch 1 year of data for 5 test stocks and confirm correct row counts.
- [x] 2.3 Implement data validation: check for missing dates, zero volumes, stale data (>2 days old). Flag invalid stocks. Verify: intentionally corrupt one stock's data and confirm it is flagged.
- [x] 2.4 Implement fundamental data fetcher for CANSLIM criteria (quarterly EPS, annual EPS, ROE, institutional holdings). Source from Screener.in scraping or Trendlyne. Verify: fetch fundamentals for 5 test stocks and confirm EPS/ROE/holdings data is populated.
- [x] 2.5 Implement FII/DII daily flow data fetcher (NSE or MoneyControl). Verify: fetch last 30 days of FII/DII cash market flows.

## 3. Trend Template Module

- [x] 3.1 Implement SMA calculation (50, 150, 200-day) for a given stock using daily_prices data. Verify: computed MAs match manually calculated values for a known stock.
- [x] 3.2 Implement the 10-point Trend Template check (price vs MAs, MA slopes, 52W positioning, RS rank). Return per-criterion pass/fail and aggregate score. Verify: test with a known Stage 2 stock that should pass all 10, and a Stage 4 stock that should fail.
- [x] 3.3 Implement Relative Strength ranking (12M return percentile vs Nifty 500 universe). Verify: top RS stock has percentile ~99, bottom has ~1.
- [x] 3.4 Implement batch Trend Template scan across all 500 stocks. Output list of passing stocks (score=10). Verify: run against full universe, confirm output is a filtered subset with scores.

## 4. VCP Detection Module

- [x] 4.1 Implement swing high/low detection algorithm using price data (identify peaks and troughs). Verify: test with known chart that has clear swings, confirm detected points match.
- [x] 4.2 Implement contraction measurement (depth from swing high to swing low as percentage). Verify: known VCP pattern returns correct contraction depths.
- [x] 4.3 Implement VCP pattern recognition: identify 2+ contractions where each is shallower than previous, volume declining. Return contraction_count, depths, base_weeks. Verify: feed a classic VCP price series and confirm pattern detected; feed a random price series and confirm no false positive.
- [x] 4.4 Implement pivot point detection (highest high in final contraction). Verify: pivot price matches the expected breakout level for test VCP.
- [x] 4.5 Implement VCP quality scoring (0-10 based on contractions, tightness, volume dry-up, duration). Verify: high-quality VCP scores ≥8, low-quality scores ≤4.
- [x] 4.6 Implement "approaching pivot" detection (stocks within 3% of pivot). Verify: stock 2% below pivot is flagged, stock 5% below is not.

## 5. Stage Analysis Module

- [x] 5.1 Implement stage classification logic using 150-day MA position, slope, and price structure (higher highs/lows vs lower highs/lows). Verify: classify 4 known stocks (one in each stage) correctly.
- [x] 5.2 Implement Stage 2 confirmation check (above rising 150-DMA for 4+ weeks, higher swing low established, 50-DMA > 150-DMA). Verify: stock in early Stage 2 (2 weeks) is classified "stage_2_early", stock with 6+ weeks is "stage_2" confirmed.
- [x] 5.3 Implement stage duration tracking (weeks in current stage). Verify: known stock in Stage 2 for 20 weeks returns stage_duration_weeks=20.

## 6. Breakout Detection Module

- [x] 6.1 Implement breakout detection: price closes above pivot + volume ≥ 150% of 50-day average. Verify: test stock breaking out on high volume triggers detection; same stock on low volume does not.
- [x] 6.2 Implement HV1 edge detection (volume is highest in 252 trading days). Verify: stock with volume exceeding all prior 252 days flags hv1_edge=true.
- [x] 6.3 Implement HVE edge detection (volume is highest in entire available history). Verify: stock with all-time high volume flags hve_edge=true.
- [x] 6.4 Implement breakout proximity alert (within 3% of pivot, not yet broken out). Verify: stock 2% below pivot flags approaching_breakout=true.

## 7. CANSLIM Scoring Module

- [x] 7.1 Implement C criterion (QoQ EPS growth ≥ 20%). Verify: stock with 35% QoQ growth passes, stock with 15% fails.
- [x] 7.2 Implement A criterion (3-year EPS CAGR ≥ 25% + ROE ≥ 17%). Verify: consistent grower passes, volatile earner fails.
- [x] 7.3 Implement N criterion (new 52-week high detection as primary signal). Verify: stock at 52W high passes, stock 20% below fails.
- [x] 7.4 Implement S criterion (accumulation/distribution day count over 50 days, float size). Verify: stock with 30 accumulation days vs 20 distribution days passes.
- [x] 7.5 Implement L criterion (RS rank in top 20% of universe). Verify: stock at 90th percentile RS passes, 55th percentile fails.
- [x] 7.6 Implement I criterion (FII/DII holding change over 2 quarters — increasing = pass). Verify: stock with rising institutional ownership passes.
- [x] 7.7 Implement M criterion (Nifty 500 above rising 150-day MA). Verify: when index is above rising MA, m_criterion=true globally.
- [x] 7.8 Implement composite CANSLIM score (0-7) and fundamentally_qualified flag (score ≥ 5). Verify: stock passing 6/7 criteria reports score=6, qualified=true.

## 8. Market Regime Module

- [x] 8.1 Implement breadth calculation (% of Nifty 500 above 50-DMA and 200-DMA). Verify: computed percentages are between 0-100 and match spot-checked manual counts.
- [x] 8.2 Implement Nifty 500 index trend assessment (position vs 150-DMA, slope). Verify: index above rising MA reports "uptrend".
- [x] 8.3 Implement FII flow assessment (5-day and 20-day rolling net flow). Verify: net positive flow reports "net_buying".
- [x] 8.4 Implement regime classification (GREEN/YELLOW/RED) based on combined signals. Verify: all positive → GREEN, mixed → YELLOW, all negative → RED.
- [x] 8.5 Implement regime change detection and logging (transitions stored in regime_history table). Verify: simulate a green→yellow transition and confirm it is logged with timestamp.

## 9. Edge Scoring Module

- [x] 9.1 Implement edge factor identification (HV1, HVE, RS, N-Factor, VCP, Trend Template edges). Verify: stock with HV1 breakout + top 10% RS + high VCP returns edge_count=3.
- [x] 9.2 Implement composite edge score formula (weighted: edge_count 40%, VCP 20%, TT 15%, CANSLIM 15%, volume 10%). Verify: known inputs produce expected score (match the example in spec: score=81 for given inputs).
- [x] 9.3 Implement edge-based ranking with tiebreakers (composite score → edge count → volume ratio). Verify: 12 stocks are ranked correctly with ties broken properly.

## 10. Position Sizing Module

- [x] 10.1 Implement edge-based risk allocation (1 edge=0.5%, 2=1%, 3=1.5%, 4+=2%). Verify: account 10L with 3 edges and 5% stop → correct share count.
- [x] 10.2 Implement stop-loss distance validation (reject if > 8%). Verify: 6% stop accepted, 12% stop rejected with reason.
- [x] 10.3 Implement market regime adjustment (GREEN=100%, YELLOW=50%, RED=0%). Verify: same trade in yellow regime gets half the shares vs green.
- [x] 10.4 Implement portfolio concentration limits (20% max position, 5% total risk, 10 max positions). Verify: position exceeding 20% is capped; trade breaching 5% total risk is warned.
- [x] 10.5 Implement complete position sizing output (all fields per spec). Verify: output includes entry, stop, shares, value, targets, R:R.

## 11. Pipeline & Narrowing Module

- [x] 11.1 Implement the full SNIPE pipeline orchestrator: Universe → TrendTemplate → VCP → CANSLIM → EdgeScore → Narrow. Verify: run on full universe, output shows counts at each stage and final 5-7 stocks.
- [x] 11.2 Implement sector diversification enforcement (max 2 per sector in final list). Verify: when top 5 are same sector, only 2 are kept and others backfilled from next-best.
- [x] 11.3 Implement watchlist output formatting (all fields per spec: rank, symbol, sector, price, pivot, stop, score, edges, sizes). Verify: output renders as a rich table with all columns populated.
- [x] 11.4 Implement watchlist history logging (store each day's watchlist in DB). Verify: run scan twice on different days, both results stored and queryable.

## 12. Sell Signals Module

- [x] 12.1 Implement position tracking: store open positions with entry/stop/date/edges. Verify: add a position and retrieve its current state with gain/loss %.
- [x] 12.2 Implement defensive sell signals (stop-loss hit, pattern failure, volume reversal, three strikes). Verify: simulate each condition and confirm correct signal type and urgency.
- [x] 12.3 Implement offensive sell signals (first target +20-25%, climactic top, 3 weeks tight, trailing stop). Verify: simulate a stock reaching +22% and confirm partial sell signal generated.
- [x] 12.4 Implement trailing stop activation (activates at +20% gain, tracks 21-EMA). Verify: stock at +25% with close below 21-EMA triggers trailing_stop signal.
- [x] 12.5 Implement R-multiple tracking for open positions. Verify: stock with risk=35, gain=70 shows r_multiple=2.0.

## 13. CLI Interface

- [x] 13.1 Implement `snipe scan` command: runs full pipeline, displays watchlist. Verify: `snipe scan` completes and prints formatted table.
- [x] 13.2 Implement `snipe regime` command: shows current market regime with all indicators. Verify: outputs GREEN/YELLOW/RED with breadth, index trend, FII flow data.
- [x] 13.3 Implement `snipe inspect <symbol>` command: shows detailed analysis of a single stock (all scores, patterns, edges). Verify: `snipe inspect RELIANCE` outputs complete breakdown.
- [x] 13.4 Implement `snipe positions` command: shows open positions with current P&L and active sell signals. Verify: positions table with gain%, R-multiple, and any triggered signals.
- [x] 13.5 Implement `snipe history` command: shows historical scan results and trade outcomes. Verify: displays past watchlists with outcome tracking (hit target/stop/still open).
- [x] 13.6 Implement `--json` flag for all commands to output structured JSON. Verify: `snipe scan --json` outputs valid JSON matching the expected schema.

## 14. Integration & End-to-End Testing

- [x] 14.1 Create test fixtures with known stock data (price series that form VCPs, breakouts, etc.) for deterministic testing. Verify: fixtures load correctly and produce expected pattern detections.
- [x] 14.2 Run full end-to-end scan on live Nifty 500 data and validate output makes sense (no crashes, reasonable candidates). Verify: scan completes in under 5 minutes and outputs 0-7 candidates with all fields populated.
- [x] 14.3 Test market regime module against current market conditions and validate regime classification matches manual assessment. Verify: regime matches what a visual check of Nifty 500 chart would suggest.
- [x] 14.4 Test sell signal module with 3 simulated open positions (one hitting stop, one hitting target, one generating trailing stop signal). Verify: all three generate correct signal types.
