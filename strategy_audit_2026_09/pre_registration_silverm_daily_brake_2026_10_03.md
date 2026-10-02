# Pre-registration: the daily brake of the current SILVERM strategy (written 2026-10-03, BEFORE the run)

Finding that motivates it: the live "350-point daily loss limit" is smaller than a typical stop (median 482, mean 998 pts; 70% of losers lose > 350),
so it behaves as "one stop-out ends the day" (locks 321 of 541 days, costs 17% of profit, halves the drawdown). Full-history glance showed 1,500 gave similar
profit with more positive months (23/33 vs 18/33) - a lead only, found by looking at all the data.

## Variants (exactly seven, SILVERM1 primary, SILVER1 confirmation; everything else is the live v4.1)
B0 current: day limit 350 pts | B1 limit 1000 | B2 limit 1500 | B3 limit 2000 | B4 limit 3000 | B5 no limit | B6 no limit but at most 2 trades per day
(limits are realised-loss totals for the day, checked after each closed trade, as in the live code.)

## Selection on DEVELOPMENT only (exits before the baseline's 80th-percentile exit date, per contract); holdout untouched until the single final look
A variant is ACCEPTED over B0 only if on BOTH contracts, on development: net points >= 95% of B0's, months positive >= B0 + 5 points,
max drawdown (R) <= B0 x 1.15, profit factor (points) >= B0 - 0.05, and >= 400 trades. The accepted variant with the highest months-positive wins; ties -> lower drawdown.
Final HOLDOUT (SILVERM1 and SILVER1, B0 vs the winner): passes if on SILVERM1 net points >= B0's, expectancy (R) >= B0's, months positive >= B0's, drawdown (R) <= B0 x 1.10,
and on SILVER1 expectancy (R) > 0. Seven trials; a pass is a config candidate, nothing changes live without the user's explicit OK.
