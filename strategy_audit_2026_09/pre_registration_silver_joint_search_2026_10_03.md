# Pre-registration: joint SILVER1 + SILVERM1 search for a better silver v4.1 (written 2026-10-03, BEFORE the run)

Baseline = the LIVE strategy (v4.1 as in [strategy.SILVER]). The goal is a config that improves it on BOTH contracts at once.
Contracts: SILVER1 and SILVERM1 5m, 2024-01 -> 2026-09, each with signals computed on its own bars. Points net of 0.02%/side.

## Search space: full factorial, exactly 64 configs (2^6), nothing else
earliest entry {none, 12:00} x RR {3.0, 4.0} x stop floor {2.5, 3.0} x stop cap {4.0, 5.0} x bo_lookback {3, 4} x day loss limit {350, 500}
(live = none/3.0/2.5/5.0/3/350). Exits, session, 15-17h exclusion and everything else unchanged.

## Stage 1 - ELIGIBILITY, on DEVELOPMENT data only (oldest 80% of exits, per contract). A config is eligible only if, on BOTH contracts:
1. expectancy (net R/trade) >= live's          2. max drawdown (R) <= live's          3. months positive >= live's - 3 points
4. >= 450 development trades                   5. min(PF-R oldest-60% window, PF-R next-20% window) >= live's minimum - 0.02
6. average hold <= live's x 1.10 (the trader buys options; longer holds are a cost, not a feature)

## Stage 2 - SELECTION: among eligible configs, rank by the WORSE contract's (net R / max drawdown R) on development; take the top one.
If nothing is eligible, the live strategy stays and the search ends there.

## Stage 3 - HOLDOUT, looked at once (newest 20% of exits per contract), live vs the selected config. It PASSES only if on BOTH contracts it is
not worse than live on expectancy, max drawdown (R) and months positive, AND the average hold is not more than 10% longer.
Also reported: how many of the 63 non-live configs were eligible (a noise yardstick), full-history side by side, month-block bootstrap.

## Interpretation rules, fixed now
64 trials on one dataset: a pass is a CANDIDATE for the shadow book, not proof, and nothing goes live from this test. A fail means keep live.
