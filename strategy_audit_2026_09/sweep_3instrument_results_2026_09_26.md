# Results: 3,000-config sweep on silver / crude / BankNifty (run 2026-09-26)

Pre-registration: `pre_registration_silver_sweep_2026_09_26.md` + amendments 1-3. Code: `silver_sweep.py`.
Raw: `research_data/sweep_{SILVER,CRUDEOIL,BANKNIFTY}.csv`. 1,000 randomized configs per instrument over 15
parameters, gross points, 30 months, six fixed calendar windows. Selection criterion: **net points, walk-forward**.

## Verdict: nothing found. Not one config beat its incumbent even in-sample.

| | configs | trades/mo median (max) | best in-sample net | **working_strategies #1** | beat it in-sample |
|---|---|---|---|---|---|
| SILVER | 1,000 | 16.1 (55.2) | +214,198.9 | **+222,240.5** | **0 of 1,000** |
| CRUDEOIL | 1,000 | 6.8 (66.5) | +5,486.9 | **+5,614.5** | **0 of 1,000** |
| BANKNIFTY | 1,000 | 6.7 (25.9) | +9,882.0 | (v0.4, different engine) | n/a |

This is a stronger negative than the focused silver grid, which at least found 86 in-sample winners. A 1,000-draw
random search over 15 parameters could not match a strategy that already exists in the repo, on the very history
that strategy was tuned on. The v5.0 filter family is simply worse than plain v4.0 at earning points.

## Walk-forward: tuning loses to doing nothing on every instrument
Select the best config on windows 1..i-1 by net points, trade it in window i:

| | W2 | W3 | W4 | W5 | W6 | **tuned total W2-W6** | median config |
|---|---|---|---|---|---|---|---|
| SILVER | -10,318 | -4,022 | +18,288 | +56,002 | -4,679 | **+55,270.8** | +64,433.5 |
| CRUDEOIL | -752 | -794 | -393 | -234 | +1,185 | **-987.5** | +859.0 |
| BANKNIFTY | -1,190 | +2,689 | -601 | +916 | -1,975 | **-160.3** | -108.3 |

Tuning underperformed a randomly-chosen median config on **all three**. On crude and BankNifty the tuned procedure
is outright negative. For reference, silver's incumbent earned +215,833.8 over the same W2-W6 - nearly **4x** what
the tuned procedure produced (+55,271).

## Rank correlation, past net points vs next-window net points
| | W2 | W3 | W4 | W5 | W6 |
|---|---|---|---|---|---|
| SILVER | -0.067 | +0.061 | +0.184 | +0.357 | +0.085 |
| CRUDEOIL | +0.168 | +0.250 | -0.345 | +0.017 | -0.110 |
| BANKNIFTY | +0.083 | +0.080 | -0.223 | +0.041 | -0.116 |

Fifteen measurements, centred on zero, sign-flipping. Combined with the focused grid's
(+0.105, -0.048, -0.118, +0.240, -0.384) this is now **twenty independent measurements** saying the same thing:
**how a parameter set performed in the past carries no usable information about how it performs next.**

## What the in-sample leaders do tell us (structure, not selection)
Across all three instruments the top-by-points configs share a shape: **`pb_atr_mult` large (2.0, 3.0, 99=off)** in
13 of the 15 leaders, and **`adx_min` low or zero** in most. That is the same finding as the frequency probe - the
EMA9 pullback proximity gate, not the ADX gate, is what costs this family its points. It is a property of the family,
visible in 3,000 configs, and it is already reflected in plain v4.0, which has neither gate.

## Bottom line
The v5.0 direction is closed. The repo's existing v4.0 strategies are better on points than anything 3,000 random
configs could find, and tuning them further does not transfer. Combined with `silver_beat_222k_results_2026_09_26.md`
and `option_premium_results_2026_09_26.md`, the actionable conclusions of this session are:
1. Keep silver working_strategies #1; it is the best thing here and it survives option buying at ~47% strength.
2. Do not trade crude as bought options - the premium is 31x the per-trade edge.
3. Stop parameter-searching this family. Twenty measurements say it does not transfer.
Running gate total: 0 of 4,714 (3,000 added here).
