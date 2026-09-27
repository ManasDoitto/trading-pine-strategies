# Pre-registration: round 6, entry signals other than SHA flip (2026-09-27), cumulative trials 298
Rounds 1-5 (248 trials) only varied exits/filters/session/RR around the SHA-flip trigger and found nothing durable. Round 6 replaces the trigger itself, keeping crude #1's risk framework unchanged for a fair isolated
comparison: same 10-bar swing stop floored at 1.5xATR, skipped if stop > 3.0xATR, fixed 4R target, one position, session filter only (no EMA9/22 alignment filter unless the signal itself is EMA-based).
25 signal families x 2 entry starts (09:15, 17:30) = 50 configs: EMA9/22 cross, EMA9/22 cross + EMA200 trend, MACD(12,26,9) histogram cross zero, MACD line/signal cross, Supertrend(10,3) flip, Donchian breakout
10/20/55, opening-range breakout 30min/60min, RSI(14) cross 50, RSI(14) reversion 30/70, Bollinger(20,2) breakout, Bollinger(20,1.5) breakout, Bollinger-squeeze breakout, Stochastic(14,3) cross 20/80, CCI(20) cross zero,
price/VWAP cross, 3-bar momentum burst, Keltner(20,2) breakout, Keltner(20,1.5) breakout, prior-day-H/L (pivot) breakout, DI+/DI- cross, Parabolic SAR flip, EMA5/13 cross.
Pick rule (fixed now): among configs with >=100 trades over 30 months, highest TRAIN (<2025-06-25) gross points is the pick. PASSES only if, at BOTH entry starts vs crude #1 (same start): HOLDOUT gross higher,
HOLDOUT after-cost (0.02%/side) higher, full PF higher, trades >= 15/month at 09:15. A pass is a forward-test candidate only, not a finding, pending TradingView replay. Report Spearman(TRAIN,HOLDOUT) over the 50.
If nothing passes that is the result; no further signal-family rounds unless the user asks.
