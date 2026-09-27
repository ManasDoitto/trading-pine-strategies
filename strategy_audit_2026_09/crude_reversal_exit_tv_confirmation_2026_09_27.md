# Crude v4.2 (reversal-exit, no target): TradingView tiled-replay confirmation, 2026-09-27
Pine: `A100_crude_reversal_exit_no_target.pine.txt`, tested in slot "crude reversal test" (`USER;aff06ea9c4124d85bf6bf16667c12f70`), MCX:CRUDEOIL1! 5m, commission 0 (gross), 1 lot.
Same 13 tiled ~81-day windows (18 Jan 2024 -> 25 Sep 2026) and AUD-block method as every other crude session-start replay this project. Raw: `research_data/tv_replay_crude_reversal_0915.txt`, `..._1730.txt`.
Same entry/stop as crude #1 (SHA 10/10 flip + EMA9>EMA22, 10-bar swing stop floored 1.5xATR, skip if >3xATR). No fixed 4R target: exit only via the stop, or a reversal exit (opposite valid signal), filled at the next bar's open.

## Verdict: real and TradingView-confirmed at 09:15. NOT confirmed at 17:30 -- the harness overestimated that pairing.

| | trades | PF | net pts | worst-window DD | windows profitable |
|---|---|---|---|---|---|
| crude #1 @09:15 (baseline, TV) | 910 | 1.229 | +5,672 | 1,898 | 8/13 |
| **v4.2 reversal/no-target @09:15 (TV)** | 885 | **1.541** | **+10,623** | **1,279** | **9/13** |
| crude #1 @17:30 (TV) | 515 | 1.361 | +6,036 | 1,293 | 8/13 |
| v4.2 reversal/no-target @17:30 (TV) | 460 | 1.361 | +5,051 | 1,098 | 6/13 |

**At 09:15**: PF up 25% (1.229 -> 1.541), gross points nearly double (+87%), drawdown down 33%, one more profitable window, at almost the same trade count (885 vs 910). Every measured axis improves. This is the strongest, cleanest confirmed result of the whole crude search.
**At 17:30**: PF ties crude #1 exactly (1.361 vs 1.361) -- but total points are 16% lower and two fewer windows are profitable (6/13 vs 8/13). Drawdown is better (-15%), but this pairing is a wash-to-worse, not an improvement. **The harness said 17:30 should also pass (corrected PF 1.582 vs control 1.476); TradingView disagrees.** This is the harness's second-half-heavy pattern (flagged as a caveat when the harness result was first reported) showing up as a real discrepancy once tested independently -- a useful reminder that a harness pass is a candidate, not a fact, which is exactly why this replay was run.

## Per-window detail (09:15, gross points)
W1 +293 | W2 +93 | W3 +1,466 | W4 -739 | W5 +255 | W6 +87 | W7 +175 | W8 -554 | W9 -133 | W10 +374 | **W11 +8,064** | W12 -3 | W13 +1,245.
Window 11 (May-Aug 2026, the same window that dominates crude #1's own baseline) still supplies most of the profit (76% of the total), but unlike crude #1's baseline it is not the *only* reason the strategy works: 8 of the other 12 windows are individually profitable too, and W3/W13 add real points (+1,466, +1,245) on their own.

## Per-window detail (17:30, gross points)
W1 +214 | W2 +338 | W3 +1,473 | W4 -508 | W5 -94 | W6 -348 | W7 -152 | W8 -241 | W9 -222 | W10 +255 | W11 +4,401 | W12 -856 | W13 +791.
Five losing windows here (W4-W9 mostly) that were smaller losses or wins in the 09:15 version -- restricting to the later session removes some of the 09:15 version's smaller winners along with its losers, and on net that trade-off doesn't pay this time.

## Recommendation
**Crude v4.2 = crude #1's exact entry/stop, session left at the script's own 09:15 default, no fixed target, exit on stop or reversal.** This is the first candidate in the whole crude search (300+ harness trials, now TradingView-confirmed) that beats crude #1 on every axis at once. It is not free: win rate drops to ~19-21% (many more small losers, fewer much-bigger wins), average hold time rises sharply (up to several days), and it has not run forward -- everything above is still backtest/replay, not live. Do not pair it with the later 17:30 start; keep the 09:15 default.
Before treating this as deployable: (1) a forward test, same discipline as the silver v4.1 test (pre-registered pass/fail rule, judged after >=60 forward trades); (2) explicit sign-off that the lower win rate / longer holds are acceptable, since that is a real behavioural change, not just a number.
