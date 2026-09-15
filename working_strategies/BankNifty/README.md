# BankNifty — top 3 working strategies (NSE:BANKNIFTY1!)

## 1. v0.4 EMA pullback + 15m ADX gate — `1_v0.4_EMA_pullback_15mADX_gate.pine.txt` (5m)
**Current best / "the holy grail" of this repo.** Rejection-wick + above-avg
volume + VWAP-side + EMA21-hold pullback reclaim, gated by prior-completed
15m ADX(14) ≥ 25. PF **1.29**, net +1,277 pts, 2.5 trades/mo, max DD 1,668 pts
(10%), positive in 3/5 windows, Mar 2024–Sep 2026 (30mo). Also the only
strategy in the whole repo that passed a strict train/holdout split cleanly
with zero new tuning (train +557 / holdout +846).
Source: `../../BEST STRATEGY PER SCRIPT (BankNifty, Nifty 50, CrudeOil - 3m-5m).md`.

## 2. v1.1 MTF pullback — `2_v1.1_MTF_pullback_3min.pine.txt` (3m)
Same pullback family, adds a daily-ADX≥20 gate alongside the 15m≥25 gate,
on 3-minute bars. Highest Sharpe of any BankNifty variant tested (1.21) and
PF 1.64, but on a much smaller/shorter sample (18mo only, 3/5 windows + 1
flat) — treat as a higher-conviction-per-trade, lower-confidence-of-edge
alternative to #1, not a straight upgrade.

## 3. v0.4 + v13 combined portfolio — `3_v0.4_plus_v13_combined_portfolio.pine.txt` (5m)
v0.4 (above) run alongside v13 (range-only sweep-fade, meant to be
uncorrelated) in one script, independent entry/exit IDs. Real result:
355 trades, PF 1.04, net +964 pts — **not** the naive sum of the two solo
backtests (+2,317) because TradingView keeps one net position per script,
so opposite-direction signals compete. Kept as the documented "more trade
frequency, modest cost to quality" option, not because it beats #1 outright.

## Caveats
- Don't loosen v0.4's filters for more frequency — tested (v0.5) and it
  collapsed PF to 0.68–0.71. Pair with an uncorrelated strategy instead.
- v0.4 needs volume; NIFTY spot borrows NSE:NIFTY1! futures volume and has
  no robust standalone Nifty-spot version.
- **Tested 15 Sep 2026: skip-Monday + skip-Friday, motivated by the user's
  own real (manual options) trading showing Monday/Friday as weak days.**
  Result: hurts v0.4 — Sharpe 1.52→0.98, net profit roughly halved on the
  same test window, PF unchanged (~1.8). The manual-trading day-of-week
  pattern does not transfer to this systematic futures signal; don't
  re-apply it here without new evidence.
- **Not tested — already covered, 15 Sep 2026:** the "pullback-reclaim
  continuation entry" idea (re-enter after the initial flip/trend-start has
  passed) was tested on Crude/Silver's SHA-flip family and failed badly
  there. v0.4 doesn't need this add-on because its core mechanic *already
  is* a pullback-reclaim design — it tracks pullbacks continuously while
  in an established regime (not just at the flip moment) and gates them
  with a wick + volume + VWAP + EMA21-hold quality filter, which is
  exactly what kept the same idea from being noise on Crude/Silver.
