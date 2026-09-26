# Crude #1: 50 untested configurations, round 1 (2026-09-27)
Harness, 30 months from 2024-03-25, gross points. Pre-registration: `pre_registration_crude_50cfg_2026_09_27.md`. Data: `research_data/crude_50cfg.csv`. Code: `crude_50cfg.py`.
Controls: crude #1 at 09:15: 785 tr, PF 1.263, +5,614 (TRAIN +2,270 / HOLDOUT +3,344); at 17:30: 429 tr, PF 1.476, +6,558 (TRAIN +2,447 / HOLDOUT +4,111).

**Pre-registered pick: FAILED.** Highest TRAIN gross was max 2 trades/day @09:15 (TRAIN +2,807), which then made only +1,471 on HOLDOUT (control +3,344).
**Transfer: Spearman(TRAIN, HOLDOUT) over the 50 = +0.008**, i.e. ranking on the first half tells nothing about the second half (same finding as every earlier search).
Clear losers: swing 7 (+1,787 / +2,262), ADX>=20, time stops of 8h and 16h at 09:15, max 1/day, no-overnight at 09:15 (+3,910), skip Fri.
Beat their control in both halves: only **EMA 9/34 @09:15** (TRAIN 2,348 / HOLDOUT 3,656, PF 1.322, +6,004, best month 24.7%, DD 1,662). It was not the pre-registered pick, so it is a post-hoc lead (one of 50); round 2 tests whether it is a plateau.
Trailing 2R/2R @09:15 (+7,402 full, holdout +5,893) and skip-22h @17:30 (+7,356) look large on the full period but lost to the control on TRAIN, so they are holdout-driven.
