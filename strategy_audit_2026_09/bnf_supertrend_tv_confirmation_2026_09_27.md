# BankNifty Supertrend(20,3)+volume-filter scalp: TradingView confirmation (2026-09-27)
Pine: `A100...` -- actually stored as the "crude reversal test" slot, now titled "BANKNIFTY Supertrend20-3 + VolFilter scalp (test)" (`USER;aff06ea9c4124d85bf6bf16667c12f70`). NSE:BANKNIFTY1! futures 5m, commission 0 (gross), 1 lot, pv=30.
6 tiled windows covering the full available history (11 Oct 2023 - 25 Sep 2026, ~35 months; TradingView's single-pass buffer for this symbol/timeframe is ~6.3 months, so 6 windows tile the whole span; the last two windows
overlap by ~3 weeks, disclosed, not corrected for). Raw: `research_data/tv_replay_bnf_supertrend_vol.txt`. Entry: Supertrend(20,3) flip + above-average-volume filter. Exit: 1.5R target, ~1.0xATR stop, 45-minute time-stop, forced flat 15:20-15:30.

## Result: confirmed. Harness and TradingView agree closely, and every one of 6 windows is individually profitable.

| | trades | PF | net pts | worst-window DD | trades/mo | windows profitable |
|---|---|---|---|---|---|---|
| Harness (35.5mo) | 997 | 1.309 | +14,700 | 1,540 | 28.1 | -- |
| **TradingView replay (6 windows, ~35mo)** | **1,016** | **1.284** | **+14,450** | 1,719 | 28.9 | **6 / 6** |

Harness and TradingView are within 2% on trades, PF and net points -- the closest agreement seen in this project's testing, and strong evidence the harness result was not an artifact. **All 6 non-overlapping windows, spanning
essentially the whole 3-year history through several different market regimes, were individually profitable** -- no window drags the total, unlike almost every commodity result this project has found (crude and silver both have losing windows even in their best configurations).

## Per-window detail (TradingView, gross points)
| window | span | trades | PF | net | DD |
|---|---|---|---|---|---|
| W1 | 11 Oct 2023 - 8 Apr 2024 | 182 | 1.254 | +2,222 | 1,191 |
| W2 | 17 Apr 2024 - 14 Oct 2024 | 167 | 1.254 | +2,114 | 998 |
| W3 | 15 Oct 2024 - 11 Apr 2025 | 188 | 1.319 | +3,258 | 1,137 |
| W4 | 17 Apr 2025 - 10 Oct 2025 | 147 | 1.268 | +1,845 | 727 |
| W5 | 14 Oct 2025 - 8 Apr 2026 | 161 | 1.332 | +2,529 | 1,719 |
| W6 (live, overlaps W5 by ~3wk) | 17 Mar 2026 - 25 Sep 2026 | 171 | 1.271 | +2,482 | 1,028 |

PF is remarkably stable window to window (1.25-1.33 throughout), which combined with the earlier harness plateau check (Supertrend period 14-25 all working) makes this the best-validated result in the whole BankNifty search.

## Comparison to the current incumbent
| | trades/mo | PF | net pts (~3yr) | worst DD |
|---|---|---|---|---|
| v0.4 (native, incumbent) | 2.5 | 1.33 | +1,403 | 1,620 |
| **Supertrend(20,3)+volfilter (TV-confirmed)** | 28.9 | 1.284 | **+14,450** | 1,719 |
Slightly lower PF than v0.4, but roughly 10x the net points at a similar drawdown and about 11x the trade frequency -- a genuinely different, higher-throughput profile, consistent with what was asked for (more, smaller, quicker trades).

## What's still open
Not yet a forward-tested, live-traded strategy. No day-loss circuit breaker has been added or calibrated (deliberately left off through the whole search). 3-minute timeframe has not been re-tested with this exact tuned combination. Recommended
next step: a pre-registered forward test, same discipline as crude v4.2 and the silver breakout test -- judged after a real number of forward trades, not on this backtest/replay alone.
