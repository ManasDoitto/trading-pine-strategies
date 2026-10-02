# Pre-registration: retuning silver E3 ("no entries before 12:00") (written 2026-10-03, BEFORE any run)

Incumbent = live v4.1 with no entries before 12:00 (RR 3, floor 2.5 / cap 5.0 x ATR, bo_lookback 3, day limit 350, hours 15-17 excluded).
Data SILVER1! 5m, 33 months. Points net of 0.02%/side. Selection uses DEVELOPMENT data only: trades exiting in the oldest 80% of the
timeline. The newest 20% (HOLDOUT) is not printed or used until the final config is frozen, then looked at once.

## Search (coordinate search, one dimension at a time from the incumbent, then combine) - 20 single-dimension trials
earliest entry: 11:00 | 13:00      RR: 2.5 | 3.5 | 4.0      floor/cap (x ATR): 2.0/4.5 | 2.5/4.0 | 3.0/5.0
bo_lookback: 2 | 4 | 5             day loss limit (pts): 250 | 500 | none      exclude hours: [15,16,22,23] | [15,16,18]
Order of combination (stage 2): earliest entry, RR, floor/cap, bo_lookback, day limit, exclude hours - each accepted single change is
re-tested against the evolving incumbent. No other dimension and no value outside this list may be tried.

## Acceptance rule (multi-metric, all on DEVELOPMENT; a change is accepted only if ALL hold vs the current incumbent)
1. expectancy (net R per trade) >= incumbent + 0.01     2. max drawdown in R <= incumbent x 1.05
3. share of months positive >= incumbent - 3 points     4. trades >= 500
5. min(PF-R in oldest-60% window, PF-R in next-20% window) >= incumbent's minimum - 0.02
Among values of one dimension that pass, the highest expectancy wins.

## Final checks (after freezing; each reported, none used to re-select)
A. HOLDOUT (newest 20%) for incumbent vs final: all metrics.   B. SILVERM1 bars (same market, different contract) for both.
C. One-step neighbours of every accepted parameter must keep PF-R >= 1.0 on development.
D. Paired month-block bootstrap, final vs incumbent, on all data (reported with the caveat that the pick was made on part of it).

## Decision rule
If nothing is accepted, E3 stays unchanged. The final config is recommended over the current live strategy only if on the HOLDOUT it
is not worse on expectancy, max drawdown (R) and share of months positive, AND passes check B on expectancy > 0. Otherwise: keep the
current live strategy and run E3/final as a shadow comparison. 20+ trials on one dataset: any gain is optimistic by construction.
