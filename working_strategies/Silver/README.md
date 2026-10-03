# Silver — working strategies (MCX:SILVER1!, 5m)

## 1. **v5.0 SHA-ADX Hybrid — `4_v5.0_SHA_ADX_hybrid.pine.txt`** (default — highest PF)
SHA-flip entry + EMA9/22/200 alignment + **15m ADX gate ≥30** + SHA stability + EMA9 proximity + **fixed 350-pt daily loss limit** + session-end forced exit. Stops: minSL 1.5, maxSL 5.0 ATR.

- Python backtest on partial cached data (4.7-mo Dhan sample, 10 trades): PF **2.04**, net +3,518 pts, Sharpe 1.41, max-DD 2,268 pts, **L/W ratio = 0.21** (avg loss = 21% of avg win)
- param sweep winner: ADX=30, PB=1.0, RR=4.0. Daily loss breaker: 350 pts.

## 2. **v5.1 Flip + Donchian Breakout — `5_v5.1_flip_breakout.pine.txt`** (high-frequency)
Adds Donchian channel breakout entry **alongside** the SHA flip. Either signal can trigger. Optimized for more trades while meeting the <40% avg-loss-of-avg-win constraint.

- Python sweep on partial data (4.7-mo): **28 trades**, PF **1.69**, WR 39.3%, net **+5,249 pts**, L/W **0.38** (avg loss = 38% of avg win)
- TV inputs pre-set to the sweep winner (ADX=25, BO5, RR=4.0). Adjust `useDonchian` toggle to disable.
- Trade count ~2.8× higher than v5.0 (10→28). PF and net profit improve; use this for active intraday.

## 2. v4.0 wide-ATR + fixed 350pt daily loss limit — `1_v4.0_wideATR_plus_fixed350_daily_limit.pine.txt`
**Formerly current best result in this entire repo, crude/gold/BankNifty included.**
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
- **Tested 15 Sep 2026: requiring 15m EMA9/22 alignment on top of the
  entry-timeframe signal (multi-timeframe confirmation).** Result: hurts
  #1 — PF 1.43→1.24, net profit roughly halved on the same test window,
  drawdown got worse (396k→471k) despite fewer trades. The extra HTF
  filter mostly screens out trades late in a move (after the HTF EMAs
  have already caught up), cutting into the same big trend-following
  winners this strategy depends on — same underlying lesson as crude's
  partial-TP result above.
- **Not separately retested, but rejected by inference 15 Sep 2026:**
  crude's "pullback-reclaim" continuation entry (see CrudeOil README)
  failed badly there for a mechanistic reason — the loose "touch EMA9"
  condition fires on almost every minor dip and floods the strategy with
  low-quality trades — that applies identically to Silver's SHA-flip
  family, so it wasn't re-run here. Would need BankNifty v0.4's full
  quality-filter stack (wick + volume + VWAP + EMA-hold) to be viable,
  not just the touch condition alone.
- **Tested 19 Sep 2026 on MCX:SILVERM1! 5m (Silver Mini, point value 5),
  quick screen only (recent quarter Jun 29-Sep 18 2026), points = INR/5:**
  "trend-following + wait for pullback sweep" instead of entering on every
  SHA flip. Built as a new TradingView script "Silver v10 Trend-Pullback
  (SILVERM)" with an entry-mode switch. Regime = SHA colour + EMA9/22
  alignment; setup = pullback sweeps the reference EMA, entry on a later
  bar that closes back through it and past the prior bar's extreme; wide-ATR
  stop, RR3, 350-pt daily limit unchanged. Control (Flip only, baseline
  logic): 65 trades, PF 1.57, +26,754 pts, DD 14,095. Pullback-sweep only
  (EMA9): 60 trades, PF 0.61, -26,036 pts, DD 31,307. Flip+pullback (EMA9):
  PF 0.55, -31,153 pts. Best variant found (Flip+pullback, EMA22 reference,
  max 1 entry per SHA run): 77 trades, PF 1.12, +7,501 pts, DD 16,193, still
  far below control. Pullback-only with EMA22 + 1 entry/run reached PF 0.95;
  longer regime age (10 bars) and same-candle reclaim were both worse. No
  full-history replay audit was run because nothing beat the control. Fifth
  rejected pullback/continuation design in this family; the flip bar itself
  carries the edge.
