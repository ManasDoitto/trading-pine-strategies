# The three breakout variants vs Silver #1 — is the plateau real? (2026-09-26)

Follow-up to `silver_final_verdict_2026_09_26.md`, which only significance-tested breakout(5). All three lookbacks
beat the incumbent on the harness, so the question is whether that is a genuine parameter plateau or one bet counted
three times.

## 1. Harness, gross, 30 months
| | trades | PF | net pts | maxDD | months +ve | vs #1 |
|---|---|---|---|---|---|---|
| Silver #1 | 747 | 1.503 | 222,240 | 33,693 | 58.1% | — |
| breakout(3) | 836 | **1.563** | **337,941** | 71,324 | 67.7% | +115,701 |
| breakout(5) | 825 | 1.519 | 307,265 | **30,646** | **74.2%** | +85,025 |
| breakout(10) | 840 | 1.515 | 317,138 | 37,207 | 71.0% | +94,898 |

## 2. Significance, paired monthly vs #1 (31 months)
| | better months | sign test p | biggest single month | edge excluding it | bootstrap 95% CI | P(worse) |
|---|---|---|---|---|---|---|
| **breakout(3)** | **20/31** | **0.150** | **2026-02 = −53,625 (a LOSS)** | **+169,326** | [−70,548 , +302,217] | 11.1% |
| breakout(5) | 18/31 | 0.473 | 2026-03 = +52,086 (61% of edge) | +32,938 | [−81,354 , +266,759] | 16.9% |
| breakout(10) | 17/31 | 0.720 | 2026-03 = +56,898 (60% of edge) | +37,999 | [−66,070 , +272,663] | 13.1% |

**breakout(3) has a different and better shape.** Its worst month is a large *loss* against the incumbent; removing it
*increases* the edge to +169,326 (+2,178/month over 30 months). For bo(5) and bo(10) the opposite is true — one good
month supplies ~60% of the edge, and removing it leaves ~+1,100-1,270/month.

## 3. Are the three independent evidence?
Correlation of their monthly advantages over #1: bo3–bo10 **0.764**, bo3–bo5 0.573, bo5–bo10 0.596.
All three beat #1 in only **13 of 31 months**; all three lose in 8. So they are related but not identical — a partial
plateau, not three independent confirmations. 2026-03 is the single biggest month for all three
(bo3 +50,374 / bo5 +52,086 / bo10 +56,898).

## 4. TradingView tiled replay, gross, 13 windows — the independent engine
| | trades | PF | net pts | worst-window dd | windows +ve | beats #1 in |
|---|---|---|---|---|---|---|
| **Silver #1** | 875 | **1.548** | 266,172 | **33,706** | **11/13** | — |
| breakout(5) | 964 | 1.369 | 261,439 | 42,612 | 10/13 | 7/13 |
| **breakout(3)** | 981 | 1.487 | **341,764** | **71,329** | **11/13** | **9/13** |

**This is the important result.** On TradingView, breakout(5) loses to the incumbent — but **breakout(3) wins**:
+341,764 vs +266,172 (**+75,592**), beats #1 in 9 of 13 windows, and matches its 11/13 positive windows. So the
ranking reversal I reported earlier applies to bo(5), **not to bo(3)**. Both measurement methods agree that bo(3)
beats the incumbent on points.

**The cost is drawdown, and it is severe.** bo(3)'s worst window drawdown is **71,329 pts — 2.1x the incumbent's
33,706**, driven by W10 (Dec 2025–Mar 2026), the same window that supplies most of its profit. At 30 kg/lot that is
roughly **Rs 2.14 million on a single lot**.

## 5. Verdict on the three
- **breakout(5) and breakout(10): not supported.** Sign tests of 0.473 and 0.720, ~60% of the edge in one month, and
  bo(5) loses outright on TradingView's engine. These are noise dressed as improvement.
- **breakout(3): the only candidate with converging evidence.** It wins on the harness (+115,701), wins on
  TradingView (+75,592), wins 20/31 months and 9/13 windows, and its edge *survives* removing its most extreme month.
  It still does **not** clear a conventional significance bar (p = 0.150, CI spans zero, 11.1% of resamples worse),
  and it is **not** free: 2.1x the drawdown.
- **This is not yet "a real edge".** It is the first variant today where two independent engines agree on direction.
  That is worth forward-testing; it is not worth switching capital to on 30 months of in-sample data.

## 6. Recommendation
The live forward test currently runs **breakout(5)** — on this evidence that is the wrong variant. Switching it to
**breakout(3)** means re-registering the drawdown rule, because bo(3) has already breached the 35,000-pt line in
backtest (71,329 in W10); a rule it is known to violate is not a rule. Either:
(a) keep bo(5) running and treat bo(3) as untested, or
(b) restart the forward test on bo(3) with a drawdown limit set from its own history (e.g. 75,000 pts) and a fresh
    boundary date — stated as a choice for the user, not made unilaterally.
Until then **Silver #1 remains the strategy to trade.**
