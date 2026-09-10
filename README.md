# trading-pine-strategies

Private collection of Pine Script v5 intraday strategies, developed and backtested
on TradingView. Each file carries a full header block with its logic, changelog,
and **honest** backtest metrics (profit factor, win%, drawdown, trade count).

> All results are single-sample in-sample backtests on ~10 months of data.
> Profit factor and win% are position-size independent; net % and drawdown depend
> on sizing/commission. **Forward-test before risking capital.**

> ⚠️ **WINDOW-DEPENDENCY WARNING (added after further testing).** The BankNifty
> strategies below are **not window-robust**. Re-running `BankNifty MTF Pullback
> v1.0` with its exact "verified" defaults on a *different* 4-month window gave
> **PF 0.33 / 21% win / −16%** vs the **PF 1.31 / 51% win / +4.2%** originally
> reported. Same code, same parameters, opposite result. Every BankNifty number
> in this README and in the `bnf *` file headers is a single favourable in-sample
> window and must be treated as **UNVERIFIED** until walk-forward tested across
> 8–12 separate quarters. The CrudeOil v1.0 numbers are also single-window and
> unverified by walk-forward, though that strategy has held up better in spot
> checks.

---

## CrudeOil (MCX:CRUDEOIL1!, 5-minute) — the strong one

EMA 9/22 pullback-continuation. Enter on the reclaim-candle high after a pullback
to EMA9 in an established trend; structure stop; fixed R target.

| Version | What changed | Backtest (5m, ~10mo) |
|---|---|---|
| v0.6–v0.8 | EMA200 + session + separation + coil break | PF 1.26 → +23% |
| **v1.0** | ~25-run parameter sweep (session-trim was the big win) | **PF 1.89 · 49% win · MaxDD 0.55% · 203 trades · +41.6%** |
| v2.0 | byte-identical snapshot of v1.0 | — |

**v1.0 is the production strategy.** Entry/SL logic is frozen (validated by the user).

---

## BankNifty (NSE:BANKNIFTY1! futures) — no window-stable edge found

Extensive attempt (~20 variants: pullback, momentum, ORB, MTF-confluence, quality
-score) across 3m/5m/15m. **None showed a window-stable edge.** The good-looking
numbers below were single favourable in-sample windows; on other windows the same
configs produce PF 0.3–0.9. Do not trade these without walk-forward validation.

| File | Concept | Single-window result (UNVERIFIED) |
|---|---|---|
| `bnf v0.1 … EMA Pullback 5min` | Pullback + VWAP + wick-quality + volume filters | 5m: PF 1.43 · 50% win · 26 trades (n too small) |
| `bnf v0.1-0.2 … experiments` | v0.1 base sweeps + impulse/momentum breakout | pullback PF ~1.03; breakout PF 0.65–1.02 |
| `bnf v0.3 … EMA Pullback 5min (quality-score)` | 4-condition wick+vol+vwap+hold gate | 5m: PF 1.2–1.4 · ~32 trades (n too small) |
| `bnf v0.3 … Opening-Range Breakout 3min` | 1st-30-min range break + 9/22 trend filter | 3m: PF 1.12 · 53% win · 75 trades |
| `bnf v1.0 … MTF Pullback` | 15m EMA cross → 3m pullback | window A: PF 1.31 · 51% win · window B: PF 0.33 · 21% win |

### Key BankNifty findings
- **Pullback edge = intersection of "rejection wick" + "above-average volume".**
  Neither filter alone beats breakeven (PF 0.66–0.77); together they lift gross
  PF over 1.0 but cut the sample to ~26 trades / 10 months.
- The R:R target is **semi-inert above ~2R** on the pullback strategy: winners
  mostly exit at the 15:15 EOD-flat, not at the target. Higher nominal R just
  lets winners ride to the forced close (verified in the trade blotter).
- **Sizing gotcha:** on `NSE:BANKNIFTY1!`, `qty=1` already equals ONE lot. Using
  `qty=15` (a common mistake — "15 units per lot") = 15 lots and inflates
  commission to ~₹3.4M, dwarfing all P&L. All BankNifty files use `qty=1`.
- Both BankNifty strategies are **timeframe-specific** (pullback 5m-only; ORB
  3m-only). Off-timeframe variants tested negative.

### `bnf v4.1` — OB Pullback, reverse-engineered from the trader's own marked trades

Built from 9 hand-marked trades + a 25-config sweep. On its tune window it hit
**PF 1.85 / +20% / 44% win**. Then walk-forward tested on 6 rolling ~2-month
windows (replay):

| Window | Regime | PF | Net |
|---|---|---|---|
| Sep–Oct 2025 | flat | 0.49 | −12% |
| Nov–Dec 2025 | strong up | 0.33 | −17% |
| Dec–Jan 2026 | up | 0.34 | −15% |
| Feb–Mar 2026 | down | 0.76 | −6% |
| Mar–Apr 2026 | down | 1.85 | +15% |
| Apr–May 2026 | strong down | 1.85 | +20% |

**Profitable only in downtrends; blows up (−15%, ~15% win) in up/flat months.**
Mean PF ≈ 0.94 — a net loser. The tune result was regime luck.

**Bottom line:** No mechanical BankNifty edge in this repo survives walk-forward,
including v4.1 which was built directly from the trader's own trades and tuned.
Every BankNifty strategy here is regime-dependent — they print in one trend
direction and bleed in the other. Treat all BankNifty files as research notes,
not systems. CrudeOil v1.0 is the only strategy here with a plausible (still
single-window, not walk-forward-verified) edge.
