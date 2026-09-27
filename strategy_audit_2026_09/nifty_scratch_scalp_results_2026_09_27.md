# Nifty 50 from scratch: 24 native intraday scalp/mean-reversion strategies (2026-09-27)
Same 24 configs and method as `bnf_scratch_scalp.py` (mean-reversion + quick-scalp continuation families), run on NSE:NIFTY spot. Data: `NSE_NIFTY_5m.csv` (6.3mo, 9 Mar-25 Sep 2026) and `NSE_NIFTY_3m.csv` (3.7mo, 1 Jun-25 Sep 2026) --
the same TradingView data floor already documented for Nifty (spot and futures identical, no 3-year option exists). pv=1. Session/flat/no-day-limit convention identical to the BankNifty version. Code `nifty_scratch_scalp.py`, data `research_data/nifty_scratch_scalp.csv`.

## Headline: weaker and less consistent than BankNifty's from-scratch search, but two genuine, checked candidates survive
Best 5m results, all mean-reversion families (RSI/Bollinger/VWAP/Stochastic/CCI fade) failed outright on Nifty, same pattern as BankNifty. The quick-scalp continuation family is again where the edge is, but PFs are
lower here (1.12-1.25 vs BankNifty's 1.19) and the 3-minute ranking looks quite different from 5-minute (a red flag on this thin dataset -- flagged explicitly, not hidden).

| candidate | trades/mo | PF | net pts | DD | win% | split-half consistency |
|---|---|---|---|---|---|---|
| **H3: EMA9/22 cross, fixed 10-min exit (no real stop/target)** | 53.7 | **1.389** | +947 | 306 | 52.4% | H1 PF 1.560 / H2 PF 1.211 -- both solidly positive |
| Q4: Donchian(20) breakout, 1.5R, 30-min time-stop | 91.7 | 1.187 | +1,433 (highest net) | 483 | 50.9% | H1 PF 1.200 / H2 PF 1.170 -- very consistent |
| Q1: EMA9/22 cross, 1.0R, 30-min time-stop | 48.1 | 1.246 | +1,044 | 386 | 51.8% | H1 PF 1.084 / H2 PF 1.504 -- leans on 2nd half |
| Q2: EMA9/22 cross, 1.5R, 45-min time-stop | 45.1 | 1.221 | +1,077 | 583 | 51.0% | H1 PF 0.966 / H2 PF 1.667 -- 2nd-half only, don't trust |

## What held up under a follow-up check
**H3 (EMA cross + pure time exit) is a genuine gradient, not a knife-edge**: shorter time-stops do better in an orderly way (10min PF 1.389, 15min 1.253, 20min 1.173, 25min 1.156) -- a real relationship, not noise. Almost all
exits (324 of 338) are the time-stop itself, not a stop-loss (only 5) -- this is really "enter on an EMA9/22 cross, hold exactly 10 minutes, exit," with the nominal 2xATR stop essentially never engaging. Both halves of the
6.3-month window are solidly profitable (PF 1.560 / 1.211) on the 10-minute version.
**Q4 (Donchian20 breakout) is also a real plateau**: RR 1.25/1.5/2.0 all land PF 1.18-1.22, stop-width doesn't bind (same pattern as everywhere else this project), and both halves are close (1.200 / 1.170) -- the most
internally consistent config found for Nifty, at the cost of a very high trade rate (91.7/month, well above what "quick trades are fine" was likely meant to cover).

## Honest caveats
- **6.3 months is genuinely thin** -- the same limitation flagged for every Nifty test so far, and it cannot be extended on this data feed.
- **3-minute results rank differently from 5-minute** (e.g. Q1 and H3 are only ~breakeven at 3m: PF 1.007 and 0.996) -- some disagreement between timeframes on the same underlying trend, worth taking as a sign that Nifty's edge here is less robust than BankNifty's (where the Supertrend result held up cleanly across a genuine multi-year, 6-window TradingView replay).
- Neither candidate is TradingView-replay-confirmed or forward-tested. Given the short history, a forward test is really the only way to get real confidence here, the same conclusion reached for the earlier ported-strategy Nifty leads.

## Recommendation
If you want to pursue Nifty, **H3 (EMA9/22 cross + 10-minute time-based exit)** is the best-supported candidate: highest PF, lowest drawdown, a real gradient rather than a lucky point, and both halves of the data profitable.
It is also the simplest possible mechanism found this project -- no stop-loss logic to speak of, just a fixed hold time -- which is easy to reason about and easy to forward-test cleanly. Q4 is the alternative if a higher trade
count and higher total points matter more than simplicity. Neither is proven; both need a forward test before being trusted the way BankNifty's Supertrend candidate now is.
