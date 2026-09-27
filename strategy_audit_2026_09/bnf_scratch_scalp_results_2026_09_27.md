# BankNifty from scratch: 24 native intraday scalp/mean-reversion strategies (2026-09-27)
Built for this request specifically -- **not** ported from crude/silver. Rationale: the crude/silver SHA-flip family tops out at PF ~1.15 on BankNifty (see `bnf_port_test_results_2026_09_27.md`) because it's a long-hold
trend-following design and BankNifty doesn't sustain multi-hour trends the way a commodity does. This instead tests mean-reversion (fade extremes back to the mean) and **quick-scalp continuation** (small RR target, 15-60
minute time-stop) families, both explicitly suited to "small moves fine, short-lived quick trade is fine."
Data: `NSE_BANKNIFTY1_5m.csv`, 35.5 months robust, NSE:BANKNIFTY1! futures, pv=30. Session 09:15-15:20, flat 15:20-15:30, no day-loss limit. Code `bnf_scratch_scalp.py`, data `research_data/bnf_scratch_scalp.csv`.
Current BankNifty best for comparison: v0.4, PF 1.33, +1,403 pts, 2.5 trades/month, DD 1,620.

## Headline finding: Supertrend flip scalp -- the most robust new result found for BankNifty this project
**Entry: Supertrend(10,3) flip. Exit: 1.5R target, ~1.0xATR stop, forced out after 45 minutes if neither hits.**

| | trades/mo | PF | net pts | DD | win% | best-month share | avg hold |
|---|---|---|---|---|---|---|---|
| v0.4 (native, for comparison) | 2.5 | 1.33 | +1,403 | 1,620 | -- | -- | -- |
| **Supertrend flip scalp** | **34.5** | **1.190** | **+11,136** | 2,906 | 48.4% | **17.1%** | **42 min** |

- **Net-points-per-unit-drawdown is much better than v0.4**: 11,136/2,906 = 3.83, vs v0.4's 1,403/1,620 = 0.87 -- more than 4x the return for each point of drawdown risked.
- **Consistent across both halves of the data** (TRAIN < 25 Jun 2025 / HOLDOUT after): TRAIN 710 trades, PF 1.219, +7,681; HOLDOUT 515 trades, PF 1.147, +3,456. Both halves solidly profitable, no second-half-only pattern.
- **A genuine plateau, not a knife-edge**: RR 1.25/1.5/1.75 all give PF 1.19-1.20; the stop-width floor (0.75-1.25xATR) doesn't even bind at these levels (the swing-based stop is already wider); the time-stop matters more --
  30 min hurts (PF 1.101), 45-60 min is the sweet spot (PF 1.19/1.18).
- **Healthy trade anatomy**: 48.4% win rate (much higher than crude v4.2's ~20%), avg win/loss ratio only 1.27x (this is a high-win-rate, small-edge-per-trade design, the opposite character from the commodity strategies), long and short both profitable and balanced (613 longs +4,149 / 612 shorts +6,987), no outlier trade (largest win +766, largest loss -543). Most exits (914 of 1,225) are the 45-minute time-stop, not the stop-loss or target -- genuinely short-lived trades as asked for.
- **Not yet confirmed on 3m** (thin data, 3.7mo, only 226 trades, PF 0.963) -- inconclusive either way, consistent with every other 3m result today. Not TradingView-replay-confirmed either.

## Full 24-config table (5m, gross points)
| id | trades/mo | PF | net | DD | best-mo | note |
|---|---|---|---|---|---|---|
| M1 RSI revert 25/75 | 21.9 | 0.831 | -5,439 | 6,837 | -- | loses |
| M2 Bollinger band fade | 123.1 | 1.027 | +4,120 | 6,172 | 39% | far too frequent |
| M3 VWAP extension fade | 207.8 | 1.018 | +4,007 | 4,719 | 80% | far too frequent, concentrated |
| M4 Stochastic revert 20/80 | 154.4 | 1.054 | +9,091 | 3,348 | 22% | too frequent (154/mo) |
| M5 CCI revert | 115.5 | 1.046 | +5,990 | 4,641 | 30% | too frequent |
| M6 Keltner band fade | 118.0 | 1.068 | +10,252 | 4,744 | 23% | too frequent |
| M7 RSI+Bollinger confluence | 18.1 | 0.815 | -5,289 | 6,605 | -- | loses |
| M8 Opening-range fade | 49.9 | 1.032 | +2,153 | 5,134 | 74% | weak, concentrated |
| **Q1 EMA9/22 cross scalp (tight)** | 50.3 | 1.166 | +10,485 | 2,979 | 14% | strong net, but TRAIN PF only 1.021 -- carried by 2nd half |
| Q2 EMA9/22 cross scalp (wide) | 47.1 | 1.147 | +10,349 | 2,443 | 22% | similar to Q1, same caveat likely |
| Q3 Donchian10 breakout scalp | 136.3 | 0.958 | -7,177 | 12,171 | -- | loses badly |
| Q4 Donchian20 breakout scalp | 83.2 | 0.993 | -913 | 11,690 | -- | ~breakeven, too frequent |
| Q5 3-bar momentum burst | 167.2 | 0.995 | -1,002 | 7,319 | -- | ~breakeven, far too frequent |
| **Q6 Supertrend flip scalp** | **34.5** | **1.190** | **+11,136** | 2,906 | **17%** | **best all-around -- see above** |
| Q7 MACD histogram cross scalp | 85.8 | 1.006 | +698 | 4,869 | -- | ~breakeven |
| Q8 VWAP-cross continuation | 49.8 | 1.090 | +5,748 | 2,541 | 37% | decent, worth a second look |
| T1 Opening-range breakout continuation | 28.0 | 1.020 | +1,886 | 9,894 | -- | weak, huge DD |
| T2 Prior-day H/L breakout continuation | 114.2 | 1.052 | +8,208 | 5,420 | 42% | too frequent |
| T3 RSI revert, morning only | 11.6 | 0.834 | -3,029 | 5,557 | -- | loses |
| T4 RSI revert, afternoon only | 5.3 | 0.833 | -1,233 | 1,634 | -- | loses |
| H1 RSI revert + trend filter | 1.0 | 0.828 | -234 | 633 | -- | almost no signals, loses |
| H2 Bollinger fade + volume filter | 97.4 | 1.017 | +2,133 | 7,877 | 57% | too frequent, weak |
| H3 Time-stop only (15min, no real target) | 55.5 | 1.110 | +5,824 | 4,848 | 19% | decent, worth a look |
| H4 RSI revert 20/80 (wider) | 9.9 | 0.916 | -1,187 | 2,766 | -- | loses |

## What this shows
**Pure mean-reversion (fade RSI/Stochastic/CCI/Bollinger/Keltner extremes) mostly fails or is only marginally profitable at very high frequency** (100-200+ trades/month) -- BankNifty's short-term extremes don't reliably
snap back the way a simple oscillator-threshold expects; the ones that do turn a profit (M4, M5, M6) do it by trading so often that the "small moves, quick trades" framing turns into "very heavy trading," working against what you asked for.
**Quick-scalp continuation (enter on a short-term trend signal, take a small 1-2R profit or bail after 30-60 minutes) is the family that actually works here.** Q6 (Supertrend) is the clean winner; Q1/Q2 (EMA cross) have
similar headline numbers but fail the train/holdout check; Q8 (VWAP-cross) and H3 (pure time-stop) are worth a second pass if Q6 needs a companion strategy.

## Recommendation
**Supertrend(10,3) flip scalp -- 1.5R target, ~1xATR stop, 45-minute time-stop -- is the strongest new BankNifty candidate this project has found**, and unlike everything ported from crude/silver, it fits your stated
preference for smaller, faster trades. It is not yet a finding: not TradingView-confirmed, no forward test, and the 3m read is inconclusive. Next step, if you want it: TradingView tiled replay the way crude v4.2 was confirmed,
then a pre-registered forward test before considering it alongside v0.4.
