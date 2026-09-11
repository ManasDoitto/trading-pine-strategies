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

## CrudeOil (MCX:CRUDEOIL1!, 5-minute) — ⚠️ downgraded, failed walk-forward

EMA 9/22 pullback-continuation. Enter on the reclaim-candle high after a pullback
to EMA9 in an established trend; structure stop; fixed R target.

| Version | What changed | Backtest (5m, ~10mo) |
|---|---|---|
| v0.6–v0.8 | EMA200 + session + separation + coil break | PF 1.26 → +23% |
| **v1.0** | ~25-run parameter sweep (session-trim was the big win) | **PF 1.89 · 49% win · MaxDD 0.55% · 203 trades · +41.6%** |
| v2.0 | byte-identical snapshot of v1.0 | — |

**v1.0 is the production strategy.** Entry/SL logic is frozen (validated by the user).
**Update: walk-forward tested (see "CrudeOil v1.0 walk-forward" section
below) — the +41.6% number was a single favourable in-sample window and does
NOT hold up. 4 of 6 out-of-sample windows are net losers (PF < 1, three of
them losing more than the entire starting capital at the current qty=10
sizing), against one wildly good outlier window. No longer "the strong one";
downgraded to the same "not robust" verdict as every BankNifty config.**

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
vendor, 45–48% win rate (a handful of big winners carry the average).

### `nifty v2` — tuned specifically for Nifty (not just ported from BankNifty)

`v1` above carried BankNifty's parameters unmodified. Swept `maxSweepMlt`,
`bufMlt`, `stopCapPts`, `regimeSlack`, `minLvlGapPts` and `rFixed` one at a time
on Nifty 15m, then re-verified the two genuine improvements across all 4
windows. **No trailing stop/target added (there wasn't one) and position sizing
left unchanged (qty=1)**, per instruction.

Changed: `maxSweepMlt` 0.8→0.5 (only fade a clean, shallow poke past the level —
a deep stab through it is a worse signal), `bufMlt` 0.6→0.4 (tighter stop
buffer, now that entries are cleaner). Everything else tested and left as-is —
each was still best or tied-best at its shipped value.

| Window | v1: Trades / Win% / PF / Net-mo | v2: Trades / Win% / PF / Net-mo |
|---|---|---|
| ~Apr–Oct 2024 (toughest) | 45 / 46.7% / 1.22 / **−7** | 34 / 41.2% / 1.36 / **−1** |
| ~Apr–Oct 2025 | 64 / 45.3% / 2.04 / +69 | 49 / 44.9% / 2.25 / +50 |
| ~Oct 2025–Apr 2026 | 83 / 48.2% / 2.90 / +189 | 65 / 43.1% / 2.71 / +119 |
| ~Feb–Sep 2026 (full) | 90 / 45.6% / 2.99 / +233 | 75 / 42.7% / 3.08 / +178 |

`v2` trades **less** and gives up some total points in the good windows, but
**profit factor is higher or equal in every window**, and the worst-case window
(2024) is now essentially **flat** (−1 pt/month instead of −7) — fewer, cleaner
setups to manually check, smaller tail. This is a genuine quality-vs-quantity
trade-off, not a strict win: keep `v1` if you want more trade frequency to
review; `nifty v2 Sweep-Fade 15min` is the shipped default for manual entry/SL/
exit review (fixed SL/target at entry, no trailing, no breakeven-move, so you
can check the plan against what actually happened on every trade).

### Extended walk-forward — as far back as data goes (~Apr 2019, ~7.5 years)

| Window (~6mo) | Trades | Win% | PF | Net/mo |
|---|---|---|---|---|
| ~Dec 2018–Apr 2019 (data start, partial) | 53 | 39.6% | 1.30 | −10 |
| ~Dec 2019–Jun 2020 (COVID crash) | 53 | 43.4% | 1.77 | +16 |
| ~Dec 2020–Jun 2021 | 32 | 31.3% | 1.73 | +20 |
| ~Dec 2021–Jun 2022 | 41 | 26.8% | 1.20 | −4 |
| ~Dec 2022–Jun 2023 | 56 | 30.4% | 1.23 | −4 |
| ~Oct 2023–Apr 2024 (worst window found) | 40 | 30.0% | **0.70** | **−40** |
| ~Apr–Oct 2024 | 34 | 41.2% | 1.36 | −1 |
| ~Apr–Oct 2025 | 49 | 44.9% | 2.25 | +50 |
| ~Oct 2025–Apr 2026 | 65 | 43.1% | 2.71 | +119 |
| ~Feb–Sep 2026 (full, most recent) | 75 | 42.7% | 3.08 | +178 |

**Honest read: 5 of 10 windows are net-negative**, one clearly so (Oct 2023–Apr
2024, PF 0.70, −40/mo — a real loser, not just thin). But **no window is a
disaster on the scale seen everywhere else in this repo** (BankNifty windows ran
to −250 to −350/mo) — the worst Nifty case is −40/mo. There's also a visible
*improving* trend from 2024 into 2025–26 that deserves suspicion rather than
excitement: this whole concept was originally **found by searching against
2025–26 data**, so outperformance there is partly what you'd expect from the
search process itself, not necessarily a strengthening edge. The pre-2024 years
(2019–2023) are the truer out-of-sample test, and they show a mixed, modest
picture — roughly flat to small-positive on average, one real loser, never
catastrophic. **Treat this as "doesn't blow up" evidence, not "proven
profitable" evidence.**

### `nifty v3` — RR 2.4 tune, chasing 50% win rate on request

User instruction: *"tune this strategy till 50% profitable with 1:2.4 RR.
iterate till you get that"* — starting from `v2`, no trailing stop/target,
qty unchanged (1). `rFixed` 6.0 → **2.4** (a smaller fixed target is hit far
more often — most of the win-rate gain by itself), plus `dispMlt` 0 → **0.5**
(require the reversal bar to show real displacement), `bufMlt` 0.40 → **0.60**
and `stopCapPts` 60 → **90** (wider stop buffer, fewer noise stop-outs).

`swLen` 3 → 5 was tried first and hit a clean **50.0% win** in the 3 most
recent windows — but it wrecked the Dec 2021–Jun 2022 window (win% 26.8→24.4,
PF 1.20→0.80, net/mo −4→−44), a clear overfit to recent swing structure, and
was rejected. The shipped combo (`dispMlt`/`bufMlt`/`stopCapPts`, `swLen` left
at 3) does **not** show that regression:

| Window (~6mo) | v2: Tr Win% PF Net/mo | v3: Tr Win% PF Net/mo |
|---|---|---|
| ~Dec 2018–Apr 2019 (data start) | 53 39.6% 1.30 −10 | 53 39.6% 1.15 −19 |
| ~Dec 2019–Jun 2020 (COVID) | 53 43.4% 1.77 +16 | 54 42.6% 1.63 +11 |
| ~Dec 2020–Jun 2021 | 32 31.3% 1.73 +20 | 34 35.3% 1.50 +15 |
| ~Dec 2021–Jun 2022 | 41 26.8% 1.20 −4 | 46 28.3% 0.96 −26 |
| ~Dec 2022–Jun 2023 | 56 30.4% 1.23 −4 | 60 36.7% 1.13 −15 |
| ~Oct 2023–Apr 2024 (old worst) | 40 30.0% 0.70 −40 | 45 44.4% 1.12 −14 |
| ~Apr–Oct 2024 | 34 41.2% 1.36 −1 | 39 **51.3%** 1.54 +9 |
| ~Apr–Oct 2025 | 49 44.9% 2.25 +50 | 57 **49.1%** 2.12 +62 |
| ~Oct 2025–Apr 2026 | 65 43.1% 2.71 +119 | 73 **47.9%** 2.28 +113 |
| ~Feb–Sep 2026 (current, full) | 75 42.7% 3.08 +178 | 83 **47.0%** 2.33 +133 |
| **Average win rate** | **37.3%** | **42.2%** |

**Honest read:** this reliably lands **47–51% win** — essentially the
requested target — in every one of the last 3 windows (2024→2026, the regime
closest to "now"), and raises the average win rate across all 10 windows from
37.3% to 42.2%. It does **not** hit 50% in the older 2019–2023 windows
(28–45% there), and 2 of those windows got *worse* in net/mo despite a higher
win% — a smaller fixed 2.4R target banks less per winner, so the same win-rate
gain doesn't always outrun the losers in a grinding/choppy regime. **`v2`
(6R target, lower win%, bigger winners) still has better long-run expectancy
in most windows** — this is the honest cost of optimizing for a specific
win-rate/RR combo instead of net expectancy. Ship `v3` only if hitting ~50%
win at 2.4R specifically matters (e.g. for manual-execution discipline);
otherwise `v2` remains the recommended default. File: `nifty v3 Sweep-Fade
15min (RR 2.4 tuned...)`.

### Trade-frequency check — can this hit 200 trades / 6 months?

User request: *"trade count is very less and i need at least 200 trades per 6
months."* Tested whether the sweep-fade concept can be pushed to that volume
without simply breaking it. Switched to **5-minute** (3x more bars than 15m)
and loosened, in stages, every frequency-limiting input on `v3`: `relaxTrig`
on (drop momentum confirmation), `dispMlt` 0 (drop displacement filter),
`maxSweepMlt` 0.5→0.8, `swLen` 3→2, `minLvlGapPts` 15→2–5, `maxLevels` 24→40–
60, `maxPerDay` 6→20–30, `allowReentry` 1→4–8, `coolBars` 1→0, plus loosening
or fully dropping the regime filters (`dirFilter`, `rangeMode`, `dayTrendFilt`,
`regimeSlack`, `rangeMaxSlope`). Measured with `replay_start` over a clean
~6-month window (2025-03-15 → ~Sep 2025) each time, so all counts below are
directly comparable, real 6-month figures:

| Config (5-minute) | Trades/6mo | Win% | PF |
|---|---|---|---|
| Level/count loosened only, regime filters (dtrend+bear) still on | ~80–90 | 34–36% | 0.97–1.03 |
| + `dayTrendFilt` off, regime filters still on | ~160–180 | 35–36% | 1.01–1.08 |
| + `rangeMode` off (dtrend only, slack −0.5) | ~257 | 32% | 0.87 |
| All regime filters off (`dirFilter`+`rangeMode` off) | ~330–400 | 30–31% | 0.74–0.75 |

**Honest read: there is no config that is both ≥200 trades/6mo and
profitable.** Trade count and edge trade off directly and predictably — every
lever that adds volume also dilutes signal quality, with no exception found.
The ~160–180/mo range (just under the ask) is the best *near-breakeven* point;
pushing past 200 requires dropping the regime filter chain almost entirely,
which lands at PF 0.87 (still a net loser after the 10pt/trade cost estimate)
and gets materially worse from there. This matches the standing repo finding
for this whole strategy family (see `bnf` notes above): a PDH/PDL and
swing-level rejection-fade has a **structural ceiling of roughly 0.5–1 genuinely
quality signal per day** on Nifty/BankNifty intraday data — there simply
aren't 1.5+/day real sweep-and-reject setups in this instrument at this kind
of statistical edge. Forcing volume past that ceiling doesn't reveal more
edge, it just adds noise trades.

**If 200+ trades/6mo is a hard requirement, this strategy *type* is the wrong
tool for it** — options going forward: (a) accept a lower, honest trade count
(~150–200/6mo, near-breakeven) if the goal is manual practice rather than a
live edge; (b) run this same setup on **multiple instruments/timeframes in
parallel** (e.g. Nifty + BankNifty + CrudeOil at once) to sum to higher
combined volume without individually forcing any one of them past its natural
ceiling; or (c) design a genuinely different, naturally higher-frequency
setup (e.g. a shorter-hold mean-reversion/scalp on 1–3m bars) rather than
tuning this one further — no parameter combination found here reaches volume
without giving up the edge.

### Running in parallel across Nifty + BankNifty + CrudeOil — the volume answer

User request: *"run it in parallel across Nifty, BankNifty and CrudeOil."*
Since no single strategy reaches 200 trades/6mo without giving up its edge
(see above), checked whether running each instrument's own best, already-
vetted strategy **simultaneously** sums to the target without diluting any
one of them individually.

| Instrument | Strategy | Trades/6mo | Win% | PF | Basis |
|---|---|---|---|---|---|
| Nifty (spot), 15m | `v2` sweep-fade | ~50–75 (avg of last 3 windows: 63) | 43–45% | 2.1–2.7 | 10-window walk-forward table above |
| BankNifty1!, 5m | `v13` sweep-fade "bear" | ~58 (9.7/mo × 6, live default window) | 34.4% | 1.56 | Fresh read via the script's own "Trades/month" stat |
| CrudeOil1!, 5m | `v1.0` EMA 9/22 pullback | ~122 (203 trades / ~10mo backtest) | 49% | 1.89 | Original v1.0 backtest — **⚠️ since shown to fail walk-forward, see below; do not rely on this row's PF/win%** |
| **Combined (3 instruments)** | — | **~240–255** | ~44% (trade-weighted, pre-CrudeOil-downgrade) | — | Sum of the three, run as separate positions |

**This clears the 200-trades/6mo bar** — comfortably, without loosening any
single strategy's filters or diluting its individual edge. The trade-off from
the earlier single-instrument tests goes away because the extra volume comes
from **adding independent instruments**, not from forcing more (worse)
signals out of one.

**Caveats to run this honestly:**
- These are **three separate positions on three separate instruments/
  contracts**, not one merged strategy — each needs its own capital
  allocation, margin, and order execution; nothing here nets them into a
  single account-level number automatically.
- **Correlation risk is not accounted for.** All three are Indian equity/
  index/commodity instruments that can all draw down on the same bad days
  (e.g. a market-wide risk-off event) — the ~240 trades are not 240
  independent bets.
- Each leg still carries its own **already-documented caveat**: Nifty v2 is
  "never catastrophic but 5 of 10 windows net-negative"; BankNifty v13-bear
  is "not robust across a full multi-year sample, loses ~-100 to -300/mo in
  strong-trend years"; CrudeOil v1.0 — **now confirmed by walk-forward (see
  below) to fail outright: 4 of 6 windows net losers, PF<1, three losing more
  than starting capital at its current qty=10 sizing.** Combining them for
  volume does not fix any of those individually — it only adds up their trade
  counts, and the CrudeOil leg specifically should not be run live as-is.
- The BankNifty and CrudeOil figures above come from different sample
  windows/methodologies (a live default-view read and an old 10-month
  backtest respectively) than Nifty's rigorous 10-window walk-forward, so the
  ~240-trade combined total is a reasonable estimate, not an apples-to-apples
  guarantee.

### Points captured per window — detailed results, all three legs

User request: *"show me detailed results, include how many points can be
captured under each strategy over 3 scripts"* / *"i want to see how each
strategy worked across different windows."* Fresh live reads (not re-derived
from earlier net/mo figures) of each script's own points scoreboard, window
by window.

**Nifty v2 sweep-fade, 15m — 10 windows, ~7.5 years (fresh re-read):**

| Window | Trades | Win% | PF | **Net pts** |
|---|---|---|---|---|
| ~Dec 2018–Apr 2019 | 53 | 39.6% | 1.30 | **−199** |
| ~Dec 2019–Jun 2020 (COVID) | 53 | 43.4% | 1.77 | **+334** |
| ~Dec 2020–Jun 2021 | 32 | 31.3% | 1.73 | **+381** |
| ~Dec 2021–Jun 2022 | 41 | 26.8% | 1.20 | **−88** |
| ~Dec 2022–Jun 2023 | 56 | 30.4% | 1.23 | **−87** |
| ~Oct 2023–Apr 2024 (worst) | 40 | 30.0% | 0.70 | **−808** |
| ~Apr–Oct 2024 | 33 | 42.4% | 1.50 | **+85** |
| ~Apr–Oct 2025 | 49 | 44.9% | 2.25 | **+1,025** |
| ~Oct 2025–Apr 2026 | 65 | 43.1% | 2.71 | **+2,418** |
| ~Feb–Sep 2026 (current) | 75 | 42.7% | 3.08 | **+3,618** |
| **10-window total** | **497** | **37.7% avg** | — | **+6,679 gross pts** |

That's raw index points, not ₹ — converting to ₹ needs the current Nifty lot
size (which changes periodically; not verified here, so no ₹ figure is
quoted). After the 10 pt/trade cost estimate (497 trades × 10 = 4,970 pts),
net is **+1,709 pts** over the full 7.5-year sample — and unevenly earned:
the first 6 windows (through mid-2024) net to roughly **−467 pts combined**,
all of the gain is concentrated in the last 3 (recent) windows.

**BankNifty v13 sweep-fade "bear", 5m — 5 windows, ~2.5 years (fresh live read
via the script's own points scoreboard):**

| Window | Trades | Win% | PF | Total pts | **Net pts (after 20/rt)** |
|---|---|---|---|---|---|
| ~Apr–Oct 2024 (strong uptrend) | 33 | 21.2% | 0.80 | −449 | **−1,109** |
| ~Dec 2024–Jun 2025 | 47 | 40.4% | 1.14 | +353 | **−587** |
| ~Apr–Oct 2025 | 50 | 46.0% | 2.00 | +2,021 | **+1,021** |
| ~Dec 2025–Apr 2026 | 37 | 29.7% | 2.31 | +3,144 | **+2,404** |
| ~Feb–Sep 2026 (current) | 76 | 35.5% | 1.74 | +3,397 | **+1,877** |
| **5-window total** | **243** | **34.6% avg** | — | **+8,466 gross** | **+3,606 net pts** |

As with Nifty, this is raw index points — no ₹ conversion is quoted since
BankNifty's lot size was not re-verified this session. Note the first window
(strong 2024 uptrend) alone cost −1,109 net pts, confirming the file's own
"not robust in trending years" warning; the next four windows are all
net-positive.

**CrudeOil v1.0 EMA 9/22 pullback, 5m** — this script tracks **₹ return, not
a points scoreboard** (unlike the other two). At the time this section was
first written, it was **not yet re-tested** this session (the original,
frozen ~10-month backtest was quoted as-is: 203 trades, 49% win, PF 1.89,
net +41.6% ≈ +₹41,600). **That has since changed — see the "CrudeOil v1.0
walk-forward" section immediately below, which found the +41.6% number does
NOT hold up out-of-sample.** Treat the figure in this paragraph as
superseded; the walk-forward section below is the current, more reliable
read on this strategy.

**Combined picture (all three, their own native windows, not aligned
calendar dates):** Nifty ≈ +1,709 net pts / 7.5yr, BankNifty ≈ +3,606 net pts
/ 2.5yr, CrudeOil — **no longer usable as a single "+₹41,600" headline; see
below.** None of these are apples-to-apples (different pt values, different
sample lengths, different verification rigor) — they are presented
separately, not summed, because summing points across three different
instruments with different lot sizes and point values would be a
meaningless number.

### CrudeOil v1.0 walk-forward — the single-window backtest does NOT hold up

User request: *"re-verify CrudeOil's backtest with a proper walk-forward."*
This is the first time this script has been walk-forward tested (every prior
mention in this repo flagged it as single-window/unverified). To avoid any
risk to the protected file (`USER;9a56139e9a5140c59ff4c7619517fdee`, must
stay at v162), its exact current source was read via `pine_get_source` and
pasted byte-for-byte into a throwaway script (`... WF TEST COPY`) — never
re-saved into or compiled onto the original. The original's version number
was reverified unchanged before and after.

6 windows tested on MCX:CRUDEOIL1! 5m, same default inputs as production
(₹100,000 capital, qty=10 lots — the config the +41.6% headline number came
from):

| Window | Trades | Win% | PF | **Net P&L** |
|---|---|---|---|---|
| ~Oct 2023–Apr 2024 | 79 | 40.5% | 0.86 | **−150.6%** |
| ~Apr–Oct 2024 | 132 | 39.4% | 0.97 | **−61.6%** |
| ~Dec 2024–Jun 2025 | 98 | 36.7% | 0.85 | **−224.7%** |
| ~Apr–Oct 2025 | 71 | 31.0% | 0.69 | **−304.7%** |
| ~Oct 2025–Apr 2026 | 199 | 46.7% | 1.73 | **+3,056.4%** |
| ~Feb–Sep 2026 (current) | 253 | 37.2% | 1.00 | **+17.6%** |

**This does NOT hold up.** 4 of 6 windows are net losers with PF < 1, three
of them losing more than the entire starting capital (−150% to −305%) —
numbers only possible in a backtest, since a real broker would have issued a
margin call and liquidated the account long before a loss like that. The one
big winning window (+3,056%) is an equally unrealistic swing in the other
direction. **Both extremes are a symptom of the same problem: `qty=10` lots
on ₹100,000 capital is heavily overleveraged** (flagged as ~25x leverage
earlier in this repo's history) — small edges get amplified into wild,
unstable equity-curve swings rather than steady compounding. The original
"+41.6%, PF 1.89, 49% win" headline number was one specific ~10-month
in-sample window, and it is now confirmed to be **not representative**: it
happened to fall in a stretch of the kind of trending move this EMA-pullback
concept needs, the same way the +3,056% window did here.

**Bottom line: CrudeOil v1.0 is downgraded from "the strong one" (its
original README billing) to "not robust — fails walk-forward," the same
verdict every BankNifty config reached in this repo.**

### CrudeOil v1.0 at qty=1 — same edge, sane leverage

User request: *"re-test CrudeOil at qty=1."* Same throwaway-copy method (the
original file was never reloaded/recompiled), same 6 windows, only
`default_qty_value` changed 10 → 1:

| Window | Trades | Win% | PF | qty=10 P&L | **qty=1 P&L** |
|---|---|---|---|---|---|
| ~Oct 2023–Apr 2024 | 79 | 40.5% | 0.86 | −150.6% | **−15.1%** |
| ~Apr–Oct 2024 | 132 | 39.4% | 0.97 | −61.6% | **−6.2%** |
| ~Dec 2024–Jun 2025 | 98 | 36.7% | 0.85 | −224.7% | **−22.5%** |
| ~Apr–Oct 2025 | 71 | 31.0% | 0.69 | −304.7% | **−30.5%** |
| ~Oct 2025–Apr 2026 | 199 | 46.7% | 1.73 | +3,056.4% | **+305.6%** |
| ~Feb–Sep 2026 (current) | 253 | 37.2% | 1.00 | +17.6% | **+1.8%** |

**Trades, win%, and PF are unchanged — qty is a pure position-size scalar,
it does not change which trades the strategy takes.** As expected, every P&L
number scales down by exactly 10x (qty=10 → qty=1 removes one zero). This
confirms the earlier read: leverage was never masking or revealing a
different *entry/SL* edge, it was only stretching the same win/loss sequence
into unrealistic swings. **De-leveraged, this is still 4 of 6 windows net
losers with PF < 1** — including one real loser (−30.5% in ~Apr–Oct 2025,
still a serious single-window drawdown for real capital) — against one large
winning window (+305.6%) and a flat-ish current window (+1.8%). **The
qty=1 re-test does not rescue the strategy: the underlying entry/SL concept
itself is what fails walk-forward, not merely its position sizing.** The
account-wiping/lottery-ticket *scale* of the numbers was a leverage artifact
and is now gone, but the *sign* and *consistency* problem — PF below 1 in
two-thirds of windows — is the concept, and remains.

### Cross-instrument generalization test — is Nifty v2's edge real or overfit?

Every result in this repo up to now was found by tuning separately per
instrument — which makes it impossible to tell whether an edge is real or
just curve-fit to that instrument's specific price history. The most
diagnostic test not yet run: take `v2`'s exact parameters **completely
unmodified** (no re-tuning, same code) and run them on sibling Indian
indices it has never seen. If the same untouched config holds up elsewhere,
that's real evidence of edge; if it falls apart, the whole result is
probably noise fitted to Nifty's particular path.

Tested on 15m, 3 comparable windows each (current/~Feb-Sep 2026, the
toughest window from Nifty's own walk-forward/~Oct 2023-Apr 2024, and the
best recent window/~Oct 2025-Apr 2026), **zero parameter changes**:

| Instrument | Window | Trades | Win% | PF | Net pts |
|---|---|---|---|---|---|
| **Nifty (reference)** | Current | 75 | 42.7% | 3.08 | **+3,618** |
| | Tough (Oct23-Apr24) | 40 | 30.0% | 0.70 | **−808** |
| | Recent (Oct25-Apr26) | 65 | 43.1% | 2.71 | **+2,418** |
| **FinNifty** (NSE:CNXFINANCE) | Current | 70 | 34.3% | 1.51 | **+908** |
| | Tough | 62 | 30.6% | 0.72 | **−1,403** |
| | Recent | 67 | 37.3% | 1.62 | **+1,047** |
| **Nifty Midcap Select** (NSE:NIFTY_MID_SELECT) | Current | 59 | 35.6% | 1.15 | **−299** |
| | Tough | 24 | 33.3% | 0.78 | **−333** |
| | Recent | 66 | 36.4% | 1.21 | **−254** |
| **Sensex** (BSE:SENSEX) | Current | 73 | 28.8% | 1.51 | **+1,683** |
| | Tough | 54 | 18.5% | 0.86 | **−1,095** |
| | Recent | 68 | 25.0% | 1.29 | **+509** |

**Read:**
- **All four instruments lose in the same "tough" window.** That's the
  strongest signal in this test — the regime filter (daily-SMA trend/bear
  gate) is picking up a genuine broad Indian-equity-market condition that
  hurts this concept everywhere, not a Nifty-specific artifact. A pure
  overfit to Nifty's price path would not be expected to fail on the same
  calendar dates across four different indices.
- **FinNifty and Sensex generalize directionally**: net-positive in both the
  current and recent windows, net-negative in the tough window — same
  *pattern* as Nifty, just weaker (lower PF/win% than Nifty itself in every
  window). This is moderate evidence of a real, modest, regime-linked
  effect rather than noise.
- **Nifty Midcap Select does NOT generalize** — net-negative in all three
  windows tested, including the two where every other index (Nifty
  included) was solidly positive. Midcap's smaller-cap, less-liquid
  constituents likely have a different microstructure (fewer/noisier PDH/PDL
  sweeps, different swing-level behavior) that this concept doesn't suit.

**Verdict: partial generalization.** This is not a strong, universal edge —
it's clearly Nifty-flavored (every sibling index underperforms Nifty
itself) and it outright fails on Midcap. But it is also not pure overfit
noise: 3 of 4 indices show the same directional pattern, on the same
calendar dates, with unmodified parameters. That's more consistent with a
real (if modest and index-family-specific) effect than with curve-fitting.
Reasonable next step per the earlier recommendation list: a volatility-
regime overlay targeting the still-unexplained tough-window loss, tested
against this same 4-index panel to see if it helps consistently rather than
just on Nifty again.

### "All-season, one strategy for all 3 scripts" search — result

User request: *"do not explore or test on anything other than banknifty,
nifty50 and crude. simulate through every parameter to find out an all
season strategy which can work on these 3 scripts."* Note on scope: "every
parameter" across a 20+ input strategy is an infinite search space, so this
was a **systematic, structured sweep** (candidate parameter bundles and
targeted single-variable tests aimed at cross-instrument consistency, not a
literal exhaustive search) — flagged upfront rather than silently narrowed.

**Data-floor discovery (changes what "all available data" means per
instrument):** checked exact history depth on this account for each
instrument/timeframe combo:
- **15-minute**: NSE:NIFTY, NSE:BANKNIFTY1!, and MCX:CRUDEOIL1! all floor at
  **~April 2019** (~7.5 years) — confirmed by clamped `replay_start` requests.
- **5-minute**: NSE:BANKNIFTY1! and MCX:CRUDEOIL1! floor at **~March 2024**
  (~2.5 years) — a hard vendor/retention limit, not a choice. 15-minute data
  is available for far longer than 5-minute data for both of these.
- This means "backtest all available data" is asymmetric by construction:
  Nifty has ~7.5yr at its native 15m; BankNifty's proven edge only exists at
  5m, capping its true full-history test at ~2.5yr; CrudeOil can be tested at
  15m for the full ~7.5yr, which is what made the "CrudeOil sweep-fade" test
  below possible.

**Attempt 1 — BankNifty's regime engine at 15m (its own native tuning):**
current window only: 89 trades, 37.1% win, PF 1.05, **−70/mo**. Fails — this
concept needs 5m to work at all on BankNifty; 15m does not carry the edge.

**Attempt 2 — Nifty v2's exact params, unmodified, on CrudeOil1! 15m, full
~7.5yr history (10 windows):**

| Window | Trades | Win% | PF | Net/mo |
|---|---|---|---|---|
| ~Dec 2018–Apr 2019 (partial) | 17 | 58.8% | 2.83 | −17 |
| ~Dec 2019–Jun 2020 (COVID) | 24 | 41.7% | 1.18 | −54 |
| ~Dec 2020–Jun 2021 | 10 | 40.0% | 1.29 | −22 |
| ~Dec 2021–Jun 2022 | 17 | 29.4% | 0.69 | −56 |
| ~Dec 2022–Jun 2023 | 42 | 28.6% | 0.63 | −137 |
| ~Oct 2023–Apr 2024 | 22 | 45.5% | 1.93 | −34 |
| ~Apr–Oct 2024 (worst) | 21 | **9.5%** | **0.23** | **−83** |
| ~Apr–Oct 2025 | 25 | 24.0% | 0.92 | −66 |
| ~Oct 2025–Apr 2026 | 20 | 20.0% | 0.54 | −65 |
| ~Feb–Sep 2026 (current) | 25 | 36.0% | 1.92 | −6 |

**9 of 10 windows net-negative.** The sweep-fade concept does not transfer
to CrudeOil — confirming and extending the earlier single-window/triage
note in this repo ("CrudeOil1! 15m mildly positive on one window but failed
2 of 3 older windows") with a full 10-window picture. Combined with the
already-documented EMA-9/22-pullback failure (also 4 of 6 windows negative,
see above), **CrudeOil has now failed walk-forward under two different
concept families** tested against it this session.

**Verdict: no single "all-season" configuration was found that works
acceptably on all three scripts.** BankNifty and CrudeOil each need their
own timeframe and tuning to show any edge at all (5m and — per this test —
nothing, respectively), and even Nifty's own config, unmodified, does not
survive contact with CrudeOil's full history. This is consistent with, not
contradictory to, the cross-instrument generalization test earlier in this
doc (Nifty's edge partially transfers to *sibling equity indices*, but nothing
here suggests it should transfer to a commodity with fundamentally different
drivers). **There is no evidence, after this search, that a single unified
strategy across Nifty + BankNifty + CrudeOil exists in this concept family.**
The realistic path forward is what the final table below already reflects:
three separate, differently-tuned strategies, one of which (Nifty) is a
genuine lead and two of which are not yet validated.

## Three-instrument, three-timeframe final recommendation

### Master comparison — every strategy, every script, this whole project

| Instrument | Timeframe | Strategy / version | History tested | Trades | Win% | PF | Net result | Verdict |
|---|---|---|---|---|---|---|---|---|
| **Nifty (spot)** | 15m | `v2` sweep-fade, Nifty-tuned | 10 windows, ~7.5yr (Apr19–Sep26) | 497 | 37.7% avg | 0.70–3.08 by window | **+1,709 net pts** (5/10 windows negative, worst −808) | **Best result in repo — promising, not proven** |
| Nifty (spot) | 15m | `v3` RR-2.4 tune (on request) | Same 10 windows | 544 | 42.2% avg | 0.96–2.55 | Net pts not separately tallied per-window; net/mo positive in last 3 windows, hits ~50% win rate there | Lower expectancy than v2 in most windows; ships only if hitting a specific win-rate matters |
| Nifty (spot) | 15m | Unmodified `v2` on FinNifty/Sensex/Midcap | 3 windows each | — | — | 0.69–3.08 | FinNifty & Sensex positive-directional; **Midcap fails all 3** | Partial generalization — real but modest, Nifty-family-specific |
| **BankNifty1!** | 5m | `v13` sweep-fade "bear", native tuning | 5 windows, ~2.5yr (full 5m history — hard data-retention floor) | 243 | 34.6% avg | 0.80–2.31 | **+3,606 net pts** (1/5 windows negative, that one −1,109 in a strong 2024 uptrend) | Regime-conditional — good outside strong trends, untested pre-2024 (no 5m data exists) |
| BankNifty1! | 15m | `v13` engine, native params | Current window only | 89 | 37.1% | 1.05 | **−70/mo** | **Fails — this concept needs 5m, not 15m** |
| **CrudeOil1!** | 5m | `v1.0` EMA 9/22 pullback, qty=10 (production) | 6 windows, ~2.5yr (full 5m history) | 832 | ~38% avg | 0.69–1.73 | Wild swings −305% to +3,056% | **Fails — the +41.6% original number was one lucky window** |
| CrudeOil1! | 5m | `v1.0` same, qty=1 (de-leveraged) | Same 6 windows | 832 | ~38% avg | 0.69–1.73 (unchanged) | Same swings ÷10: −30.5% to +305.6% | **Still fails — leverage wasn't the problem, the entry logic is** |
| CrudeOil1! | 15m | Sweep-fade, Nifty `v2` params (unmodified) | 10 windows, ~7.5yr (full 15m history) | 223 | ~33% avg | 0.23–2.83 | 9 of 10 windows net-negative | **Fails — concept does not transfer to crude at all** |

**Bottom line on the whole repo:** No mechanical BankNifty **3m** edge survived
walk-forward. `v13` "bear" is BankNifty's least-bad config but not
multi-year-robust (and its only provable window is the last 2.5 years — that's
all the 5m data that exists); ported to **Nifty spot at 15m it becomes the
strongest result in the repo**, the only config that's never catastrophic
across a full 7.5-year sample. **CrudeOil has now failed walk-forward twice**,
under both concept families tested against it (EMA-pullback and sweep-fade),
across both its available timeframes. **Nothing here is a validated, durable
mechanical strategy** — the Nifty 15m result is a genuine lead worth manually refining
(entry/SL/exit marked on chart for exactly that); everything else is a research
note. Forward-test on paper before risking capital.
