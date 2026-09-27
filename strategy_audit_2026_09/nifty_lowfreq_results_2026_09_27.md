# Tightening Nifty to a lower trade rate, maximizing PF (2026-09-27), 36 configs
Pre-registration: `pre_registration_nifty_lowfreq_2026_09_27.md`. Code `nifty_lowfreq_tune.py`, data `research_data/nifty_lowfreq_tune.csv`. NSE:NIFTY spot 5m, 6.3mo, gross points.
Goal: BankNifty's live forward test already trades ~28.9/month on its own; targeting Nifty at roughly 15-35/month keeps the combined total near the requested ~60/month across both scripts, while maximizing PF within that band.

## Result: found a real, well-supported tightening -- higher PF AND lower frequency AND lower drawdown, all at once
**EMA9/22 cross, 10-minute time-based exit, restricted to the morning session only (09:15-12:00):**

| | trades/mo | PF | net pts (6.3mo) | DD | 1st-half PF | 2nd-half PF |
|---|---|---|---|---|---|---|
| Previous Nifty pick (EMA cross, 10-min exit, full session) | 53.3 | 1.389 | +947 | 306 | 1.560 | 1.211 |
| **Morning-only (09:15-12:00)** | **23.7** | **1.517** | +550 | **203** | 1.565 | **1.464** |

- PF up (1.389 -> 1.517), drawdown down by a third (306 -> 203), and trade count cut by more than half (53.3 -> 23.7/month) -- this is not a frequency-for-quality trade-off, it is a genuine improvement on every axis except total points (lower, because there are fewer trades -- expected and accepted given the frequency ask).
- **Both halves of the data improve, and the improvement is concentrated where it matters**: the second half's PF rises from 1.211 to 1.464 (the weaker half got meaningfully better), while the first half stays about the same (1.560 -> 1.565). This is exactly the kind of change that inspires confidence -- cutting the afternoon session removed weak trades broadly, not just in one lucky stretch.
- Mechanism: Nifty's morning session (open to noon) carries this scalp's edge; the afternoon session dilutes it. This matches the general pattern that opening-hour momentum tends to be cleaner than midday/afternoon chop.

## Other configs tried in the 15-35 trades/month band (none as good)
| id | trades/mo | PF | net | DD |
|---|---|---|---|---|
| EMA cross ts=10 + ADX15>=15 + volume filter | 30.0 | 1.362 | +558 | 283 |
| EMA cross ts=10 + volume filter alone | 32.0 | 1.301 | +499 | 278 |
| EMA cross ts=10, afternoon only (12:30-15:15) | 25.9 | 1.210 | +272 | 223 |
| Donchian(30) breakout, morning only | 34.2 | 1.207 | +598 | 601 |
EMA200 trend filters and ADX+EMA200 combinations mostly failed (PF 1.0-1.06, one went net-negative in the second half) -- the morning-only time restriction is doing more work than any indicator-based filter tried.

## What was NOT chosen, for reference
Two configs outside the 15-35/month band had even stronger numbers and are worth knowing about if the frequency target ever loosens:
- **Donchian(30) breakout + volume filter: PF 1.441, +2,042 net (highest of everything tried), but 54.6 trades/month** -- alone it would blow the combined budget.
- **EMA cross ts=10, skip Monday: PF 1.630, +1,074 net, 42.1 trades/month** -- strongest PF found, but frequency is above the target band; combined with BankNifty's 28.9 this would put the total around 71/month.

## Combined picture (BankNifty forward test, unchanged + this Nifty pick)
| script | trades/mo | PF | basis |
|---|---|---|---|
| BankNifty: Supertrend(20,3)+volume scalp | 28.9 | 1.284 (TradingView-confirmed) | live forward test |
| Nifty: EMA9/22 cross, 10-min exit, morning-only | 23.7 | 1.517 (harness only) | not yet TV-confirmed or forward-tested |
| **Combined** | **52.6** | -- | -- |
Comfortably within the ~60/month target with room to spare.

## What's still open
Not TradingView-replay-confirmed (only BankNifty's candidate has been independently confirmed so far), no forward test running for this Nifty pick, and the usual thin-data caveat (6.3 months, no second window to cross-check) still applies. Recommended next step: TradingView tiled replay for this Nifty candidate specifically (Nifty's whole usable history is one window, so this would be a single-pass confirmation, not a multi-window one), then a pre-registered forward test alongside BankNifty's.
