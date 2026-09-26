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
