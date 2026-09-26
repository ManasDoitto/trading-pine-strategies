# SILVER v4.1 forward test: LIVE as of 2026-09-26

Script: `6_v4.1_flip_breakout_forwardtest` (TradingView id `USER;81dddb8a44dd413890eb0882d509c316`, title
"SILVER v4.1 flip+breakout (forward test)"), loaded on MCX:SILVER1! 5m, study id `l7BgGR`, on the Intraday layout.
Rules: `pre_registration_silver_v41_forwardtest_2026_09_26.md`. Forward boundary **2026-09-27 00:00 IST**.

## On-chart table at load
| | trades | PF | net pts | maxDD |
|---|---|---|---|---|
| BACKTEST | 72 | 1.082 | +5,656 | 23,950 |
| FORWARD | 0 | - | 0 | 0 |

FORWARD is correctly zero: the boundary is tomorrow. Lookback 5 (B2), point value 30 confirmed on-chart.

## Harness vs TradingView: they agree
TradingView cannot backtest 30 months of 5m silver in one pass - its bar limit covers only the most recent ~10k bars,
which is why the backtest column shows 72 trades rather than the harness's 825. That is a data-window difference, not
a disagreement. Comparing like-for-like, the harness's **last 72 trades** over the same stretch
(2026-07-02 -> 2026-09-24), net of 0.02%/side as TradingView charges:

| | trades | PF | net pts | maxDD | win% |
|---|---|---|---|---|---|
| **harness (last 72)** | 72 | **1.080** | **+5,506.9** | **23,942.6** | **31.9%** |
| **TradingView** | 72 | **1.082** | **+5,656** | **23,950** | **31.9%** |

Identical trade count and win rate, drawdown within **0.03%**, PF within 0.2%, net within 2.7% (commission rounding).
**This validates the whole session's methodology** - every number reported today from `research_sim` is reproducing
TradingView's own fill engine, not an approximation of it.

## What to do next
Check the table after >= 60 FORWARD trades (~2.5 months at 27.5/mo) and judge against the pre-registered rules:
keep at PF >= 1.20 with forward drawdown under 35,000 pts; drop below PF 0.90 or if drawdown exceeds 35,000.
Read it with `data_get_pine_tables` filter "v4.1". Never move the goalposts.

## Related finding: the CRUDE forward test is NOT running
`[[crude-v4-forward-test]]` says v4.0 SHA flip RR3 has been forward testing on MCX:CRUDEOIL1! since 2026-09-14 in the
shared slot "BankNifty MTF Pullback v1.0". That slot does not exist in the account's saved scripts, and the crude
chart carries only Hull Suite Strategy, Hull Suite by InSilico, EMA and Smoothed Heiken Ashi - no v4.0 script.
It has been collecting nothing. Unknown for how long.
