# Pre-registration: v4.0 exit changes on SILVERM (written 2026-09-25, BEFORE the run)

Entries are FROZEN: the deployed SILVERM v4.0 signal (config.toml [strategy.SILVERM]: SHA flip, wide-ATR 2.5-5, RR 3,
350-pt daily limit), on harvested SILVERM 5m bars (~33 months). Only the exit management changes. Points, net of 0.02%/side,
gap fills as TradingView, first 400 bars skipped. Split by exit time: 60% TRAIN / 20% VALIDATION / 20% HOLDOUT.
Baseline (must reproduce first): PF 1.156, +76,428 pts, 788 trades.

## Variants (exactly six; nothing else may be added after seeing results)
V1-V3  time stop N = 90 / 120 / 180 min from the fill (exit at next bar's open) + flat at the open of the 23:25 bar (H1 of the
       earlier pre-registration; no position carried overnight).
V4     flat at the open of the 23:25 bar only (no time stop) - isolates the overnight effect.
V5     breakeven: once a bar's favourable extreme reaches +1R (R = original stop distance), stop moves to the entry price
       (effective from the NEXT bar). Otherwise baseline (overnight allowed).
V6     trail: once favourable extreme reaches +1.5R, stop trails 1.0R behind the running favourable extreme (effective from the
       NEXT bar); target stays at 3R. Otherwise baseline (overnight allowed).

## Pass criteria (six variants > 5 => haircut bar applies)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT, each net of costs.   2. >= 150 trades.   3. >= 70% of months positive.
4. No month > 25% of total net.   5. Also must beat the baseline's HOLDOUT PF and must not have a larger max drawdown than baseline.
Fail any = dropped, no retuning. Anything that passes goes to the shadow book for a month; never straight to real money.
A variant that fails the bar but clearly lowers drawdown while keeping PF >= baseline is REPORTED as a risk-only finding,
not as a pass.
