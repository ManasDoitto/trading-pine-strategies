# Porting crude + silver's top 15 strategies each onto BankNifty (2026-09-27)
Data: `NSE_BANKNIFTY1_5m.csv` (35.5mo usable, Sep 2023-Sep 2026, robust) and `NSE_BANKNIFTY1_3m.csv` (3.7mo usable, Jun-Sep 2026 -- TradingView's own data floor for 3m
intraday on this feed, confirmed by paging until "no older data", not a stall; **same floor on the spot index**, so this is a real platform limit, not a spot-vs-futures issue).
NSE:BANKNIFTY1! futures, pv=30/pt, 1 lot. Session capped to real market hours 09:15-15:20, flat 15:20-15:30. `day_loss_limit` deliberately OFF on every port: it is a nominal-point
breaker calibrated to each commodity's own price scale (silver's 350-pt limit has no meaning on BankNifty's index-point scale) and needs its own calibration, not a blind port.
Code: `bnf_port_test.py`, data: `research_data/bnf_port_test.csv`. Current BankNifty best for comparison: **v0.4 EMA pullback + 15m ADX gate: PF 1.33, +1,403 pts, 2.5 trades/month, DD 1,620.**

## Result: none of the 30 ports beats v0.4. On 3m, every single one loses money.

### 5m (35.5 months, robust): best 8 of 30 by PF
| strategy | trades/mo | PF | net pts | worst DD | best-month share |
|---|---|---|---|---|---|
| **BankNifty v0.4 (native, for comparison)** | **2.5** | **1.33** | **+1,403** | **1,620** | -- |
| C8: crude maxSL 2.75xATR | 22.4 | 1.154 | +7,571 | 3,701 | 25% |
| C11: crude + ATR<p90 filter | 22.5 | 1.130 | +6,334 | 3,140 | 39% |
| C13: crude swing lookback 15 | 21.4 | 1.124 | +6,014 | 4,166 | 34% |
| C6: crude RR 4.5 | 23.7 | 1.096 | +5,312 | 3,234 | 48% |
| C5: crude RR 3.5 | 24.0 | 1.096 | +5,325 | 3,249 | 45% |
| C15: crude long-only | 18.6 | 1.110 | +4,330 | 2,298 | 70% |
| C7: crude minSL 2.0xATR | 23.0 | 1.064 | +3,536 | 3,732 | 44% |
| S9: silver vanilla (narrow ATR) | 24.2 | 1.089 | +4,978 | 2,844 | 48% |
Every crude/silver port that beats breakeven does it at **8-18x v0.4's trade frequency** and **1.4-2.6x v0.4's drawdown**, for a PF still well below v0.4's 1.33. C2 (crude v4.2, the strongest crude result on its native instrument) manages only PF 1.056 here, worse than plain crude #1's own port (1.086) -- the reversal-exit mechanism doesn't help on BankNifty either.
**6 of 30 ports are net-negative even on the robust 5m data**: S1 (silver#1 wide-ATR), S4 (bo10), S6 (v5.1), S8 (wide-ATR RR4), S12 (short-only). The whole silver breakout family (S2-S4, S7, S10, S11, S14) clusters at PF 0.98-1.02 -- essentially breakeven before costs.

### 3m (3.7 months, thin -- directional only): **all 30 configs lose money**
PF ranges from 0.49 (crude maxSL2.75) to 0.88 (silver short-only), every single one below 1.0. Trade frequency is very high relative to the short window (33-64/month). This is too little data for a confidence verdict on its own, but 30-for-30 negative is a consistent signal, not noise clustered near breakeven.

## Why the transfer fails
This confirms and extends a conclusion already on record for this project (13-14 Sep): the SHA-flip/EMA9-22 family (crude, silver, and now v4.2's reversal-exit variant) caps out around PF 1.05-1.16 on every instrument tried except BankNifty's own purpose-built v0.4 -- which uses a completely different entry (rejection-wick + above-average-volume + VWAP-side + EMA21-hold pullback reclaim, gated by a 15m ADX filter), not a flip/breakout. BankNifty is index-derivative price action: choppier and more mean-reverting intraday than a trending commodity, and it punishes a trend-following flip system with far more false signals -- exactly what the 20-40 trades/month here (vs v0.4's 2.5) shows happening.

## On your frequency preference
You said you don't want a heavy trade count on BankNifty (crude + silver combined already run ~60 trades/month across two instruments). Every profitable port here trades 18-24/month **on its own** -- before even weighing performance, that alone works against what you asked for. v0.4's 2.5 trades/month is a feature of its design (highly selective, index-specific filters), not something the crude/silver family replicates.

## Recommendation
Keep v0.4 as the BankNifty strategy. Don't port the crude/silver family here -- it has now been tried (30 configurations, both timeframes) and it doesn't work, consistent with the earlier finding and now including the current best commodity strategy (v4.2). Nifty 50 is still pending as a separate test (data harvest not yet done); the same transfer risk applies there and this result should lower expectations going in, though Nifty's own character isn't guaranteed to match BankNifty's.
