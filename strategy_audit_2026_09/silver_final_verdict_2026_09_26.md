# Silver: every variant tested 2026-09-26 vs working_strategies/Silver #1 — is there a real edge?

One harness, same bars (MCX:SILVER1! 5m), same 30-month window (2024-03-25 -> 2026-09-24), qty 1.
Code: `silver_final_comparison.py`. `eff` = net points per point of max drawdown. `conc` = biggest month as % of net.

## GROSS (no costs — the user's standing convention)
| strategy | trades | /mo | PF | net pts | maxDD | win | months +ve | conc | eff | vs #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Silver #1 INCUMBENT** | 747 | 24.9 | 1.503 | **222,240** | 33,693 | 30.5% | 58.1% | 49.2% | 6.60 | — |
| Silver #2 wideATR no breaker | 1,014 | 33.8 | 1.277 | 198,886 | 79,621 | 29.5% | 67.7% | 48.8% | 2.50 | −23,354 |
| Silver #3 v4.0 vanilla | 984 | 32.8 | 1.173 | 87,282 | 43,067 | 28.3% | 48.4% | 43.2% | 2.03 | −134,958 |
| **v4.1 = #1 + breakout(5)** | 825 | 27.5 | 1.519 | **307,265** | **30,646** | 30.2% | **74.2%** | **34.2%** | **10.03** | **+85,025** |
| v4.1 = #1 + breakout(3) | 836 | 27.9 | **1.563** | **337,941** | 71,324 | 30.9% | 67.7% | 40.2% | 4.74 | +115,701 |
| v4.1 = #1 + breakout(10) | 840 | 28.0 | 1.515 | 317,138 | 37,207 | 30.6% | 71.0% | 44.1% | 8.52 | +94,898 |
| v5.0 SHA-ADX hybrid | 112 | 3.7 | 1.968 | 39,577 | 6,959 | 32.1% | 44.8% | 41.5% | 5.69 | −182,663 |
| v5.1 = v5.0 + breakout(5) | 202 | 6.7 | 1.874 | 60,183 | 8,847 | 33.2% | 63.3% | 38.8% | 6.80 | −162,057 |

## NET of 0.02%/side
Same ordering. #1 -> 173,363 (PF 1.372); v4.1 bo(5) -> 258,250 (PF 1.412); v4.1 bo(3) -> 329,029 (PF 1.530);
v5.0 -> 32,739. Costs take ~22% off #1 and ~16% off v4.1 — the breakout variants are *less* cost-sensitive because
their average trade is larger.

## Every comparison run today, and what each says
| comparison | result |
|---|---|
| Harness, gross, 30 mo | v4.1 bo(5) **+38%** over #1, with **9% lower drawdown** and 1.5x the efficiency |
| Harness, net of costs | v4.1 bo(5) **+49%** over #1 |
| Harness, walk-forward (6 windows, 7 configs) | tuned picks **+277,934** vs #1 held **+215,834** — v4.1 favoured |
| **TradingView tiled replay, gross, 13 windows** | **#1 WINS**: PF 1.548 / +266,172 / dd 33,706 / 11-of-13 windows, vs v4.1 PF 1.369 / +261,439 / dd 42,612 / 10-of-13 |
| TradingView single pass, 72-trade overlap | harness and TV agree to **0.03%** — the harness is not the problem |
| Option premium, 1%/side spread | #1 keeps 47% of points; v4.1 keeps 36% — **#1 translates better** |
| Months profitable | v4.1 74.2% vs #1 58.1% — v4.1 better |
| Concentration | v4.1 34.2% vs #1 49.2% — v4.1 better |
| 1,200-config grid around #1 | 86 beat #1 in-sample; walk-forward earned **+161,337 vs #1's +215,834** — tuning loses |
| 1,000-config random sweep | **0 of 1,000** beat #1 even in-sample |

## The decisive test: is the v4.1 advantage distinguishable from noise?
Paired month-by-month, incumbent vs v4.1 breakout(5), 31 months, gross:
- v4.1 better in **18 months**, worse in 13. **Sign test two-sided p = 0.473** — indistinguishable from a coin flip.
- Total difference **+85,024 pts**, but **+52,086 of it is one month (2026-03)**. Remove that month and the
  advantage falls to +32,938 over 30 months — about 1,100 pts/month against strategies that swing tens of thousands.
- **Bootstrap 95% CI on the total difference: [−79,668 , +269,073] pts.** It spans zero by a wide margin.
- **16.7% of bootstrap resamples have v4.1 LOSING to the incumbent.**

## Verdict: no, we have not found a real edge.
The breakout variant looks better on almost every summary statistic — more points, less drawdown, more winning
months, less concentration, better cost-resilience — and it still is not supported:
1. **It fails the only independent measurement.** TradingView's own replay engine ranks the incumbent ahead.
2. **It fails a significance test.** p = 0.473 on monthly wins; the confidence interval on the difference spans zero;
   one month out of 31 supplies 61% of the advantage.
3. **It loses the comparison that matters most for the account.** As bought options at a realistic spread, #1 keeps
   47% of its points and v4.1 keeps 36%.

What IS supported, and is worth keeping:
- **Nothing beats Silver #1.** 1,000 random configs and a 1,200-config grid both failed to, and the two variants that
  appear to (v4.1 bo(3)/bo(5)) do not survive scrutiny.
- **The v5.x direction is dead**: 3.7 trades/month and 18% of #1's points. The EMA9 pullback gate is the specific
  cause; the ADX gate is the second.
- **Silver #1's own weaknesses are now measured**: 49.2% of its profit is one month, only 58.1% of months are
  positive, and in 2026 TradingView shows window drawdowns of 33,700-42,600 pts — bigger than its own 30-month figure.

## What would settle it
The forward test, already live with pre-registered rules (`silver-v41-forward-test`), boundary 2026-09-27. At ~27.5
trades/month it reaches the 60-trade judging threshold in about 2.5 months. Until then, **stay on Silver #1** and do
not size anything on the +307,265 figure.


---
## CORRECTION (added same day, see `silver_definitive_comparison_2026_09_26.md`)
Reason 3 above ("as bought options ... #1 keeps 47% of its points and v4.1 keeps 36%") is WRONG. 36% was v5.1's figure,
not v4.1's. Measured properly, bo(3) as options is +181,947 at a 1% spread (vs #1's +104,882) and +114,618 at 2% (vs
+46,014). The breakout variants translate to options better than #1. Reason 1 applied to bo(5) only, not bo(3) (see
`breakout_three_variants_verdict_2026_09_26.md`). The verdict "no real edge found" was too strong.
