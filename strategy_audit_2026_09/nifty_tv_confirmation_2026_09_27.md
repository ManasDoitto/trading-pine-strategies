# Nifty EMA9/22 cross + 10-min exit (morning-only): TradingView confirmation (2026-09-27)
Pine: "nifty test" slot (`USER;232a87d07f3747a0aa0659c031458f67`). NSE:NIFTY spot 5m, commission 0 (gross), 1 lot, pv=1. Nifty's whole usable history (6.3mo, TradingView's own floor) fits in a single pass -- no tiled replay needed, unlike BankNifty.

| | trades | PF | net pts | DD |
|---|---|---|---|---|
| Harness (6.3mo) | 150 | 1.517 | +550 | 203 |
| **TradingView (single pass, same ~6.3mo)** | 151 | **1.248** | **+373** | 236 |

**Confirmed directionally** (solidly profitable both ways, low drawdown both ways, trade count matches almost exactly: 150 vs 151), but **the magnitude gap is real** -- PF is 18% lower and net points 32% lower on TradingView than the harness suggested.
This is a bigger gap than seen confirming BankNifty's Supertrend candidate (which matched within 2%). Most likely cause: a small difference in exactly where the two engines' usable history starts (the harness counts from
its own CSV's row 400; TradingView counts from its own loaded buffer's bar 400, which may begin a few days earlier or later) -- not investigated further here, but honestly flagged rather than smoothed over.
**Bottom line: real, but weaker than the harness estimate.** Forward test judgment thresholds (see `pre_registration_nifty_forwardtest_2026_09_27.md`) were set with this gap in mind -- lower than what BankNifty's better-confirmed candidate would need.
