# Pre-registration: v5.0 SHA-ADX Hybrid on CrudeOil / BankNifty / Silver, 30 months (written 2026-09-26, BEFORE the run)

Claim under test (working_strategies/*/README.md, `4_v5.0_SHA_ADX_hybrid.pine.txt`): walk-forward avg PF
Crude 4.54, BankNifty 2.85, Silver 2.12; full-history PF Crude 3.82 (+4,677 pts), BankNifty 1.494 (+1,807), Silver 2.04 (+3,518).

## What is actually tested, and why (three sources disagree; decided now, not after seeing results)
The Pine files are NOT testable as written: all four (`atr >= riskL`) require ATR >= riskL, but riskL is floored at
minSL*ATR (1.5x; 2.5x Silver), so the condition is unsatisfiable and the scripts should take zero trades (checked by
count in the run). The Pine `shaStable` is also always true on a flip bar (valuewhen returns the current bar), so
that filter is a no-op there, and the Silver Pine day-limit compares points to limit*pointvalue. The numbers in the
README came from `trading_agents/core/signals_v50.py`, so THAT logic is what is tested, unchanged, with the README /
Pine parameter values (the Python dict V50_INSTRUMENT_PARAMS disagrees with the README on BankNifty and Silver; README wins):

| | Crude MCX_CRUDEOIL1 | BankNifty NSE_BANKNIFTY1 | Silver MCX_SILVER1 |
|---|---|---|---|
| session / force-flat (IST) | 09:15-23:30 / 22:45 | 09:30-15:00 / 14:45 | 09:15-23:30 / 22:45 |
| 15m ADX >= | 30 | 25 | 30 |
| pullback (x ATR from EMA9) | 1.0 | 0.5 | 0.5 |
| minSL / maxSL (x ATR), swing 10, buf 0.1 | 1.5 / 3.0 | 1.5 / 3.0 | 2.5 / 5.0 |
| RR | 3.0 | 3.5 | 4.0 |
| vol regime (ATR > SMA80) | off | ON | off |
| daily loss limit (pts) | off | off | 300 (README text says 350; image and Pine say 300) |
Common: SHA 10/10, EMA9/22 alignment, SHA stability >= 3 bars (Python definition), signal on close, fill next open.

## Harness (frozen, same as every audit here)
`research_sim.simulate`: points, 0.02%/side commission, gap fills as TradingView, qty 1. Bars `research_data/bars/*_5m.csv`
(TradingView). WINDOW = 2024-03-25 -> 2026-09-24 = 30 months (the TradingView 5m replay floor); indicators warm up on the
earlier bars, no trade is counted before 2024-03-25. Split by exit time 60/20/20 by trade count (TRAIN/VALID/HOLDOUT).

## Runs (6 pass/fail + 1 informational)
PRIMARY (the pass/fail verdict): each strategy exactly as generated the claim (EMA200 filter ON, as the Python always applies it).
SENSITIVITY: same with the EMA200 filter OFF (the Pine's default). 6 trials > 5 => the PF >= 1.30 haircut bar applies.
INFORMATIONAL only: Silver on MCX_SILVERM1 (config.toml trades SILVERM, not SILVER).
BASELINE per strategy = its own ancestor, plain v4.0 SHA flip on the same bars/window/costs with the SAME stops, RR and
session (v5.0 minus ADX, vol regime, stability, pullback, EMA200, force-flat, day limit): isolates what the added layers buy.

## Pass criteria (primary runs)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT, net of costs.  2. >= 100 trades in the window (lowered from the usual 150 because
these are ADX-gated low-frequency strategies; stated before the run).  3. >= 70% of months positive.  4. No month > 25% of total net.
5. Beat the baseline's HOLDOUT PF and not exceed its max drawdown.
Fail any = not a pass, no retuning. A pass goes to the shadow book for a month, never straight to money.

## Reproduction layer (diagnostic, not a pass/fail)
Original engine (`signals_v50.simulate`, gross, no commission) with the same params on the ORIGINAL Dhan cache
`journal_data/cache/backtest/*_5min.csv`, to see whether the claimed full-history PF / net reproduce at all, plus the README's walk-forward
statistic (mean of per-window PF over overlapping 90-day windows stepped 30 days) next to the pooled PF, to show how a 4.54 "average PF" arises.

## Prior
0 of 460 tested strategies have passed these gates. PF 4.54 with 75% of windows profitable and only +764 pts net is the signature of a
mean of small-window PFs on a parameter set chosen on the same history; net-of-cost PF will be well below it. Run to know, not to hope.
