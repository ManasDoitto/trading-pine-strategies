# Silver: definitive comparison of everything tested, one basis (2026-09-26)

Same bars (MCX:SILVER1! 5m), same window (2024-03-25 -> 2026-09-24, 30 months), 1 lot, points. Code:
`silver_final_comparison.py` + `option_premium_sim.py`. Raw: `research_data/silver_definitive.csv`.
"Silver #1" = working_strategies/Silver #1 (SHA flip + EMA9/22, wide-ATR stops 2.5-5.0, RR 3, daily limit 350).
"bo(N)" = Silver #1 unchanged PLUS an extra entry when price closes beyond the prior N-bar high/low.

| strategy | trades | gross pts | after 0.02%/side | PF (gross) | maxDD gross / net | best-3-months share | profit ex best 3 mo | 95% CI low (total) | P(total<=0) | as options 1% spread | as options 2% spread |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Silver #1** | 747 | 222,240 | 173,363 | 1.503 | 33,693 / 38,708 | **84%** | +34,726 | +25,064 | 1.1% | +104,882 | +46,014 |
| Silver #2 (no breaker) | 1,014 | 198,886 | 137,427 | 1.277 | 79,621 / 90,030 | 88% | +24,605 | -21,984 | 4.0% | +82,050 | -1,210 |
| Silver #3 (vanilla) | 984 | 87,282 | 27,276 | 1.173 | 43,067 / 45,805 | 86% | +12,136 | -1,544 | 2.8% | -10,872 | -91,772 |
| **bo(3)** | 836 | **337,941** | **329,029** | **1.563** | 71,324 / **43,748** | **66%** | **+113,719** | **+111,678** | **0.0%** | **+181,947** | **+114,618** |
| **bo(5)** | 825 | 307,265 | 258,250 | 1.519 | **30,646** / **37,432** | 64% | +110,976 | +100,158 | 0.0% | +169,554 | +104,628 |
| bo(10) | 840 | 317,138 | 273,528 | 1.515 | 37,207 / 37,933 | 74% | +83,693 | +85,099 | 0.0% | +183,489 | +115,959 |
| v5.0 SHA-ADX | 112 | 39,577 | 32,739 | 1.968 | 6,959 / 7,670 | 90% | +3,877 | +354 | 2.4% | +15,147 | +5,255 |
| v5.1 v5.0+breakout | 202 | 60,183 | 47,604 | 1.874 | 8,847 / 9,790 | 85% | +9,322 | +6,918 | 0.9% | +19,577 | +2,091 |

## Profit by calendar year (net of 0.02%/side; 2026 is Jan-Sep only)
| | 2024 (from Mar 25) | 2025 | 2026 (Jan-Sep) |
|---|---|---|---|
| Silver #1 | +16,073 | **-102** | +157,392 |
| bo(3) | +13,609 | **+60,363** | +255,058 |
| bo(5) | +5,059 | +56,878 | +196,312 |
Silver #1 earned nothing in 2025 after costs. The breakout versions earned ~+57,000-60,000 in that same year, in a
period with no Jan-Mar 2026-style move. That is evidence the breakout adds something that does not depend on the one
big silver run - the single most useful fact in this table.

## CORRECTION to earlier statements today
1. **I told the user that as bought options "#1 keeps 47% of its points and v4.1 keeps 36%", and used that as one of
   three reasons the breakout was not supported. That was wrong.** The 36% figure belonged to v5.1 (breakout bolted
   onto the v5.0 filter stack, +52,920 of +145,387), not to v4.1. Measured properly, bo(3) as options is +181,947
   at a 1% spread and +114,618 at 2%; bo(5) is +169,554 / +104,628; Silver #1 is +104,882 / +46,014. **The breakout
   versions translate to options BETTER than #1, not worse** - about 2.5x #1's option profit at a 2% spread.
2. I held the new strategy to a stricter standard than the incumbent. Silver #1's best 3 months are 84% of its
   profit (bo(3): 66%), and it has never been forward tested and was itself tuned on this same history. Under
   the same test that I applied to the breakout - "is the total distinguishable from zero" - #1 passes (lower 95%
   bound +25,064, 1.1% of resamples <= 0) and so do bo(3)/bo(5) (lower bounds +111,678 / +100,158, 0.0%).
3. The "2.1x drawdown" for bo(3) is a gross-of-costs figure (71,324 vs 33,693). Net of costs it is 43,748 vs
   38,708 - **13% higher, not 110%** - and bo(5) is 37,432, lower than #1. The gross figure is path-dependent (the
   daily-loss lock is computed on realized P&L, so costs change which days lock); costs are real, so the net
   figure is the better guide. I have not fully isolated the mechanism, so treat both numbers as a range.

## What is genuinely still open
- All silver strategies here share one problem: a single silver move (Jan-Mar 2026) dominates. Every strategy's
  profit is heavily weighted to it, #1 most of all.
- The breakout-vs-#1 DIFFERENCE, paired monthly, is not conventionally significant (bo(3): better in 20/31 months,
  sign test p = 0.150). 31 months is a low-power sample; this is "not proven", not "disproved".
- Both #1 and bo(3) were tuned on this same 30 months. Neither has any out-of-sample evidence.
- bo(5) is the variant that loses to #1 on TradingView's replay; bo(3) does not.

## Bottom line
On every basis measured - harness gross, harness net, TradingView replay (bo(3)), options at 1% and 2% spread,
2025 alone, profit excluding the best 3 months, concentration, and lower confidence bound - bo(3) is ahead of
Silver #1. It is behind only in 2024 and on gross-of-costs drawdown. It is worth forward testing, and is now running.

---
## Anatomy of bo(3) vs Silver #1 (30 months, gross points, 1 lot) — and a description correction
| measure | Silver #1 | bo(3) |
|---|---|---|
| trades (per month) | 747 (24.9) | 836 (27.9) |
| win rate | 30.5% | 30.9% |
| avg win / avg loss | +2,912 / -851 (3.42x) | +3,637 / -1,039 (3.50x) |
| avg trade / median trade | +298 / -290 | +404 / -324 |
| largest win / largest loss | +43,422 / -9,542 | +36,806 / -16,490 |
| longest losing streak | 16 | 20 |
| avg hold (median) | 10.9h (3.1h) | 15.0h (4.0h) |
| avg stop distance | 833 pts (0.58%) ~ Rs 24,990/lot | 1,044 pts (0.72%) ~ Rs 31,320/lot |
| exits | 518 stop / 229 target | 578 stop / 258 target |
| long / short net | +117,307 (376) / +104,933 (371) | +152,897 (467) / +185,045 (369) |
| entry trigger | SHA flip 100% | breakout 757, flip 39, both 40 |
| days with an entry | 481 (1.55/day) | 417 (2.00/day) |

**Description correction.** bo(3) has been called "Silver #1 plus an extra breakout entry". That understates it:
**90.5% of its trades (757 of 836) are triggered by the breakout**, and running a 3-bar breakout with NO SHA flip at all
gives +329,025 gross (PF 1.546, 855 trades) versus +337,941 with it, with identical drawdown (71,324). The flip adds
~2.6%. bo(3) is effectively a **3-bar Donchian breakout with an EMA9/22 trend filter** that borrows Silver #1's stop,
target and daily-limit rules. The comparison is therefore "breakout trigger vs SHA-flip trigger, same exits" — which is
also why breakouts at lookbacks 3, 5 and 10 all land in the same place: it is the breakout family, not a lucky setting.
Consequences: (1) at 20 consecutive losses and a median trade of -324 pts, the psychological load is higher than #1's;
(2) the median trade loses, so the strategy lives entirely on the 3.5x win/loss ratio; (3) shorts out-earned longs by
21% despite fewer trades in a period when silver rose.
Dashboard: `strategy_comparison_dashboard.html` (Silver H2H card).


---
## CORRECTION 2 (found 26 Sep while testing BankNifty): bo(3)'s "after costs" number is flattered
Gross-to-net gap per trade for the silver variants: Silver #1 67.6 pts, bo(5) 58.5, bo(10) 51.4, **bo(3) 10.6**.
Costing bo(3) removed only 8,912 pts (2.6%) where the others lose 15-22%. Costs change which days the 350-pt daily-loss
lock fires, so the net run took a different, luckier trade sequence; roughly 40,000 pts of bo(3)'s +329,029 net looks
like path luck, and my "+90% after costs" and "2025: +60,363" headlines for bo(3) overstate it. The GROSS comparison
(+337,941 vs +222,240, +52%) is the cleaner one and is unaffected. It also shows this strategy's outcome moves by tens
of thousands of points from a 0.02% cost change - a robustness warning independent of the ranking.
The Silver H2H dashboard card has been patched (headline stat replaced, asterisk on the bo(3) net cell).
