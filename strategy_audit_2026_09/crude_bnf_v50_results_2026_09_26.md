# Crude and BankNifty v5.0, 30 months, with and without the ADX gate (run 2026-09-26)

Companion to `silver_v50_results_2026_09_26.md`. Gates/window pre-registered in `pre_registration_v50_2026_09_26.md`.
Code: `crude_bnf_v50_adx_test.py`. **Gross points, no costs**, 2024-03-25 -> 2026-09-24, qty 1, gap fills as
TradingView, split 60/20/20 by exit time. Params are `V50_INSTRUMENT_PARAMS` plus the config.toml ATR floor
(BankNifty `atr_min_pts=50`), i.e. what the code holds, not the README table.

## MCX:CRUDEOIL1!  (ADX>=30, minSL 1.5, maxSL 3.0, RR 3.0, pullback 1.0, daily limit 300)

| | trades | PF | net (pts) | maxDD | win | months +ve | best month | TRAIN / VALID / HOLDOUT | fails |
|---|---|---|---|---|---|---|---|---|---|
| **ADX >= 30 (shipped)** | 155 | **1.575** | +1,347.0 | **399.4** | 39.4% | 58.1% | 37.1% | **1.366 / 1.958 / 1.585** | months, concentration |
| ADX gate OFF | 544 | 1.166 | +1,618.0 | 1,301.2 | 32.5% | 48.4% | 65.3% | 1.021 / 1.566 / 1.104 | PF, months, concentration |
| shipped, net of 0.02%/side | 155 | 1.361 | +933.2 | 440.2 | 38.1% | 54.8% | 49.8% | 1.124 / 1.732 / 1.425 | PF, months, concentration |
| ancestor, plain v4.0 | 856 | 1.205 | +4,480.7 | 2,001.4 | 28.3% | 58.1% | 33.2% | 1.128 / 1.202 / 1.294 | PF, months, concentration |

**The ADX gate is the whole strategy here.** 544 -> 155 trades, PF 1.166 -> 1.575, max drawdown 1,301.2 -> **399.4 (-69%)**,
for 271 points of forgone gross profit. Points per trade 3.0 -> 8.7.

**Crude is the only configuration in this whole audit to clear the PF gate: 1.366 / 1.958 / 1.585, all three splits
above 1.30, on 155 trades.** It still fails two gates - 18 of 31 months positive (58.1%, needs 70%) and best month
37.1% of net (needs <= 25%) - and the PF pass does NOT survive costs (TRAIN falls to 1.124). Months are at least not
one-quarter-driven the way silver's are: worst 2026-07 -164.9 and 2026-05 -158.4, best 2026-04 +499.6 and 2026-06 +291.5.
Exits 85 SL / 38 TP / 32 force-flat.

Note the trade-off against its own ancestor: plain v4.0 makes **3.3x the points** (+4,480.7 vs +1,347.0) with **5x the
drawdown** (2,001.4 vs 399.4). v5.0 is a smaller, much smoother strategy, not a bigger one.

## NSE:BANKNIFTY1!  (ADX>=20, minSL 1.5, maxSL 3.0, RR 4.0, pullback 1.0, ATR floor 50, vol-regime ON, daily limit 500)

| | trades | PF | net (pts) | maxDD | win | months +ve | best month | TRAIN / VALID / HOLDOUT | fails |
|---|---|---|---|---|---|---|---|---|---|
| ADX >= 20 (shipped) | 56 | 1.484 | +1,980.2 | 1,358.1 | 48.2% | 52.2% | 40.3% | 1.568 / **1.015** / 1.688 | PF, trades, months, concentration |
| ADX gate OFF | 73 | 1.441 | +2,238.5 | 1,243.9 | 49.3% | 52.0% | 40.0% | 1.433 / 1.560 / 1.379 | trades, months, concentration |
| shipped, net of 0.02%/side | 56 | 1.165 | +779.6 | 1,583.9 | 48.2% | 47.8% | 94.8% | 1.232 / 0.762 / 1.367 | PF, trades, months, concentration |
| ancestor, plain v4.0 | 378 | 1.081 | +3,667.0 | 4,189.0 | 22.5% | 54.8% | 69.3% | 1.097 / 1.722 / 0.679 | PF, months, concentration |

**The ADX gate does almost nothing on BankNifty and is mildly harmful.** 73 -> 56 trades, PF 1.441 -> 1.484 (+0.04),
net -258 points, and max drawdown gets **worse**, 1,243.9 -> 1,358.1. Note the ADX-off run fails one fewer gate than the
shipped one, because the shipped run's VALIDATION PF drops to 1.015. This mirrors the repo's 2026-09-14 finding that the
v0.4 ADX gate does not port to SHA-flip entries - it filters roughly at random with respect to trade quality.

**Structural problem: the 4R target is unreachable.** Exit reasons for the 56 shipped trades are **35 force-flat, 20 stop,
1 take-profit.** One winner in 56 trades reached the target. With entries allowed 09:30-14:30 and everything closed at
14:30, a 4R bracket on a 1.5-3.0 ATR stop essentially never fills intraday, so this is not a 4R strategy - it is
"hold ~2.4h and take whatever the force-flat gives". The 48.2% win rate comes from force-flat exits that happen to be
green, not from targets. Any BankNifty retune should fix R:R or the flat window before anything else is read into these numbers.

56 trades in 30 months is also below the 100-trade gate, so no BankNifty figure here is statistically meaningful either way.

## Bottom line
- **Crude: keep the ADX gate** (PF 1.166 -> 1.575, drawdown -69%). Best result in the audit; clears the PF gate on gross
  points but not net, and still fails the month gates. Closest thing to a candidate, still not a pass.
- **BankNifty: the ADX gate is not earning its place**, and the 4R target never fills. Fix the exit design first.
- **Silver (previous run): keep the gate**, but the profit is two months and SILVERM's holdout loses.
Nothing passes. Running gate total: 0 of 474.
