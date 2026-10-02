# Pre-registration: broad search for a genuinely better SILVERM strategy (written 2026-10-03, BEFORE the run)

Baseline = the deployed strategy ([strategy.SILVERM]: v4.1 on SILVERM1's own bars, 350 brake, hours 15-17 excluded). Primary data SILVERM1, confirmation SILVER1, both to 2026-10-01.
Points / R, net of 0.02%/side. DEVELOPMENT = exits before each contract's baseline 80th-percentile exit date; HOLDOUT = after it, not printed or used until the one final look.

## Candidates: exactly 21 single changes, each switched on alone against the baseline
Entry filters (signal bar must satisfy):
F1 EMA9-EMA22 gap >= 0.2 ATR in the trade direction | F2 close on the right side of EMA200 | F3 15-minute EMA9/EMA22 trend agrees (previous completed 15m bar)
F4 60-minute EMA9/EMA22 trend agrees (previous completed 60m bar) | F5 long-only | F6 breakout bar closes in the outer 30% of its range in the trade direction
F7 signal-bar range >= 0.8 ATR | F8 signal-bar volume >= 1.2 x its 20-bar average | F9 close beyond the 3-bar channel by >= 0.1 ATR
F10 ATR above its 50th percentile of the previous 2,000 bars | F11 ATR above its 67th percentile | F12 ATR below its 95th percentile
F13 skip signals in hours 13 and 17 (in-sample motivated by the earlier hour table) | F14 breakout entries only | F15 breakout lookback 5 instead of 3
Exit management: X1 sell 50% at +1.5R, rest to the normal exit | X2 sell 50% at +1.0R | X3 stop to entry at +2R | X4 trail 1.5R behind the extreme once +2R is reached
X5 reversal exit (an opposite signal closes the trade; no change to entries) | X6 stop buffer 0.3 ATR instead of 0.1 ATR

## Stage 1 - eligibility on DEVELOPMENT (BOTH contracts, all must hold, vs baseline)
expectancy (R) >= baseline + 0.03 | max drawdown (R) <= baseline x 1.10 | months positive >= baseline - 3 points | profit factor (points) >= baseline - 0.03 | >= 350 trades.
Luck check for ENTRY FILTERS (F1-F15) on SILVERM1: the candidate's expectancy gain must exceed the 90th percentile of the gain obtained by deleting the SAME share of baseline
trades at random (2,000 draws). Exit-management candidates (X1-X6) have no such null and carry that caveat explicitly.
## Stage 2 - combine: add eligible candidates greedily by SILVERM development gain, at most 3 changes, each addition must keep the Stage-1 conditions and add >= 0.01 expectancy.
## Stage 3 - HOLDOUT, one look, SILVERM1 and SILVER1, baseline vs the final combination. PASS only if on SILVERM1: expectancy >= baseline, PF >= baseline, max drawdown (R) <= baseline x 1.10,
net points >= 90% of baseline, AND on SILVER1 expectancy > 0.
## Stage 4 - if it passes: month-block bootstrap on the full history, P(expectancy better than baseline) reported with the caveat that the pick was made on part of that data.
Interpretation: 21 trials -> some will pass by chance; that is why Stage 1 needs both contracts, the random-deletion check and an untouched holdout. A pass is a shadow-book
candidate only; nothing changes live without the user's explicit OK.
