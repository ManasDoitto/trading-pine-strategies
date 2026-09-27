# Pre-registration: round 7, genuinely new mechanisms (2026-09-27), cumulative trials 328
Rounds 1-5 (248 trials) varied exits/filters/EMA/RR around the SHA-flip trigger; round 6 (50 trials) replaced the trigger with 25 alternatives and lost every time. Round 7 keeps the SHA-flip trigger (it is the one
component that works) but adds mechanisms not tried in any earlier round, most needing new engine hooks added to `research_sim.simulate` this round: `cooldown_bars` (block new entries for N bars after a stop-loss)
and `reversal_exit` (force-exit a position at the open of the bar where an opposite SHA-flip signal fires, instead of waiting for the stop or target). Both are additive/opt-in; the crude #1 control was re-run
after adding them and is unchanged (785 / 429 trades) -- confirms no regression.
15 ideas x 2 entry starts (09:15, 17:30) = 30 configs: (1) reversal exit alone, (2) reversal exit with no fixed target (let winners run, only stop or reversal exits it), (3) cooldown 6 bars after an SL,
(4) cooldown 24 bars after an SL, (5) cooldown 6 bars + reversal exit combined, (6) 15m-timeframe SHA(10,10) agreement gate (previous COMPLETED 15m bar, no lookahead), (7) 15m EMA9/22 alignment gate (same convention),
(8) dual-length SHA confirmation (SHA(5,5) AND SHA(20,20) must both agree with the SHA(10,10) flip direction), (9) silver 5m EMA9/22 trend-agreement filter (a correlated-market filter, crude vs MCX silver),
(10) round-number filter (skip if entry price is within 0.3xATR of the nearest 50-point level), (11) ATR-regime-scaled stop cap (2.5xATR top tercile of vol, 3.5xATR bottom tercile, 3.0x otherwise, tercile on trailing 500 bars),
(12) ATR-regime-scaled RR (RR 3 high-vol tercile, RR 5 low-vol tercile, RR 4 otherwise), (13) close-based swing stop (10-bar rolling close min/max instead of low/high), (14) two-consecutive-bar confirmation
(signal bar's close must also clear the flip bar's own high/low in the trade direction), (15) delayed entry (arm the signal one extra bar later than usual).
Pick rule (fixed now, same as rounds 3-6): a config PASSES only if, at BOTH entry starts vs crude #1 (same start): HOLDOUT gross higher, HOLDOUT after-cost (0.02%/side) higher, full PF higher, trades >= 15/month
at 09:15. A pass is a forward-test candidate only, pending TradingView replay -- not a finding on its own. Report Spearman(TRAIN, HOLDOUT) over the 30. If nothing passes that is the result.
