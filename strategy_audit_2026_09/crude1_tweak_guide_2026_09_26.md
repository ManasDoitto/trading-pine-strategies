# CrudeOil working_strategies #1 — full explanation and tweak guide (2026-09-26)

Script: `working_strategies/CrudeOil/1_v4.0_SHA_flip_RR4.0_recal.pine.txt` (MCX:CRUDEOIL1!, 5-minute, 1 lot = 100 barrels, Rs 100 per point).
All numbers: harness on the TradingView-harvested 5m bars, 2024-03-25 -> 2026-09-24 (30 months), **gross points** unless stated.
Data: `research_data/crude1_trades.pkl` (per trade), `research_data/crude1_sensitivity.csv` (knob map).

## 1. What it is, in one paragraph
A trend-following strategy. It waits for a smoothed Heikin-Ashi colour change ("SHA flip") that agrees with the EMA9/EMA22 direction, enters at the
next bar open, puts a stop behind the recent 10-bar swing (never closer than 1.5 x ATR, and it refuses the trade if that stop would need to be
wider than 3 x ATR), and sets a fixed profit target at 4 times the risk. No trailing stop, no time exit. It loses about 3 trades in 4 and makes money because
winners are about 4x the size of losers.

## 2. The rules, step by step (mapped to the code)
1. **SHA (smoothed Heikin-Ashi).** EMA(10) of open, high, low and close separately -> build a Heikin-Ashi candle from those (`haC = (o+h+l+c)/4`,
   `haO = (previous haO + previous haC)/2`) -> smooth again: EMA(10) of `haC` vs EMA(10) of `haO`. **Up** when the first is above the second.
   A **flip** is the bar where that comparison changes (`flipUp`, `flipDn`). Inputs: `shaLen1`, `shaLen2`.
2. **Trend filter.** Long only if EMA9 > EMA22, short only if EMA9 < EMA22 (`useEmaAl`). Optional EMA200 filter (`use200`, off).
3. **Session filter.** The *signal* must occur 09:15-23:30 IST (`sess`). An open trade can exit at any time, including overnight.
4. **Stop.** Long: lowest low of the last 10 bars (`swLen`) minus 0.1 x ATR (`swBuf`). Short: mirror. Distance is never less than 1.5 x ATR (`minSL`).
5. **Stop-width cap.** If the stop distance would exceed 3.0 x ATR (`maxSL`) the signal is **skipped entirely**.
6. **Target.** Entry +/- 4.0 x the stop distance (`rr`). Stop and target are placed together (one cancels the other).
7. **One position at a time.** New flips are ignored while a trade is open (`flat` must be true). No reversals, no adding.
8. **Timing.** Everything is evaluated on the closed bar; the order fills at the **next bar open**. Stop and target prices are computed from the signal bar close,
   so a gap at the open changes the real risk slightly.

## 3. The funnel: why about 5,000 flips become 785 trades
| stage | count | |
|---|---|---|
| SHA colour flips (both directions) | 5,155 | one every ~21 bars (~1.8 h) |
| inside the 09:15-23:30 entry session | 4,875 | |
| AND EMA9/22 agrees with the flip | 2,970 | 61% survive |
| AND stop <= 3.0 x ATR | **1,348** | **only 45% survive; 1,622 skipped as "stop too wide"** |
| AND no trade already open | **785** | 563 signals ignored because a trade was running |

**The 3 x ATR stop cap removes more than half the signals that pass the trend filter. That filter is the strategy's most important lever** (section 5).

## 4. How it behaves
| | |
|---|---|
| Trades | 785 (26.2/month) |
| Win rate | **24.3%** (break-even at RR 4.0 is 20.0%) |
| Profit factor / net | **1.263 / +5,614 pts** = Rs 561,447 on one lot |
| Average win / average loss | +141.2 / -36.0 pts (3.93x) |
| Average trade / median trade | **+7.15 / -18.6 pts** (the median trade is a loss) |
| Longest losing streak | **24 trades** |
| Typical risk per trade | 32.7 pts = **Rs 3,271 per lot**; typical target 130.8 pts = Rs 13,085 |
| Exits | 593 stop / 192 target |
| Hold time | mean 9.7 h, median 1.8 h; **26% of trades stay open past midnight** |
| Long / short | +3,460 (394 trades, 26.0% win) / +2,154 (391 trades, 23.0% win) |
| After 0.02%/side costs | +3,577 pts (about 36% of the profit is eaten by costs; ~2.6 pts per trade) |

**By entry hour (IST), net points:** 10h +629, 11h -409, 12h +190, 13h +37, 14h -227, 15h +437, 16h +122, 17h +119, 18h +190, **19h +1,295, 20h +1,763, 21h +1,199**,
22h -429, 23h +692. **By weekday:** Mon +2,038, Tue +742, Wed +1,320, Thu +522, Fri +944.
**By year:** 2024 +901, 2025 +381, 2026 (Jan-Sep) +4,333.

**The honest picture:** the best 3 months are **85% of the profit** (excluding them: +853 over 28 months); train (to 2025-06-25) +2,270, holdout +3,344. It earns most
of its money in a few trending stretches, mainly Jan-Mar 2026.

## 5. Knob map — each input moved on its own from the baseline
(TRAIN = to 2025-06-25, HOLD = after. "After cost" = after 0.02%/side. Baseline: 785 trades, PF 1.263, +5,614, train +2,270, hold +3,344, after cost +3,577.)

| knob (input) | tested | result | verdict |
|---|---|---|---|
| **SHA smoothing** (`shaLen1/2`) | 5/5, 7/7, 14/14, 20/20 | +998, +1,613, **-566, -903** (PF 1.03, 1.06, 0.98, 0.96) | **FRAGILE. 10/10 sits on a narrow peak; both neighbours fail. Do not touch.** |
| **Stop-width cap** (`maxSL`) | 2.5, 2.75, 3.0, 3.25, 3.5, 4.0 | +2,025, +5,047, **+5,614**, +4,532, +2,541, **-2,900** (train +2,414, +3,202, +2,270, +556, +266, +447) | **The most sensitive knob.** Best at 2.75-3.0. Loosening it lets in the noisy wide-stop bars and destroys the edge |
| Target (`rr`) | 2, 3, 4, 5, 6 | +2,551, +4,481, +5,614, +5,277, +5,987 (train 533, 1,893, 2,270, 888, 432; hold 2,018, 2,588, 3,344, 4,389, 5,555) | Higher RR shifts profit from the train half to the 2026 holdout: a **bet on rare big trends**, not a free improvement |
| Minimum stop (`minSL`) | 1.0, 2.0, 2.5 | +5,598, **+6,231**, +5,394 | Flat plateau (PF 1.25-1.29). 2.0 is slightly better in both halves; low risk to change |
| Swing lookback (`swLen`) | 5, 15, 20 | +4,198, +4,062, +4,160 | All lower than 10 but positive: a mild peak |
| Stop buffer (`swBuf`) | 0.0, 0.25 | +5,804, +5,156 | Almost no effect |
| EMA9/22 alignment (`useEmaAl`) | off | +2,279 (after cost -714) | **Keep it**: removing it more than halves the profit |
| EMA200 filter (`use200`) | on | +4,973, PF 1.290, 634 trades, after cost +3,329 | Neutral: same efficiency, fewer trades |
| **Session** (`sess`) | see below | see below | **The best-supported tweak** |

### The session finding (entries from X to 23:30)
| entry window | trades (/mo) | PF | net | train | hold | after cost | pts/trade |
|---|---|---|---|---|---|---|---|
| 09:15-23:30 (baseline) | 785 (26) | 1.263 | +5,614 | +2,270 | +3,344 | +3,577 | +7.2 |
| 13:00-23:30 | 632 (21) | 1.293 | +5,641 | +1,807 | +3,834 | +3,990 | +8.9 |
| 15:00-23:30 | 545 (18) | 1.365 | +6,118 | +2,167 | +3,951 | +4,687 | +11.2 |
| 16:00-23:30 | 504 (17) | 1.398 | +6,269 | +2,204 | +4,066 | +4,945 | +12.4 |
| 17:00-23:30 | 461 (15) | 1.392 | +5,841 | +2,286 | +3,555 | +4,634 | +12.7 |
| **17:30-23:30** | 429 (14) | 1.476 | +6,558 | +2,447 | +4,111 | **+5,437** | +15.3 |
| 18:00-23:30 | 392 (13) | 1.478 | +6,273 | +2,181 | +4,092 | +5,250 | +16.0 |
| 19:00-23:30 | 322 (11) | 1.504 | +5,750 | +1,222 | +4,528 | +4,908 | +17.9 |
| 20:00-23:30 | 263 (9) | 1.360 | +3,549 | +610 | +2,939 | +2,857 | +13.5 |
| **Morning only 09:15-17:00** | 471 (16) | 1.043 | **+431** | +17 | +414 | **-786** | +0.9 |

**The 471 morning and afternoon trades earn almost nothing (+431 in total; negative after costs).** Nearly all the edge is in the evening, when NYMEX/US hours drive
MCX crude. Start times from 15:00 to 19:00 all beat the baseline on PF and on after-cost profit, on both halves of the data, so this is a plateau, not one lucky
setting. **The price is trade count**: 26 a month falls to 18 (15:00 start) or 14 (17:30 start). That is the trade-off to choose.

## 6. What I would and would not change
| | |
|---|---|
| **Consider** | Session start 15:00-18:00 (best evidence; fewer trades, but gross points per trade rise from +7.2 to +11 to +16, and after-cost profit rises from +3,577 to +4,600 to +5,400). minSL 2.0 (harmless plateau). |
| **Trade-off, your call** | RR: higher means more dependence on rare big trends; 4.0 is a reasonable middle. maxSL 2.75 vs 3.0: 2.75 was better in training, worse in the holdout. |
| **Leave alone** | SHA lengths (10/10), never loosen the 3 x ATR cap, keep EMA9/22 alignment. |
| **Do not expect to help** | More trades (the breakout, loosened filters): crude earns about +7 pts per trade against about 2.6 pts of cost. A daily loss limit (inert: crude daily moves are far below 300 pts). |
| **Not tested here** | Exit on an opposite flip; break-even stop; time stop. The repo tested scaling out at 2R on 15 Sep and it hurt (the edge lives in rare big winners). |

## 7. Limits you should know before tweaking
- **Everything above is in-sample on 30 months.** The session result is the most convincing because both halves improve and it forms a plateau, but it is still one
  of about 30 knobs looked at on the same data. Treat any tweak as a candidate for forward testing, not as a fact.
- **The profit is concentrated.** 85% comes from 3 months; the strategy was flat in 2025. Tweaks that add a few points in 2026 are not evidence of a better strategy.
- **Options do not work for crude:** the ATM premium is about 31x the per-trade edge. This is a futures strategy.
- **The crude forward test is not running** (its script slot no longer exists). Whatever you settle on should be forward tested with a fixed rule set.

## 8. How to test a tweak properly
1. Change **one** input at a time. TradingView inputs: `shaLen1/2, useEmaAl, use200, swLen, swBuf, minSL, maxSL, rr, sess`.
2. TradingView Strategy Tester loads only about 10,000 bars of 5m in one pass (about 2 months), so a single view is not enough. Use **Replay in about 81-day windows**
   (the AUD table at the bottom of the chart accumulates per window) or ask me to run it on the harness (about 5 seconds per variant; it matches TradingView engine to 0.03% on drawdown).
3. Compare **gross and after-cost**, **train and holdout**, and **per window**, not just the total.
4. Need at least about 60 trades before believing anything; a 24-trade losing streak is normal for this strategy.
5. Judge against crude #1 itself over the *same* bars, not against zero.
