# Pre-registration: round 5 (2026-09-27), cumulative trials 248
50 configs = 25 ideas x starts 09:15 and 17:30, on crude #1 base. New ideas (none tried before):
Asymmetric RR long/short (L5/S4, L5/S3, L6/S4, L4/S3, L6/S3); long-only with RR 5 and 6; asymmetric max stop (long 3.5 / short 2.5, and long 2.5 / short 3.5);
day range so far >= 6 / >= 10 ATR; overnight gap direction (long only if the day open is above the previous close, short if below); close above/below the prior-day midpoint; trend strength |EMA9-EMA22| >= 0.5 / >= 1.0 ATR;
Tue-Thu only; ATR / ATR(100) >= 0.8; 12-bar and 24-bar momentum with the trade; EMA9 slope over 3 / 12 / 24 bars (plateau check on the round-4 EMA9-slope lead, which used 6);
EMA9 slope(6) combined with long-only RR 5... no: with break-even 2R, with trail 2R/2R, and with long RR 5 / short RR 4 (3 combos).
Note: research_sim.simulate gained optional p["rr_l"]/p["rr_s"] (default = p["rr"], so every earlier result is unchanged; the control is re-run and must equal 785 / 429 trades).
Rule 1 (same as rounds 3-4): PASS only if at BOTH starts it beats the same-start control in TRAIN gross, HOLDOUT gross, full PF and HOLDOUT after-cost.
Rule 2 (EMA9-slope plateau): among slope windows {3, 6, 12, 24}, at least 3 of 4 must beat control in TRAIN and HOLDOUT gross at each start; otherwise the round-4 lead is noise.
Only a Rule 1 pass goes to TradingView replay (needs a Pine change; user creates the slot).
