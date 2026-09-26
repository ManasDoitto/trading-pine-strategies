# Silver v5.0 SHA-ADX Hybrid, 30 months, with and without the ADX gate (run 2026-09-26)

Gates and window pre-registered in `pre_registration_v50_2026_09_26.md`. Code: `silver_v50_adx_test.py`.
**Gross points, no costs** (user's standing instruction). Window 2024-03-25 -> 2026-09-24 (30 months),
qty 1, gap fills as TradingView, split 60/20/20 by exit time.

Parameters are `V50_INSTRUMENT_PARAMS["SILVER"]` as the code actually holds them, NOT the README table:
minSL **1.5** (README says 2.5), maxSL 5.0, R:R 4.0, ADX >= 30, pullback 0.5 ATR, daily limit **350**
(README says 300), vol-regime off, ATR floor 0. My earlier 30-month run used the README values, so its
silver numbers (PF 1.423 net / 1.605 gross) are superseded by this one.

## Result: fails the gates either way. The ADX gate trades quality for quantity.

| MCX:SILVER1 | trades | PF | net (pts) | maxDD | win | months +ve | best month | TRAIN / VALID / HOLDOUT |
|---|---|---|---|---|---|---|---|---|
| **ADX >= 30 (as shipped)** | 112 | **1.968** | **+39,577.2** | **6,958.6** | 32.1% | 44.8% | 41.5% | 1.064 / 3.133 / 1.464 |
| ADX gate OFF | 329 | 1.438 | +46,331.5 | 14,845.5 | 34.3% | 54.8% | 42.1% | 1.478 / 1.993 / **0.862** |
| ancestor, plain v4.0 | 902 | 1.079 | +54,853.3 | 127,929.5 | 22.6% | 51.6% | 87.9% | 1.073 / 1.139 / 0.988 |

| MCX:SILVERM1 (the contract config.toml trades) | trades | PF | net (pts) | maxDD | win | months +ve | best month | TRAIN / VALID / HOLDOUT |
|---|---|---|---|---|---|---|---|---|
| ADX >= 30 (as shipped) | 127 | 1.329 | +16,659.4 | 11,829.9 | 26.8% | 36.7% | 71.1% | 1.516 / 1.446 / **0.925** |
| ADX gate OFF | 372 | 1.256 | +32,496.4 | 25,873.3 | 31.7% | 58.1% | 40.4% | 1.190 / 1.619 / **0.861** |

Failed gates in all four runs: PF >= 1.30 in all three splits, >= 70% months positive, no month > 25% of net.
The >= 100 trades gate passes everywhere.

## What the ADX gate actually does (SILVER1)
It is a real filter, not decoration: 329 -> 112 trades, PF 1.438 -> **1.968**, max drawdown 14,845.5 -> **6,958.6 (-53%)**.
It gives up 6,754 points of net (+46,331 -> +39,577) to remove two thirds of the trades and less than half the drawdown.
On points-per-trade it is a large improvement: 141 -> 353 pts/trade. If the choice is only between these two, keep the gate.

But the gate does not fix the strategy's actual problem, and on one axis it makes it worse:
- **The profit is one quarter.** Best month 2026-01 +16,419.3 and 2026-02 +12,814.7 = 29,234 of the 39,577 total (74%).
  Only 13 of 29 months are positive. Worst months 2026-03 -3,504.3 and 2026-08 -3,038.7.
- **TRAIN is barely above water (PF 1.064)** while VALIDATION is 3.133. The edge is not present in the first 60% of trades;
  it appears in one stretch. Turning the gate off inverts which slice looks good (TRAIN 1.478, HOLDOUT 0.862) - a sign that
  neither configuration has a stable edge, just different exposure to the same few volatile months.
- Net of 0.02%/side the shipped config is PF 1.721 / +32,739.2, and TRAIN drops to **0.870** - a loser in the train slice.

## SILVERM is the number that matters and it is much worse
`config.toml` trades SILVERM, not SILVER. Same signal, same params, on SILVERM's own bars: PF 1.329 (not 1.968), net
+16,659.4 (not +39,577), max DD 11,829.9 (not 6,959), one month = 71.1% of net, and **HOLDOUT PF 0.925 - the most recent
20% of trades loses**. Do not read the SILVER1 number as what this would have done on the contract you trade.

## Versus the claim
README claims walk-forward avg PF 2.12, full-history PF 2.04, net +3,518 pts. The gross PF here (1.968 on SILVER1) is
close to 2.04, but the net points are an order of magnitude apart (+39,577 vs +3,518), so these are not the same
measurement, and the walk-forward 2.12 is still a mean of overlapping-window PFs from parameters chosen on this history.

## Bottom line
Keep the ADX gate - it roughly halves drawdown and lifts PF from 1.438 to 1.968 on SILVER1. But neither configuration
passes, the profit is concentrated in Jan-Feb 2026, TRAIN is near breakeven, and on SILVERM the recent slice loses.
Not deployable. Running gate total: 0 of 470.
