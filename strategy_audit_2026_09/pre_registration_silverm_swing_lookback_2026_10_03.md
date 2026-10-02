# Pre-registration: stop-loss swing lookback of the deployed SILVERM strategy (written 2026-10-03, BEFORE the run)

Current stop: beyond the lowest low (long) / highest high (short) of the last 10 five-minute bars, +0.1 ATR, floored at 2.5 ATR from the signal-bar close, skipped if wider than 5 ATR.
Variants requested by the trader (exactly four, nothing else): swing lookback 5, 6, 7 bars, and "the extreme of the day so far" (lowest low / highest high since that day's first bar).
Everything else (entries, RR 3, 350 brake, hours 15-17 excluded, floor/cap) unchanged. Because the target is 3 x the stop distance, changing the stop also changes the target.

Data SILVERM1 (primary) and SILVER1 (confirmation), 2024-01 -> 2026-10-01. Points, net of 0.02%/side. Development = exits before the baseline's 80th-percentile exit date, holdout after it.
A variant is ACCEPTED on development only if on BOTH contracts: PF (points) >= baseline + 0.05, net points >= baseline, max drawdown (R) <= baseline x 1.05, months positive >= baseline - 3 points.
If any are accepted the best goes to ONE holdout look on SILVERM1 (PF, net, expectancy not below baseline; drawdown (R) <= baseline x 1.10) and SILVER1 expectancy > 0.
Full-history numbers for all variants are shown to the trader regardless, as descriptive information; selection uses development only. Four trials.
