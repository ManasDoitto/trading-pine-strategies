# Pre-registration: forward test of the deployed SILVERM strategy (written 2026-10-03, BEFORE any forward trade)

What is being tested: the strategy exactly as deployed on 2026-10-03: v4.1 on SILVERM's own 5-minute bars, 3-bar breakout or SHA flip, 10-bar swing stop (+0.1 ATR), stop floor/cap 2.5/5.0 ATR,
RR 3, `min_stop_pct` 0.35, daily brake 350 pts, hours 15-16 excluded. Settings are FROZEN for the test: no parameter may change until a verdict, unless the verdict is REVIEW.
Forward trades = the strategy's own closed trades whose SIGNAL is later than 2026-10-01 10:00 (the last history trade in `exec_data/strategy_health_silverm.csv`), recorded nightly by
`trading_exec/strategy_health.py` in points, net of 0.02%/side. They describe the STRATEGY, not the trader's account.

## Judged at 60 forward trades (about 2.5 months at 26 a month), then again at 100
- KEEP: profit factor >= 1.15 AND maximum drawdown during the forward period <= 75,000 points.
- REVIEW: profit factor < 0.85, OR drawdown above 100,000 points, OR a losing streak above 20 trades, OR more than 365 days below the 2026-02-05 equity peak.
- INCONCLUSIVE: anything between. Keep running, change nothing, judge again at 100 trades.
Thresholds come from the strategy's own 34-month history (rolling-100-trade PF 5th percentile 0.86, 25% of 60-trade windows below PF 1.0, historical max drawdown 68,416 points,
longest losing streak 20): they say what is ordinary and what is outside history. A single bad month, or a PF below 1.0 inside the first 60 trades, is NOT a verdict.

## Why this is the test that matters
Every in-history result is optimistic by construction (many trials on one data set; stop settings sit on a peak; 10 trades are most of the profit). Forward trades are the only evidence that was
not available when the settings were chosen. Option costs are measured separately in the shadow book once the trader asks for it.
