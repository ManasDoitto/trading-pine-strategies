# Pre-registration: LONGER stop swing lookbacks for the deployed SILVERM strategy (written 2026-10-03, BEFORE the run)

Follow-up to pre_registration_silverm_swing_lookback_2026_10_03.md (5/6/7 bars and day extreme all lost to the current 10 bars; the trend 5<6<7<10 suggested longer might do better).
Variants (exactly four, nothing else): swing lookback 12, 15, 20 and 30 bars. Everything else unchanged (0.1 ATR buffer, floor 2.5 / cap 5.0 ATR, RR 3, 350 brake, hours 15-17 excluded).
Same data, development / holdout cut and acceptance rule as the earlier file: accepted on development only if on BOTH contracts PF >= baseline + 0.05, net >= baseline,
max drawdown (R) <= baseline x 1.05, months positive >= baseline - 3 points; the best accepted gets ONE holdout look (SILVERM1 PF, net, expectancy not below baseline,
drawdown (R) <= baseline x 1.10; SILVER1 expectancy > 0). Cumulative trials on this question: 8 (4 earlier + these 4). A pass is a candidate for the shadow book, not a live change.
