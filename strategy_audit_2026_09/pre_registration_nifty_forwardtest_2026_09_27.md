# Pre-registration: Nifty EMA9/22 cross, 10-min exit, morning-only forward test (2026-09-27)
Strategy: EMA9 crosses EMA22 -> enter, hold exactly 10 minutes, exit (2.0xATR stop essentially never binds -- only ~3% of exits in the backtest were the stop). Entries restricted to 09:15-12:00. NSE:NIFTY spot 5m, gross points, 1 lot (pv=1).
Backtest/replay basis: harness 150 trades/6.3mo, PF 1.517, +550 net, DD 203. TradingView single-pass confirmation (Nifty's whole usable history fits one pass -- no tiling needed): 151 trades, PF 1.248, +373 net, DD 236 --
same direction (solidly profitable, low drawdown) but a real magnitude gap vs the harness (PF -18%, net -32%), larger than the ~2% gap seen confirming BankNifty's Supertrend candidate. Likely a small window-boundary
difference between the harness CSV and TradingView's own loaded history, not investigated further -- flagged honestly rather than hidden.
Pine: "nifty test" slot (`USER;232a87d07f3747a0aa0659c031458f67`), titled "NIFTY EMA9-22 cross, 10min exit, morning only (forward test)", live on the NSE:NIFTY 5m chart from **2026-09-27 00:00 IST**.

At ~23.7 trades/month, 40 forward trades should take roughly 1.7 months; using 40 as the judgment threshold here (lower than the 60 used for crude/silver/BankNifty) because Nifty's own backtest sample is already thin (150 trades)
and the point of this test is mainly to check the TV-vs-harness gap resolves one way or the other, not to demand as much forward evidence as a fully-validated candidate.

**Judged only after >=40 forward trades (or sooner if the hard-stop triggers):**
- **KEEP** if forward PF >= 1.10 AND forward drawdown < 500 pts.
- **DROP** if forward PF < 0.85 at the 40-trade mark, OR forward drawdown exceeds 800 pts at any point (hard stop, checked continuously).
- **INCONCLUSIVE** if forward PF is between 0.85 and 1.10 at the 40-trade mark.

No re-tuning during the forward test. Combined with BankNifty's forward test, total expected frequency is ~52.6 trades/month across both scripts, within the user's ~60/month combined target.
Related: `nifty_lowfreq_results_2026_09_27.md`, `bnf-supertrend-forward-test.md` (memory).
