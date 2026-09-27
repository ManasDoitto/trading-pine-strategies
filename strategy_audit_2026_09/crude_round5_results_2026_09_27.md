# Crude #1: round 5 (2026-09-27), 50 configs + slope-6 re-run. Cumulative trials 248.
Pre-registration: `pre_registration_crude_round5_2026_09_27.md`. Code `crude_round5.py`, data `research_data/crude_round5.csv`. Controls re-run and unchanged (785 / 429 trades) after the optional rr_l/rr_s addition to research_sim.
Controls (TRAIN / HOLDOUT): 09:15 +5,614 (2,270 / 3,344), 17:30 +6,558 (2,447 / 4,111).

**Rule 2 (EMA9-slope plateau, >=3 of 4 windows {3, 6, 12, 24} beat control in TRAIN and HOLDOUT at each start): FAILED, 1 of 4 at each start.** Slope 3 is a no-op (783 / 428 trades), slope 12 gives PF 1.001 / 0.987 (+9 / -120 points), slope 24 loses (+3,434 / +4,005).
The round-4 "EMA9 slope 6" pass was a lucky point, not a signal.
**Rule 1 (both starts): NO PASS.** Only RR long 4 / short 3 passed at 09:15 (TRAIN 2,444, HOLDOUT 3,414, PF 1.276, +5,859) and failed at 17:30 (HOLDOUT 3,827 < 4,111).
Everything else lost: higher long RR (L5/S4, L6/S4, long-only RR 5/6) lowers the first half and total points; asymmetric max stops hurt (L3.5/S2.5 +3,685 / +3,818; L2.5/S3.5 +2,671 / +2,229); gap direction, day-range, Tue-Thu, momentum (roc12 +1,527) and ATR ratio all cut profit at both starts.
Prior-day midpoint (PF 1.328 / 1.578, +5,152 / +5,504) lifts PF at both starts but total points and TRAIN are below control (1,667 / 1,155).
Trend-strength filters were near-empty (1 / 32 / 6 trades): EMA9-EMA22 gap at a flip is almost always small, so those two tests are uninformative, not negative.
Slope 6 + break-even 2R or trail 2R/2R again lift full-period and HOLDOUT (+8,095 with trail at 09:15) with TRAIN below control (1,924 vs 2,270): the recurring second-half-only pattern.
