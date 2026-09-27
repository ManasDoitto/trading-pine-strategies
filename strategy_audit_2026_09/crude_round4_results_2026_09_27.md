# Crude #1: round 4 (2026-09-27), 48 configs (24 per start; the pre-registration said 50, the F and E groups came to 24 not 26). Cumulative trials 198.
Pre-registration: `pre_registration_crude_round4_2026_09_27.md`. Code `crude_round4.py`, data `research_data/crude_round4.csv`. Harness, gross points, TRAIN (2,270 / 2,447) / HOLDOUT (3,344 / 4,111) controls at 09:15 / 17:30.

**Rule 2, ATR-percentile plateau (>=6 of 9 settings beat control in TRAIN and HOLDOUT at each start): FAILED.** At 09:15 none of the 9 does (best p95 W1000: TRAIN 2,261, 9 short of control); at 17:30 only 1 of 9 (p95 W1000: 2,638 / 4,582).
The round-3 ATR<p90 hypothesis is treated as noise: most settings lose TRAIN badly (p80 W500: 859 / 928) while raising HOLDOUT.
**Rule 1 (beat control in TRAIN, HOLDOUT, PF, HOLDOUT after-cost at BOTH starts): ONE PASS, marginal: "EMA9 slope with the trade over 6 bars".**
| | trades | PF | net | TRAIN | HOLDOUT | after-cost HOLDOUT |
|---|---|---|---|---|---|---|
| 09:15 control | 785 | 1.263 | +5,614 | 2,270 | 3,344 | 2,191 |
| 09:15 + EMA9 slope | 728 | 1.291 | +5,911 | 2,552 | 3,359 | 2,260 |
| 17:30 control | 429 | 1.476 | +6,558 | 2,447 | 4,111 | 3,487 |
| 17:30 + EMA9 slope | 404 | 1.517 | +6,774 | 2,487 | 4,287 | 3,688 |
Margins are small: +297 / +216 total points (+5% / +3%), HOLDOUT +15 at 09:15, from removing 57 / 25 trades. That is the size of the noise in rounds 1-3 (Spearman about 0 to +0.4), and it is one of 48 tried in this round (198 overall), though the two starts are not independent.
It has NOT been replayed on TradingView: it needs an EMA9-slope input in the Pine script (not present in the loaded study).
Not passing: every combination with the p90 filter (B group, e.g. +skip 22h @17:30 PF 1.928, +8,598) lifts full-period and HOLDOUT, but TRAIN is below control (1,709 vs 2,447). Long-only keeps 64-68% of profit; short-only is ~breakeven (+1,254 / +1,056), so nearly all of crude #1's edge is long trades.
Entry-end-time cuts (22:00, 21:00) lose points. Prior-day range and ATR-rising cut trades and TRAIN.
