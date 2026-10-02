# Pre-registration: a SILVERM-native, short-hold, many-profitable-months strategy (written 2026-10-03, BEFORE the run)

Why: the trader buys SILVERM options (2 lots). The live signal is computed on the SILVER chart (a proxy), holds average ~14-16h (theta), and profit leans on a
few big months. Goal here: signals AND P&L on SILVERM1 itself, short holds, profit spread over many months.

## Frozen base
Entries = v4.1 (SHA flip OR 3-bar Donchian breakout, EMA9>EMA22 trend filter, hours 15-17 excluded), stop = 10-bar swing +/-0.1 ATR, day limit 350 pts.
Primary data: SILVERM1 5m, 2024-01 -> 2026-09 (33 months). Confirmation data: SILVER1 with the identical rules. Points, net of 0.02%/side.

## Search space: full factorial, exactly 72 configs (nothing else)
entry window {all day 09:15-23:30 | evening only 17:00-23:00 | from 12:00}  x  RR {1.5, 2.0, 3.0}  x  stop floor/cap {2.5/5.0 | 1.5/3.0} x ATR
x  exit style {overnight allowed | flat at 23:25 | 240-min time stop + flat 23:25 | 120-min time stop + flat 23:25}
(the evening-only window is a hypothesis: COMEX/London drive silver then; it is also where the live strategy's profits cluster, so it is in-sample motivated.)

## Split and selection (SILVERM1; development = oldest 80% of exits; holdout = newest 20%, untouched until the end)
ELIGIBLE on development only if ALL hold:
1. average hold <= 5.0 h        2. >= 400 development trades        3. net points > 0 and expectancy (R) > 0 in BOTH the oldest-60% and next-20% windows
4. share of months positive >= 55%        5. best single month <= 30% of total development net points
6. confirmation: on SILVER1 the same config has development expectancy > 0 and months positive >= 50%
Rank eligible configs by the lower of the two contracts' development expectancy (R). Top 3 go to the holdout, ONE look, config #1 is the primary.
Live v4.1 is evaluated on the same development/holdout cut as the baseline.

## Holdout pass rule (SILVERM1 newest 20%), primary config: expectancy (R) > 0, PF (R) >= 1.0, months positive >= 50%, average hold <= 5h,
AND not worse than live v4.1 on max drawdown (R). A pass is a SHADOW-BOOK candidate only; nothing goes live from this test.
72 trials on one dataset: if nothing is eligible, that is the answer - the honest statement is that no variant in this family meets all of the trader's goals.
