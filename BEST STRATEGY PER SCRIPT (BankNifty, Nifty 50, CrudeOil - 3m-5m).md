# Best strategy per script: BankNifty, Nifty 50, CrudeOil, Gold, Silver (3m / 5m)

> **Scope note (14 Sep 2026):** this doc's title still says the original three
> instruments, but it now also covers **Gold (MCX:GOLD1!)** and
> **Silver (MCX:SILVER1!)**, added 14 Sep 2026 -- see sections 5 and 6. Filename
> unchanged so existing cross-references (README.md, the dashboard) still resolve.

This document picks **one strategy per script** from everything built and
tested in this repo. Each pick is meant to balance four things:

1. total points made
2. number of trades
3. profit factor (PF)
4. staying profitable across time windows

Written 12 Sep 2026. Every number below is **net of costs** and was measured
in the real TradingView Strategy Tester (or a lab that was checked against it).

- Windows are tiled with no overlap, covering all the 3m/5m history TradingView
  replay allows.
- Size is 1 lot, with 0.02% commission per side. BankNifty also has 5 points of
  slippage per fill.
- Rupees = points x point value. The point value is 100 for CrudeOil, 30 for
  BankNifty futures (1 lot) and 1 for Nifty spot.


> **Audit update (12 Sep 2026).** Every BankNifty and crude strategy file was
> re-run on all history with identical costs. See the README section "Full
> audit" and `strategy_audit_2026_09/`.
> - **BankNifty:** the picks stand. v0.4 is +1,403 pts over 30 months, PF
>   1.33, with no extra slippage charged. MTF v1.1 on 3m is +1,170 pts, PF
>   1.69.
> - **Crude:** v1.0-tuned / v2.0 (the EMA 9/22 pullback with separation 0.5)
>   **ties v4.0 on points**: +2,155 vs +2,136. It trades 45 times a month
>   against 28, at the same PF of 1.09. v2.1 stays the smoother choice: PF
>   1.14, max drawdown 900.
> - **Volume profile (POC):** it cuts drawdown and trade count but does not add
>   points.
> - No profitable BankNifty setup was found at 20 or more trades a month.
> - Crude prototypes v0-v0.4 were re-run on the same 11 windows. All five
>   lose (−1,780 to −7,301 pts), so the crude picks do not change.

> **Audit update (14 Sep 2026).** Deep multi-day retuning exercise: tested
> v4.0's exact logic on new instruments, ran a proper train/holdout validation
> against overfitting, and instrument-tuned Gold and Silver for the first time.
> - **Gold and Silver are new to this doc.** Both are net-profitable with
>   v4.0's SHA-flip logic, and both improved further with light instrument
>   tuning. See sections 5 and 6.
> - **Silver is now the best result in the entire repo by profit factor**:
>   wide ATR stops (calibrated for silver's higher ATR/price ratio) plus a
>   fixed 350-point daily loss circuit breaker reaches **PF 1.35**, ahead of
>   BankNifty v0.4's 1.33 -- though on a much shorter track record (2.7
>   months of live-equivalent testing vs BankNifty's years, and one huge
>   2026 window still carries most of the total). Treat as promising, not a
>   replacement for v0.4 as the "most proven" pick.
> - **Crude v4.0 got a genuine, validated improvement**: raising the target
>   from 3R to 4R lifts PF 1.09→1.12 and net points +2,136→+2,811 at
>   essentially the same trade frequency. This is now the crude v4.0 pick,
>   not a copy of the original 3R version. Nothing else moved the needle
>   positively on crude -- a 15m ADX trend gate (BankNifty v0.4's structural
>   trick) was tried and made crude *worse* (PF 1.09→1.02), confirming the
>   gate's success is specific to v0.4's pullback+wick+volume entry, not a
>   general fix.
> - **A proper train/holdout test (train = Mar24-Jan26, holdout =
>   Jan-Sep26) found that vanilla crude v4.0/v2.0/v2.1 all lose money in the
>   train period** and are profitable only because of Jan-Sep 2026's
>   volatility. No crude strategy in this repo passes train/holdout cleanly
>   except a lower-conviction, lower-point variant (v4.0 + "outside prior
>   value area" filter, PF 1.07). This is the honest caveat behind every
>   crude pick in this doc.
> - **BankNifty v0.4 + v13 combined in one script did NOT reach the naively
>   expected sum** of their solo backtests (+1,403 + +914 = +2,317
>   expected). The actual combined script gets **+964, PF 1.04** -- v13's
>   component turns into a net loser once trades compete with v0.4 for one
>   shared account. Not recommended over v0.4 alone.
> - **A loosened v0.4 (v0.5: lower ADX threshold, no volume filter, wider
>   R:R) was tested and rejected** -- PF collapsed to 0.71 (5m) / 0.68 (3m).
>   The dropped volume filter was load-bearing, not a bottleneck.
> - **A separate generic "VWAP-EMA Pullback" script was tested on BankNifty**
>   (the user had found it promising elsewhere) and came back badly negative
>   here (PF 0.60, -38,163 pts) -- flagged as an unresolved discrepancy with
>   the user's own finding, not adopted.
> - Full detail, raw data and source scripts for all of the above:
>   `strategy_audit_2026_09/v4.0_mcx_naturalgas_gold_silver_results.md`,
>   `.../v4.0_adx_gate_mcx_results.md`, `.../v4.0_recalibration_results.md`,
>   `.../gold_silver_recalibration_results.md`,
>   `.../silver_daily_loss_limit_results.md`,
>   `.../bnf_portfolio_v04_v13_results.md`, `.../bnf_v0.5_loosened_results.md`,
>   `.../vwap_ema_pullback_bnf_results.md`. Interactive comparison across
>   everything: `strategy_audit_2026_09/strategy_comparison_dashboard.html`.

---

## 1. The picks at a glance

| Script | Pick | TF | Trades / month | Win % | PF | Net pts | Pts / month | Rs / month (1 lot) | Max drawdown | Positive windows | History tested |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **CrudeOil** | **v4.0 SHA flip, R:R 4.0** (updated 14 Sep, was 3.0) | 5m | 26 | 23.5 | 1.12 | **+2,811** | +87 | **~Rs8,700** | not yet re-measured at RR4.0 | - | Mar 2024 - Sep 2026 (32.3 mo) |
| **BankNifty** | **v0.4 EMA pullback + 15m ADX gate** | 5m | 2.5 | 41.9 | **1.29** | **+1,277** | +42 | ~Rs1,270 | 1,668 pts (Rs50k) | 3 / 5 | Mar 2024 - Sep 2026 (30 mo) |
| **Gold** (new 14 Sep) | **v4.0 SHA flip, COMEX session (1730-0030)** | 5m | 16.6 | 31.0 | **1.13** | **+16,312** | +505 | ~Rs50,500 | not yet measured | - | Jan 2024 - Sep 2026 (32.3 mo) |
| **Silver** (new 14 Sep) | **v4.0 SHA flip, wide ATR stops + 350pt daily loss limit** | 5m | 24.2 | 29.6 | **1.35** | **+160,845** | +4,980 | ~Rs1,49,400 | 24,551 pts (Rs7.4L), down from 76,863 pre-limit | - | Jan 2024 - Sep 2026 (32.3 mo) |
| **Nifty 50** | **none at 3m / 5m** | - | - | - | < 1 | all negative | - | - | - | - | Mar 2024 - Sep 2026 |

For every script, the goals pulled against each other. Loosening a strategy
to get more trades always added losing trades faster than winning ones. So
each pick is the best compromise found. None meets all four goals at once.

**Read the caveats before sizing any of these** -- especially Silver, whose
PF-leading number still depends heavily on one or two 2026 windows and had a
76,863-pt single-window drawdown *before* the daily loss limit was added.
See the 14 Sep audit update above and sections 5-6 below for the full picture,
not just this table.

---

## 2. CrudeOil (MCX:CRUDEOIL1!, 5m): v4.0 SHA flip, now R:R 4.0

**File:** `v4.0 crudeoil strategy 5min (SHA flip RR3 - variant lab V21, forward-test build).pine.txt`,
with one parameter changed 14 Sep 2026: target R:R raised from 3.0 to 4.0
(`A95_v4.0_rr4.0_recal.pine.txt` in `strategy_audit_2026_09/`).

> **Read this before trusting the number below.** A proper train/holdout
> test (14 Sep 2026, train = Mar24-Jan26, holdout = Jan-Sep26) found that
> vanilla v4.0 (RR3) loses money in the training period (-623 pts) and is
> profitable only because of Jan-Sep 2026's volatility. RR4.0 has not been
> separately train/holdout tested -- treat its full-period numbers below
> with the same skepticism as RR3's until that's done. The only crude
> variant that has passed train/holdout cleanly is a *different*, lower-
> point strategy (v4.0 + "outside prior value area" filter, PF 1.07, see
> the 14 Sep audit update above) -- not this RR4.0 pick.

### Why this one

- It made the **most points** (+2,240 at RR3, +2,811 at RR4) of any
  profitable CrudeOil strategy.
- It has the **most trades** among the profitable ones (28/mo at RR3, 26/mo
  at RR4 -- barely changes).
- Its PF is close to the best (1.10-1.12 vs v2.1's 1.14).
- It has the **most positive windows** of any crude pick.

### Rules

| Part | Rule |
|---|---|
| Trend signal | Smoothed Heikin Ashi (EMA10 of OHLC, then HA, then EMA10) **changes colour**. Green means long, red means short. |
| Filter | EMA9 must be above EMA22 for longs, below for shorts. |
| Entry | Market order at the close of the flip bar. Entries only 09:15-23:30 IST, one position at a time. |
| Stop-loss | Beyond the 10-bar swing low/high + 0.1 x ATR14, **at least 1.5 x ATR** away. The trade is skipped if the stop would be more than 3 x ATR. |
| Target | **4R** (RR 1:4, raised from 3R on 14 Sep 2026 -- see below). No trailing stop, no breakeven move. Trades may be held overnight. |

### RR4.0 vs RR3.0 (14 Sep 2026 recalibration)

| Metric | RR3.0 (original) | RR4.0 (updated pick) |
|---|---|---|
| Trades / month | 28.3 | 26.0 |
| Win % | 28.2 | 23.5 |
| PF | 1.09-1.10 | **1.12** |
| Net pts | +2,136 to +2,240 | **+2,811** |
| History | 29.7mo / 11 windows | 32.3mo / 12 windows |

Raising the target lowered the win rate (a wider target is harder to reach)
but the strategy earns enough more per winner to more than cover it -- a
real, walk-forward-validated improvement, not noise. It's still the only
parameter change out of everything tried this project (ADX gates, ATR
recalibration, session changes) that improved crude specifically. See
`strategy_audit_2026_09/v4.0_recalibration_results.md` for the full
window-by-window RR4.0 breakdown.

**Note:** the live forward test described below (started 14 Sep 2026, run in
the protected `Crude 5 min profitable draft` script, version 162) is still
running the **original RR3.0** config -- the RR4.0 finding came from a
same-day audit-copy test and was not applied to the protected script.
Don't assume the forward test is tracking RR4.0.

### Results by window, RR3.0 original (oldest to newest, net pts)

| Window | Net pts |
|---|---|
| Mar - Jun 2024 | +281 |
| Jun - Sep 2024 | +621 |
| Sep - Nov 2024 | -1,295 |
| Nov 2024 - Feb 2025 | -129 |
| Feb - May 2025 | +1,248 |
| May - Jul 2025 | -460 |
| Jul - Oct 2025 | -376 |
| Oct 2025 - Jan 2026 | -408 |
| Jan - Apr 2026 | +1,216 |
| Apr - Jun 2026 | +1,215 |
| Jun - Sep 2026 (live) | +327 |
| **Total** | **+2,240 (838 trades, avg win 105 / avg loss -38 pts, daily Sharpe 0.53)** |

The Strategy Tester matched the lab closely on three windows. For example,
Apr-Jun 2026 was +1,118 in the tester against +1,215 in the lab. The live
chart table currently shows 78 trades, 29.5% win, PF 1.20, +578 pts.

### Caveats

- **Selection bias.** v4.0 was the only one of 192 variants that made money
  over this same history, so some of that result may be luck.
- A **forward test** started on 14 Sep 2026. The pass/fail rules were fixed in
  advance:
  - Keep it if PF >= 1.0 and drawdown stays under 2,100 pts after 60+ trades.
  - Drop it if drawdown goes over 2,100 pts at any time, or PF is below 0.8
    after 60 trades.
- With a 28% win rate, a run of 8-9 losses in a row is normal.

### Alternative: v2.1 EMA 9/22 pullback (RR 1:2)

Choose this if you want a smoother equity curve rather than more points.

| Metric | v2.1 |
|---|---|
| Trades / month | 17 |
| Win % | 37.4 |
| PF | 1.14 |
| Net pts | +1,337 |
| Daily Sharpe | **0.68** (best of the crude strategies) |
| Worst-window drawdown | **607 pts** (a third of v4.0's) |
| Positive windows | 5 / 11 |

By window, oldest to newest: -195, -62, +278, +260, -179, -166, +45, -92,
+1,602, +324, -477.

- v2.1 lives in the protected script `Crude 5 min profitable draft`
  (TradingView version 162, never modified).
- Running v2.1 and v4.0 together means 2 lots of crude, and their risk is
  correlated.

---

## 3. BankNifty (NSE:BANKNIFTY1!, 5m): v0.4 EMA pullback + 15m ADX gate

**File:** `bnf v0.4 BankNifty EMA Pullback 5min (15m ADX25 trend gate - robust version, Nifty-spot capable).pine.txt`

This strategy is also module B of the combined script. Tested on its own
there, it reproduces the standalone results exactly.

### Why this one

Every BankNifty candidate was re-run on the same five 6-month windows with
the same costs:

| Candidate | TF | Trades / mo | Win % | PF | Net pts | Sharpe | Max DD pts | + windows |
|---|---|---|---|---|---|---|---|---|
| **v0.4 EMA pullback + 15m ADX >= 25** | 5m | 2.5 | 41.9 | **1.29** | **+1,277** | **0.52** | **1,668** | **3 / 5** |
| Combined script, all modules A + B + C | 5m | **11.7** | 34.6 | 1.06 | +1,438 | 0.26 | 3,979 | 3 / 5 |
| Combined script, B + C only | 5m | 4.4 | 40.2 | 1.17 | +1,403 | 0.44 | 2,593 | 3 / 5 |
| MTF v1.1 (daily + 15m ADX gates) | **3m** | 2.1 | 52.6 | **1.64** | +1,113 | **1.21** | **482** | 3 / 5 + 1 flat (18 mo only) |
| v13 sweep-fade "bear", RR 1:6 | 5m | 7.6 | 31.1 | 0.99 | -124 | -0.03 | 2,415 | 2 / 5 |

- **v0.4 gives the best PF and Sharpe over the full 30 months** of any
  BankNifty 5m strategy, with the smallest drawdown.
- Adding the other modules roughly **quadruples the trade count** (11.7 a
  month) but adds almost **no extra points** (+1,438 against +1,277). PF falls
  to 1.06, and drawdown grows to 2.4x (Rs1.19L).
- **v13 roughly breaks even** once 5 pts of slippage per fill is charged. Its
  earlier +914 was measured without slippage. At 228 trades, the slippage
  alone costs about 2,280 pts.
- **MTF v1.1** has the best quality numbers, but only on **3m**:
  - It can only be tested over about 18 months, because the 3m replay data
    starts around Mar 2025.
  - It takes about 2 trades a month.
  - On 5m (module C) it drops to PF 1.03-1.10.
  - It makes a good **companion** to v0.4 on its own 3m chart. The two
    together would give about 4.6 trades a month, roughly +100 pts/mo, or
    about Rs3,000/mo at 1 lot each. This sum was never tested as a single
    backtest.

### Rules (v0.4)

| Part | Rule |
|---|---|
| Trend regime | Long when EMA9 > EMA21, short when EMA9 < EMA21. A "coil" also counts: EMA9, EMA21 and EMA200 all within 1 x ATR of each other. |
| Trend-strength gate | The **last completed 15m bar's ADX(14) >= 25**. It reads completed bars only, so there is no lookahead. |
| Volatility filter | ATR14 >= 50 pts. |
| Pullback | Within 10 bars of closing on the trend side of the EMAs, price pulls back to EMA9 and a candle shows a **rejection wick** (at least 50% of its range). |
| Confirmation | A reclaim bar, within 8 bars, that closes back on the trend side. Its volume must be at least the 20-bar average, it must be on the correct side of the day's VWAP, and the pullback must have held EMA21. RSI(3) is not above 80 for longs or below 20 for shorts. |
| Entry | **Stop order** at the signal bar's high for longs (low for shorts). It stays live for 8 bars. Entries only 09:30-15:00 IST, and not in the first 15 minutes. |
| Stop-loss | The lower of: pullback low - 0.15 x ATR, or signal high - 0.5 x ATR. Capped at 2 x ATR. Mirrored for shorts. |
| Target | **2.5R**. No trailing. Everything is closed by 15:15 IST. After a trade, it waits 3 bars before arming again. |

### Results by window (oldest to newest)

| Window | Trades | Wins | PF | Net pts |
|---|---|---|---|---|
| Mar - Sep 2024 | 14 | 5 | 2.07 | +816 |
| Sep 2024 - Mar 2025 | 17 | 6 | 1.19 | +206 |
| Mar - Sep 2025 | 8 | 2 | 0.27 | -533 |
| Sep 2025 - Mar 2026 | 11 | 4 | 0.87 | -102 |
| Mar - Sep 2026 (live) | 24 | 14 | 1.83 | +889 |
| **Total** | **74** | **31 (41.9%)** | **1.29** | **+1,277** |

### Caveats

- **Few trades.** 74 trades is a small sample, and the ADX gate was chosen
  after looking at the newest windows. The older windows did hold up.
- The gate works by **sitting out choppy markets**. That is the reason for
  the low frequency, and it is also why loosening it loses. At ADX 20 the
  strategy gains 0.8 trades a month but gives up about 880 pts.
- One full year (Mar 2025 - Mar 2026) was net negative (-635 pts).

### If you want more BankNifty trades

Use the combined script
`bnf combined v1 BankNifty 5min (v13 sweep-fade + v0.4 pullback + MTF v1.1 in one script).pine.txt`
with all three modules on. It trades about 12 times a month and makes about
the same total points (+1,438). The price is a lower PF (1.06) and a much
deeper drawdown (3,979 pts). Its table shows each module's results
separately.

At about 22 pts round-trip cost, **no single BankNifty 3m/5m strategy trading
15 or more times a month made money** in this data.

### Three more BankNifty attempts, tested 14 Sep 2026, none beats v0.4

- **v0.4 + v13 combined in one script (independent modules, `pyramiding=2`,
  same capital).** Expected the naive sum of their solo backtests
  (+1,403 + +914 = +2,317). Actual: **+964 pts, PF 1.04** -- only 42% of
  that estimate. v0.4's component held up close to solo (+1,469), but v13's
  flipped from a modest solo winner to a **net loser** (-505, PF 0.97) once
  its signals had to compete with v0.4's for the same account (TradingView
  keeps one net position per script, so opposite-direction signals between
  modules are mutually exclusive by necessity). Real interaction effect, not
  a bug -- don't run this combination expecting the sum. See
  `strategy_audit_2026_09/bnf_portfolio_v04_v13_results.md`.
- **v0.5: v0.4 with the ADX gate lowered (25→20), the volume filter removed,
  and R:R tightened (2.5→2.0)**, aimed at more trade frequency. Rejected --
  trade count did jump (74→693/mo on 5m, 9.4x), but PF collapsed to 0.71
  (5m) / 0.68 (3m). The removed volume filter was screening out exactly the
  low-conviction reclaims it existed to block. See
  `strategy_audit_2026_09/bnf_v0.5_loosened_results.md`.
- **A generic "VWAP-EMA Pullback" strategy** (not built for BankNifty
  specifically) that the user separately believed was promising for this
  instrument. Tested with this project's standard tiled method: PF 0.60,
  -38,163 pts over 35.6 months -- one of the worst BankNifty results in
  this whole repo. Win rate (31.1%) sits below the mathematical breakeven
  for its own 2:1 target (33.3%) even before costs. This directly
  contradicts the user's own finding; the discrepancy was flagged, not
  resolved -- possible causes (different parameters, different instrument
  variant, a non-replayed Strategy Tester read) were never confirmed. See
  `strategy_audit_2026_09/vwap_ema_pullback_bnf_results.md`.

**v0.4 alone remains the pick.** None of these three attempts beat it.

---

## 4. Nifty 50 (NSE:NIFTY spot): no viable 3m / 5m strategy

Every concept tested on Nifty 50 spot at 3m and 5m was net-negative after
costs. The best results on the same tiled windows:

| Candidate | TF | Trades / mo | PF | Net pts | + windows |
|---|---|---|---|---|---|
| v2 sweep-fade, re-tuned for 5m, RR 1:6 | 5m | 5 | 0.71 | -1,436 | 1 / 5 |
| Best lab variant (V22 SHA flip + EMA200) | 5m | 12 | 0.84 | -1,846 | 0 / 5 |
| Best 3m lab variant (V21 SHA flip) | 3m | 22 | 0.73 | -3,430 | 0 / 5 |
| SHA pullback / CPR / PDH-PDL levels (lab v2, 20 variants) | 5m | 8+ | <= 0.62 | all negative | 0 / 5 |
| v0.4 EMA pullback, ATR >= 25 (live window only*) | 5m | 2.5 | 0.95 | -21 | - |

\* v0.4 needs volume. Nifty spot has none, so the script borrows NIFTY1!
futures volume. TradingView replay cannot load another symbol's data, so
v0.4 can only be tested on the live window.

**The only Nifty strategy in this repo that holds up** is
`nifty v2 Sweep-Fade` on the **15-minute** chart, which is outside the
3m/5m scope:

- It was tested over about 7.5 years in 10 windows.
- Results ranged from -40 to +178 pts a month per window.
- 5 of the 10 windows were net-negative, though never disastrously.
- It was measured under the older cost convention: no commission, with a flat
  per-trade deduction. It has not been re-run at 0.02%.

If a Nifty strategy is required, that 15m script is the only candidate. It
needs a fresh walk-forward under current costs before it is used.

---

## 5. Gold (MCX:GOLD1!, 5m): v4.0 SHA flip, COMEX-active session

**File:** `v4.0 crudeoil strategy 5min (SHA flip RR3...).pine.txt`, ported
to gold unmodified except the session filter
(`A96_gold_comex_session_recal.pine.txt` in `strategy_audit_2026_09/`).
Added 14 Sep 2026 -- gold had never been individually tuned before this.

### Why this one

Crude's exact v4.0 logic (SHA colour flip, EMA9>EMA22, swing-based stop,
RR3) was ported to gold unchanged first, then one instrument-specific
change was tested: the entry session, changed from crude's daytime MCX
window to COMEX-active hours (18:30-19:00 IST onward through early NY).

| | Crude session (0915-2330) | **COMEX session (1730-0030)** |
|---|---|---|
| Trades / month | 30.3 | **16.6** |
| Win % | 29.7 | **31.0** |
| PF | 1.07 | **1.13** |
| Net pts | +13,152 | **+16,312** |

The session change is a genuine improvement in both PF and points together
-- not just a frequency/quality trade-off. It also appears to reduce the
window-concentration problem: on the crude-session baseline, one single
window (+24,172) was 1.8x the entire 32-month net; the COMEX-session
version's best window (+18,819) is only ~1.15x the full net.

### Results by window (oldest to newest, net pts)

| Window | Net pts |
|---|---|
| ~Jan - Mar 2024 | -596 |
| ~Mar - Jun 2024 | +4,374 |
| ~Jun - Sep 2024 | -2 |
| ~Sep - Nov 2024 | -2,145 |
| ~Nov 2024 - Feb 2025 | -4,160 |
| ~Feb - May 2025 | -6,267 |
| ~May - Jul 2025 | +1,026 |
| ~Jul - Oct 2025 | +4,171 |
| ~Oct 2025 - Jan 2026 | -1,286 |
| ~Jan - Apr 2026 | +18,819 |
| ~Apr - Jun 2026 | -2,984 |
| ~Jun - Sep 2026 (live) | +5,363 |
| **Total** | **+16,312 (536 trades, 32.3 months, 12 windows)** |

### Caveats

- **Never tuned beyond this one change.** The session filter was the only
  gold-specific parameter tested; ATR multiples, SHA lengths and R:R still
  use crude's defaults. There may be more headroom, untested.
- **A 15m ADX>=25 gate was also tried on gold and made things slightly
  worse**, not better (net points fell 13,152→11,146 on the untuned
  baseline) -- same finding as on crude, this gate doesn't transfer to the
  SHA-flip signal the way it does for BankNifty v0.4's different entry.
- No forward test started for gold; this is backtest-only so far.

---

## 6. Silver (MCX:SILVER1!, 5m): v4.0 SHA flip, wide ATR stops + daily loss limit

**File:** v4.0's logic with two changes: `minSL` 1.5→2.5 ATR, `maxSL`
3.0→5.0 ATR (`A97_silver_wide_atr_recal.pine.txt`), plus a hard 350-point
daily loss circuit breaker (`A98_silver_daily_limit_fixed350.pine.txt`).
Added 14 Sep 2026 -- silver had never been individually tuned before this.
**This is currently the highest-PF strategy in the entire repository.**

### Why this one

Crude's v4.0 logic ported to silver unchanged was already net-positive
(PF 1.06, +32,815 pts) but with severe drawdown (45,815 pts) and heavy
concentration in a few windows. Two changes fixed both problems:

1. **Wider stops** (silver's ATR/price ratio is higher than crude's, so
   crude's tight stops were cutting valid trades short): PF 1.06→1.15, net
   +32,815→+116,096, but single-window drawdown actually got *worse*
   (45,815→76,863) -- wider stops let more real moves run, but also let
   losing trades run further before being cut.
2. **A fixed 350-point daily loss circuit breaker** (force-flat any open
   position and lock out new entries for the rest of the day once realized
   daily loss hits -350pts; sized at ~2x the wide-ATR version's own average
   daily profit of 167pts/day): PF 1.15→**1.35**, net +116,096→**+160,845**,
   max single-window drawdown 76,863→**24,551 (-68%)**.

| | Crude defaults | Wide ATR only | **Wide ATR + daily limit** |
|---|---|---|---|
| Trades / month | 31.9 | 33.1 | **24.2** |
| Win % | 28.7 | 28.7 | **29.6** |
| PF | 1.06 | 1.15 | **1.35** |
| Net pts | +32,815 | +116,096 | **+160,845** |
| Max single-window DD | 45,815 | 76,863 | **24,551** |

**A fixed-point breaker was tested against a volatility-scaled one (limit =
7.5x ATR14) and won on every metric** (PF 1.35 vs 1.18, net +160,845 vs
+125,529, DD 24,551 vs 62,493). Reason: the worst-loss window was exactly
the one where ATR spiked, so a volatility-scaled breaker's own threshold
expanded right along with the danger and barely tripped when it mattered.
General principle for future risk design: scale *position/stop* sizing
with volatility (correct), but use a *fixed* cap for a circuit breaker
meant to catch regime-breaking tail days -- scaling the safety net with
the danger defeats it.

### Rules (on top of v4.0's SHA-flip entry, unchanged)

| Part | Rule |
|---|---|
| Stop-loss | Beyond the 10-bar swing +0.1xATR, **at least 2.5x ATR** away (widened from crude's 1.5x). Skipped if wider than **5.0x ATR** (widened from 3.0x). |
| Target | 3R, unchanged. |
| Daily loss limit | Realized P&L for the session day tracked live; once it hits **-350 points**, any open position is force-closed immediately and no new entries are taken until the next day. |

### Results by window, wide ATR + daily limit (oldest to newest, net pts)

| Window | Net pts |
|---|---|
| ~Jan - Mar 2024 | -2,924 |
| ~Mar - Jun 2024 | -482 |
| ~Jun - Sep 2024 | +6,099 |
| ~Sep - Nov 2024 | +10,743 |
| ~Nov 2024 - Feb 2025 | +91 |
| ~Feb - May 2025 | +5,320 |
| ~May - Jul 2025 | -1,542 |
| ~Jul - Oct 2025 | -15,916 |
| ~Oct 2025 - Jan 2026 | +11,278 |
| ~Jan - Apr 2026 | +137,335 |
| ~Apr - Jun 2026 | +126 |
| ~Jun - Sep 2026 (live) | +10,718 |
| **Total** | **+160,845 (783 trades, 32.3 months, 12 windows)** |

### Caveats -- read before sizing this

- **One window (Jan-Apr 2026) alone is +137,335, more than 85% of the
  entire 32-month total.** Even with the daily loss limit taming the
  drawdown side, the *profit* side is still extremely concentrated in one
  volatile stretch. This is the same "most of the edge is a few extreme
  windows, not a steady signal" pattern already flagged for crude -- the
  daily limit manages downside risk, it does not fix concentration.
  Silver's win rate (29.6%) and PF alone would not look nearly this good
  without that one window.
- **24,551 points is still a real drawdown at 1 lot** (~Rs7.4 lakh at
  pv=30) even after the limit -- not small money.
- **The 350-point limit was calibrated on this exact backtest's own
  average daily profit.** It hasn't been sensitivity-tested (e.g. 250 vs
  350 vs 450) -- treat 350 as a reasonable starting point, not a uniquely
  correct number.
- No forward test started for silver; this is backtest-only so far.

---

## 7. Suggested portfolio and what to expect

| Leg | Lots | Trades / month | Expected pts / month | Expected Rs / month | Worst drawdown seen |
|---|---|---|---|---|---|
| CrudeOil v4.0, RR4.0 (5m) | 1 | ~26 | +87 | ~Rs8,700 | not yet re-measured |
| BankNifty v0.4 (5m) | 1 | ~2.5 | +42 | ~Rs1,270 | 1,668 pts = Rs50k |
| *optional:* BankNifty MTF v1.1 (3m) | 1 | ~2 | +60 | ~Rs1,800 | 482 pts = Rs14.5k |
| Gold v4.0, COMEX session (5m) | 1 | ~17 | +505 | ~Rs50,500 | not yet measured |
| Silver v4.0, wide ATR + daily limit (5m) | 1 | ~24 | +4,980 | ~Rs1,49,400 | 24,551 pts = Rs7.4L |
| **Total** | 4-5 | **~71** | - | **~Rs2,11,700** | legs not simulated together |

"Expected" means the backtest average. Every leg had losing stretches of 3-6
months, and Gold/Silver's totals lean heavily on 2026's volatility (see
their caveats above) -- don't extrapolate these Rs/month figures forward
without discounting for that concentration. Most of the profit across
*every* leg in this table came from 2-3 strong windows per strategy, not a
steady drip. **Paper-trade first**, especially Gold and Silver, which have
no forward test running yet. For crude v4.0, the forward test from 14 Sep
2026 (running the original RR3.0 config, not the updated RR4.0) will show
whether its edge is real.

---

## 8. How these numbers were produced

- Tester settings: qty 1 and 0.02% commission per side, about 22 pts per
  round trip on BankNifty. v0.4, MTF and the combined script also include 5
  pts of slippage per fill.
- **Tiled windows.** Each replay window counts only the trades that start
  after its 400-bar warm-up. The next window picks up exactly where the
  previous one's counting began. Windows that overlapped were thrown away.
  Chained drawdown is exact across windows.
- **Data floors.** 5m replay starts around 25 Mar 2024 and 3m around 20 Mar
  2025 for CrudeOil/BankNifty/Nifty, so nothing older could be tested at
  these timeframes. **Gold and Silver's 5m floors are earlier, around
  31 Jan / 21 Feb 2024** -- their walk-forward windows (12 each, 32.3
  months) run about 2 months longer than crude/BankNifty's (11/5 windows,
  ~30 months) as a result. Point values: Gold pv=100, Silver pv=30 (same
  scale as BankNifty), CrudeOil pv=100. Gold/Silver tests use the same
  0.02%/side commission convention as crude, no added slippage (Silver's
  daily-loss-limit version also has no added slippage beyond that).
- **Bugs found and fixed while building the combined BankNifty script.** An
  early result of 131 trades and +3,751 pts in the live window was **wrong**
  and has been replaced.
  1. A module's armed stop order could fill a second lot while its trade was
     already open.
  2. TradingView's default first-in-first-out exits let one module's exit
     close another module's trade.
  After the fixes, each module run alone matches its standalone script
  exactly.
- Raw data and aggregation scripts:
  - `variant_lab_v1/head_to_head_*`
  - `variant_lab_v1/robust_tuning/*`
  - `variant_lab_v2/*`
