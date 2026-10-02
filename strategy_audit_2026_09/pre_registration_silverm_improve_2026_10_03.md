# Pre-registration: improving the CURRENT SILVERM strategy on profit factor and net P&L (written 2026-10-03, BEFORE any test)

Baseline = [strategy.SILVERM] as live (v4.1 on SILVERM1's own bars). Primary data SILVERM1; confirmation SILVER1 with identical rules.
Points, net of 0.02%/side. DEVELOPMENT = trades exiting before the cut date, HOLDOUT = after it (cut = baseline's 80th-percentile exit date per contract),
the holdout is not printed or used for selection until the single final look.

## Where the idea list comes from (descriptive full-history detail of the current strategy, silverm_current_detail.py)
SHA-flip entries: 92 trades, -32,234 pts, PF 0.66; breakout entries: 769 trades, +273,350 pts, PF 1.50. Low-vol third of trades earns ~0; high-vol third earns 89%.
Signal hour 13 loses (PF 0.63). Stops of 3-4 ATR are non-monotonic (not tested: no mechanism). Weekday splits have no mechanism (not tested).

## Candidates (exactly six; nothing else may be added)
C1  breakout-only: drop the SHA-flip entry (keep the 3-bar Donchian breakout, trend filter, stops, exits unchanged)
C2  hour rule: exclude every signal hour whose DEVELOPMENT net is negative on BOTH contracts with >= 25 development trades on each (hours chosen by this rule on development data only)
C3  breakeven: once a bar's favourable extreme reaches +1.0R, the stop moves to entry (from the next bar)
C4  volatility floor: skip entries when ATR is below its 33rd percentile of the previous 2,000 bars (causal)
C5  stop-out cooldown: after a stop-out, no new entry for 60 minutes
C6  combination of the candidates ACCEPTED below, in the order C1, C2, C3, C4, C5 (tested once)

## Acceptance on DEVELOPMENT (both contracts must satisfy ALL; single candidates C1-C5)
1. profit factor (points) >= baseline + 0.05     2. net points >= baseline     3. max drawdown (R) <= baseline x 1.05
4. months positive >= baseline - 3 points        5. >= 400 development trades
Final HOLDOUT (one look, SILVERM1 and SILVER1, baseline vs C6, or vs the single accepted candidate): passes if on SILVERM1 the candidate has PF (points) >= baseline,
net points >= baseline, expectancy (R) >= baseline and max drawdown (R) <= baseline x 1.10, and on SILVER1 expectancy (R) > 0.
Six trials on one dataset: a pass is a shadow-book / config candidate, reported with that caveat. Nothing changes live without the user's explicit OK.
