# trading-pine-strategies

Private collection of Pine Script v5 intraday strategies, developed and backtested
on TradingView. Each file carries a full header block with its logic, changelog,
and **honest** backtest metrics (profit factor, win%, drawdown, trade count).

> All results are single-sample in-sample backtests on ~10 months of data.
> Profit factor and win% are position-size independent; net % and drawdown depend
> on sizing/commission. **Forward-test before risking capital.**

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

## BankNifty (NSE:BANKNIFTY1! futures) — hard instrument, thin edges

Extensive attempt to build a BankNifty strategy matching or beating crude. Three
distinct entry concepts were tested across 3m/5m/15m. **None reached crude's edge.**

| File | Concept | Best result | Verdict |
|---|---|---|---|
| `bnf v0.1 … EMA Pullback 5min` | Pullback + VWAP + wick-quality + volume filters | 5m: PF **1.43** · 50% win · DD 2.5% · **26 trades** · +3.9% | Net-positive but **very thin sample** |
| `bnf v0.1-0.2 … experiments` | v0.1 base sweeps + impulse/momentum breakout | pullback PF ~1.03; breakout PF 0.65–1.02 | Not adopted (breakeven / loss) |
| `bnf v0.3 … Opening-Range Breakout 3min` | 1st-30-min range break + 9/22 trend filter | 3m: PF **1.12** · 53% win · DD 5.4% · 75 trades · +3.5% | Real but thin edge |

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

**Bottom line:** BankNifty futures on this data resisted a durable edge. The two
adopted strategies are marginal and should be treated as forward-test candidates,
not production systems. CrudeOil v1.0 remains the only strong performer here.
