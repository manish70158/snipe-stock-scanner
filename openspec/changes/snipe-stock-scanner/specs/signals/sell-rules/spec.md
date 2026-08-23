## Purpose

Monitors open positions and generates defensive and offensive sell signals based on stop-loss breach, pattern failure, volume reversals, climactic tops, and trailing stop logic to protect capital and lock in profits.

## ADDED Requirements

### Requirement: Defensive Sell Signals

The system SHALL generate a SELL signal when any of the following defensive conditions are met:

1. **Stop-Loss Hit**: Price closes below the predefined stop-loss level
2. **Pattern Failure**: Price closes below the base low of the pattern from which it broke out, on above-average volume
3. **Volume Reversal**: Stock gaps up or advances to new high on heavy volume, then reverses and closes near the low of the day (bearish engulfing / outside reversal on highest volume)
4. **Earnings Miss**: Stock gaps down >5% on earnings release (if fundamental data is available)
5. **Three Strikes Rule**: Stock triggers 3 minor warning signals within 2 weeks (e.g., closes below 10-DMA 3 times)

#### Scenario: Stop-loss triggered
- **WHEN** a stock with entry at 500 and stop at 465 closes at 462
- **THEN** the system SHALL generate sell_signal with type="stop_loss_hit", urgency="immediate"

#### Scenario: Pattern failure
- **WHEN** a stock that broke out from a VCP with base low at 450 closes below 450 on volume 80% above average
- **THEN** the system SHALL generate sell_signal with type="pattern_failure", urgency="immediate"

#### Scenario: Volume reversal day
- **WHEN** a stock advances to a new high, then reverses and closes in the bottom 25% of the day's range on the highest volume in 20 days
- **THEN** the system SHALL generate sell_signal with type="volume_reversal", urgency="warning" (not immediate — watch next day)

#### Scenario: Three strikes
- **WHEN** a stock closes below its 10-DMA on 3 separate days within a 10-trading-day window
- **THEN** the system SHALL generate sell_signal with type="three_strikes", urgency="consider_exit"

### Requirement: Offensive Sell Signals (Profit Taking)

The system SHALL generate profit-taking signals when:

1. **First Target Hit**: Price reaches +20-25% from entry (take partial profits — sell 1/3 to 1/2)
2. **Climactic Volume Top**: After extended advance (≥20% from entry), stock surges on volume 3× average with wide range, often largest single-day gain — signals exhaustion
3. **Three Weeks Tight at Top**: After a significant advance, price trades in a very tight range (<3% weekly range) for 3 consecutive weeks — potential distribution
4. **Market Enters Stage 3**: Market regime shifts to "red" — tighten all stops to 10-DMA
5. **Trailing Stop Triggered**: Price closes below the 21-day EMA after being ≥20% above entry (trailing stop for winners)

#### Scenario: First target profit taking
- **WHEN** a stock entered at 500 reaches 610 (+22%)
- **THEN** the system SHALL generate sell_signal with type="first_target", action="partial_sell_33_to_50_pct", urgency="plan_exit"

#### Scenario: Climactic top
- **WHEN** a stock has advanced 45% from entry, then surges 8% in one day on volume 3.5× the 50-day average (largest single-day % gain and highest volume day in the move)
- **THEN** the system SHALL generate sell_signal with type="climactic_top", urgency="high", action="sell_all_or_majority"

#### Scenario: Trailing stop for winners
- **WHEN** a stock is 30% above entry and closes below its 21-day EMA
- **THEN** the system SHALL generate sell_signal with type="trailing_stop_21ema", urgency="next_day_confirm"

### Requirement: Sell Signal Priority

The system SHALL prioritize sell signals by urgency:
1. **Immediate**: Stop-loss hit, pattern failure → execute same day / next open
2. **High**: Climactic top, volume reversal → execute within 1-2 days
3. **Plan Exit**: First target, trailing stop → plan orderly exit over 1-3 days
4. **Consider**: Three strikes, three weeks tight → tighten stops, reduce if not improving

#### Scenario: Multiple signals on same stock
- **WHEN** a stock triggers both "volume_reversal" (high) and "three_strikes" (consider) on the same day
- **THEN** the system SHALL report the highest urgency signal first and recommend action based on the most urgent one

### Requirement: Position Tracking for Sell Signals

The system SHALL track for each open position:
- Entry price and date
- Current stop level
- Current gain/loss percentage
- Days held
- R-multiple (current gain / initial risk)
- Whether trailing stop is active (activates when gain ≥ 20%)

#### Scenario: Trailing stop activation
- **WHEN** a stock entered at 500 (stop at 465, risk = 35) reaches 600 (gain = 20%)
- **THEN** the system SHALL activate trailing_stop=true and begin monitoring the 21-day EMA as the new dynamic stop level

#### Scenario: R-multiple tracking
- **WHEN** a stock entered at 500 with stop at 465 (risk=35) is currently at 570
- **THEN** the system SHALL report r_multiple = (570-500)/35 = 2.0R
