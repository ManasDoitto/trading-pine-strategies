# "VWAP-EMA Pullback Intraday Strategy" on BankNifty -- 14 Sep 2026

## What was tested

`v1.0 VWAP-EMA Pullback Intraday Strategy (multi-asset, 3-5min).pine.txt` -- a generic, symbol-agnostic
intraday script: daily VWAP sets bias, EMA9/21 confirms momentum + slope, entries only on a pullback into the
EMA band with a rejection-wick or close-back trigger, ADX>20 and an opening-range breakout filter screen out
chop, stop is swing-based capped at 1.5xATR, fixed 2R target.

Per the user's request, **only BankNifty was tested here** (crude was already found unsuitable by the user
separately). Audit copy adds only 0.02%/side commission (the original script sets none) and the standard AUD
block -- every entry/exit/risk rule is byte-identical to the original file. Same tiled non-overlapping-window
method as every other audit in this project. Default script settings used throughout (EMA 9/21, ADX>20, ORB 15
min, session 0915-1515, R:R 2.0, stop cap 1.5xATR).

## Result: 5m, 6 windows, 2023-09-26 -> 2026-09-13 (35.6 months)

| Trades | Trades/mo | Win% | PF | Net pts | Max DD (largest window) |
|---|---|---|---|---|---|
| **1,586** | **44.5** | **31.1%** | **0.60** | **-38,163** | 9,568 |

By window, oldest to newest: -6,943, -4,387, -4,964, -7,162, -7,595, -7,112 -- **every single window is
negative**, several of them badly.

## This does not match what you found -- flagging the gap rather than picking a side

**With this project's standard test method and the script's own default settings, this is one of the worst
BankNifty results tested in this entire project** -- worse than the rejected v0.5 loosening attempt (PF 0.71),
worse than every SMC variant, worse than every one of the 76 lab variants tested against BankNifty. Trade
frequency is very high (44.5/month, 1,586 trades) -- consistent with "good for BankNifty" if you were reading
trade *count* or a visual backtest -- but profitability is catastrophic on every single window.

One structural note: at a 2:1 reward:risk target, the mathematical breakeven win rate (ignoring costs
entirely) is 33.3%. This strategy's actual win rate here is 31.1% -- *below* breakeven before a single rupee of
cost is applied. That's consistent with the entry filter (EMA-band touch + ADX>20 + ORB breakout) not being
selective enough to hit its own target ratio, not with a testing artifact.

**Possible reasons your result differed** (not verified here, worth checking on your end):
- Different parameter values than the script's defaults (EMA lengths, ADX threshold, R:R, session times)
- A different chart/instrument variant (BANKNIFTY spot vs the BANKNIFTY1! continuous futures contract used
  here, or a different expiry/roll convention)
- A shorter or specific date range, rather than the full available history
- TradingView's built-in Strategy Tester summary on a non-replayed chart, which is a different (and less
  rigorous) method than this project's tiled walk-forward -- it can look better on a single pass over history
  if the account balance/percent-of-equity sizing masks a string of early losses, or if some trades that would
  be excluded by a proper warm-up period are counted

If you can share the exact settings and date range you tested, I can re-run this exact configuration through
the same tiled method to find where the discrepancy comes from.

## Standing conclusion for now

**Don't use this strategy for BankNifty as tested.** v0.4 (PF 1.33, +1,403 pts) remains the best BankNifty
strategy found in this project by a wide margin.
