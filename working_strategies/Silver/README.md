# Silver — top 3 working strategies (MCX:SILVER1!, 5m)

## 1. v4.0 wide-ATR + fixed 350pt daily loss limit — `1_v4.0_wideATR_plus_fixed350_daily_limit.pine.txt`
**Current best result in this entire repo, crude/gold/BankNifty included.**
SHA-flip v4.0 core, stops widened (minSL 1.5→2.5 ATR, maxSL 3.0→5.0 ATR),
plus a fixed 350-pt/day circuit breaker layered on top. PF **1.35**, net
+160,845 pts, ~24 trades/mo, max single-window DD cut from 76,863→24,551 pts
(−68%) by the breaker. A fixed cap beat a volatility-scaled (7.5x ATR14)
alternative decisively — see caveat below.
Source: `strategy_audit_2026_09/silver_daily_loss_limit_results.md`.

## 2. v4.0 wide-ATR recal, no breaker — `2_v4.0_wideATR_recal_no_breaker.pine.txt`
Same wide-stop change as #1, without the daily loss limit. PF 1.15, net
+116,096 pts — real edge, but **not deployable as-is**: one window alone
contributed +134,977 pts (more than the full-period net) and max drawdown
was 76,863 pts at 1 lot. Kept as the "before" reference for #1; use #1
instead unless you specifically want to study the breaker's effect.
Source: `strategy_audit_2026_09/gold_silver_recalibration_results.md`.

## 3. v4.0 vanilla baseline (unmodified) — `3_v4.0_vanilla_baseline_multiasset.pine.txt`
Plain SHA-flip v4.0 logic with no Silver-specific tuning, PF 1.06, net
+32,815 pts. Kept as the control/baseline so the wide-ATR change's real
contribution stays visible instead of getting lost.
Source: `strategy_audit_2026_09/v4.0_mcx_naturalgas_gold_silver_results.md`.

## Caveats
- **Why a fixed breaker, not volatility-scaled:** tested both. The worst
  drawdown window was exactly when ATR spiked, so an ATR-scaled breaker's
  threshold expands right when the danger is highest, defeating the purpose.
  General principle — scale *position/stop sizing* with volatility, but keep
  a circuit breaker's cap *fixed* absolute. See `protected-crude-script.md`
  memory for the full writeup.
- Wide stops mean genuinely larger tail risk per trade even with #1's
  breaker capping the daily total — size accordingly.
