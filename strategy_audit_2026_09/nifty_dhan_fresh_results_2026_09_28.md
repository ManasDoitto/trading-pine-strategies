# Nifty built fresh on Dhan's real 9.5-year history (2026-09-28)
Data: `DHAN_NIFTY_5m.csv`, 177,972 bars, 3 Apr 2017 - 28 Sep 2026 (harvested via `dhan_harvest_5m.py`, chunked 90-day requests, Dhan's actual data floor). NSE:NIFTY index, pv=1. Volume field is 91% zero/broken on this feed
(same issue found for BankNifty) -- every signal tested here is price-action only (no volume, no VWAP). Lesson applied from the last round: a strategy that looks good on 6 months can be flat-to-negative over the real long run
(the previous Bollinger-squeeze pick was PF 0.975 over the full 9.5yr history) -- this round requires positive performance in a clear majority of individual CALENDAR YEARS, not just a train/holdout split, before trusting anything.
Code `nifty_dhan_fresh.py`, data `research_data/nifty_dhan_fresh.csv`. Screened 37 signal families (the same 24+15 built earlier, minus 3 volume-dependent ones) at a baseline exit (1.5R, 30-min time-stop) first.

## The finding: Tenkan/Kijun cross + EMA200 trend filter, positive in ALL 10 calendar years
**Entry: Ichimoku Tenkan(9) crosses Kijun(26), filtered to only trade with the EMA200 trend. Exit: 2.0R target, ~1.0xATR stop, 45-minute time-stop, forced flat 15:20-15:30.**

| | trades/mo | PF | net pts (9.5yr) | DD | TRAIN (to 2024) PF | HOLDOUT (2024+) PF | years positive |
|---|---|---|---|---|---|---|---|
| Base (Tenkan/Kijun alone, no filter) | 61.8 | 1.053 | +3,778 | 1,576 | 1.053 | 1.054 | 7/10 |
| **+ EMA200 filter** | 34.3 | **1.151** | **+6,975** | 1,784 | 1.166 | 1.126 | **10/10** |

- **Every single calendar year from 2017 to 2026 was individually profitable** -- the first time anything in this whole project has cleared that bar. TRAIN and HOLDOUT PF are close (1.166 / 1.126), so the edge hasn't decayed into the most recent data either.
- **Checked as a real plateau, not a lucky point**: RR 1.25-2.0 all give PF 1.13-1.17 (RR 1.25 and RR 2.0 both hit 10/10 positive years); time-stop 45-90 minutes all give PF 1.09-1.15, gently declining past 45; adding a mild ADX filter (10-12) barely changes anything (still 10/10 years) -- the result is not sitting on a knife-edge.
- **Fully volume-free**: Tenkan/Kijun uses only rolling high/low, EMA200 uses only close. Unlike the earlier Bollinger-squeeze finding, this result cannot be an artifact of Dhan's broken volume field.

## Lower-frequency variant, if the combined BankNifty+Nifty trade budget needs it
Restricting entries to the morning session only (09:15-12:00, the same trick that helped an earlier Nifty candidate):

| | trades/mo | PF | net pts | DD | years positive |
|---|---|---|---|---|---|
| Morning-only (09:15-12:00) | 15.2 | 1.141 | +3,186 | **906** (-49%) | 7/10 |

Trades less than half as often, drawdown falls by half, PF stays essentially the same -- but 3 of 10 years turn negative instead of 0. A real, honest trade-off: the full-session version's "positive every year" record is its strongest selling point, and restricting to mornings gives some of that up for a much smaller footprint.

## Why everything else failed
Every mean-reversion family (RSI/Bollinger/Stochastic/CCI/Keltner fade) was negative across the whole 9.5 years, same pattern as BankNifty and as Nifty's earlier short-window test -- confirms these don't have a real edge on Indian index intraday data, it isn't a data-window artifact. Most breakout/momentum families (Donchian, momentum-burst, NR7, PSAR, inside-bar, ATR-channel, plain Heikin-Ashi) were flat-to-negative or too high-frequency to be useful even when marginally positive. Two other candidates looked good on net points alone -- opening-range breakout continuation (+13,991 net) and prior-day-H/L breakout (+6,347 net) -- but both need 120-150 trades/month even after filtering, far outside any reasonable budget, so they were not pursued further.

## Recommendation
**Tenkan/Kijun cross + EMA200, RR 2.0, 45-min time-stop** is the strongest, best-validated Nifty candidate this project has produced -- a genuine multi-year, multi-regime edge, not a recent-window artifact. Not yet TradingView-confirmed
or forward-tested. Given the frequency (34.3/mo full-session or 15.2/mo morning-only), this needs to be weighed against whatever BankNifty configuration you keep running to land in your preferred combined trade budget.
