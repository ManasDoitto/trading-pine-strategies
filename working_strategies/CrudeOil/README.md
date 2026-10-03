# CrudeOil — top 3 working strategies (MCX:CRUDEOIL1!, 5m)

All walk-forward tested on this repo's tiled non-overlapping-window method,
qty=1 lot, 0.02%/side commission. Full detail in
`../../strategy_audit_2026_09/` (see filenames in each entry below).

## 1. **v5.0 SHA-ADX Hybrid — `4_v5.0_SHA_ADX_hybrid.pine.txt`** (default — highest PF)
SHA-flip entry + EMA9/22/200 alignment + **15m ADX gate ≥30** + SHA stability + EMA9 proximity + daily loss circuit breaker + session-end forced exit.

- **TradingView full-history** (MCX:CRUDEOIL1! 5m, Mar 2024–Sep 2026, 155 trades): PF **1.575**, net +1,347 pts, max-DD 399 pts (17%)
- ADX gate effect: PF 1.166 (gate OFF, 544 trades) → **1.575** (gate ON, 155 trades) — +35% PF, -70% max-DD
- Beats plain v4.0 (PF 1.205, 856 trades, max-DD 2,001 pts)
- Note: L/W ratio ~0.55 — avg loss is 55% of avg win, does not meet <40% constraint
- param sweep winner: ADX=30, PB=1.0, RR=3.0. Daily loss breaker: 300 pts.

## 2. **v5.1 Flip + Donchian Breakout — `5_v5.1_flip_breakout.pine.txt`** (high-frequency)
Adds Donchian channel breakout entry alongside SHA flip. Optimized for more trades (ADX=15, SHA=2, RR=3.0, BO5): 71 trades, PF 1.58, net +2,721 pts.
- L/W ratio still ~0.55 on crude — does not meet the <40% avg-loss constraint. For that constraint, Silver is the right instrument.

## 2. v4.0 SHA flip, R:R 4.0 recal — `1_v4.0_SHA_flip_RR4.0_recal.pine.txt`
SHA-flip entry + EMA9/22 alignment, R:R target raised 3.0→4.0.
PF 1.12, net +2,811 pts, ~26 trades/mo, Mar 2024–Sep 2026 (32.3mo).
De-ranked from #1 to #2 by v5.0. Source of results: `strategy_audit_2026_09/v4.0_recalibration_results.md`.

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
- **Tested 15 Sep 2026: scaling out 50% at 2R, letting the rest ride to
  4R.** Result: hurts #1 — PF 1.12→1.08, net profit roughly halved on the
  same test window, max drawdown got *worse* (71k→108k), not better. This
  strategy's edge lives in rare large trend-following winners (25% win
  rate) — capping them early removes exactly what funds the many small
  losses. Don't scale out of this entry mechanic; if partial profit-taking
  is wanted, it needs a structurally different (higher win-rate) entry.
- **Tested 15 Sep 2026: added a "pullback-reclaim" continuation entry**
  (catch trend legs after the SHA-flip bar has already passed — price dips
  to touch EMA9 then next bar reclaims the dip bar's high). Result: badly
  hurts #1 — PF 1.12→0.80 (combined) / 0.86 (pullback-only), net
  +36,469→−168,641 / −117,335, trades 72→190. The loose "touch EMA9"
  condition fires on almost every minor dip and floods the strategy with
  low-quality trades, crowding out the good flip signals (both variants
  ended up taking the same 190 trades). BankNifty v0.4's own pullback
  mechanic avoids this because it requires a rejection wick + above-average
  volume + VWAP-side + EMA21-hold together, not just a touch — don't
  re-attempt this without that same quality-filter stack.
