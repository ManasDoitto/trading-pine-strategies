# Pre-registration: Hull Suite concept on CRUDEOIL 5m (written 2026-09-26, BEFORE the Hull run)

Motivation: a public "Hull Suite Strategy" (InSilico) was found deployed on the user's MCX:CRUDEOIL1! **Daily**
chart. It has taken **zero trades** there (Strategy Tester: "This report requires trade data"; capital 100K INR vs
~8.85L notional per lot), so there is no verified larger-timeframe result to port. Hull/HMA has never been tested
in this repo. This pre-registers a proper 5m test of the *concept*, not of that script.

## Frozen harness (identical to every other audit in this folder)
`research_sim.simulate` on `research_data/bars/MCX_CRUDEOIL1_5m.csv` — 119,099 bars, 2024-01-08 -> 2026-09-24
(33 months). Points, net of 0.02%/side, gap fills as TradingView, first 400 bars skipped, qty 1.
Non-entry params FROZEN at the deployed crude v4.0: sha_len1/2=10, sw_len=10, sw_buf=0.1, min_sl=1.5,
max_sl=3.0, **rr=4.0**, session 09:15-23:30. Only the entry condition changes.
Split by exit time: 60% TRAIN / 20% VALIDATION / 20% HOLDOUT (boundaries 2025-09-12 and 2026-03-11).

## Baseline (reproduced BEFORE writing any Hull code)
Full: PF **1.145**, net **+3,504.9 pts**, 853 trades, max DD 2,280.0, win 23.9%, best month = 65.0% of net.
TRAIN PF 1.061 (+622.9) | VALIDATION PF 0.955 (-186.5) | HOLDOUT PF 1.312 (+3,068.5).
Note the baseline itself FAILS criteria 1, 3 and 4 below — it is the incumbent, not a passing strategy.

## Hull definition (fixed now)
`WMA(2*WMA(n/2) - WMA(n), sqrt(n))` = Hma. Ehma substitutes EMA for WMA throughout. Direction is InSilico's own
rule: `hull > hull[2]` = up, else down. A "flip" is a change in that direction.

## Variants (exactly eight; nothing may be added after seeing results)
Track A - Hull as BIAS FILTER, replacing the `e9 > e22` alignment. SHA flip stays the trigger.
  A1  Hma(55) on 5m close.      A2  Ehma(55) on 5m close.
  A3  Hma(55) on 1H bars (resampled from the same 5m data, no lookahead).
  A4  Hma(55) AND e9/e22 both required (strictest; filter added, not swapped).
Track B - Hull as TRIGGER, replacing the SHA flip. `e9 > e22` alignment stays.
  B1  Hma(55) flip.   B2  Ehma(55) flip.   B3  Hma(89) flip.
  B4  Hma(55) flip + 2-bar confirmation (direction must hold 2 bars; entry on the 2nd).

## Pass criteria (eight variants > 5 => multiple-testing haircut applies, so criterion 1 is PF >= 1.30)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT, each net of costs.
2. >= 150 trades.   3. >= 70% of months positive.   4. No month > 25% of total net.
5. Must beat the baseline's HOLDOUT PF (1.312) and not have a larger max drawdown than baseline (2,280.0).
Fail any = dropped, no retuning. Anything passing goes to the shadow book for a month, never straight to money.
A variant that fails the bar but clearly lowers drawdown while keeping PF >= baseline is REPORTED as a
risk-only finding, not as a pass.

## Prior
0 of 200 standard strategies passed these gates (2026-09-25); no crude strategy in this repo clears PF 1.3
without overfitting. Hull is a 1970s-lineage moving average. Expect failure; run it to know, not to hope.
