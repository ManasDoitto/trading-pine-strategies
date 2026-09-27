# Pre-registration: round 4 (2026-09-27), cumulative trials 200
Round 3 left one hypothesis: skipping the most volatile bars (ATR < its 90th percentile over 500 bars) improved full/holdout at both starts but not TRAIN. Round 4 = 50 configs at starts 09:15 and 17:30, crude #1 base:
A (18) ATR-percentile plateau: window W in {250,500,1000} x percentile in {80,90,95} and W=500 with {75,85} handled as: W250:{80,90,95}, W500:{80,85,95}, W1000:{80,90,95} = 9 per start.
B (10) atr<p90(W500) combined with break-even 2R, trail 2R/2R, skip 22h, EMA 9/34, SHA hold 4 (5 x 2 starts).
C (4) long-only, short-only. D (6) entry window end 23:00 / 22:00 / 21:00. E (6) prior-day range above its 20-day median; ATR rising vs 12 bars ago; EMA9 slope with the trade over 6 bars.
F (4) SHA min hold 6 and 8.
Rules fixed now: (1) A config PASSES only if at BOTH starts it beats the same-start control in TRAIN gross, HOLDOUT gross, full PF and HOLDOUT after-cost (same as round 3). (2) The ATR-percentile family is a PLATEAU only if at each start at least 6 of its 9 settings beat control in both TRAIN and HOLDOUT gross. Otherwise the round-3 result is treated as noise.
Anything passing goes to TradingView replay; nothing else does. Spearman(TRAIN, HOLDOUT) reported.
