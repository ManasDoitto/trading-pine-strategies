# CrudeOil — top 3 working strategies (MCX:CRUDEOIL1!, 5m)

All walk-forward tested on this repo's tiled non-overlapping-window method,
qty=1 lot, 0.02%/side commission. Full detail in
`../../strategy_audit_2026_09/` (see filenames in each entry below).

## 1. v4.0 SHA flip, R:R 4.0 recal — `1_v4.0_SHA_flip_RR4.0_recal.pine.txt`
**Current best.** SHA-flip entry + EMA9/22 alignment, R:R target raised 3.0→4.0.
PF 1.12, net +2,811 pts, ~26 trades/mo, Mar 2024–Sep 2026 (32.3mo).
Source of results: `strategy_audit_2026_09/v4.0_recalibration_results.md`.

## 2. v4.0 + initiative filter (train/holdout-robust) — `2_v4.0_initiative_filter_train_holdout_robust.pine.txt`
Same SHA-flip core + "outside prior-day value area" filter. Lower PF (1.07)
than #1 but the only crude variant that stays profitable in **both** the
train (Mar24–Jan26) and holdout (Jan–Sep26) halves — #1 above actually loses
money in the train half and is positive only because of 2026 volatility.
Pick this one if out-of-sample robustness matters more than raw PF.
Source: `strategy_audit_2026_09/v4.0_initiative_filter_train_holdout.md`.

## 3. v3.0 SHA + RSI3 pullback (tuned to marked trades) — `3_v3.0_SHA_RSI3_pullback_marked_trades.pine.txt`
Different entry mechanic (RSI3 pullback vs SHA-flip), reverse-engineered
from the user's own 36 manually marked CrudeOil entries. Kept as a
structurally distinct alternative, not a tuned variant of #1/#2.

## Caveats (apply to all three)
- No crude strategy in this repo clears PF ≥ 1.3 without overfitting a fixed
  dataset — this was tested and explicitly declined. See
  `[[crude-v4-forward-test]]` / `protected-crude-script.md` memory.
- None of these are options-tested — TradingView backtests are futures/points-based.
