# Best strategy per script: BankNifty, Nifty 50, CrudeOil (3m / 5m)

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

---

## 1. The picks at a glance

| Script | Pick | TF | Trades / month | Win % | PF | Net pts | Pts / month | Rs / month (1 lot) | Max drawdown | Positive windows | History tested |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **CrudeOil** | **v4.0 SHA flip RR3** | 5m | **28** | 28.2 | 1.10 | **+2,240** | **+75** | **~Rs7,500** | 2,106 pts, worst window (Rs2.1L) | **6 / 11** | Mar 2024 - Sep 2026 (30 mo) |
| **BankNifty** | **v0.4 EMA pullback + 15m ADX gate** | 5m | 2.5 | 41.9 | **1.29** | **+1,277** | +42 | ~Rs1,270 | 1,668 pts (Rs50k) | 3 / 5 | Mar 2024 - Sep 2026 (30 mo) |
| **Nifty 50** | **none at 3m / 5m** | - | - | - | < 1 | all negative | - | - | - | - | Mar 2024 - Sep 2026 |

For every script, the goals pulled against each other. Loosening a strategy
to get more trades always added losing trades faster than winning ones. So
each pick is the best compromise found. None meets all four goals at once.

---

## 2. CrudeOil (MCX:CRUDEOIL1!, 5m): v4.0 SHA flip RR3

**File:** `v4.0 crudeoil strategy 5min (SHA flip RR3 - variant lab V21, forward-test build).pine.txt`

### Why this one

- It made the **most points** (+2,240) of any profitable CrudeOil strategy.
- It has the **most trades** among the profitable ones (28 a month).
- Its PF of 1.10 is close to the best (v2.1 has 1.14).
- It has the **most positive windows**: 6 of 11.

### Rules

| Part | Rule |
|---|---|
| Trend signal | Smoothed Heikin Ashi (EMA10 of OHLC, then HA, then EMA10) **changes colour**. Green means long, red means short. |
| Filter | EMA9 must be above EMA22 for longs, below for shorts. |
| Entry | Market order at the close of the flip bar. Entries only 09:15-23:30 IST, one position at a time. |
| Stop-loss | Beyond the 10-bar swing low/high + 0.1 x ATR14, **at least 1.5 x ATR** away. The trade is skipped if the stop would be more than 3 x ATR. |
| Target | **3R** (RR 1:3). No trailing stop, no breakeven move. Trades may be held overnight. |

### Results by window (oldest to newest, net pts)

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

## 5. Suggested portfolio and what to expect

| Leg | Lots | Trades / month | Expected pts / month | Expected Rs / month | Worst drawdown seen |
|---|---|---|---|---|---|
| CrudeOil v4.0 (5m) | 1 | ~28 | +75 | ~Rs7,500 | 2,106 pts = Rs2.1L (one window) |
| BankNifty v0.4 (5m) | 1 | ~2.5 | +42 | ~Rs1,270 | 1,668 pts = Rs50k |
| *optional:* BankNifty MTF v1.1 (3m) | 1 | ~2 | +60 | ~Rs1,800 | 482 pts = Rs14.5k |
| **Total** | 2-3 | **~32** | - | **~Rs10,500** | legs not simulated together |

"Expected" means the backtest average. Every leg had losing stretches of 3-6
months. Most of the profit came from 2-3 strong windows per strategy.
**Paper-trade first.** For crude v4.0, the forward test from 14 Sep 2026 will
show whether its edge is real.

---

## 6. How these numbers were produced

- Tester settings: qty 1 and 0.02% commission per side, about 22 pts per
  round trip on BankNifty. v0.4, MTF and the combined script also include 5
  pts of slippage per fill.
- **Tiled windows.** Each replay window counts only the trades that start
  after its 400-bar warm-up. The next window picks up exactly where the
  previous one's counting began. Windows that overlapped were thrown away.
  Chained drawdown is exact across windows.
- **Data floors.** 5m replay starts around 25 Mar 2024 and 3m around 20 Mar
  2025, so nothing older could be tested at these timeframes.
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
