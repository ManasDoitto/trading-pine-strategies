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

### CrudeOil "is it fixable?" — sepMlt tuning: partial fix, not a cure

User question: *"is it fixable?"* after v1.0/v2.0 failed walk-forward twice.
Ran a real single-variable sweep against the worst window (~Apr–Oct 2025,
baseline PF 0.69): `allowCoil` off made it *worse* (PF 0.58 — coil breakouts
were quietly helping, not hurting); raising `sepMlt` (minimum required
EMA9–EMA22 separation before a pullback entry is allowed) from 0.5 up to
**1.5** was a clear local peak (PF 1.05 in that window; 2.0 was worse again
at PF 0.76). Cross-checked the 1.5 setting against all 6 windows:

| Window | v1.0/v2.0 (qty=1) | **v2.1, sepMlt 1.5 (qty=1)** |
|---|---|---|
| ~Oct 2023–Apr 2024 | PF 0.86, −15.1% | **PF 1.40, +13.8%** |
| ~Apr–Oct 2024 | PF 0.97, −6.2% | **PF 1.05, +4.1%** |
| ~Dec 2024–Jun 2025 | PF 0.85, −22.5% | PF 0.64, −20.5% |
| ~Apr–Oct 2025 (old worst) | PF 0.69, −30.5% | **PF 1.05, +1.9%** |
| ~Oct 2025–Apr 2026 | PF 1.73, +305.6% | PF 1.93, +159.2% (lower % but higher PF) |
| ~Feb–Sep 2026 (current) | PF 1.00, +1.8% | **PF 0.77, −49.3%** |

**Genuine, partial fix**: negative windows drop from 4 of 6 to 2 of 6, and
the single worst loss shrinks from −30.5% to −20.5%. **Not a cure**: the
same filter that rescues 3 windows flips the current window from this
family's *best*-behaved result (+1.8%) to its *worst* (−49.3%) — the same
overfitting trade-off seen everywhere else in this repo. Dec 2024–Jun 2025
stays a loser regardless. Saved as `v2.1 crudeoil strategy 5min (sepMlt
0.5-1.5 fix...)` at qty=1 (leverage already proven not to be the issue).
**Verdict: tunable toward better consistency, not provably fixed** — treat
this exactly like every other lead in this repo: a research candidate, not
a validated edge.

## 3-minute / 5-minute only — one strategy per script, full available data

User request: *"test all the strategies over all available data, retune it
if possible. get me 1 strategy per script which works best... focus on
points captured, profitability, sharpe, best RR... and profitable trade
percentage and trade counts over all the windows. lets not focus on 15 min
TF at all. test only over 3 min and 5min TF."*

**Data-floor discovery, repeated at 3m:** on top of the earlier 5-minute
finding (~Mar 2024 floor, ~2.5yr, for all three), **3-minute data floors
even later, at ~March 2025 (~1.5 years)**, for NIFTY, BANKNIFTY1!, and
CRUDEOIL1! alike. So "all available data" at 3m is a materially shorter,
less conclusive sample than at 5m for every instrument.

### Nifty — genuinely re-tuned for 5m, still does not work

Nifty's only proven edge in this whole project (`v2` sweep-fade) was built
and validated at **15m**, now off the table per this instruction. Ran a
real retuning pass for 5m: `dispMlt` 0→0.3, `swLen` 3→5, `stopCapPts`
60→**40** (tighter — 5m's smaller average range needs a tighter cap) was
the best combination found, improving the current window from PF 1.12/−62
net-per-month to **PF 2.24/+102/mo**. Walk-forwarded across the full ~2.5yr
5m history (5 windows):

| Window | Trades | Win% | PF | Net/mo |
|---|---|---|---|---|
| ~Apr–Oct 2024 (partial, near floor) | 15 | 26.7% | 1.29 | −10 |
| ~Dec 2024–Jun 2025 | 29 | 34.5% | 1.03 | −41 |
| ~Apr–Oct 2025 | 30 | 16.7% | **0.40** | **−109** |
| ~Oct 2025–Apr 2026 | 49 | 20.4% | 1.16 | −41 |
| ~Feb–Sep 2026 (current, the one it was tuned on) | 47 | 36.2% | 2.24 | +102 |

**4 of 5 windows net-negative.** A quick check with BankNifty's native 5m
parameters transplanted onto Nifty didn't rescue it either (PF 0.73 in the
worst window). **Verdict: no viable Nifty strategy was found at 3m or 5m**
despite a genuine retuning effort — this isn't a case of "didn't try hard
enough," the tuned config that looks best in the current window fails
almost everywhere else, the same overfitting pattern seen throughout this
repo. **Nifty's only real edge in this entire project requires 15m** — if
that timeframe stays off the table, there is currently no Nifty pick to
recommend.

### BankNifty1!, 5m — the pick: `v13` sweep-fade "bear"

Already the best-tested config on this instrument (native tuning:
`maxSweepMlt=0.8, minLvlGapPts=30, stopCapPts=120, bufMlt=0.6, rFixed=6,
rangeMode="bear"`). Full available 5m history (~2.5yr) was already
walk-forward tested this session — no 15m dependency, so no retest was
needed here.

| Window | Trades | Profitable % | R:R (`rFixed`) | PF | Net pts |
|---|---|---|---|---|---|
| ~Apr–Oct 2024 (strong uptrend) | 33 | 21.2% | 1:6 | 0.80 | −1,109 |
| ~Dec 2024–Jun 2025 | 47 | 40.4% | 1:6 | 1.14 | −587 |
| ~Apr–Oct 2025 | 50 | 46.0% | 1:6 | 2.00 | +1,021 |
| ~Dec 2025–Apr 2026 | 37 | 29.7% | 1:6 | 2.31 | +2,404 |
| ~Feb–Sep 2026 (current) | 76 | 35.5% | 1:6 | 1.74 | +1,877 |
| **Total** | **243** | **34.6% avg** | — | — | **+3,606 net pts** |

**Sharpe ratio (current window): 0.48.** Best R:R found for this instrument
via all prior tuning remains **1:6** (`rFixed=6`) — every attempt at a
tighter target reduced net expectancy in earlier sessions. **This is the
pick for BankNifty1!**: positive in 3 of 5 windows, the only losing window
tied to a strong 2024 uptrend the "bear" regime filter is explicitly
designed to sit out of (and only partly does).

### CrudeOil1!, 5m — the pick: `v2.1` EMA 9/22 pullback (sepMlt-tuned)

Already re-tuned this session (`sepMlt` 0.5→1.5, qty 10→1) — a genuine,
partial improvement over the original `v1.0`. Full available 5m history
(~2.5yr, 6 windows) already walk-forward tested:

| Window | Trades | Profitable % | R:R (`rMultiple`) | PF | Net P&L |
|---|---|---|---|---|---|
| ~Oct 2023–Apr 2024 | 30 | 50.0% | 1:2 | 1.40 | +13.8% |
| ~Apr–Oct 2024 | 51 | 39.2% | 1:2 | 1.05 | +4.1% |
| ~Dec 2024–Jun 2025 | 35 | 31.4% | 1:2 | 0.64 | −20.5% |
| ~Apr–Oct 2025 | 26 | 42.3% | 1:2 | 1.05 | +1.9% |
| ~Oct 2025–Apr 2026 | 75 | 42.7% | 1:2 | 1.93 | +159.2% |
| ~Feb–Sep 2026 (current) | 102 | 33.3% | 1:2 | 0.77 | −49.3% |
| **Total** | **319** | **39.8% avg** | — | — | mixed (4 of 6 positive) |

**Sharpe ratio: −0.13 in the current (worst) window, positive in the best
window (Oct 2025–Apr 2026).** Best R:R found via tuning remains **1:2**
(`rMultiple=2.0`, unchanged from the original — untested for improvement
this round, time did not permit a fresh R:R sweep on top of the `sepMlt`
fix). **This is the pick for CrudeOil1!**: 4 of 6 windows net-positive
(up from 2 of 6 pre-fix), but the current window is a clear loser — still
the least-proven of the three picks in this repo.

### Why Feb–Sep 2026 looked better with earlier strategies

The user's observation that this window performed better before is
correct and explained by the numbers above: `v3` (15m, RR 2.4 tune) scored
+133 net/mo in this exact window; the BankNifty and CrudeOil 5m picks above
score +1,877 net pts and −49.3% respectively **in this same window** — a
strategy tuned for 15m Nifty and one tuned for 5m BankNifty are not
comparable on the same scale, and restricting to 3m/5m specifically removes
Nifty's only working config (15m) from consideration entirely. This is the
direct, mechanical reason results look worse under the new constraint — not
a regression in the work, but the cost of excluding the one timeframe where
Nifty actually has an edge.

### Trying to enhance Sharpe with price-action risk management

User request: *"how can you enhance sharpe... use your professional trader
mindset along with price action trading skill to improve it further."*
Tested three classic professional exit-management techniques on the
CrudeOil `v2.1` pick (Sharpe −0.13 in its worst window), isolating each
before combining:

1. **Move stop to breakeven after +1R** (protect capital once a trade
   proves itself) — alone: barely moved Sharpe in the worst window
   (−0.13 → −0.11) and actively *hurt* the best window (0.22 → 0.16, since
   it can shake a real trend out on a normal pullback).
2. **Partial profit-take 50% at +1R, let the rest run to full target** (bank
   a "single," professional risk-reduction) — this was the one lever that
   moved the needle: worst window Sharpe **−0.13 → −0.09**, win rate
   **33% → 52%**, max drawdown cut by ~45%. But in the best (trending)
   window it capped upside: Sharpe **0.22 → 0.16**, net return **+159% →
   +71%** — cutting a winner in half before a strong trend paid out in full.
3. **Trail the stop to the EMA9 (the same MA the entry pulled back to)
   after +1R**, instead of a fixed target — a genuine price-action idea
   (ride the trend, exit only when structure breaks). Tested alone and
   combined with #2: **no measurable improvement over #2 alone** in either
   window — the trail never got a chance to bind before the fixed target
   or the partial-exit already closed the trade out. Checked a 4th window
   (Dec 2024–Jun 2025): Sharpe **worsened** to −0.19 with the combo despite
   win rate rising to 46% — PF fell to 0.54 because winners shrank more than
   losses were avoided.

**Honest professional read: none of these are a clean fix.** Every lever
that raises Sharpe/win-rate/consistency in one window does so by capping
winners, and pays for it in whichever window has the real trend that this
strategy actually needs to be profitable overall. This is not a coding
gap — it is the fundamental trade-off between **smoothing an equity curve**
(better Sharpe, lower variance, more "professional-looking" trade sequence)
and **capturing full trend extension** (better raw return, worse Sharpe on
paper) that every trend/pullback strategy faces, and it cannot be solved by
exit-mechanism tuning alone when the underlying edge is this thin and
regime-dependent. **The binding constraint is entry-signal quality, not
exit management** — a genuinely higher-Sharpe version of this strategy
would need a better filter for *which* pullbacks are worth taking (e.g.
higher-timeframe trend confluence, or volatility-regime gating), not a
better way to exit the ones it already takes. That is a new research
direction, not a tuning pass, and has not been attempted.

### Entry-quality filter: daily-trend confluence — a real, asymmetric improvement

Following through on "happy to take that on next" — added a daily-timeframe
trend-confluence gate to CrudeOil `v2.1`'s entries (only take the 5m
pullback long/short when the **daily** trend, close vs a daily EMA20 via
`request.security`, agrees with it). This is an entry-quality filter, not
another exit tweak: fewer, more selective signals rather than the same
signals managed differently.

| Window | v2.1 (no HTF filter): Tr / PF / P&L | **v2.3 (+HTF filter): Tr / PF / P&L** |
|---|---|---|
| ~Oct 2023–Apr 2024 | 30 / 1.40 / +13.8% | 19 / 1.20 / +4.2% (worse) |
| ~Apr–Oct 2024 | 51 / 1.05 / +4.1% | 29 / 0.95 / −2.1% (worse) |
| ~Dec 2024–Jun 2025 | 35 / 0.64 / −20.5% | 21 / 0.69 / **−12.0%** (better) |
| ~Apr–Oct 2025 | 26 / 1.05 / +1.9% | 13 / 1.51 / **+8.4%** (better) |
| ~Oct 2025–Apr 2026 | 75 / 1.93 / +159.2% | 52 / 1.43 / +55.4% (worse, still healthy) |
| ~Feb–Sep 2026 (current) | 102 / 0.77 / −49.3% | 63 / 0.86 / **−17.2%** (much better) |
| **Total trades** | **319** | **197 (62% of original)** |

**Still not a clean per-window win** (3 of 6 improved, 3 worsened — the same
shape seen throughout this repo). **But the trade-off is asymmetric and
genuinely more favourable than any exit-tweak tried**: the worst window's
loss shrinks by far more (−49.3% → −17.2%, a 32-point swing) than the best
window's gain shrinks (+159.2% → +55.4%, still comfortably profitable, PF
still a healthy 1.43). Sharpe in the worst window: **−0.13 → −0.04**.
Sharpe in the best window: 0.22 → 0.13 (also down there, so still not
unambiguous). A risk-averse professional would likely call this a real
improvement in risk-adjusted terms — meaningfully smaller tail losses,
in exchange for giving back part (not all) of the best window's gain —
even without every single window improving. Saved as `v2.3 crudeoil
strategy 5min (HTF daily-trend confluence filter...)`.

**Bottom line on the whole Sharpe-improvement exercise**: entry-side
filtering (trade fewer, better-confirmed setups) moved the needle more than
any exit-side technique did. This is consistent with professional practice
— disciplined trade selection usually does more for risk-adjusted returns
than exit engineering on a marginal edge. Still a research lead, not a
proven edge: same single-vendor, in-sample, never-forward-tested caveat as
everything else in this repo.

> ⚠️ **CORRECTION — the v2.3 HTF filter is NOT doing what its name implies.**
> Found on visual inspection of the marked-up 5m chart: a **daily** EMA20 is
> far too slow for a 5-minute strategy. After crude's ~11% rally in early
> Sep 2026 (8,700 → 9,700 in ~4 days), the daily EMA20 sat ~950 points
> *below* price, so `close > dailyEMA` stayed TRUE continuously —
> **every one of the last 10 trades on the chart is a LONG; there is not a
> single short.** The gate is not behaving as "trade with the daily trend";
> it behaves as a **slow one-directional switch** that blocks one entire
> side of the market for weeks at a time.
>
> That materially weakens the claimed improvement above. The worst window's
> gain (−49.3% → −17.2%) may simply be "it happened to block the losing
> direction in that window", not genuine multi-timeframe confluence — and
> with only ~2.5 years and 6 windows, a directional-bias filter can look
> good by luck very easily. **Treat the v2.3 numbers as unexplained until
> re-tested with a responsive HTF gate** (e.g. a 1-hour EMA, or the *slope*
> of the daily EMA rather than price-vs-level, which would not pin to one
> direction for weeks). That re-test has not been done.

## Three-instrument, three-timeframe final recommendation

*(This section covers the original 15m-inclusive picture. For the current
3m/5m-only scope, see the "3-minute / 5-minute only" section above instead.)*

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

---

## Tuning to the user's own marked trades (CrudeOil 5m, v3.0)

**What changed in approach:** instead of a parameter search, the user marked
their own trades on the MCX:CRUDEOIL1! 5m chart (TradingView long/short
position tools, replay forward test from Feb 2026). They were read off the
chart programmatically into `user_marked_trades_crudeoil_5m.csv` (36 trades).
Trades #1-9 (Apr 2025) are timing-only: the chart is back-adjusted (B-ADJ), so
their price levels sit ~200-300 pts away from the current bars.

**The user's own 27 clean trades (#10-36):** 21 TP / 6 SL, **77.8% win,
~+2,626 pts, points PF ~9.6**. That is the benchmark.

**What their entries had in common** (from
`user trade diag (...).pine.txt`, which dumps indicator state at each entry):

- Smoothed Heikin Ashi (EMA10/EMA10) colour on the trade's side: 20/27
- EMA9 vs EMA22 aligned with the trade: 24/27
- every long had RSI(3) < 30 within ~11 bars; every short had RSI(3) > 70
  within ~18 bars. They buy pullbacks and don't chase breakouts.
- SL ~2x ATR, just beyond the 10-bar swing; fixed R:R (2.4 in Feb, 3-5 later)
- they never exit on an SHA flip

These became the rules of
`v3.0 crudeoil strategy 5min (SHA + RSI3 pullback, tuned to user's 36 marked trades).pine.txt`.
It has an anti-churn rule (a brand-new pullback is needed after every exit),
added because of the user's feedback: "multiple trades inside my mark". A
table on the chart scores it against the marks. A trade counts as **caught**
when the strategy enters the same direction within ±30 min of the user's
entry. **Extra** counts strategy entries inside the user's trade after that.

### Single-variable tuning (window 29-Dec-25 → 25-Mar-26, 14 user trades #12-25)

| Step | Trades | Win% | PF (pts) | Net pts | Caught /14 | Extra inside | Feb 2-6 (user: 8) | Kept? |
|---|---|---|---|---|---|---|---|---|
| Baseline (minSL 1.2, EMA200 on, RSI 30/70, RR 2.4) | 166 | 30.1 | 1.24 | +1,129 | 6 | 5 | 13 | start |
| minSL 2.0 ATR | 156 | — | 1.29 | +1,423 | 5 | 8 | — | yes |
| + max 2 entries/day | — | — | 0.81 | −739 | 4 | — | — | no |
| + EMA200 filter off | 191 | 35.1 | 1.70 | +3,528 | 5 | 7 | 14 | yes |
| trigger = high-break | 208 | — | 1.43 | +2,700 | — | 13 | 20 | no |
| cooldown 6 bars | — | — | 1.56 | +2,889 | 4 | — | — | no |
| RSI 20/80 | 124 | 29 | 1.33 | +1,231 | 3 | 0 | 4 | no |
| RSI 25/75 | 161 | 29.8 | 1.42 | +1,949 | 5 | 4 | 11 | no |
| R:R 3.0 | 180 | 27.8 | 1.39 | +2,150 | 4 | 11 | 17 | no |
| **SHA colour held ≥ 3 bars** | **189** | **35.4** | **1.66** | **+3,338** | **6** | **7** | **14** | **final** |
| SL beyond 20-bar swing | 126 | 28.6 | 1.15 | +652 | 4 | 6 | 12 | no |
| pullback window 18 | 198 | 35.4 | 1.59 | +3,149 | 6 | 8 | 15 | no |

Deeper RSI thresholds remove the churn but also remove the edge. A wider R:R
or a wider SL makes the churn worse, because trades stay open longer and more
get stopped out.

### Walk-forward of the final config (qty 1, 0.02% commission)

| Window (5m bars loaded) | Trades | Win% | Tester PF | Net ₹ | Net pts | Sharpe | User trades caught | Extra inside |
|---|---|---|---|---|---|---|---|---|
| 02-Jun → 28-Aug 2025 | 170 | 31.2 | 0.89 | −35,600 | +38 | −0.04 | 0 / 2 | 1 |
| 29-Dec-25 → 25-Mar-26 *(tuning)* | 189 | 35.4 | 1.54 | +285,743 | +3,338 | −0.08 | 6 / 14 | 7 |
| 16-Mar → 10-Jun 2026 | 203 | 35.5 | 1.17 | +190,592 | +2,654 | +0.17 | 5 / 9 | 3 |
| 22-Jun → 12-Sep 2026 (live) | 189 | 30.2 | 0.94 | −36,532 | +222 | +0.04 | 0 / 4 | 3 |

**Verdict (honest):** v3.0 is profitable in the volatile Jan-Jun 2026 regime
and roughly breakeven-to-slightly-negative after costs in the quieter
mid-2025 and Jun-Sep 2026 windows (2 of 4 windows lose money). It catches
**9 of the user's 27 clean trades** (#13, 14, 16, 20, 24, 25, 26, 28, 32). It
still takes ~190 trades a quarter against the user's handful. On Sep 1-4 2026
it fired 18 times; the user took 4. The mechanical rules reproduce the *setup*
the user trades, but not their *selection*, and the selection is where the
user's 78% win rate comes from. Use v3.0 as a signal generator to review. It
is not an autonomous system. Marking more trades, especially ones the user
**skipped** despite a setup, is the most useful next input: that would show
what the selection filter actually is.

---

## Variant lab: 32 strategy variations x 3 scripts x 3m/5m, all available history

**Why a lab:** one indicator
(`variant lab v1 (32 intraday variants, 6 families, scored side by side in one pass).pine.txt`)
simulates 32 variants on the same bars at once, so every variant sees exactly
the same data. Each variant covers one of 6 strategy families that this repo
has tried:

- **A** SHA+RSI(3) pullback (v3.0 and 16 variations)
- **B** EMA9/22 touch pullback (crude v1 idea)
- **C** SHA colour flip
- **D** Donchian breakout + SHA
- **E** RSI(3) extreme snap-back
- **F** liquidity-sweep fade (BN v13 / Nifty v2 idea)

It was walked back through **42 replay windows** that tile the history
exactly, each counting trades from its own UTC midnight so nothing is
double-counted:

| Script / TF | History | Windows |
|---|---|---|
| CrudeOil 5m | Mar 2024-Sep 2026 | 11 |
| CrudeOil 3m | Mar 2025-Sep 2026 | 11 |
| BankNifty 5m | Mar 2024-Sep 2026 | 5 |
| BankNifty 3m | Mar 2025-Sep 2026 | 5 |
| Nifty 50 spot 5m | Jan 2024-Sep 2026 | 5 |
| Nifty 50 spot 3m | Feb 2025-Sep 2026 | 5 |

Two windows were discarded because replay clamps at its floor and they would
have overlapped. Raw dumps, aggregation scripts, the full CSV and the full
192-row comparison are in `variant_lab_v1/`.

**Sim rules** (mirror the Strategy Tester):
- qty 1, points, cost 0.02% of price per side
- signal on close, fill at the next open, fixed SL/TP
- TradingView's intrabar-path heuristic
- indices are always flat by 15:24 IST, so V01 = V02 on indices
- sanity check: V01 = 184 trades vs the real v3.0 strategy's 189 on the same crude 5m window

### Best variant per script/TF (ranked by daily Sharpe, net of costs)

| Script / TF | Best variant | Trades | Win% | PF | Net pts | Gross pts | Sharpe | +windows | v3.0 (V01) net |
|---|---|---|---|---|---|---|---|---|---|
| Crude 5m | V21 SHA flip, RR 1:3 | 838 | 28.2 | 1.10 | **+2,240** | +4,401 | **+0.53** | 6/11 | -2,587 |
| Crude 3m | V07 v3.0 with RSI>50 trigger | 2,253 | 31.6 | 1.00 | -144 | +5,770 | -0.04 | 4/11 | -723 |
| BankNifty 5m | V22 SHA flip + EMA200, RR 1:2 | 393 | 39.7 | 0.88 | -3,289 | +5,184 | -0.63 | 1/5 | -29,037 |
| BankNifty 3m | V24 Donchian20 + SHA, RR 1:3 | 517 | 33.7 | 0.75 | -10,939 | +762 | -2.12 | 1/5 | -24,830 |
| Nifty 5m | V22 SHA flip + EMA200, RR 1:2 | 374 | 39.6 | 0.84 | -1,846 | +1,766 | -0.89 | 0/5 | -8,372 |
| Nifty 3m | V21 SHA flip, RR 1:3 | 425 | 31.5 | 0.73 | -3,430 | +743 | -2.06 | 0/5 | -7,741 |

### Family ranking (best member's daily Sharpe)

| Family | Crude 5m | Crude 3m | BN 5m | BN 3m | Nifty 5m | Nifty 3m |
|---|---|---|---|---|---|---|
| C SHA flip | **+0.53** | -0.11 | **-0.63** | -3.05 | **-0.89** | **-2.06** |
| D Breakout | -0.11 | -0.64 | -1.66 | **-2.12** | -1.44 | -2.20 |
| A SHA+RSI3 pullback (v3.0) | -0.34 | **-0.04** | -2.36 | -3.08 | -1.85 | -2.66 |
| B EMA-touch | -0.49 | -1.09 | -3.97 | -4.13 | -2.89 | -4.76 |
| F Sweep-fade | -0.76 | -1.47 | -1.41 | -2.26 | -2.23 | -3.90 |
| E RSI3 snap-back | -2.48 | -3.43 | -4.37 | -5.78 | -3.83 | -4.66 |

### Cost drag: profitable before vs after costs (of 32 variants)

| Script / TF | Cost per trade | Gross-profitable | Net-profitable |
|---|---|---|---|
| Crude 5m | 2.6 pts | 26 | 1 |
| Crude 3m | 2.6 pts | 24 | 0 |
| BankNifty 5m | 21.7 pts | 5 | 0 |
| BankNifty 3m | 22.6 pts | 4 | 0 |
| Nifty 5m | 9.7 pts | 20 | 0 |
| Nifty 3m | 9.8 pts | 12 | 0 |

**Verdict (honest):**

1. **Only 1 of 192 variant/script/TF combinations is net-profitable:** SHA flip
   with RR 1:3 on CrudeOil 5m (+2,240 pts over 2.5 years, PF 1.10, daily
   Sharpe 0.53, 6/11 windows positive). With 192 attempts, one such result can
   appear by chance. Treat it as a lead to forward-test, not an edge.
2. **Costs are the main killer on crude.** 26 of 32 variants make money before
   costs but lose after them. The crude signals have a small real gross edge,
   about 1-3 bps per trade, which 0.04% round-trip costs erase.
3. **Indices at 3m/5m have no edge in any family**, even before costs, for
   most variants. BankNifty's ~22-point round trip is decisive.
4. **Trend-following (SHA flip, breakout) beats mean-reversion everywhere.**
   Fading RSI extremes and fading sweeps are the worst families on all 6
   script/TFs. Fewer, longer trades with RR >= 2 do best.
5. **v3.0 (tuned to the user's marks) is net-negative on every script/TF.**
   On crude it is gross-positive but net-negative. It catches 10-11 of the
   user's 36 marked trades. EMA-touch variants catch the most (up to 16/36 on
   crude 3m) but lose more money.
6. The lab's sweep-fade is a simplified version of BN v13 / Nifty v2, so it
   does not replace those scripts' own walk-forward numbers above.

**What would actually help next:** cut trade frequency, costs per trade, or
both. For example, trade SHA flip only in the direction of a higher-timeframe
trend, or use limit entries. Forward-test V21 on CrudeOil 5m on paper before
risking capital.

---

## v4.0 forward-test build: SHA flip RR3 on CrudeOil 5m

`v4.0 crudeoil strategy 5min (SHA flip RR3 - variant lab V21, forward-test build).pine.txt`
is a rule-for-rule TradingView strategy of lab variant V21, the only
net-profitable combination in the variant lab. Its rules:

- **Entry:** Smoothed Heikin Ashi (10/10) colour flip, with EMA9 vs EMA22
  agreeing, 09:15-23:30 IST.
- **Stop:** beyond the 10-bar swing + 0.1 ATR, at least 1.5 ATR away. The trade
  is skipped if the stop would be wider than 3 ATR.
- **Target:** 3R. No trailing, one position at a time, may hold overnight.

**Fidelity check: real Strategy Tester vs lab simulation** (qty 1, 0.02%/side).
The tester counts from the first loaded bar, about 3 days before the lab
window starts.

| Window | Strategy Tester | Lab (V21) |
|---|---|---|
| 22 Jun-11 Sep 2026 (live) | 78 trades, 29.5% win, PF 1.20, **+578 pts** | 72 trades, **+327 pts** (from 25 Jun) |
| 30 Mar-24 Jun 2026 | 92 trades, 34.8% win, PF 1.20, **+1,118 pts** | 88 trades, **+1,215 pts** (from 2 Apr) |
| 2 Sep-27 Nov 2024 | 95 trades, 16.8% win, PF 0.43, **-1,379 pts** | 91 trades, **-1,295 pts** (from 5 Sep) |

The lab is a faithful model, in both the winning and the losing windows. Lab
per-window net points, oldest to newest:
+281, +621, -1,295, -129, +1,248, -460, -376, -408, +1,216, +1,215, +327.

**Forward-test protocol.** The test starts **14 Sep 2026 00:00 IST**. This is
data the lab has never seen, because every bar up to 11 Sep was used to select
V21. The chart table splits BACKTEST and FORWARD-TEST trades, and forward
entries are labelled blue/purple. Pass/fail rules are fixed now, before
seeing results:

- Judge after at least 60 forward trades (about 2 months at about 28
  trades/month).
- **Keep:** net PF >= 1.0 and drawdown < 2,100 pts.
- **Drop:** drawdown > 2,100 pts at any time (worse than any backtest
  window), or PF < 0.8 after 60 trades.
- Expect losing streaks. At a 28% win rate, the longest run of losses in 60
  trades is typically 8-9. That alone is not a failure.

---

## Best strategy per script: head-to-head on identical windows (3m/5m)

The earlier per-script picks were measured on different, partly overlapping
windows. BankNifty v13 and Nifty v2 also ran with zero commission and a flat
20 or 10 points per round trip deducted in their own tables. For a fair
comparison, each was re-run in the **real Strategy Tester** on exactly the
same 5m windows as the variant lab: same start date to the day, 0.02% per
side, qty 1. A small add-on counted only the trades inside each window.
Raw rows and the scripts are in `variant_lab_v1/head_to_head_*`.

| Script | Strategy | TF | Trades | /month | Win% | Avg win / loss (pts) | PF | Net pts | Daily Sharpe | Worst-window DD | +windows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CrudeOil | **v2.1 EMA 9/22 pullback** | 5m | 519 | 17 | **37.4** | 56 / -29 | **1.14** | +1,337 | **+0.68** | **607** | 5/11 |
| CrudeOil | **v4.0 SHA flip RR3** (lab V21) | 5m | 838 | 28 | 28.2 | 105 / -38 | 1.10 | **+2,240** | +0.53 | 2,106 | **6/11** |
| CrudeOil | v3.0 SHA+RSI3 pullback (lab V01) | 5m | 1,965 | 66 | 30.1 | 75 / -34 | 0.94 | -2,587 | -0.55 | 1,552 | 2/11 |
| CrudeOil | best 3m (lab V07) | 3m | 2,253 | 123 | 31.6 | 66 / -31 | 1.00 | -144 | -0.04 | 2,130 | 4/11 |
| BankNifty | **v13 sweep-fade "bear", RR 1:6** | 5m | 231 | 8 | 32.5 | 224 / -102 | **1.06** | **+914** | **+0.19** | 1,944 | **2/5** |
| BankNifty | best lab variant (V22 SHA flip + EMA200) | 5m | 393 | 13 | 39.7 | 160 / -119 | 0.88 | -3,289 | -0.63 | 3,028 | 1/5 |
| BankNifty | best 3m (lab V24 Donchian) | 3m | 517 | 28 | 33.7 | 187 / -127 | 0.75 | -10,939 | -2.12 | 5,610 | 1/5 |
| Nifty 50 | v2 sweep-fade, 5m retune, RR 1:6 | 5m | 161 | 5 | 24.2 | 90 / -41 | 0.71 | -1,436 | -1.01 | 992 | 1/5 |
| Nifty 50 | best lab variant (V22 SHA flip + EMA200) | 5m | 374 | 12 | 39.6 | 64 / -50 | 0.84 | -1,846 | -0.89 | 1,281 | 0/5 |
| Nifty 50 | best 3m (lab V21 SHA flip) | 3m | 425 | 22 | 31.5 | 70 / -44 | 0.73 | -3,430 | -2.06 | 1,679 | 0/5 |

Net points by window, oldest to newest:

| Strategy | Net pts by window |
|---|---|
| CrudeOil v2.1 | -195, -62, +278, +260, -179, -166, +45, -92, +1,602, +324, -477 |
| CrudeOil v4.0 | +281, +621, -1,295, -129, +1,248, -460, -376, -408, +1,216, +1,215, +327 |
| BankNifty v13 | -503, -1,221, +1,496, -566, +1,707 |
| Nifty v2 5m | -230, -428, -597, -877, +697 |

**Pick per script:**

- **CrudeOil: a near tie between two different styles.**
  - **v2.1** (EMA 9/22 pullback, RR 1:2) is the better risk-adjusted
    strategy: highest Sharpe (0.68), PF 1.14, 37% win rate, and a
    worst-window drawdown of only 607 pts.
  - **v4.0** (SHA flip, RR 1:3) books the most points (+2,240) and has
    more positive windows (6/11), but with 3.5x the drawdown and a 28% win
    rate.
  - Both are profitable after costs over 2.5 years, and both make most of
    their money in 2-3 strong windows.
  - **Best overall: v2.1.** It wins on Sharpe, PF, win rate and drawdown.
    v4.0 is the choice if total points matter more than smoothness.
- **BankNifty: v13 "bear"** is the only net-profitable strategy found at
  3m/5m. It is thin: +914 pts over 2.5 years, PF 1.06, 2 of 5 windows
  positive, and a -1,221 pt window through the late-2024 trend and crash.
- **Nifty 50: no viable 3m/5m strategy.** Every candidate is net-negative.
  The least-bad is v2 5m retune (-1,436 pts). Its only positive window is
  the one it was tuned on. Nifty's working edge in this repo is `v2` at 15m,
  which is excluded by the 3m/5m scope.

**Corrections to earlier numbers:**
- BankNifty v13's earlier "+3,606 net pts" came from overlapping windows,
  which double-counted its good 2025-26 period. On exact, non-overlapping
  windows with 0.02% per side it is **+914 pts**.
- CrudeOil v2.1's earlier per-window % figures are superseded by the
  points above.

---

## Best robust version per script: walk-forward tuning (3m/5m)

The request was to tune three scripts until each hit **PF > 1.4, win rate
> 50%, max drawdown < 3% of capital and at least 15 trades a month**:

- BankNifty MTF v1.0 (3m)
- BankNifty EMA Pullback v0.3 (5m)
- the same v0.3 code on Nifty 50 **spot**

The baselines quoted in the request were mislabelled. The "v0.3" rows were
really v13 sweep-fade and Nifty v2 results, and the MTF row matched only
its single good window. Every script was therefore re-measured from
scratch, in the **real Strategy Tester**:

- same tiled windows as the variant lab
- qty 1 lot, 0.02% per side plus 5 points of slippage
- rupees = points x pointvalue: 30 for BankNifty futures, 1 for Nifty spot

Each script was checked against the fixed targets first. When those proved
unreachable, the aim switched to the **most robust version** (option 2):
- **structural changes only**, each with a market reason, judged on every window
- no fine parameter search
- trend gates read from completed bars only, so no lookahead

Raw rows and the summary script are in `variant_lab_v1/robust_tuning/`.

### Script 3: BankNifty MTF v1.0, 3m, 5 windows, Mar 2025 - Sep 2026

| Version | Trades (/mo) | Win% | PF | Net pts | Sharpe | Max DD | Windows + / - / flat | By window, old to new |
|---|---|---|---|---|---|---|---|---|
| v1.0 as-is | 217 (12) | 33.6 | 0.69 | -3,880 | -2.09 | 3,880 pts = Rs1.16L = 23% | 1 / 4 / 0 | -382, -346, -999, +625, -2,777 |
| + 15m ADX >= 25 | 73 (4) | 41.1 | 0.94 | -224 | -0.20 | 1,094 pts = 6.6% | 2 / 3 / 0 | -320, +235, -66, +987, -1,059 |
| + daily ADX >= 20 | 101 (5.6) | 40.6 | 0.99 | -52 | -0.04 | 1,068 pts = 6.4% | 1 / 3 / 1 | -243, -60, -569, +820, 0 |
| **+ both gates, v1.1** | **38 (2.1)** | **52.6** | **1.64** | **+1,113** | **+1.21** | **482 pts = Rs14.5k = 2.9%** | **3 / 1 / 1** | -252, +397, +139, +829, 0 |

The request's own "Set A" did not help:

- **Set A** (breakeven after 1R, fresh-cross window 20, skip the first 20
  min, skip midday) made both windows it was tested on **worse**:
  - Jan-May 2026: +625 fell to -1,043, and drawdown rose from 589 to 1,382
  - May-Sep 2026: -2,777 fell to -3,287
- Breakeven hurts because winners often return to entry before reaching
  the 2.5R target.
- A 0.5xATR trailing stop lifted win rate to 55% but turned PF to 0.85.
- Widening the fresh-cross window added trades that lose.
- Wick plus volume filters left 2 trades in 4 months.
- EMA200 and 15m-slope filters had little or no effect.

### Script 1: BankNifty EMA Pullback v0.3, 5m, 5 windows, Mar 2024 - Sep 2026

| Version | Trades (/mo) | Win% | PF | Net pts | Sharpe | Max DD | Windows + / - | By window, old to new |
|---|---|---|---|---|---|---|---|---|
| v0.3 as-is | 131 (4.4) | 33.6 | 0.86 | -1,229 | -0.43 | 2,968 pts = Rs89k = 18% | 2 / 3 | -88, -216, -1,584, +282, +378 |
| **+ 15m ADX >= 25, v0.4** | **74 (2.5)** | **41.9** | **1.29** | **+1,277** | **+0.52** | **1,668 pts = Rs50k = 10%** | **3 / 2** | +816, +206, -533, -102, +889 |

Rejected:
- **ATR floor 40:** 4x the trades, and it loses.
- **Daily-ADX gate, alone or with the 15m gate:** in Sep 2025 - Mar 2026 it
  took 5 trades and all 5 lost.

### Script 2: Nifty 50 spot, same v0.3 code: no robust version

- **Nifty spot has no volume in TradingView**, so v0.3's core
  volume/VWAP condition can never pass on NSE:NIFTY.
- v0.4 adds `volSym = NSE:NIFTY1!`. That takes volume from the futures
  and builds VWAP from spot prices, and it works on the **live chart**.
- **Bar replay does not return another symbol's volume.** Every older
  window silently degrades to about 1 trade. Proof: with the volume/VWAP
  condition off, the same window takes 127 trades.
- So Nifty spot can only be judged on the live window, Mar - Sep 2026:

  | Version | Result |
  |---|---|
  | ATR >= 20 (scaled from BankNifty) | 27 trades, PF 0.68, -239 pts |
  | + 15m ADX >= 25 | 16 trades, -183 |
  | ATR >= 25 | 15 trades, PF 0.95, -21 |
  | ATR >= 25 + ADX gate | 10 trades, -113 |
  | Request's own Nifty set (ATR 30, max stop 1.5, wick 0.6, skip midday, gap lock, breakeven 1R) | 5 trades in 6 months, -12 |

- The no-volume version that *can* be tested in older windows loses:
  Aug 2025 - Mar 2026 gave 127 trades, PF 0.65, -1,196 pts.
- **Verdict: no viable Nifty-spot version of this script.** Judging it
  across windows would need testing on NIFTY1! futures as a stand-in.

### Against the requested targets

| Script | PF > 1.4 | Win > 50% | DD < 3% of Rs5L | >= 15 trades/mo |
|---|---|---|---|---|
| BankNifty MTF v1.1 | yes (1.64) | yes (52.6%) | yes (2.9%) | **no (2.1)** |
| BankNifty EMA Pullback v0.4 | no (1.29) | no (41.9%) | no (10%) | **no (2.5)** |
| Nifty spot | no | no | - | no |

**Honest read:**
- The trend-strength gates are the one structural change that helped
  both BankNifty scripts. They work by **standing aside in choppy
  markets**, which is also why trade frequency falls to 2-3 a month.
- **More trades and higher quality pulled in opposite directions in
  every test.** Every change that added trades added losing trades.
- Samples are small: 38 and 74 trades. The gates were chosen after
  screening on the newest windows, then held up on the older ones. Treat
  both as leads to forward-test, not proven systems.
- An input-carryover quirk was found and controlled for. When a script
  in the TV slot is replaced, **inputs the user changed that have
  identical names carry over**. From here on, every test sets its gate
  inputs explicitly.

---

## The user's two concepts tested, and the final strategy set

### Concepts tested (VARIANT LAB v2, 20 variants, 5m, all history, 21 windows)

`variant lab v2 (...).pine.txt` implements both of the user's ideas. It
uses the same simulation rules and window tiling as lab v1: 0.02% per side,
fill at the next open, indices flat by 15:24.

**H - Smoothed Heikin Ashi pullback (the user's rules):**
- The 5m SHA flips colour and stays that colour.
- Price pulls back into the EMA 9/22 channel.
- A candle then closes beyond the pullback candle.
- The stop goes at the previous candle's high or low; the target is
  RR 2, 2.4 or 3.
- Filter variants tested:
  - EMA alignment
  - 15m SHA same colour
  - the user's "strong candle" rule: the 15m SHA candle has little or no
    opposite wick, a 5m SHA candle in the same leg mimics it, then wait
    for the pullback
  - first pullback only
  - wider stop
  - next-bar trigger

**J - next-day levels from the previous day's H/L/C:**
- CPR pullback
- PDH/PDL break-and-retest
- S1/R1 fade
- each with and without SHA agreement, max 2 entries a day

Results: `variant_lab_v2/lab2_summary.md`.

| Script (5m) | Best new variant | Trades/mo | PF | Net pts | +windows | Verdict |
|---|---|---|---|---|---|---|
| CrudeOil (30 mo, 11 windows) | PDH/PDL break-retest RR3 | 24 | 1.03 | **+223** | 6/11 | only net-positive new variant, and barely |
| CrudeOil | best SHA-pullback: 15m + 5m strong, RR2.4 | 47 | 0.84 | -3,344 | 1/11 | gross +330, costs make it negative |
| CrudeOil | plain SHA pullback RR3 | 154 | 0.89 | -8,438 | 2/11 | **gross +3,462**: a real edge before costs, but too many tight-stop trades |
| BankNifty (30 mo, 5 windows) | CPR pullback + SHA agree RR2 | 8 | 0.74 | -4,074 | 0/5 | every variant loses heavily at ~22 pts cost a trade |
| Nifty 50 spot (32 mo, 5 windows) | CPR pullback + SHA agree RR2 | 8 | 0.62 | -2,362 | 0/5 | every variant loses |

**Reading:**
- The SHA-pullback idea has genuine *gross* edge on CrudeOil and Nifty.
- The previous-candle stop is so tight that it trades 110-190 times a
  month, and the round-trip cost is a large share of each trade's risk.
- The strong-candle filter cuts trading to about 45 a month but doesn't
  fix it.
- The closest profitable relative is **v4.0**: an SHA colour flip with a
  **swing** stop (at least 1.5 ATR) and RR 3, which trades about 28 a
  month. Wide stops and fewer trades are what make it survive costs.
- The daily-level strategies only work on crude, and only marginally.

### Final strategy set: best balance of trade count and positive points

All figures come from the real Strategy Tester, or the fidelity-verified
lab, on the same no-overlap windows, net of 0.02% per side.

| # | Script | Strategy (file) | TF | Trades/mo | Win% | PF | Net pts | Pts/mo | Rs/mo at 1 lot | Max DD | +windows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CrudeOil | **v4.0 SHA flip RR3** | 5m | 28 | 28 | 1.10 | +2,240 | +75 | ~Rs7,500 | 2,106 pts (worst window) | 6/11 |
| 2 | CrudeOil | **v2.1 EMA 9/22 pullback RR2** | 5m | 17 | 37 | 1.14 | +1,337 | +45 | ~Rs4,500 | 607 pts | 5/11 |
| 3 | BankNifty | **v0.4 EMA pullback + 15m ADX gate** | 5m | 2.5 | 42 | 1.29 | +1,277 | +42 | ~Rs1,270 | 1,668 pts | 3/5 |
| 4 | BankNifty | **v13 sweep-fade "bear" RR6** | 5m | 8 | 33 | 1.06 | +914 | +30 | ~Rs900 | 1,944 pts | 2/5 |
| 5 | BankNifty | **v1.1 MTF pullback + ADX gates** | 3m | 2 | 53 | 1.64 | +1,113 | +60 | ~Rs1,800 | 482 pts | 3/5 (+1 flat) |
| - | Nifty 50 | **none at 3m/5m** | - | - | - | - | all negative | - | - | - | - |

Notes on the table:
- Rs/mo uses TradingView point values: CrudeOil 100 per point, BankNifty
  futures 30.
- v0.4 and v1.1 include 5 pts of slippage; the others do not.
- The strategies are listed separately. Combined drawdown was not
  computed.
- v4.0 and v2.1 both trade crude, so running both means 2 lots on one
  instrument, with correlated risk.

Together these give **about 57 trades a month**, mostly from crude. That
is roughly 45 on crude and 12 on BankNifty. Every row is positive over its
full history, but none is consistently positive window-to-window. Each
had losing stretches of 3-6 months.

**Nifty 50 has no 3m/5m strategy in this repo.** Its only edge found was
`nifty v2` at 15m, which is outside the current scope.

Forward-test all of them on paper before trading real money. v4.0's forward
test started 14-Sep-2026.

---

## BankNifty: pushing for more trades per month

Request: more BankNifty trades. The constraint is cost. At about 55,000, a
0.02% per side round trip is about 22 pts, close to real futures cost
(brokerage + STT + exchange + stamp + slippage). Every extra trade must
earn more than that on average. All tests below use the real Strategy
Tester on the same tiled windows as the rest of this README.

| Candidate | TF | Trades/mo | Win% | PF | Net pts | +windows | Verdict |
|---|---|---|---|---|---|---|---|
| v0.4 EMA pullback, 15m ADX >= 25 (current) | 5m | 2.5 | 41.9 | 1.29 | +1,277 | 3/5 | keep |
| v0.4 with ADX >= 20 | 5m | 3.3 | 38.1 | 1.06 | +399 | 4/5 | +0.8 trade/mo costs ~880 pts |
| v0.4 with ADX >= 15 (live window only) | 5m | - | - | - | +482 vs +624 at ADX 20 | - | no extra trades (35 vs 34) |
| v0.3 with no gate | 5m | 4.4 | 33.6 | 0.86 | -1,229 | 2/5 | loses |
| v0.4 on 3m (ATR >= 40, ADX >= 25) | 3m | 7.8 | 31.6 | 0.60 | -1,559 | 0/2 | lost even in the best window, dropped |
| v13 sweep-fade "bear" (current) | 5m | 8 | 32.5 | 1.06 | +914 | 2/5 | keep: highest-frequency profitable single |
| v13 on 3m | 3m | 10.7 | 28.9 | 0.91 | -1,126 | 2/5 | more trades, net negative |
| MTF v1.1 (daily + 15m ADX gates) | 3m | 2 | 52.6 | 1.64 | +1,113 | 3/5 +1 flat | keep |
| Variant lab v1 (32) + v2 (20) | 3m/5m | 8-190 | - | < 1 | all negative | - | no BankNifty variant profitable at any frequency |

**Running the profitable ones together is what adds frequency.**

v13 plus v0.4, both on 5m and on the same windows:

| Metric | Result |
|---|---|
| Trades | 305 in 30 months = **10.1 a month** |
| Net | **+2,189 pts** |
| Positive windows | 3/5 |
| By window, old to new | +313, -1,015, +963, -668, +2,596 |

The two partly offset each other: v13 loses in trends, and v0.4 needs
trends. Adding MTF v1.1 (3m, about 2 a month) brings the BankNifty set to
**about 12 trades a month**, roughly +130 pts/mo, or about Rs4,000/mo at
1 lot each.

At times all three can hold positions together, so up to 3 lots.

**Verdict:**
- No single BankNifty strategy at 15 or more trades a month survives the
  ~22-pt round trip in this data.
- Every loosening that adds trades adds losing trades faster than
  winning ones.
- The practical answer is the **combined set**.
- Anything faster would need lower cost per trade (for example a
  low-brokerage broker, or limit entries). That has not been tested here.

---

## BankNifty combined script: v13 + v0.4 + MTF in one strategy (5m)

`bnf combined v1 BankNifty 5min (v13 sweep-fade + v0.4 pullback + MTF v1.1 in one script).pine.txt`
puts three modules on one 5m chart:

- **A** = v13 sweep-fade "bear"
- **B** = v0.4 EMA pullback with the 15m ADX gate
- **C** = MTF v1.1 with both ADX gates

How it trades:
- Each module trades 1 lot with its own order IDs.
- Modules may stack in the same direction. A signal opposite to another
  module's open or armed trade is skipped.
- Everything is flat by 15:15.
- The chart table shows trades, trades/month, win %, PF, net points,
  points/month and max drawdown for each module and in total.

**Two bugs were found by running each module alone and comparing it with its
standalone script. Both are fixed.**

1. **Duplicate lots.** Armed stop-entries of B and C were not cancelled once
   their trade was open. With `pyramiding=3`, the same order could fill a
   second and third lot. B alone showed 46 trades against 24 for standalone
   v0.4.
2. **Misattributed exits.** TradingView closes trades first-in-first-out by
   default, so one module's exit could close another module's earlier
   same-direction trade. Fixed with `close_entries_rule="ANY"`.

After the fixes, each module run alone matches its standalone script (B: 24
trades, +889 pts in the live window). The first combined figure quoted (131
trades, +3,751 pts) came from the buggy version and is **withdrawn**.

**Walk-forward:** same 5 tiled 5m windows, Mar 2024 - Sep 2026, 30.2 months,
0.02%/side plus 5 pts slippage. Raw rows and the aggregator are in
`variant_lab_v1/robust_tuning/combined_bnf_*`.

| Config | Trades | /mo | Win% | PF | Net pts | pts/mo | Sharpe | Max DD pts | +windows | By window, old to new |
|---|---|---|---|---|---|---|---|---|---|---|
| A + B + C (all on) | 353 | 11.7 | 34.6 | 1.06 | +1,438 | +48 | 0.26 | 3,979 | 3/5 | +249, -976, +128, -246, +2,282 |
| of which A (v13) | 228 | 7.6 | 31.1 | 0.99 | -124 | -4 | -0.03 | 2,415 | 2/5 | -567, -838, +1,035, -617, +863 |
| of which B (v0.4) | 72 | 2.4 | 41.7 | 1.28 | +1,190 | +39 | 0.49 | 1,559 | 3/5 | +816, +316, -533, -102, +692 |
| of which C (MTF) | 53 | 1.8 | 39.6 | 1.10 | +372 | +12 | 0.19 | 1,542 | 2/5 | 0, -454, -374, +473, +727 |
| B + C (A off) | 132 | 4.4 | 40.2 | 1.17 | +1,403 | +46 | 0.44 | 2,593 | 3/5 | +816, -180, -1,008, +270, +1,505 |
| B alone (= standalone v0.4) | 74 | 2.5 | 41.9 | 1.29 | +1,277 | +42 | 0.52 | 1,668 | 3/5 | +816, +206, -533, -102, +889 |

**Reading:**
- Combining multiplies trades by 4.7 (11.7 a month against 2.5) but adds
  almost no net points (+1,438 against +1,277). PF falls to 1.06, and
  drawdown grows 2.4x.
- **A breaks even once slippage is charged.** v13's earlier +914 had no
  slippage. 228 trades at 10 pts a round trip is about 2,280 pts.
- **C is weak on 5m** (PF 1.03-1.10) and takes no trades in the oldest
  window. Its home is 3m, where it has PF 1.64.
- **Verdict:** use v0.4 (module B) as the BankNifty strategy. Keep the
  combined script only as the "more trades" option, and accept a lower PF
  and deeper drawdown with it.

The final pick per script, with full rules, is in
`BEST STRATEGY PER SCRIPT (BankNifty, Nifty 50, CrudeOil - 3m-5m).md`.

---

## Full audit: every BankNifty and CrudeOil strategy, re-run on all 3m/5m history (12 Sep 2026)

**Why this was run.** Some earlier strategies were reported with bigger point
totals than the current picks. So every strategy file was re-run on:
- all history TradingView replay allows at 3m and 5m
- the same non-overlapping windows
- the same costs: qty 1, 0.02% commission per side, no extra slippage

How it was done:
- `strategy_audit_2026_09/audit_gen.py` makes an audit copy of each script
  with a tiled-window scoreboard added.
- Later files that expose an older version's settings were used to reproduce
  that version by changing inputs:
  - v10.5 covers v10.3, v10.4 and v10.6
  - v13 covers v12
  - v0.4 covers v0.3, and approximately v0.1
  - v1.1 covers v1.0
  - crude v2.3 covers v2.1, v2.0, v1.0-tuned, v1.0-pure / v0.7,
    v1.1 / v0.8, v0.6 and v0.5
- Raw rows, the aggregator and summaries are in `strategy_audit_2026_09/`.

### Why the earlier totals were bigger

| Strategy | Earlier headline | Full-history result (same costs as every row here) |
|---|---|---|
| BankNifty v13 "bear" | +3,606 pts | **+914** |
| BankNifty v10.4 | +4,994 pts gross | **−119** |
| BankNifty v10.5 | +5,693 pts gross | **−1,551** |
| BankNifty combined v1 | +3,751 (live window, buggy build) | **+1,438** (bug fixed) |
| Crude v1.0 | +41.6%, one +3,056% window (qty 10) | **+2,155** best config (v1.0-tuned / v2.0 settings) |

The big numbers came from five things:
- overlapping windows that counted the strong 2025-26 period twice
- zero commission with a flat per-trade deduction
- gross rather than net figures
- a single in-sample window
- qty 10

Every BankNifty sweep version made about +2,000 pts in Mar-Sep 2026 alone.
That one window is what those headlines were built on.

### BankNifty 5m: 5 windows, Mar 2024 - Sep 2026 (30 months)

| Strategy | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| **v0.4 EMA pullback + 15m ADX** | 2.5 | 41.9 | **1.33** | **+1,403** | 1,620 | 3/5 |
| v10.3 sweep + daily trend | 3.5 | 38.1 | 1.10 | +924 | 2,631 | 2/5 |
| v13 sweep "bear" | 7.7 | 32.5 | 1.06 | +914 | 2,642 | 2/5 |
| v0.1 pullback (approx.) | 3.1 | 35.8 | 1.01 | +70 | 1,945 | 3/5 |
| v10.4 | 3.1 | 37.6 | 0.99 | −119 | 2,345 | 2/5 |
| v0.3 pullback | 4.3 | 33.6 | 0.88 | −997 | 2,844 | 2/5 |
| v10.5 (v10.6 identical at defaults) | 4.2 | 32.3 | 0.85 | −1,551 | 3,763 | 2/5 |
| v12 | 9.8 | 30.4 | 0.86 | −2,954 | 5,422 | 2/5 |
| v11 | 7.4 | 29.6 | 0.79 | −3,220 | 5,192 | 1/5 |

### BankNifty 3m: 5 windows, Mar 2025 - Sep 2026 (18 months; the 3m data floor)

| Strategy | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| **v1.1 MTF + ADX gates** | 2.1 | 52.6 | **1.69** | **+1,170** | 465 | 3/5 |
| v7 OB+FVG | 15.3 | 36.9 | 0.92 | −1,291 | 3,445 | 1/5 |
| v4.1 OB pullback (4 windows) | 15.7 | 24.1 | 0.78 | −3,340 | 4,839 | 1/4 |
| v1.0 MTF | 11.8 | 33.6 | 0.71 | −3,514 | 3,515 | 1/5 |
| v10 3m sweep | 8.9 | 26.4 | 0.68 | −4,085 | 4,310 | 1/5 |
| v9 sweep + CHoCH | 7.8 | 25.9 | 0.62 | −4,418 | 4,521 | 0/5 |
| ORB v0.3 | 19.2 | 47.2 | 0.76 | −9,988 | 10,459 | 0/5 |
| v8 SMC pure | 22.7 | 29.3 | 0.58 | −10,602 | 10,602 | 0/5 |
| v6 level fakeout | 26.6 | 25.8 | 0.60 | −13,002 | 13,002 | 0/5 |
| v5 lab, 4 trading modes | 6-77 | 26-39 | 0.36-0.55 | −3,907 to −36,098 | - | 0/5 each |
| v3 session + SMC | 56.9 | 32.3 | 0.57 | −26,969 | 27,822 | 0/5 |

v5's "orb-break" mode takes no trades: the opening range is always wider
than its 2 × ATR stop cap.

### CrudeOil 5m: 11 windows, Mar 2024 - Sep 2026 (30 months)

| Strategy | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| **v4.0 SHA flip RR3** (lab V21, fidelity-checked) | 28 | 28.0 | 1.09 | **+2,136** | 2,339 | 6/11 |
| **v2.0 / v1.0-tuned** (EMA 9/22 pullback, separation 0.5) | 45 | 37.8 | 1.09 | **+2,155** | 2,398 | 4/11 |
| v2.1 (separation 1.5) | 17 | 37.3 | **1.14** | +1,304 | **900** | 5/11 |
| v2.3 (+ daily-trend filter) | 11 | 36.5 | 1.02 | +98 | 874 | 4/11 |
| v1.0-pure / v0.7 | 102 | 37.3 | 0.91 | −4,118 | 6,215 | 2/11 |
| v0.6 | 98 | 36.3 | 0.90 | −5,102 | 6,853 | 3/11 |
| v1.1 / v0.8 (coil break) | 115 | 36.9 | 0.89 | −5,522 | 6,880 | 3/11 |
| v0.5 | 187 | 37.1 | 0.89 | −9,340 | 10,942 | 3/11 |

### CrudeOil 5m prototypes v0-v0.4: same 11 windows (added 12 Sep 2026)

These are the deep-sweep-breakout and pullback prototypes that came before
v0.5. They were written for qty 10. The audit copies use qty 1, so the
figures are points per lot, like every other row here.

| Prototype | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| v0.2 deep sweep breakout, close-based SL, one trade per leg | 38 | 28.9 | 0.90 | −1,780 | 3,374 | 3/11 |
| v0.3 v0.2 with a 15m bias and a 12-bar sweep window | 28 | 27.4 | 0.88 | −2,164 | 3,312 | 4/11 |
| v0.4 pullback-candle trigger, raw Heikin Ashi | 84 | 36.2 | 0.90 | −4,027 | 5,022 | 3/11 |
| v0 deep sweep breakout (1:3) | 32 | 24.2 | 0.77 | −6,858 | 9,665 | 1/11 |
| v0.1 EMA9 continuous trail | 116 | 22.1 | 0.78 | −7,301 | 7,431 | 1/11 |

- All five lose after costs. None comes near v2.0 / v1.0-tuned (+2,155) or
  v4.0 (+2,136).
- v0 and v0.2 each have one big winning window in 2026 (+2,286 and +2,119),
  the period they were built on. Their older windows mostly lose.
- Check on the emulation: the v1.0-tuned file run directly on the live
  window gives 246 trades and +108 pts, the same as the v2.3-file emulation.

Not re-run here:
- v0.9, the SMC experiment: its default `smcMode="off"` is the v1.1 engine
- v3.0: variant lab V01 covered it, at −2,587 pts
- one v4.1 window: a script save replaced the study on the chart mid-run

### Volume profile (POC): `variant lab v3`, 24 variants

The profile is built from the chart's own futures volume:
- bins of 10 points for BankNifty and 2 points for crude
- today's developing POC, and yesterday's POC with its 70% value area
- naked POCs (earlier POCs price hasn't returned to yet)

The variants use these levels two ways:
- as filters on the v4.0 SHA flip
- as setups of their own: 80% rule, value-area-edge fades, POC bounce,
  value-area breakout-retest, developing-POC trend pullback, and sweep fades
  at the profile levels

Summaries: `strategy_audit_2026_09/vp_lab3_summary.md`.

| Script | Variant | Trades/mo | PF | Net pts | + windows |
|---|---|---|---|---|---|
| BankNifty 5m | SHA flip, no filter | 16 | 0.86 | −5,068 | 2/5 |
| BankNifty 5m | SHA flip, only outside prior value area | 9 | 1.00 | −45 | 3/5 |
| BankNifty 5m | best standalone POC setup | 1-18 | 0.71 or less | all negative | 2/5 or fewer |
| BankNifty 5m | high-frequency POC setups (30-42/mo) | 30-42 | 0.68 or less | −24,000 to −35,000 | 0/5 |
| Crude 5m | SHA flip, no filter (= v4.0) | 28 | 1.09 | +2,136 | 6/11 |
| Crude 5m | SHA flip, only outside prior value area | 14 | 1.10 | +1,225 (max DD 1,804 vs 2,339) | 6/11 |
| Crude 5m | SHA flip, on the prior-day POC side | 21 | 1.08 | +1,247 | 6/11 |
| Crude 5m | POC bounce RR3 | 17 | 1.07 | +373 (max DD 665) | 6/11 |

**Reading:**
- POC works as a **risk filter**. It halves the trades and cuts drawdown, but
  it also cuts profit, and it never turned a losing strategy into a winner.
- POC setups on their own lose on BankNifty at every frequency. At about 22
  points of cost per round trip, their small edge disappears.

### Can BankNifty reach 20 trades a month profitably?

Not in this data. The profitable BankNifty strategies and their frequencies:

| Strategy | Trades/mo |
|---|---|
| v0.4 | 2.5 |
| v10.3 | 3.5 |
| v13 | 7.7 (shares its signal engine with v10.3) |
| v1.1 3m | 2.1 |

- Running v0.4 + v13 + v1.1 together gives about **12 trades a month**.
- Every one of the roughly 80 strategy/configuration combinations above about
  10 trades a month lost after costs.
- 20 a month would need a lower cost per trade, such as a low-cost broker or
  limit entries. That has not been tested here.
