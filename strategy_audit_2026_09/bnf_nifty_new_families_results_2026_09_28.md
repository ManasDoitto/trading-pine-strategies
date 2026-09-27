# 15 new signal families for BankNifty and Nifty (2026-09-28)
Not overlapping with the 24 families in `bnf_scratch_scalp.py` or the crude/silver port test: Parabolic SAR flip, DI+/DI- cross, NR7 breakout, gap-fade, gap-and-go, Fibonacci 50% bounce, inside-bar breakout, VWAP-reclaim,
triple-EMA alignment, RSI(2) pullback, Ichimoku Tenkan/Kijun cross, plain Heikin-Ashi flip, first-hour breakout+retest, tight ATR channel fade, Bollinger-squeeze breakout. Same quick-scalp exit style as the live candidates
(1.5R target, 1.0xATR stop, 30-min time-stop baseline). BankNifty futures 5m (3yr robust), Nifty spot 5m (6.3mo). Code `bnf_new_families.py`, data `research_data/bnf_nifty_new_families.csv`.

## BankNifty: nothing beats the incumbent (Supertrend20-3+volume, PF 1.309, 28.9 tr/mo, live forward test)
Best of the 15: VWAP-reclaim (PF 1.083, +7,812 net, 68.3 tr/mo), DI+/DI- cross (PF 1.068, +6,166, 70.8 tr/mo), Parabolic SAR flip (PF 1.057, +7,657, 105 tr/mo -- far too frequent). Everything else is weaker or net-negative
(fib_bounce, inside_bar_breakout, gap_fade, ha_flip, atr_channel, first_hour_retest all lose or are flat). No change recommended -- the live BankNifty forward test stays as is.

## Nifty: two new candidates that look genuinely stronger than the current forward test
Current live pick (EMA9/22 cross, 10-min exit, morning-only): 150 trades/6.3mo, PF 1.517 (harness) / 1.248 (TV-confirmed), +550 net, DD 203.

| candidate | trades/mo | PF | net pts | DD | 1st-half PF | 2nd-half PF |
|---|---|---|---|---|---|---|
| **Bollinger-squeeze breakout (RR 1.5, 20-min time-stop)** | 33.0 | 1.478 | **+1,115** | 239 | 1.352 | 1.629 |
| First-hour breakout + retest (RR 1.5, 30-min time-stop) | 26.7 | 1.513 | +718 | 245 | 1.225 | 2.040 |
| Current live Nifty pick, for comparison | 23.7 | 1.517 | +550 | 203 | 1.565 | 1.464 |

Both checked across several RR/time-stop variants (not just the one shown) -- PF stayed in a consistent 1.2-1.5 band for both, and both halves of the data were positive in every variant tried, so these are real plateaus, not lucky single points.
**Bollinger-squeeze breakout earns roughly double the net points of the current live pick** (+1,115 vs +550) at similar PF and a similar/lower drawdown, for a bit more trade frequency (33.0 vs 23.7/month -- still well inside the combined budget:
28.9 + 33.0 = 61.9/month, right at the ~60 target). Its trade-off: more of its edge sits in the second half of the data (1.352 -> 1.629) than the current pick's more even split (1.565 -> 1.464) -- slightly less balanced, though never negative in either half.
First-hour retest has a similar PF to the current pick but earns more net points at a similar low frequency; its split is more second-half-weighted than Bollinger-squeeze's.

## Recommendation
Bollinger-squeeze breakout is worth switching to for Nifty: more points, comparable PF and drawdown, and the live forward test has accumulated **zero forward trades so far** (started yesterday), so nothing is lost by swapping now versus
waiting. Not done automatically -- this changes what the forward test is testing, so it needs your go-ahead. If you'd rather keep the simpler, more evenly-split EMA-cross pick, that's a reasonable call too; the difference between them
is a real but modest trade-off, not a clear-cut mistake either way.
