# Porting crude + silver's top 15 strategies each onto Nifty 50 spot (2026-09-27)
Data: `NSE_NIFTY_5m.csv` (6.3mo usable, 9 Mar-25 Sep 2026) and `NSE_NIFTY_3m.csv` (3.7mo usable, 1 Jun-25 Sep 2026). Unlike BankNifty, where the futures contract had 3 years of 5m history,
**Nifty futures and Nifty spot hit the identical TradingView data floor** (confirmed on both by paging to "no older data"): 5m only back to 9 Mar 2026, 3m only back to 1 Jun 2026. There is no robust
multi-year option for Nifty on this feed either way, so spot was used since it was the literal ask and costs nothing extra this time. NSE:NIFTY spot pv=1. Same session (09:15-15:20, flat by 15:30),
day-loss-limit off, and config set as the BankNifty port (`bnf_port_test.py` / `bnf_port_test_results_2026_09_27.md`). Code: `nifty_port_test.py`, data: `research_data/nifty_port_test.csv`.
**No existing Nifty 3m/5m strategy exists to compare against** -- the dashboard's own Cross-Instrument table lists Nifty as "none at 3m/5m" (the only prior Nifty work was a 15-minute sweep-fade family, out of this scope).

## Result: noticeably more promising than BankNifty on 5m -- but the sample is thin and this is a 30-config screen on one short window. Treat as a lead, not a finding.

### 5m (6.3 months, ~125-260 trades per config): best 8 of 30 by PF
| strategy | trades/mo | PF | net pts | DD | best-month share |
|---|---|---|---|---|---|
| C11: crude + ATR<p90 filter | 21.4 | **1.633** | +2,369 | **374** | 28% |
| S5: silver v5.0 SHA-ADX hybrid | 18.0 | 1.645 | +2,104 | 318 | 26% |
| C8: crude maxSL 2.75xATR | 19.7 | 1.566 | +1,975 | 334 | 42% |
| S9: silver vanilla (narrow ATR) | 22.9 | 1.488 | +1,971 | 317 | 28% |
| S12: silver short-only wide-ATR | 20.8 | 1.447 | +1,966 | 600 | 36%, **win 47%** |
| C6: crude RR 4.5 | 21.3 | 1.483 | +1,927 | 498 | 31% |
| C14: crude v4.2 + min-hold-before-reversal 6 | 26.0 | 1.511 | +1,949 | 635 | 35% |
| C2: crude v4.2 (reversal, no target) | 28.4 | 1.471 | +1,794 | 646 | 38% |
This is a real change from BankNifty: **10 of 30 configs clear PF 1.4** here (BankNifty's best was 1.154), drawdowns are small in absolute terms (317-874 on most), and best-month concentration is
mostly 26-42% (not one lucky month carrying the result). Only 3 of 30 are net-negative on 5m (S2, S4, S6 -- the loosest breakout-heavy silver variants), a much better hit rate than BankNifty's.

### 3m (3.7 months, thin): weaker and mixed, but not uniformly negative like BankNifty
Best: **C14 (crude v4.2 + min-hold 6): PF 1.234, +671 pts, 46.9 tr/mo, DD 501.** C7 (minSL 2.0): PF 1.134, +402. C13 (sw_len 15): PF 1.146, +393. Most of the rest are flat-to-negative, and the whole silver family
fails again (same pattern as BankNifty: breakout-heavy silver configs don't transfer to an index). **Same-config PF rank correlation between 5m and 3m results: Spearman +0.73** -- a real relationship,
though the two windows overlap in calendar time (Jun-Sep is inside Mar-Sep), so this is a consistency check, not an independent confirmation.

## Why this needs a caveat, not a celebration
Two honest problems, both already flagged repeatedly this project:
1. **Thin data.** 6.3 months is barely above this project's own "need >=60 trades before believing anything" floor for most of these configs, and it is genuinely the most history TradingView will give for Nifty on this feed -- there is no way to get more without waiting for more calendar time to pass or a different data source.
2. **Multiple comparisons.** This is 30 configurations screened on one short, non-tiled window. Every crude round this project ran (rounds 1-7, 326 trials) found that a promising-looking config on one window regularly failed to repeat on a second one. There is no second window available here to check against -- Nifty's whole usable history *is* the test window.

## What I'd actually trust
**C11 (crude + ATR-below-90th-percentile filter) and S5 (silver's v5.0 SHA-ADX hybrid)** are the two best-supported leads: highest PF, lowest drawdown, lowest best-month concentration, and both are low-frequency
(18-21 trades/month, well inside what you asked for). Both are candidates for a forward test on Nifty, not a proven result -- the only way to get real confidence here is to accumulate more out-of-sample data over
time (paper/forward test) since the historical window can't be extended further on this feed.

## Recommendation
Don't deploy anything from this test yet. If you want to pursue Nifty, the two candidates above (C11, S5) are worth a pre-registered forward test, same discipline as crude v4.2 and the silver breakout test --
judged after a real number of forward trades, not on this backtest alone. BankNifty stays on v0.4; this Nifty result does not change that.
