# Nifty forward test switched: EMA9/22 cross -> Bollinger-squeeze breakout (2026-09-28)
Old candidate (EMA9/22 cross, 10-min exit, morning-only) had accumulated **zero forward trades** since starting 2026-09-27, so nothing was lost by switching. New candidate found in `bnf_nifty_new_families_results_2026_09_28.md`.
Same Pine slot reused ("nifty test", `USER;232a87d07f3747a0aa0659c031458f67`), now titled "NIFTY Bollinger-squeeze breakout scalp (forward test)". Verified only this slot changed (v2->v3) before proceeding.

## TradingView confirmation (single pass -- Nifty's whole usable history, 6.3mo, fits one pass)
| | trades | PF | net pts | DD |
|---|---|---|---|---|
| Harness (6.3mo) | 208 | 1.478 | +1,115 | 239 |
| **TradingView** | 220 | **1.257** | **+755** | 377 |

Same pattern as the previous Nifty candidate: directionally confirmed (solidly profitable, reasonable drawdown, trade count close), but TradingView runs meaningfully lower than the harness (PF -15%, net -32%, DD +58%) --
consistent with the harness/TV gap already flagged for Nifty (likely a small difference in where each engine's usable history starts; not fully resolved). Forward-test thresholds below are set with this gap already priced in.

## Forward test, restarted
Entry: Bollinger(20,2) squeeze (width below the 20th percentile of its trailing 100-bar range) followed by a close outside the band. Exit: 1.5R target, ~1.0xATR stop, 20-minute time-stop, forced flat 15:20-15:30.
Start: **2026-09-28 00:00 IST**. 2 forward trades already registered from today's session (PF 0.78, net -5 -- meaningless at n=2, noted only for completeness).

**Judged only after >=40 forward trades:**
- KEEP if forward PF >= 1.05 and forward drawdown < 700 pts (lower PF bar than the EMA-cross candidate's would-have-been 1.10, and a wider DD allowance, both reflecting this candidate's larger harness-vs-TV gap and higher DD on TV)
- DROP if forward PF < 0.80 at the 40-trade mark, OR drawdown exceeds 1,200 pts at any point (hard stop)
- INCONCLUSIVE between 0.80 and 1.05 at the 40-trade mark

Combined with BankNifty's live forward test (~28.9 tr/mo), expected combined frequency is now ~28.9 + 33.0 = ~61.9 trades/month, essentially at the ~60/month target.
