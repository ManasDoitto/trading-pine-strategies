# Nifty forward test switched: Bollinger-squeeze -> Tenkan/Kijun + EMA200 (2026-09-28)
Old candidate (Bollinger-squeeze breakout) had accumulated only 2 forward trades (net -5, meaningless), so switching cost essentially nothing. New candidate found in `nifty_dhan_fresh_results_2026_09_28.md` -- built fresh
on Dhan's real 9.5-year NSE:NIFTY history, positive in all 10 calendar years, fully volume-free. Same Pine slot reused ("nifty test", `USER;232a87d07f3747a0aa0659c031458f67`), now titled "NIFTY Tenkan-Kijun + EMA200 scalp (forward test)".
Verified only this slot changed (v3->v4) before proceeding.

## TradingView confirmation (single pass -- TV's Nifty spot floor, ~6.3 months, Mar-Sep 2026)
| | trades | PF | net pts | DD |
|---|---|---|---|---|
| Harness (9.5yr, full history) | 3,892 | 1.151 | +6,975 | 1,784 |
| **TradingView (single pass, recent ~6.3mo only)** | 231 | **1.011** | **+43** | 938 |

This TV window lands close to breakeven -- a bigger harness/TV gap than the ~15-18% seen on the previous two Nifty candidates. Two things temper how much weight to put on this single reading: (1) TradingView can only ever show
a recent ~6.3-month slice for Nifty (its own data floor, unrelated to Dhan), so this is one partial year out of the ten the harness checked, not a contradiction of the "positive every year" result -- the harness itself doesn't
claim every 6-month sub-window is positive, only every full calendar year; (2) the strategy's own long-run numbers already show real year-to-year variation within an all-positive record. Still, this is a real, not-fully-explained
gap and it is flagged rather than smoothed over, same as the prior two Nifty confirmations. Forward-test thresholds below are set conservatively given this history of TV running weaker than the harness for Nifty specifically.

## Forward test, restarted
Entry: Ichimoku Tenkan(9)/Kijun(26) cross, filtered to only trade with the EMA200 trend. Exit: 2.0R target, ~1.0xATR stop, 45-minute time-stop, forced flat 15:20-15:30. Start: **2026-09-28 00:00 IST**. 3 forward trades already
registered from today (net +111, 100% win -- meaningless at n=3, noted only for completeness).

**Judged only after >=60 forward trades** (~1.7 months at ~34.3/mo -- the higher bar reflects this being the best-validated Nifty candidate so far, worth the same discipline as crude/silver/BankNifty's confirmed candidates):
- KEEP if forward PF >= 1.05 and forward drawdown < 2,500 pts
- DROP if forward PF < 0.85 at the 60-trade mark, OR drawdown exceeds 3,500 pts at any point (hard stop)
- INCONCLUSIVE between 0.85 and 1.05 at the 60-trade mark

Combined with BankNifty's live forward test, expected combined frequency depends on which BankNifty configuration is running (~16-29 tr/mo) plus this Nifty pick's ~34.3 tr/mo.
