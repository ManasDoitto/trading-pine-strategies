# Pre-registration: BankNifty Supertrend(20,3)+volume scalp forward test (2026-09-27)
Strategy: Supertrend(20,3) flip + above-average-volume filter, entries 09:15-15:20, 1.5R target, ~1.0xATR stop, 45-minute time-stop, forced flat 15:20-15:30. NSE:BANKNIFTY1! futures 5m, gross points (no costs), 1 lot.
Backtest/replay basis (for reference, not re-litigated here): harness 997 trades/35.5mo, PF 1.309, +14,700 net, DD 1,540; TradingView 6-window replay 1,016 trades, PF 1.284, +14,450 net, DD 1,719, 6/6 windows profitable.
Pine: "crude reversal test" slot (`USER;aff06ea9c4124d85bf6bf16667c12f70`), titled "BANKNIFTY Supertrend20-3 + VolFilter scalp (forward test)", live on the NSE:BANKNIFTY1! 5m chart from **2026-09-27 00:00 IST**. Everything at/after that timestamp is genuinely out-of-sample (the strategy code and parameters are now frozen).

At ~28.9 trades/month, 60 forward trades should take roughly 2 months.

**Judged only after >=60 forward trades (or sooner if the hard-stop triggers):**
- **KEEP** (treat as validated, consider live sizing) if forward PF >= 1.15 AND forward drawdown < 3,500 pts.
- **DROP** (abandon) if forward PF < 0.90 at the 60-trade mark, OR forward drawdown exceeds 5,000 pts at any point before that (hard stop, checked continuously, not just at the 60-trade mark).
- **INCONCLUSIVE** (keep watching, no verdict) if forward PF is between 0.90 and 1.15 at the 60-trade mark.

No re-tuning during the forward test. No day-loss circuit breaker is active (matches how it was tested); this is a monitoring/validation test, not a recommendation to size real capital before it resolves KEEP.
Related: `bnf_supertrend_tune_results_2026_09_27.md`, `bnf_supertrend_tv_confirmation_2026_09_27.md`.
