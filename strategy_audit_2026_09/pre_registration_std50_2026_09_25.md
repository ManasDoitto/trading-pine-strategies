# Pre-registration: 50 standard intraday strategies (written 2026-09-25, BEFORE any test)

Replaces the "top 100 YouTube videos" idea: the tools here return video titles only (no rules, no transcripts, no view
counts), so rules cannot be extracted honestly. These 50 are textbook rule sets that the videos are built on. Every
rule and number below is frozen; nothing is tuned.

## Common template (identical for all 50, so strategies differ ONLY by entry rule)
- Data: harvested 5m futures bars, ~33 months: BankNifty (NSE_BANKNIFTY1), crude, silver, SILVERM (MCX). 50 x 4 = 200 trials.
- Signal on a closed bar; fill at the next bar's open. Long and short both allowed; a bar with both -> long only.
- Stop = 1.5 x ATR14 from the SIGNAL bar's close; target = 2R (R = stop distance). Both hit in one bar -> stop.
- Time stop 120 min after fill; flat at the open of the 15:20 bar (BankNifty) / 23:25 bar (MCX). Entries from the
  09:15 bar until 14:30 (BankNifty) / 22:30 (MCX). Max 2 trades per day. First 250 bars skipped (indicator warm-up).
- Cost 0.02% per side. Gap fills at the open as TradingView does. Results in POINTS.
- Split by time per instrument: oldest 60% TRAIN, next 20% VALIDATION, newest 20% HOLDOUT (by exit time).

## Pass criteria (all must hold, per instrument+strategy; more than 5 variants => multiple-testing bar)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT, each net of cost.
2. >= 150 trades in total.   3. >= 70% of calendar months positive.   4. No month > 25% of total net.
5. (Parameter robustness: N/A - no parameter is tuned.) Instead: report on how many of the 4 instruments it passes.
Failing any criterion = dropped and recorded; not re-tuned.
**False-pass calibration:** 100 random-direction strategies (seeded; ~1 signal per 100 bars) run through the same
gates on every instrument. If random strategies pass at a rate comparable to the real ones, the real passes are noise.

## The 50 (indicator params in brackets; all EMA/SMA on close unless said)
Trend / moving averages
1 EMA 9/21 cross | 2 EMA 20/50 cross | 3 EMA 5/13 cross | 4 close crosses EMA200 | 5 EMA8 crosses EMA21 while EMA21 vs EMA55 agrees
6 SMA 10/30 cross | 7 MACD(12,26,9) line/signal cross | 8 MACD line crosses zero | 9 Supertrend(10,3) flip | 10 Supertrend(7,2) flip
11 ADX(14)>25 and +DI/-DI cross | 12 Parabolic SAR(0.02,0.2) flip | 13 Ichimoku tenkan(9)/kijun(26) cross | 14 Heikin-Ashi colour change confirmed by 2nd bar
15 Donchian 20 close-break | 16 Donchian 55 close-break | 17 Keltner(20,1.5xATR) close outside | 18 Bollinger(20,2) close outside
19 Bollinger squeeze: bandwidth in lowest 20% of last 100 bars, then close outside band | 20 10-bar high/low break with close beyond EMA50 in that direction
Mean reversion
21 RSI14 crosses back through 30 (long) / 70 (short) | 22 RSI2<10 long above EMA200 / >90 short below EMA200 | 23 close back inside Bollinger(20,2)
24 Stochastic(14,3,3) K/D cross while <20 (long) / >80 (short) | 25 CCI20 crosses back through -100 / +100 | 26 close > 2.5xATR from VWAP, then next close toward it
27 Williams %R(14) crosses back through -80 / -20 | 28 RSI14 crosses 50 in direction of EMA50 slope
Intraday structure
29 ORB 15 min (first 3 bars) close-break | 30 ORB 30 min | 31 ORB 60 min | 32 ORB-30 failed break: closes back inside -> fade
33 close crosses VWAP | 34 pullback: close>VWAP and >EMA20, low touched EMA20 (short mirrored) | 35 previous-day high/low close-break
36 floor-pivot R1/S1 close-break | 37 narrow CPR (width<0.25% of close) and close beyond TC/BC | 38 gap>0.3% and first bar closes with gap (go)
39 gap>0.3% and first bar closes against gap (fade toward fill) | 40 inside bar breakout | 41 narrowest range of last 7 bars, next close breaks it
42 engulfing bar in direction of EMA50 slope | 43 pin bar (wick>=2x body, at 20-bar extreme) in EMA50 direction | 44 three consecutive higher (lower) closes with rising volume
45 volume >2x 20-bar avg and close beyond prior 5-bar high/low | 46 break of 10-bar fractal swing high/low | 47 first 5m bar high/low close-break
48 at the 60-min mark, day move from open > 1xATR: trade in its direction | 49 bar range >2xATR closing in top/bottom 25% | 50 ROC(10) crosses 0 with ADX(14)>20
