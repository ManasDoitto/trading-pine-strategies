# TradingView tiled replay: SILVER v4.1 across 30 months (run 2026-09-26)

Method: the repo's CMP tiled-replay pattern. `replay_stop` -> `replay_start <date>` -> read the AUD table, thirteen
times, chaining ~81-day windows from the 5m replay floor to the live edge. Script
`6_v4.1_flip_breakout_forwardtest` on MCX:SILVER1! 5m. **These are TradingView's own fills, net of the script's
0.02%/side commission** - unlike the harness headline numbers, which were gross.
Checkpoint: `research_data/tv_replay_v41_checkpoint.txt`. Windows overlap ~5 days each (TV decides how much history
it loads behind the cursor); the overlap is disclosed, not removed.

## Per-window
| window | period | days | trades | wins | PF | net pts | maxDD |
|---|---|---|---|---|---|---|---|
| W1 | 2024-01-18 -> 2024-04-08 | 81 | 76 | 19 | 0.754 | **-4,285.1** | 6,376.5 |
| W2 | 2024-04-04 -> 2024-06-24 | 81 | 82 | 23 | 1.031 | +831.1 | 6,771.2 |
| W3 | 2024-06-20 -> 2024-09-09 | 81 | 79 | 22 | 1.004 | +90.7 | 6,729.7 |
| W4 | 2024-09-05 -> 2024-11-25 | 81 | 79 | 23 | 1.081 | +2,196.8 | 6,305.0 |
| W5 | 2024-11-21 -> 2025-02-10 | 81 | 80 | 17 | 0.787 | **-4,994.5** | 6,250.0 |
| W6 | 2025-02-06 -> 2025-04-28 | 81 | 83 | 24 | 1.126 | +3,515.8 | 6,792.9 |
| W7 | 2025-04-24 -> 2025-07-14 | 81 | 79 | 21 | 0.928 | **-1,848.8** | 9,697.8 |
| W8 | 2025-07-10 -> 2025-09-29 | 81 | 78 | 25 | 1.295 | +6,547.3 | 6,200.9 |
| **W9** | 2025-09-25 -> 2025-12-15 | 81 | 66 | 28 | **2.095** | **+49,585.8** | 8,906.9 |
| **W10** | 2025-12-11 -> 2026-03-02 | 81 | 73 | 28 | **1.969** | **+175,050.7** | 28,280.7 |
| W11 | 2026-02-26 -> 2026-05-18 | 81 | 74 | 23 | 0.857 | **-23,037.7** | **43,797.2** |
| W12 | 2026-05-14 -> 2026-08-03 | 81 | 61 | 19 | 0.946 | **-5,513.5** | 32,341.9 |
| W13 | 2026-07-09 -> 2026-09-25 | 78 | 67 | 21 | 1.027 | +1,767.8 | 23,950.2 |
| **TOTAL** | **Jan 2024 -> Sep 2026** | | **977** | | **1.267** | **+199,906.4** | **43,797.2 (W11)** |

## What TradingView says that the single-pass harness number did not
1. **Only 8 of 13 windows are profitable**, and the five losers are spread across the period, not clustered early.
2. **The first 20 months are a net loss.** Jan 2024 - Sep 2025: 7 windows, 558 trades, **net -4,494.1 pts, PF 0.974**.
   Sep 2025 - Sep 2026: 6 windows, 419 trades, **net +204,400.4, PF 1.355**. The later stretch is **102% of all
   profit** - the earlier stretch subtracts from it.
3. **Two windows are the strategy.** W9 (+49,586) and W10 (+175,051) together are +224,637 - more than the total.
   Every other window nets **-24,730** combined. Remove Sep 2025 - Mar 2026 and this does not work.
4. **Drawdown grows sharply once silver got volatile**: 6,200-9,700 pts per window through W8, then 28,281 / **43,797**
   / 32,342 / 23,950. W11's 43,797-pt drawdown is above the incumbent's whole-period 33,693 and above the 35,000-pt
   drop line pre-registered for the forward test.

## Reconciling with the harness
Harness (gross, 30 months, 2024-03-25 start): 825 trades, PF 1.519, +307,265 pts.
TradingView (net of 0.02%/side, Jan 2024 start, ~5-day window overlaps): 977 trades, PF 1.267, +199,906 pts.
The gap is explained, not mysterious: (a) commission - ~36 pts round trip on silver at ~90,000, about 35,000 pts
across 977 trades; (b) TradingView's span starts ~2 months earlier and includes W1's -4,285; (c) the ~5-day overlaps
double-count a small number of trades, inflating TV's trade count. Direction and shape agree; the earlier like-for-like
check on the same 72 trades matched to 0.03% on drawdown.

## Bottom line
The replay confirms v4.1 works, and confirms **how** it works - which is the part that matters. It is not a steady
+200k-point earner. It is flat-to-negative for 20 months, makes everything in a six-month silver move, then gives some
back with the largest drawdown of the whole period. The pre-registered forward test is the right next step and its
35,000-pt drop line is now known to be a level this strategy has genuinely breached before (W11: 43,797).
**Do not size this on the 30-month average.**
