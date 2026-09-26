# Can anything beat silver's +222,240 pts? (run 2026-09-26)

Question: "can we beat +222,240 on silver?" Code: `silver_beat_222k.py`. Raw: `research_data/silver_beat_222k.csv`.
1,200-combination grid around the incumbent (working_strategies/Silver #1: v4.0 wide-ATR + fixed 350 daily limit)
over minSL / maxSL / R:R / daily-limit / swing-lookback. Same harness, 30 months, gross points, qty 1.
Six fixed five-month windows. Selection criterion: **net points**, walk-forward.

## Answer: in-sample yes, out-of-sample no. Tuning earned LESS than leaving the incumbent alone.

| | W2-W6 net points |
|---|---|
| **Incumbent, held unchanged** | **+215,833.8** |
| Median config, held unchanged | +168,271.2 |
| **Tuned walk-forward** (re-pick each window on past net points) | **+161,337.0** |

Tuning is **25% worse than doing nothing**, and also worse than picking a config at random and leaving it. This is the
whole answer: the search does find better numbers, but they do not survive the next window.

## In-sample, it looks easy - 86 of 1,200 configs beat the incumbent
Best: minSL 2.5 / maxSL 4.0 / R:R 2.0 / no daily limit / swing 15 -> **+289,189.3 pts** (+30%), 1,168 trades
(38.9/mo), PF 1.459, max DD **28,908.9 (lower than the incumbent's 33,692.8)**, 67.7% of months positive.
More points, more trades, less drawdown, more winning months. It is exactly the result that would be quoted as a
discovery - and it is in-sample only.

## Why it is not real: pick-on-the-past, trade-the-next
| window | config picked on prior windows | its prior net | what it then earned | incumbent | median config |
|---|---|---|---|---|---|
| W2 | 3.0/5.0 rr3.0 dl250 sw10 | +15,752 | +10,952 | **+17,786** | +12,057 |
| W3 | 2.0/5.0 rr4.0 dl250 sw5 | +32,904 | +1,415 | **+4,921** | +7,862 |
| W4 | 3.0/5.0 rr3.5 dl350 sw5 | +42,367 | +3,237 | **+12,519** | +7,700 |
| W5 | 3.0/5.0 rr3.0 dl0 sw10 | +64,269 | +115,443 | **+136,555** | +90,225 |
| W6 | 3.0/4.0 rr3.5 dl0 sw5 | +231,877 | +30,289 | **+44,052** | +50,428 |

The tuned pick lost to the incumbent in **all five** windows. In W6 the config that had earned the most over the
previous 25 months ranked **968th of 1,200** in the window that followed.

## The transfer measurement (this is the number worth keeping)
Spearman rank correlation, cumulative past net points vs next-window net points, across all 1,200 configs:

| W1->W2 | W1-W2->W3 | W1-W3->W4 | W1-W4->W5 | W1-W5->W6 |
|---|---|---|---|---|
| +0.105 | -0.048 | -0.118 | +0.240 | **-0.384** |

Full-period net vs W6 net: **rho = -0.022**, i.e. no relationship at all. Knowing how a parameter set performed over
30 months tells you nothing about the next five, and at the final window the relationship is meaningfully NEGATIVE:
the configs that did best historically did worst next. **Parameter performance in this family does not persist.**
This closes the "tune it harder" question for the v4.0 silver family - not with an opinion, with a measurement.

## A caveat that cuts against the incumbent too
The incumbent earns **61.4% of its total in window 5 alone** (Nov 2025 - Apr 2026: +136,555 of +222,240). The best
in-sample config has the same shape (59.5%). This is not a strategy with a steady edge; it is a strategy that was
long the right way during one silver move. The incumbent's own parameters were also chosen on roughly this history
(the 14 Sep wide-ATR recalibration), so +222,240 is not a clean out-of-sample number either - it is the best
available reference point, not proof.

## Bottom line
+222,240 cannot be beaten in any way that would have helped you. Keep silver working_strategies #1. Do not re-tune
this family on this history again - the measurement above says the information is not there. The open questions that
could still change the answer are new out-of-sample data (forward testing) and option-premium economics, neither of
which is a parameter search. Running gate total: 0 of 1,714 (1,200 added here).
