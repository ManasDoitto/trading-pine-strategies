# TradingView replay, commission removed, BOTH variants (run 2026-09-26)

User asked to remove TradingView's 0.02%/side charge and test both strategies, because the numbers were not coming
close. Both requests were right, and the second one overturns a claim I made earlier today.

## 1. Removing commission closes most of the gap
| | trades | PF | net pts | worst dd |
|---|---|---|---|---|
| harness, v4.1, full CSV, GROSS | 899 | 1.501 | +304,285 | 30,646 |
| **TV replay, v4.1, GROSS** | 964 | 1.369 | **+261,439** | 42,612 |
| TV replay, v4.1, net 0.02%/side (earlier run) | 977 | 1.267 | +199,906 | 43,797 |

Commission alone was ~61,500 pts of the discrepancy. The residual (+304,285 vs +261,439, and 899 vs 964 trades) is
the tiled method itself: 13 windows with ~5-day overlaps double-count some trades, and each window restarts the
strategy flat with its own 400-bar warm-up, so trades near boundaries are gained or lost.

## 2. Both variants, TradingView replay, GROSS - and the ranking FLIPS
| window | ending | v4.1 PF | v4.1 net | incumbent PF | incumbent net |
|---|---|---|---|---|---|
| W1 | 2024-04-08 | 0.863 | -2,319 | 0.646 | -4,949 |
| W2 | 2024-06-24 | 1.180 | +4,388 | 1.233 | +4,378 |
| W3 | 2024-09-09 | 1.207 | +4,633 | 1.556 | +8,833 |
| W4 | 2024-11-25 | 1.189 | +4,787 | 1.869 | +13,407 |
| W5 | 2025-02-10 | 0.831 | -2,870 | 1.073 | +1,191 |
| W6 | 2025-04-28 | 1.306 | +7,740 | 1.533 | +10,151 |
| W7 | 2025-07-14 | 1.257 | +6,062 | 0.987 | -292 |
| W8 | 2025-09-29 | 1.488 | +10,142 | 1.235 | +5,034 |
| W9 | 2025-12-15 | **2.238** | **+53,440** | 1.030 | +1,385 |
| W10 | 2026-03-02 | 2.040 | +182,856 | **2.548** | **+164,791** |
| W11 | 2026-05-18 | 0.900 | -15,556 | 1.018 | +1,654 |
| W12 | 2026-08-03 | 1.002 | +220 | **2.103** | **+55,615** |
| W13 | 2026-09-25 | 1.132 | +7,916 | 1.105 | +4,974 |
| **TOTAL** | | **1.369** | **+261,439** | **1.548** | **+266,172** |
| trades / worst dd / windows +ve | | 964 / 42,612 / 10 | | 875 / **33,706** / **11** | |

**On TradingView the incumbent WINS**: higher PF (1.548 vs 1.369), slightly more net, **9,000 pts less drawdown**,
and more positive windows. v4.1 beats it in only **7 of 13** windows.
**On the harness the opposite**: v4.1 +304,285 vs incumbent +219,403, a 39% advantage.

## 3. Correction to today's earlier claim
I reported that adding a Donchian breakout to the silver base is "a genuine improvement - the first real one found
today", on the strength of +307,265 vs +222,240 and a walk-forward that passed. **That claim does not survive an
independent measurement method.** Swap the harness for TradingView's own tiled replay and the ranking reverses.

The reason is visible in the table: both variants are dominated by a handful of trades in a six-month window, and
they catch different ones. W9 is +53,440 for v4.1 and +1,385 for the incumbent; W12 is +220 for v4.1 and +55,615 for
the incumbent. With ~70 trades per window and single windows worth 60-70% of the total, which variant looks better
is decided by a few trades, not by the entry logic. Neither total is a stable estimate of anything.

## 4. What is actually supported
- Removing commission reconciles the harness and TradingView to within the tiled method's own noise. **The harness is
  sound** (it matched TV to 0.03% on the single-pass 72-trade overlap).
- **The v4.1-beats-incumbent ranking is NOT supported.** It is method-dependent, and the methods disagree.
- Both strategies share the same real problem: profit concentrated in Dec 2025 - Mar 2026, and drawdowns of
  33,700-42,600 pts in 2026 - larger than either strategy's whole-period drawdown on the harness.
- The forward test remains the right arbiter, and is now more clearly necessary than it looked this morning.
  Script left configured as the forward test: breakout ON, commission 0.02%/side, boundary 2026-09-27.

## Bottom line
The user's scepticism was correct on both counts. Commission explained most of the gap; testing both variants
revealed that the improvement I claimed is not robust to how it is measured. Do not switch away from
working_strategies/Silver #1 on the strength of the harness number.
