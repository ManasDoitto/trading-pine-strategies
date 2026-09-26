# Results: Hull Suite concept on CRUDEOIL 5m (run 2026-09-26)

Pre-registration: `pre_registration_hull_2026_09_26.md` (written before any Hull code existed).
Harness frozen, only the entry condition changed. Points, net of 0.02%/side, qty 1, 33 months.
Code: `hull_variants.py`. Raw: `../research_data/hull_results.csv`.

## Verdict: 0 of 8 pass. One risk-only finding (A2).

| variant | entry change | n | PF | net (pts) | maxDD | TRAIN | VALID | HOLD |
|---|---|---|---|---|---|---|---|---|
| BASELINE | v4.0 SHA flip + EMA9/22 | 853 | 1.145 | +3,504.9 | 2,280.0 | 1.061 | 0.955 | 1.312 |
| A1 | Hma(55) bias replaces EMA9/22 | 1020 | 0.882 | −3,296.7 | 4,026.9 | 0.774 | 0.941 | 0.983 |
| **A2** | **Ehma(55) bias replaces EMA9/22** | 932 | **1.145** | **+3,706.7** | **1,878.8** | 1.026 | 0.821 | 1.368 |
| A3 | Hma(55) on 1H as bias | 895 | 1.069 | +1,674.9 | 2,518.3 | 1.030 | 0.852 | 1.180 |
| A4 | Hma(55) AND EMA9/22 | 459 | 0.954 | −648.4 | 2,954.9 | 0.734 | 0.864 | 1.276 |
| B1 | Hma(55) flip replaces SHA flip | 803 | 1.015 | +336.9 | 3,115.0 | 0.933 | 0.871 | 1.188 |
| B2 | Ehma(55) flip | 802 | 0.966 | −827.3 | 4,040.3 | 1.019 | 0.588 | 1.150 |
| B3 | Hma(89) flip | 721 | 1.103 | +2,210.3 | 3,010.4 | 0.953 | 0.956 | 1.455 |
| B4 | Hma(55) flip + 2-bar confirm | 880 | 0.905 | −2,409.5 | 5,799.7 | 0.799 | 0.767 | 1.107 |

Criterion 1 (PF >= 1.30 in all three splits) is failed by every variant, and not narrowly: no variant
reaches 1.30 in TRAIN or VALIDATION at all. Criteria 3 and 4 also fail everywhere (best single month is
93-368% of net where net is positive). Nothing goes to the shadow book.

## Track B (Hull flip as the trigger) is the clearer failure
All four B variants come in below baseline PF with a LARGER drawdown (3,010-5,800 vs 2,280). Swapping the
SHA flip for a Hull flip is not a lateral move - it is worse on both axes. B4 is the sharpest lesson: adding
a 2-bar confirmation, the textbook whipsaw fix, made it the worst variant tested (PF 0.905, DD 5,799.7). The
confirmation delays entry past the part of the move that pays, while the flip count barely drops (803 -> 880,
it went UP because a held direction re-arms differently). **Do not re-attempt Hull-as-trigger on this
instrument.** It confirms the standing read that this SHA-flip family tops out at PF ~1.05-1.15 and that
swapping one smoothed-trend trigger for another does not move it.

## Hma vs Ehma is the one real signal in this run
A1 (Hma bias) PF 0.882 vs A2 (Ehma bias) PF 1.145 - same variant, same length, only the smoothing differs,
and the gap is 0.26 PF / 7,000 points. Mechanically this is what the formula predicts: Hull's
`2*WMA(n/2) - WMA(n)` step is a linear extrapolation that overshoots, and on 5m crude the overshoot lands on
noise. Ehma's EMA path damps it. **If Hull is ever used anywhere in this repo, use Ehma on intraday
timeframes, not Hma** - and note the deployed InSilico script's default is Hma.

## A2, reported as a risk-only finding (NOT a pass)
Swapping the EMA9/22 alignment filter for an Ehma(55) direction filter holds PF exactly at baseline (1.145),
slightly improves net (+3,706.7 vs +3,504.9, +5.8%) and cuts max drawdown from 2,280.0 to **1,878.8 points,
−17.6%**, on 79 more trades. Per the pre-registration this is reported as risk-only, not as a pass.

**Two caveats that matter more than the headline:**
1. VALIDATION PF degrades, 0.955 -> 0.821 - A2 is worse than baseline in the one slice where the baseline was
   already losing. The drawdown gain is not uniform across the period.
2. Concentration gets worse, not better: best month rises from 65.0% to 93.2% of total net. A2's whole net is
   essentially one month. Max drawdown is a single-path statistic and this one is not robustly sampled.
So: a plausible drawdown lever, on one path, with worse out-of-sample behaviour. Not deployable. If it is
ever revisited it needs a walk-forward re-run, not this single split.

## Bottom line
The Hull Suite concept adds nothing to the crude 5m stack. It cannot replace the SHA flip (Track B, worse on
every axis) and it cannot beat EMA9/22 as a filter on the metric that matters (Track A, PF unchanged at best).
Running total of this repo's gate: 0 of 208 strategies passed.
