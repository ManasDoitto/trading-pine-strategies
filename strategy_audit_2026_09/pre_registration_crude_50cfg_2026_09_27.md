# Pre-registration: 50 untested crude #1 configurations (2026-09-27)
Base = crude #1 (SHA 10/10, EMA9>EMA22, swing 10, buf 0.1, minSL 1.5, maxSL 3.0, RR 4, no day limit, hold overnight). Harness, 30 months from 2024-03-25, gross points, TRAIN < 2025-06-25 <= HOLDOUT.
25 ideas not in the earlier knob map, each run on two entry starts (09:15 and 17:30) = 50 configs. Controls: crude #1 at 09:15 and at 17:30 (same harness).
Ideas: breakeven 1R/2R, trailing (2R/2R, 3R/1.5R), time stops 4h/8h/16h, no-overnight (entries to 22:30, flat 23:25), max 1 and 2 trades a day, EMA 8/21, 12/26, 9/34, SHA min hold 2 and 4,
ATR>SMA50 filter, 15m ADX>=20, skip Friday, skip 22h entries, swing 7 and 14, minSL 1.75, RR 3.5 and 4.5.
Pick rule (fixed now): among configs with >=100 trades, highest TRAIN gross points. It PASSES only if, versus the control with the same entry start: HOLDOUT gross points higher, HOLDOUT after-cost (0.02%/side) higher, full PF higher,
trades >= 15/month. Also report Spearman(TRAIN, HOLDOUT) over the 50 (selection transfer). A pass is only a candidate: needs TradingView replay confirmation before being called better. If none passes, that is the result.
If nothing passes, at most 2 further rounds of 50 new ideas; each round is reported separately with the cumulative trial count.
