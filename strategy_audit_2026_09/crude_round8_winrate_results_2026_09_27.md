# Round 8: raising crude v4.2's win rate without giving up net points/drawdown (2026-09-27), 50 configs
Pre-registration: `pre_registration_crude_round8_2026_09_27.md`. Code `crude_round8_winrate.py`, data `research_data/crude_round8.csv`. Harness, 09:15 (the only TradingView-confirmed start), gross points.
Base = crude v4.2 (SHA flip + EMA9/22, 10-bar swing stop, no fixed target, exit on stop or reversal). Reference: 758 trades, PF 1.727, **+12,105 net, win 20.7%, worst DD 2,027**.
Bar for a genuine candidate: win% >= 28 (meaningfully higher), net >= 10,289 (within 15% of reference), DD <= 2,432 (within 20%).

## Result: zero of 50 configurations clear the bar. There is a real, structural trade-off, not noise.
**Correlation between win% and net points across all 50 configs: -0.67.** Every mechanism that raises win rate (break-even stops, trailing stops, partial scale-outs, shorter minimum hold before a reversal can fire) works by capping or realising profit earlier -- which is exactly what cuts into the handful of oversized winners that produce most of this strategy's edge. There is no configuration tested where win rate rises substantially and net/drawdown stay close.

### The closest compromises (win% >= 25, ranked by how much net survives)
| config | trades | PF | net pts | win% | DD | net as % of reference |
|---|---|---|---|---|---|---|
| F: trailing stop only, start 2.5R, trail 2.0R (no break-even) | 940 | 1.494 | 9,698 | **28.7%** | 2,115 | 80% |
| C: scale out 33% at 3.0R, ride the rest | 758 | 1.597 | 9,266 | 27.0% | 2,029 | 77% |
| F: trailing stop only, start 2.0R, trail 2.0R | 951 | 1.481 | 9,220 | 31.0% | 2,115 | 76% |
| C: scale out 33% at 2.5R, ride the rest | 758 | 1.613 | 9,175 | 29.2% | 1,870 | 76% |

The single best all-around compromise is **trailing stop only, starting at 2.5R, trailing 2.0R behind the extreme (no break-even, no scale-out)**: win rate rises from 20.7% to 28.7% (+8 points, +39% relative) and drawdown is essentially unchanged (2,115 vs 2,027), but net points fall to 80% of the reference (-20%, about -2,400 pts over 30 months).

### If net/DD closeness matters more than win rate
| config | net pts | win% | DD | net as % of reference |
|---|---|---|---|---|
| minSL 1.25xATR (was 1.5) | 12,114 | 20.6% | 2,025 | 100.1% |
| minSL 1.0xATR | 12,103 | 20.6% | 2,025 | 100.0% |
| min-hold 3 bars before a reversal can fire | 11,977 | 20.8% | 2,037 | 99% |
| break-even at 2.0R | 11,938 | 17.2% | 1,887 | 99% |

These barely move win rate at all (17-21%, essentially unchanged from 20.7%) -- they preserve the profile rather than improving it.

### A side effect worth flagging: win-rate fixes make profit MORE concentrated, not less
Best-month share rises in almost every config that raises win rate -- e.g. break-even(1.0R) + scale-out(2.0R, 50%): best month = **73.2%** of total profit, vs 47.2% for the unmodified strategy. Cutting off the tail of big winners doesn't spread the remaining profit out; it just shrinks it while the same few trend windows still supply most of what's left. A higher win rate here is not "smoother" -- it is a smaller, still-concentrated result.

## Why this strategy resists a win-rate fix
v4.2's entire edge is "let a small number of trades run very large, accept a high frequency of small stops." That is the reversal-exit/no-target design itself, not a flaw to patch. Any early profit-taking mechanism (break-even, trailing, scale-out) is philosophically opposed to that design: it converts stopped-out-for-loss trades into stopped-out-for-tiny-loss/scratch/small-win trades (raising win%), but it also converts the rare enormous winners into merely large winners (cutting net). The two effects don't cancel; on 30 months of crude, cutting the winners costs more than fixing the losers saves.

## Recommendation
Don't change v4.2 for win rate alone -- the trade-off is real and this option costs meaningfully more than it's worth unless a higher win rate has value to you beyond the P&L curve (e.g. psychological tolerance for the current ~20% win rate). If it does, **trailing stop only, start 2.5R / trail 2.0R** is the single best-supported compromise found (28.7% win, -20% net, ~flat DD). None of this has been TradingView-confirmed; it is harness-only, exploratory, and did not clear the pre-registered bar for a "candidate."
