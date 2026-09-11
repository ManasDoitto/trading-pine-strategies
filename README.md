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
| 13b | Sweep fade + daily-trend regime gate (**5m**, `v10.3`) | 50% | 1.97 | +ve/breakeven in 4 of 5 windows **Apr-2025→Sep-2026 only** (see 2024 failure below) |
| 13c | + strict gate, points-scored for options (**5m**, `v10.4`) | 59% | 2.71 | net-+ve pts all 5 windows **Apr-2025→Sep-2026 only**; ~+190 net pts/mo |
| 13d | + SL cap 120 pts, 6R target, re-entry (**5m**, `v10.5`) | 48% | 3.08 | all 5 windows +ve **Apr-2025→Sep-2026 only**; worst trade −134; ~+205 net pts/mo, ~4 tr/mo |
| 13e | multi-level rejection fade, higher freq (**5m**, `v11`) | 49% | 1.78 | ~7–15 tr/mo; +ve in 3 of 4 recent windows, −100 pts/mo in one uptrend; companion, not standalone |
| 13f | confidence score (0–100) → RR by grade (**5m**, `v10.6`) | 48% | 3.08 | score does **not** order outcomes; RR-by-grade ≤ flat 6R; ships useConf **off** = v10.5, A/B/C table is a discretionary dashboard |
| 13g | **v10.4 core + v11 layer combined** (**5m**, `v12`) | 41% | 1.88 | +ve every window Apr-2025→Sep-2026 (~0.5 tr/day) **BUT every 2024→mid-2025 window −200…−350 pts/mo** |
| 13h | + daily regime filter (**5m**, `v13`, mode="bear") | 40–75% (CORE) | 2.0–2.4 | best of the family: "bear" gate improves 7 of 8 windows, up windows +13→+164 / +12→+219, halves 2024 loss (−348→−164) **but 2024→mid-2025 still net −94…−302/mo. ADX & slope-magnitude filter modes both fail entirely.** |
| 14 | Opening-range breakout **continuation** (5m/15m) | 32% | 1.2–1.25 | loser after cost: ~19–30 tr/mo, net −90/mo (2024) to −227/mo (2025-26) — gross edge too thin for 20-pt option friction |
| 15 | ORB break + retest re-entry (5m) | 28% | 0.94 | loser — retest condition re-fires; 32 tr/mo, net −785/mo |
| 16 | EMA 9/21/50 stack + pullback-to-EMA21 (5m) | 24% | 0.91 | loser — pullback trigger fires every bar in a stack; 30 tr/mo, net −768/mo |
| 17 | Displacement "drive" candle continuation (5m) | — | — | ~0 trades at any sane filter; not viable |
| 18 | VWAP ±2σ band mean-reversion (5m) | 36% | 0.85 | loser — 46 tr/mo, band pierced and price continues; net −1293/mo |
| 19 | Opening-gap fade toward prior close (5m) | 23% | 0.79 | loser — BankNifty gaps continue, don't fill; 17 tr/mo, net −633/mo |
| 20 | Range-day fade of developing day H/L (5m) | 50% | 0.97 | ~2 trades / 6 months — first-90-min range is essentially never small enough; not viable |

¹ tuned on one favourable window; ² tiny sample.

> **Concepts 14–20 (focused momentum/mean-reversion batch, tested with 2024
> included).** All seven lose after the 20-pt/round-trip option-friction charge,
> most badly, and several barely trigger. The recurring killers: BankNifty 5m
> intraday **continues rather than reverts or cleanly breaks-and-runs**, entry
> triggers fire far too often (17–46 trades/month) for option-buying friction,
> and win rates sit at 22–36%. This is now **~20 distinct concept families**
> across 3m/5m/15m — pullback, breakout, breakout-retest, fade (level/ORB/sweep/
> VWAP/gap/range-day), momentum, EMA-stack, displacement, MTF confluence,
> SMC/OB/FVG, order-flow proxy, CHoCH, prior-day-level sweep + regime gate.
> **None has a durable, friction-surviving mechanical BankNifty intraday edge.**
> The `v13` "bear" sweep-fade is the least-bad (regime-conditional, positive
> 2025–26, negative through 2024). Further mechanical search on BankNifty
> intraday is very unlikely to change this conclusion.

> **2024 walk-forward failure (rows 13b–13h).** All of the 5m sweep-fade
> versions were tuned and tested on **Apr 2025 → Sep 2026**, a range-bound /
> corrective stretch. Extending the walk-forward to 2024 (a trending year) makes
> every ~6-month window from Apr 2024 to mid-2025 a net loser, −94 to −350
> pts/month — including the CORE alone (17–38% win). The `v13` "bear" regime
> filter roughly halves the 2024 damage and lifts the recent windows, but the
> mid-2024→mid-2025 span is still net-negative. **None of v10.3–v13 is a
> multi-year-robust system; the 2025–26 numbers are regime-conditional.**

**~70 configurations. Walk-forward tested. On 3m every approach lands at 22–37%
win, PF 0.4–0.9. The three that tuned positive on one 3m window all failed on
the next.**

### `bnf v10.3` — Sweep + daily-trend regime (5-minute)

Moving the PDH/PDL liquidity-sweep fade to **5m** and adding a **daily-trend
regime gate** (fade a high only while price is at/below its 8-day SMA of daily
closes; mirror for lows) produced a config that does not blow up in any
**2025–26** regime window (but see the 2024 failure box above — this held only
on the Apr-2025→Sep-2026 sample):

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

### `bnf v12` — v10.4 core + v11 layer, one deployable strategy

Combines the two into a single script sharing one position and one risk model:
**CORE** = the PDH/PDL sweep-fade (always on, dtrend gate only — net-positive in
every regime on its own); **LAYER** = fade a one-bar rejection at a rolling
basket of intraday levels (5m swing H/L + opening range), running only while the
**8-day** daily-SMA slope is not rising (off in sustained uptrends). Shared
120-pt stop cap, 6R target, 15:15 flat. The scoreboard splits CORE vs LAYER.

| Window | Market | Tr | Tr/day | Win% | Net @20 | Net/mo |
|---|---|---|---|---|---|---|
| Apr–Oct 2025 | strong up | 63 | 0.48 | 41% | +83 | +13 |
| Jun–Dec 2025 | up | 56 | 0.43 | 39% | +72 | +12 |
| Dec 2025–Apr 2026 | flat | 53 | 0.41 | 28% | +1158 | +186 |
| Feb–Jun 2026 | down | 71 | 0.54 | 35% | +2657 | +427 |
| Feb–Sep 2026 | down | 80 | 0.58 | 39% | +2518 | +385 |

All 5 windows above net-positive, ~0.5 trades/day (~2.5× v10.4). The **8-day**
daily-slope lookback is essential — at 3 days, brief pullbacks flip the filter
and the up windows bleed −110 to −135 pts/month.

> ⚠️ **ROBUSTNESS FAILURE ON OLDER DATA.** Walk-forward extended back to 2024:
>
> | Window (~6mo) | v12 Net/mo | CORE (tot) | LAYER (tot) |
> |---|---|---|---|
> | ~Apr–Oct 2024 | −348 | −390 (17% win) | −734 |
> | ~Jun–Dec 2024 | −323 | −110 | −837 |
> | ~Aug 2024–Feb 2025 | −204 | −221 | +92 |
> | ~Oct 2024–Apr 2025 | −253 | −739 | +565 |
> | ~Dec 2024–Jun 2025 | −210 | −546 | +479 |
>
> **Every window before ~Apr 2025 is a net loser (−200 to −350 pts/month), and
> it is not just the LAYER — the CORE (pure v10.3/10.4/10.5 PDH/PDL fade) loses
> in all 5 at 17–38% win.** The whole sweep-fade family was tuned and
> walk-forward-tested on Apr 2025–Sep 2026, a range-bound / corrective stretch
> that suits mean-reversion. 2024 trended and the fade got run over. The
> positive 2025–26 numbers are **regime-conditional, not a durable edge.**

**Bottom line:** No mechanical BankNifty **3m** edge survived walk-forward. On
**5m**, the prior-day-level liquidity-sweep fade + daily-trend regime gate
(`v10.3`–`v10.6`, `v12` +intraday layer, `v13` +daily regime filter) is
net-positive across every walk-forward window **from ~Apr 2025 to Sep 2026** —
but **extending the walk-forward back to 2024 breaks it.** A regime filter
(`v13`) was added and every mode tested: **daily ADX** and **slope-magnitude**
filters fail outright — they can't separate the profitable 2025–26 down-drift
from the 2024 trend. The best mode, **"bear"** (trade only while the 8-day daily
SMA is flat or falling), improves 7 of 8 windows, roughly halves the 2024 loss
(−348 → −164 pts/month) and lifts the recent up windows from breakeven to
+150…+220/month. **But the three windows spanning mid-2024 to mid-2025 are still
net losers (−94 to −302/month)** — a ~9-month drawdown, mostly the 2024 uptrend
plus the Oct-2024 crash. `v13` mode "bear" is the best version and the one to
forward-test, but it is **still not robust across a full multi-year sample.**
Deploy only accepting that strong-trend years lose, or with a discretionary
"sit out obvious trends and crashes" overlay. Every BankNifty file here is a
research note, not a system.

### Combined book: v13-bear (BankNifty) + CrudeOil v1.0

Tested both as equal ₹500k-capital sleeves over four ~6-month replay windows
(same end dates; CrudeOil re-run at qty=1 — the shipped qty=10 is ~55× leverage
and unusable). Futures %, CrudeOil with its 0.02% commission:

| Window (end) | v13-bear | CrudeOil v1.0 | Book (avg) |
|---|---|---|---|
| Apr–Oct 2024 | −2.1% | +0.5% | −0.8% |
| Oct 2024–Apr 2025 | +1.5% | −6.7% | −2.6% |
| Apr–Oct 2025 | +12.1% | −6.1% | +3.0% |
| Oct 2025–Apr 2026 | +18.9% | +61.1% | +40.0% |

The two sleeves **are lowly / negatively correlated** — when one is weak the
other is usually flat-or-positive, so the book never blows up on both at once
(the diversification the pairing was meant to provide). **But neither sleeve has
a durable edge:** CrudeOil v1.0 is breakeven-to-losing in 3 of 4 windows (its
famous +41.6% was one favorable window; the +61% here is a single crude
trend-run). Strip the one CrudeOil blow-out window and the combined book is
≈ flat over 18 months. The book is smoother than either piece alone but is
**not a tradeable system** — its positive total rests on one lucky window.

## Nifty 50 (NSE:NIFTY spot index, 5-minute) — the 3 best-tested concepts, all fail

Took the 3 concept families that performed best elsewhere in this repo —
`v13` sweep-fade (BankNifty's least-bad), the CrudeOil v1.0 EMA 9/22 pullback,
and ORB continuation (the least-bad momentum concept) — and ran each fresh on
Nifty spot across the same ~6-month windows used everywhere else. Points =
index points (qty=1 "unit"), 10-pt/round-trip option-cost charge, no commission.

| Concept | Full window | ~Apr–Oct 2024 | ~Apr–Oct 2025 | ~Oct 2025–Apr 2026 |
|---|---|---|---|---|
| `v13` sweep-fade (bear) | +204 gross, 29% win, PF 1.09 → **net −546** | +94 gross, 39% win → **net −136** | −251 gross, 30% win → **net −691** | −595 gross, 21% win → **net −1225** |
| EMA 9/22 pullback (CrudeOil logic) | PF 0.69, 31% win, **−0.42%** | PF 1.06, 42% win, **+0.05%** | PF 0.62, 35% win, **−0.45%** | PF 0.90, 40% win, **−0.14%** |
| ORB continuation | PF 0.78, 24% win, **net −752** | PF 1.08, 28% win, **net +236 gross → net negative after cost** | — | — |

**All three lose in every window, several worse than on BankNifty.** Nifty is a
diversified large-cap index — lower intraday volatility and more efficient than
BankNifty (which is dominated by a handful of high-beta financials), so the
same point-based sweep/pullback/breakout triggers have even less to work with.
Re-tuning parameters specifically for Nifty was not attempted: given that
BankNifty's own "edge" collapsed the moment the walk-forward window was
extended (see above), and that the same three concepts independently fail on
two different instruments, further Nifty-specific curve-fitting would very
likely just manufacture another regime artifact rather than find a real one.

## Three-instrument scoreboard — the honest comparison

| Instrument | Best strategy | 2025–26 result | Extended (2024+) result | Verdict |
|---|---|---|---|---|
| **BankNifty** | `v13` sweep-fade, mode "bear" | +12% to +19% per 6mo window, PF 1.1–2.3 | 1 of 4 windows negative (−2%), rest positive | **Least-bad of the three** — regime-conditional, not durable |
| **CrudeOil** | `v1.0` EMA 9/22 pullback | +41.6% single tuned window (PF 1.89) | Breakeven-to-losing 3 of 4 windows (−6.1% to −6.7%); +61% in 1 window | Single-window edge, not reproducible on demand |
| **Nifty** | none of the 3 tested | all net-negative after cost, every window | all net-negative after cost, every window | **No candidate found** |

**There are not three winning strategies per instrument.** Across BankNifty (~20
concept families), CrudeOil (1 strategy, re-tested), and Nifty (the 3 best
candidates from the other two), the search converges on the same result: no
mechanical intraday strategy in this rule space (price-action pullback,
breakout, fade/sweep, mean-reversion, SMC/order-block, VWAP, gap, EMA-stack,
momentum) holds up once tested across more than one favourable window. If you
want to trade any of these, `v13`-bear on BankNifty is the one with the most
walk-forward support — treat it as regime-conditional (works when the market
drifts down or sideways, bleeds in a sustained uptrend), paper-trade it, and
size for the drawdowns shown above, not the best-window headline numbers.

## Cross-instrument x cross-timeframe matrix (2 concepts x 3 instruments x 3m/5m/15m)

Took the two strongest concepts in the repo (`v13` sweep-fade and the CrudeOil
`v1.0` EMA 9/22 pullback) and ran each on **every instrument at every
timeframe** — 18 cells, single recent window (un-tuned `stopCapPts`, not
instrument-optimised — a triage pass, not a final backtest):

**`v13` sweep-fade** — PF / net-points-per-month:

| Instrument | 3m | 5m | 15m |
|---|---|---|---|
| BankNifty1! | 0.89 / −254 | 0.99 / −137 | 0.93 / −67 |
| **NIFTY (spot)** | 0.71 / −211 | 1.08 / −89 | **2.99 / +233** |
| CrudeOil1! | 0.64 / −94 | 1.17 / −57 | 1.99 / +48 |

**EMA 9/22 pullback** — PF / net-points-per-month (all 9 cells negative):

| Instrument | 3m | 5m | 15m |
|---|---|---|---|
| BankNifty1! | 0.77 / −1114 | 0.98 / −383 | 0.97 / −179 |
| NIFTY (spot) | 0.73 / −714 | 0.69 / (single-window, ~−0.4%) | 1.16 / −44 |
| CrudeOil1! | 1.51 / −398 | 0.69–1.89 (window-dependent) | 0.91 / −181 |

**One cell stood out: `v13` sweep-fade on NIFTY spot, 15-minute.** Walk-forwarded
it across the same four windows used everywhere else in this repo:

| Window | Trades | Win% | PF | Net pts | Net/mo |
|---|---|---|---|---|---|
| ~Apr–Oct 2024 (the window that breaks every other config) | 45 | 46.7% | 1.22 | −134 | −7 |
| ~Apr–Oct 2025 | 64 | 45.3% | 2.04 | +1407 | +69 |
| ~Oct 2025–Apr 2026 | 83 | 48.2% | 2.90 | +3858 | +189 |
| ~Feb–Sep 2026 (full) | 90 | 45.6% | 2.99 | +4733 | +233 |

**This is the first config in the entire project — across ~25 BankNifty
concept families, CrudeOil, and Nifty — to survive the 2024 trending-year
stress test without going net negative.** Every other config broke on 2024;
this one goes to roughly breakeven (−7 pts/month) instead of −150 to −350.
Saved as `nifty v1 Sweep-Fade 15min`, built for manual review: green/red
background = daily-trend regime (price vs 8-day daily SMA), BUY/SELL shapes on
every entry, STOP-LOSS/TARGET lines plotted live, on-chart points scoreboard.

**Caveats — promising, not proven:** only 4 windows (~18 months), single data
vendor, 45–48% win rate (a handful of big winners carry the average), and this
emerged from an un-tuned parameter set carried over from BankNifty rather than
optimised for Nifty specifically — the real test is tuning it properly and then
walk-forwarding again, plus extending further back than 2024 if data allows.

## Three-instrument, three-timeframe final recommendation

| Instrument | Best strategy found | Why | Status |
|---|---|---|---|
| **Nifty (spot), 15m** | `v13` sweep-fade "bear" | Only config to survive 2024 net-non-negative; PF 1.2–3.0 across 4 windows | **Most promising — start here** |
| **BankNifty, 5m** | `v13` sweep-fade "bear" (native tuning, `stopCapPts=120`) | Positive 3 of 4 windows, PF 1.1–2.3, but −2% in the 2024 window | Regime-conditional |
| **CrudeOil, 5m** | `v1.0` EMA 9/22 pullback | Best (only) candidate tested; breakeven-to-losing 3 of 4 windows, +61% in 1 | Single-window edge, weakest of the three |

**Bottom line on the whole repo:** No mechanical BankNifty **3m** edge survived
walk-forward. `v13` "bear" is BankNifty's least-bad 5m config but not
multi-year-robust; ported to **Nifty spot at 15m it becomes the strongest result
in the repo**, surviving all four walk-forward windows. CrudeOil v1.0's edge is
a single favourable window and does not survive extended walk-forward on 3m/5m/
15m or on other instruments. **Nothing here is a validated, durable mechanical
strategy** — the Nifty 15m result is a genuine lead worth manually refining
(entry/SL/exit marked on chart for exactly that); everything else is a research
note. Forward-test on paper before risking capital.
