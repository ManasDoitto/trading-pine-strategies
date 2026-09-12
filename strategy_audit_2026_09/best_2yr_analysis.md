# Best CrudeOil and BankNifty strategies over at least 2 years (13 Sep 2026)

## What was analysed

Every crude and BankNifty strategy with **24 or more months** of results, all measured the same way:
- 5m chart
- non-overlapping replay windows covering all the history TradingView allows
- 1 lot, 0.02% commission per side, no extra slippage

Coverage:
- **CrudeOil (MCX:CRUDEOIL1!):** 11 windows, Mar 2024 to Sep 2026, 29.7 months.
- **BankNifty (NSE:BANKNIFTY1!):** 5 windows, Mar 2024 to Sep 2026, 30.2 months.

Excluded:
- **BankNifty MTF v1.1 on 3m** (PF 1.69). 3m data only goes back about 18 months, so it cannot meet the 2-year minimum.
- **Nifty 50.** No strategy was profitable there.

The older headline figures were re-run in the full audit, and none of them survived:

| Strategy | Earlier headline | Full-history result |
|---|---|---|
| v13 | +3,606 | +914 |
| v10.4 | +4,994 | −119 |
| v10.5 | +5,693 | −1,551 |
| crude v1.0 | +41.6% at qty 10 | +2,155 per lot |

The script is `best2y.py`. Its inputs are `audit_raw.txt` and `lab3_raw.txt`.

## Core results

Points are per lot. "Excl. best window" removes the single best window, as a test of how much the total depends on one lucky stretch.

| Strategy | Trades/mo | Win% | PF | Net pts | Sharpe | Max DD | Net/DD | Avg win / loss | pts/trade | + windows | Excl. best window |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Crude v4.0 SHA flip RR3** | 28.3 | 28.0 | 1.09 | +2,136 | 0.50 | 2,339 | 0.91 | 105 / −38 | +2.54 | **6/11** | **+888** |
| Crude v2.0 EMA pullback (sep 0.5) | 45.3 | 37.9 | 1.09 | **+2,195** | **0.72** | 2,358 | 0.93 | 52 / −29 | +1.63 | 4/11 | −493 |
| **Crude v2.1 EMA pullback (sep 1.5)** | 17.4 | 37.3 | **1.14** | +1,304 | 0.67 | **900** | **1.45** | 56 / −29 | +2.52 | 5/11 | −298 |
| Crude v4.0 + outside prior value area | 14.1 | 29.3 | 1.10 | +1,225 | 0.39 | 1,804 | 0.68 | 108 / −40 | +2.92 | 6/11 | +378 |
| Crude v4.0 + prior-POC side | 20.7 | 28.2 | 1.08 | +1,247 | 0.36 | 2,533 | 0.49 | 101 / −37 | +2.03 | 6/11 | +97 |
| Crude v2.3 (v2.1 + daily trend) | 11.0 | 36.5 | 1.02 | +98 | 0.07 | 874 | 0.11 | 53 / −30 | +0.30 | 4/11 | −376 |
| **BankNifty v0.4 pullback + 15m ADX** | 2.5 | 41.9 | **1.33** | **+1,403** | **0.57** | **1,620** | **0.87** | 185 / −100 | +18.96 | 3/5 | **+475** |
| BankNifty v10.3 PD sweep + daily trend | 3.5 | 38.1 | 1.10 | +924 | 0.22 | 2,631 | 0.35 | 254 / −142 | +8.80 | 2/5 | −1,132 |
| BankNifty v13 sweep fade (bear) | 7.7 | 32.5 | 1.06 | +914 | 0.19 | 2,642 | 0.35 | 225 / −102 | +3.96 | 2/5 | −794 |

In rupees per lot:

| Strategy | Net | Per month | Max drawdown |
|---|---|---|---|
| Crude v4.0 | Rs2.14 lakh | Rs7,186 | Rs2.34 lakh |
| Crude v2.0 | Rs2.20 lakh | Rs7,385 | Rs2.36 lakh |
| Crude v2.1 | Rs1.30 lakh | Rs4,389 | Rs90k |
| BankNifty v0.4 | Rs42k | Rs1,395 | Rs49k |

## When the money was made

| Strategy | Mar 24 - Feb 25 | Feb 25 - Jan 26 | Jan 26 - Sep 26 |
|---|---|---|---|
| Crude v2.0 | −897 | −1,091 | **+4,183** |
| Crude v4.0 | −627 | +4 | **+2,759** |
| Crude v2.1 | +280 | −424 | **+1,449** |
| Crude v4.0 + outside VA | −8 | +369 | +865 |

| Strategy | Mar-Sep 24 | Sep 24-Mar 25 | Mar-Sep 25 | Sep 25-Mar 26 | Mar-Sep 26 |
|---|---|---|---|---|---|
| BankNifty v0.4 | +840 | +235 | −518 | −82 | +928 |
| BankNifty v10.3 | +883 | −490 | −372 | −1,154 | +2,056 |
| BankNifty v13 | −503 | −1,221 | +1,496 | −566 | +1,707 |

**This is the most important finding.** Every crude strategy made its money in Jan-Sep 2026. Over the first 22 months, Mar 2024 to Jan 2026, all three main crude strategies were flat or losing:

| Strategy | Mar 2024 - Jan 2026 |
|---|---|
| v2.1 | −144 |
| v4.0 | −623 |
| v2.0 | −1,988 |

The 30-month totals are positive only because of 2026's volatile crude market.

BankNifty v0.4 is more evenly spread. It made money in 2024 and in 2026 and lost moderately in 2025.

## Execution-cost stress

Extra slippage per round trip is on top of the 0.02%-per-side commission. The commission alone already costs crude v4.0 about 2.6 pts a trade, half of its gross profit.

| Strategy | +2 pts (crude) / +5 pts (BN) | +4 / +10 | +6 / +20 |
|---|---|---|---|
| Crude v4.0 | +452 (PF 1.02) | −1,232 | −2,916 |
| Crude v2.0 | **−497** (PF 0.98) | −3,189 | −5,881 |
| Crude v2.1 | +268 (PF 1.03) | −768 | −1,804 |
| Crude v4.0 + outside VA | +385 (PF 1.03) | −455 | −1,295 |
| BankNifty v0.4 | +1,033 (PF 1.23) | **+663** (PF 1.14) | −77 |
| BankNifty v10.3 | +399 | −126 | −1,176 |
| BankNifty v13 | **−241** | −1,396 | −3,706 |

The crude edges are thin:
- **v2.0 has the highest total but turns negative with just 1 tick of slippage per side**, because it trades 45 times a month.
- v4.0 and v2.1 survive 1 tick but not 2.
- BankNifty v0.4 is the most cost-robust strategy in the whole set, thanks to its large average trade (+19 pts).

## Combining strategies (1 lot each)

Correlation is between each strategy's window-by-window results.

| Pair | Correlation | Net | + windows | Window-level DD* |
|---|---|---|---|---|
| **Crude v4.0 + v2.1** | **+0.29** | **+3,440** | 5/11 | **1,457** |
| Crude v4.0 + v2.0 | +0.62 | +4,331 | 5/11 | 2,735 |
| Crude v2.0 + v2.1 | +0.86 | +3,499 | 4/11 | 2,132 |
| **BankNifty v0.4 + v13** | **−0.03** | **+2,317** | 3/5 | **985** |
| BankNifty v0.4 + v10.3 | +0.82 | +2,328 | 2/5 | 2,380 |

\* Drawdown measured at window boundaries only, so it understates the true intra-window drawdown.

- **v2.0 and v2.1 are nearly the same bet** (r = +0.86), as are v0.4 and v10.3 (r = +0.82).
- **Crude v4.0 + v2.1** and **BankNifty v0.4 + v13** are genuinely different signals.
- Caveat: v13 alone turns negative with 5 pts of slippage. The BankNifty pair beats v0.4 alone only with near-zero slippage. At 5 pts per trade, v0.4 alone (+1,033) beats the pair (+792).

## Verdict

**CrudeOil**

| Role | Strategy | Why |
|---|---|---|
| **Primary** | **v4.0 SHA flip RR3** | The most robust over the full period: 6/11 windows positive, the only one still positive (+888) with its best window removed, survives 1 tick of slippage, +2.54 pts/trade. |
| **Companion / lower-risk** | **v2.1** | The best PF (1.14) and return-to-drawdown (1.45), with a max DD of only 900 pts (Rs90k). |
| Portfolio | v4.0 + v2.1 | Low correlation (+0.29), +3,440 combined, about 46 trades a month. |
| Not recommended | v2.0 | The top raw total (+2,195), but it is all from 2026, it dies at 1 tick of slippage, and it duplicates v2.1. |

**Warning for crude:** nothing made money from Mar 2024 to Jan 2026. Size positions for a long flat or losing stretch. v4.0's forward test, from 14 Sep 2026, is the real check.

**BankNifty**

| Role | Strategy | Why |
|---|---|---|
| **Primary** | **v0.4 EMA pullback + 15m ADX gate** | The best PF (1.33), Sharpe (0.57) and drawdown (1,620) of any BankNifty strategy with 2+ years of data. Still positive with its best window removed. Survives 10 pts of slippage. |
| Optional add-on | v13 | Uncorrelated with v0.4 (r = −0.03), but only worth adding with very low slippage. |

v0.4's limit is frequency: 2.5 trades a month, 74 trades in total, which is a small sample. No BankNifty strategy with 2+ years of data made money at 20 trades a month.
