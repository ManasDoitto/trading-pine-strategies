# Pre-registration: round 2 (50 configs), written after seeing round 1 (2026-09-27)
Round 1 (crude_50cfg.py, 50 configs + 2 controls): the pre-registered pick (highest TRAIN gross, max 2/day @09:15, TRAIN +2,807) FAILED: HOLDOUT +1,471 vs control +3,344.
Post-hoc observation (NOT a pick, one of 50 trials): EMA 9/34 @09:15 beat crude #1 in BOTH halves (TRAIN 2,348 vs 2,270; HOLDOUT 3,656 vs 3,344; PF 1.322 vs 1.263; +6,004 vs +5,614; best month 24.7% vs 42.1%; DD 1,662 vs 2,176).
Round 2 tests whether that is a plateau or a lucky point. Config set (fixed now, 50): EMA slow in {28,30,32,36,40,45,50} with fast 9 at starts 09:15 and 17:30 (14); fast in {7,10,11} with slow 34 at both starts (6);
EMA 9/34 plus each of trail 2R/2R, skip 22h, be 2R, be 1.5R, hold 4, rr 4.5, max 2/day, trail 3R/2R at both starts (16); EMA 9/34 at starts 15:00, 16:00, 17:00, 18:00 (4); EMA 9/34 with maxSL 2.75, 3.25, minSL 2.0, swing 8, swing 12 at both starts (10).
Test 1 (plateau): of the 7 slow values at 09:15 (28..50), at least 5 must beat the 09:15 control in BOTH halves on gross points. Otherwise the 9/34 result is treated as noise.
Test 2 (candidate): among configs with >=100 trades and TRAIN gross above its control, the one with best HOLDOUT is only a candidate; nothing is called better until TradingView replay confirms.
Cumulative trials after this round: 100.
