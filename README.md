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

## BankNifty (NSE:BANKNIFTY1! futures) — one thin regime-gated edge (v10.3)

Extensive attempt (~70 configs: pullback, momentum, ORB, MTF-confluence,
quality-score, SMC/OB/FVG, liquidity sweep, prior-day levels) across 3m/5m/15m.
**Nothing worked on 3m.** The one config that survived walk-forward is
`bnf v10.3` on **5m** — a prior-day-level liquidity-sweep fade with a daily-trend
regime gate (details at the bottom of this section). The other good-looking
numbers below were single favourable in-sample windows; on other windows the same
configs produce PF 0.3–0.9. Do not trade any of these without walk-forward
validation and live paper-trading first.

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

### Full BankNifty concept scoreboard (all 3m, all tested)

| # | Concept | Best win% | Best PF | Result |
|---|---|---|---|---|
| 1 | EMA 9/22 pullback (v0.1–v1.0, Sets A–K) | ~50% | 1.4 | fails walk-forward |
| 2 | Opening-range breakout | 53% | 1.12 | regime bet |
| 3 | Opening-range fade | 35% | 0.50 | loser |
| 4 | Momentum breakout | 35% | 1.0 | loser |
| 5 | MTF confluence (15m+3m) | 43% | 0.76 | loser |
| 6 | Session + SMC structure | 39% | 0.73 | loser |
| 7 | OB pullback (from marked trades, tuned) | 44% | 1.85¹ | fails walk-forward (0.33 in up months) |
| 8 | VWAP mean-reversion | 37% | 0.59 | loser (stretches continue) |
| 9 | Morning-move fade | 34% | 0.55 | loser |
| 10 | PDH/PDL level fakeout | 26% | 1.10² | loser |
| 11 | FVG + order-flow proxy | 37% | 1.12¹ | fails walk-forward (mean PF 0.86) |
| 12 | Pure SMC (OB+FVG+structure, clean chart) | 33% | 0.71 | loser |
| 13 | Sweep + CHoCH + prior-day levels + premium/discount (3m) | 26% | 0.40 | loser |
| 13b | Sweep fade + daily-trend regime gate (**5m**, `v10.3`) | 50% | 1.97 | **regime-robust: +ve/breakeven in 4 of 5 windows, worst −2.2%** |
| 13c | + strict gate, points-scored for options (**5m**, `v10.4`) | 59% | 2.71 | **net-positive pts in all 5 windows; ~+190 net pts/mo** |
| 13d | + SL cap 120 pts, 6R target, re-entry (**5m**, `v10.5`) | 48% | 3.08 | **all 5 windows +ve; worst trade −134; ~+205 net pts/mo, ~4 tr/mo** |

¹ tuned on one favourable window; ² tiny sample.

**~70 configurations. Walk-forward tested. On 3m every approach lands at 22–37%
win, PF 0.4–0.9. The three that tuned positive on one 3m window all failed on
the next.**

### `bnf v10.3` — Sweep + daily-trend regime (5-minute) — first regime-robust config

Moving the PDH/PDL liquidity-sweep fade to **5m** and adding a **daily-trend
regime gate** (fade a high only while price is at/below its 8-day SMA of daily
closes; mirror for lows) produced the first BankNifty config that does not blow
up in any regime window:

| Window (approx) | Market | PF | Net | Win% | Trades | MaxDD |
|---|---|---|---|---|---|---|
| Apr–Oct 2025 | strong up | 1.06 | +0.6% | 44% | 25 | 5.5% |
| Jun–Dec 2025 | up | 0.78 | −2.2% | 33% | 24 | 5.1% |
| Dec 2025–Apr 2026 | flat | 1.19 | +2.4% | 37% | 19 | 9.1% |
| Feb–Jun 2026 | down | 1.71 | +9.2% | 50% | 20 | 6.5% |
| Feb–Sep 2026 | down | 1.97 | +12.1% | 46% | 24 | 4.1% |

Only one losing window (−2.2%); mean PF ≈ 1.25. The **same setup with the gate
OFF** runs PF 0.66 / −9.1% in the strong-up window — the gate is doing the work.
Caveats: thin edge (net +0.6% to +12% per ~6 months, commission ≈ 30% of gross),
19–25 trades/window (small sample), single vendor, overlapping windows 4 & 5.
Tuning `regimeLen` just see-saws which up-window loses, so it is left at 8 (the
smaller worst case). **Research config, not a validated system — paper-trade first.**
It will not deliver the "50% win / 70% PnL" naked-option-buying target: real R:R
is ≈ 1:2–1:3 at ≈ 40% win, so expectancy is only ≈ +0.3R per trade.

### `bnf v10.4` — same engine, POINTS-first for option buying

`v10.4` re-scores `v10.3` in **BankNifty index points** (what an option buyer
actually needs) instead of rupees, drops the meaningless futures commission, and
tightens one knob: `regimeSlack 0.0 → −1.5` (fade a high only when 5m price is
≥ 1.5×avgRange **below** the 8-day daily SMA). That single change makes **every**
walk-forward window net-positive after a 20-pt/round-trip option-friction charge:

| Window | Market | Tr | Win% | Total pts | Pts/tr | PF | Net @20/rt |
|---|---|---|---|---|---|---|---|
| Apr–Oct 2025 | strong up | 23 | 43.5% | +792 | +34 | 1.64 | +332 |
| Jun–Dec 2025 | up | 20 | 40% | +521 | +26 | 1.55 | +121 |
| Dec 2025–Apr 2026 | flat | 16 | 43.8% | +1117 | +70 | 1.74 | +797 |
| Feb–Jun 2026 | down | 17 | 58.8% | +2365 | +139 | 2.52 | +2025 |
| Feb–Sep 2026 | down | 21 | 52.4% | +2564 | +122 | 2.71 | +2144 |

Non-overlapping (rows 1,2,3,5): **+4994 gross pts / ~18 mo ≈ +277 pts/month
gross, ~+190 net**. Avg win ~+200–370 pts, avg loss ~−80–220 pts. Caveats:
~3 trades/month; ~2.5-hour holds (theta drag on weekly options — the 20-pt
charge is optimistic on slow days); the down-month totals lean on 1–2 big
runners; capping hold time kills the edge; single vendor, ~18 months. The
on-chart POINTS SCOREBOARD table shows all of this live. **Paper-trade first.**

### `bnf v10.5` — SL capped at 120 pts, big-R target, more trades

For an option buyer who cannot stomach a −450-pt stop. `v10.5` makes the risk
block configurable and ships a tuned default: **stop = min(wick stop, 120 pts)**,
**target = 6R** (so winners still ride to the 15:15 flat), **re-entry allowed once
per level per day** (recovers the trades the tight stop loses).

| Window | Market | Tr | Tr/mo | Win% | Total pts | PF | Worst | Net @20 |
|---|---|---|---|---|---|---|---|---|
| Apr–Oct 2025 | strong up | 28 | 4.5 | 42.9% | +924 | 1.66 | −126 | +364 |
| Jun–Dec 2025 | up | 26 | 4.2 | 46.2% | +1106 | 2.01 | −122 | +586 |
| Dec 2025–Apr 2026 | flat | 22 | 3.5 | 40.9% | +1106 | 1.77 | −134 | +666 |
| Feb–Jun 2026 | down | 23 | 3.7 | 43.5% | +2006 | 2.31 | −134 | +1546 |
| Feb–Sep 2026 | down | 25 | 3.8 | 48% | +2557 | 3.08 | −131 | +2057 |

Non-overlapping (1,2,3,5): **+5693 gross pts / ~18 mo ≈ +316 gross / +205 net
pts per month**, ~4 trades/month. **Worst single trade −134 pts** (vs v10.4's
−448); PF 1.66–3.08 every window. What mattered: the 120-pt cap (worst loss and
drawdown down, PF up); keeping the target at 6R not 2R (a 2R target on a capped
stop collapses net from +2557 to +367 on the strong window — BankNifty fade
winners run to EOD); re-entry (weak Jun–Dec window +121 → +586 net). **Fixed
small targets tested and lose.** Still ~4 trades/month — the prior-day-level
sweep only sets up a few times a month; genuine higher frequency needs a
different entry model. Research config — paper-trade first.

**Bottom line:** No mechanical BankNifty **3m** edge survived walk-forward. On
**5m**, `bnf v10.3`/`v10.4`/`v10.5` (prior-day-level liquidity-sweep fade +
daily-trend regime gate) is the one family that stays net-positive across up,
flat and down windows. Use **`v10.5`** for option buying (SL ≤ 120 pts,
points-scored, ~+205 net pts/month); `v10.4` for the wider-stop points version;
`v10.3` for the rupee version. A thin, regime-gated edge worth forward-testing,
not yet a proven system. Every other BankNifty file here is a research note.
CrudeOil v1.0 remains the strongest strategy in the repo (single-window, not
walk-forward-verified).
