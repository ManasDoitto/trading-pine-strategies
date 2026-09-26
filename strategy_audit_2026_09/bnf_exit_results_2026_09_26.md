# Results: BankNifty v5.0 R:R + force-flat sweep (run 2026-09-26)

Pre-registration: `pre_registration_bnf_exit_2026_09_26.md` (written before the run). Code: `bnf_exit_sweep.py`.
Raw (gitignored): `research_data/bnf_exit_sweep.csv`. Gross points, 30 months, entries frozen, 40 combos.

## Verdict: the design flaw is real and fixed; the performance problem is not. 0 of 40 pass.

**Pre-registered pick (highest TRAIN PF, >= 40 trades): flat 15:00, R:R 1.5, ADX on.**
PF 1.553, net +2,197.0 pts, maxDD 1,121.4, 58 trades, win 51.7% | TRAIN 1.914 / VALIDATION **0.885** / HOLDOUT 1.376.
Exits 21 TP / 20 SL / 17 force-flat - **take-profit share 36.2%, up from the shipped config's 1.8%.**
It fails four gates: VALIDATION PF 0.885, 58 trades (< 100), 56.5% months positive, best month 48.0% of net. It also
fails criterion 5 - HOLDOUT 1.376 does not beat the shipped 1.688 - though its drawdown is lower (1,121.4 vs 1,358.1).

| | trades | PF | net (pts) | maxDD | win | TP share | TRAIN / VALID / HOLDOUT |
|---|---|---|---|---|---|---|---|
| shipped (14:30, RR 4.0, ADX on) | 56 | 1.484 | +1,980.2 | 1,358.1 | 48.2% | **1.8%** | 1.568 / 1.015 / 1.688 |
| **pick** (15:00, RR 1.5, ADX on) | 58 | 1.553 | +2,197.0 | 1,121.4 | 51.7% | **36.2%** | 1.914 / 0.885 / 1.376 |
| best full PF, in-sample only (15:00, RR 2.0, ADX off) | 76 | 1.657 | +3,361.1 | 1,368.7 | 51.3% | 19.7% | 1.852 / 1.239 / 1.503 |

## 1. The unreachable target was a genuine bug, and R:R - not the flat window - is the lever that fixes it
Take-profit share, ADX on:

| R:R \ flat | 14:30 | 15:00 | 15:15 | 15:20 |
|---|---|---|---|---|
| 1.5 | 33.9 | **36.2** | 36.2 | 36.2 |
| 2.0 | 17.9 | 20.7 | 20.7 | 20.7 |
| 2.5 | 7.1 | 12.1 | 12.1 | 12.1 |
| 3.0 | 5.4 | 8.6 | 8.6 | 8.6 |
| 4.0 | 1.8 | 1.7 | 1.7 | 1.7 |

Moving the flat from 14:30 to 15:00 adds only 2-5 points of TP share; going past 15:00 adds nothing at all, because
entries stop at 15:00 either way. At R:R 4.0 the target is unreachable no matter how late the flat is (1.7-1.8%).

## 2. But fixing it does not buy performance. PF across all 40 combos is 1.334 to 1.657; shipped is 1.484 - mid-pack.
Raising the TP share from 1.8% to 36.2% moved full-sample PF from 1.484 to 1.553. The exit change trades win rate
against average win size and roughly cancels: the strategy was never losing because targets did not fill, it was
force-flatting into a mix that happened to be similar. **This is the main finding - the 4R target was a real design
flaw but not the binding constraint.**

## 3. One consistent, non-cherry-picked effect: flat at 15:00 beats every alternative
Mean full PF over the five R:R values: 14:30 -> 1.447, **15:00 -> 1.572**, 15:15 -> 1.455, 15:20 -> 1.405 (ADX on;
ADX off is the same shape: 1.462 / 1.577 / 1.466 / 1.416). It is the best flat time at 9 of 10 (R:R, ADX) pairs.
Holding past 15:00 is worse than closing at 15:00, and closing at 14:30 forfeits real profit. **If one change is made
to this config, move the force-flat from 14:30 to 15:00.**

## 4. The ADX gate remains not worth its place
Mean PF, ADX off vs on: 1.477 vs 1.469 overall, and every one of the 8 combos that clears PF >= 1.30 in all three
splits has the gate OFF. Consistent with `crude_bnf_v50_results_2026_09_26.md` and the repo's 2026-09-14 conclusion
that the v0.4 ADX gate does not port to SHA-flip entries.

## 5. What still fails everywhere
**0 of 40 combos reach 100 trades** (max 76), **0 reach 70% months positive** (max 60%), **0 keep the best month under
25% of net** (min 29.5%). 8 of 40 clear PF >= 1.30 in all three splits, all with the ADX gate off, best being
flat 15:00 / R:R 3.0 / ADX off (PF 1.599, +3,226.9 pts, TRAIN 1.600 / VALID 1.411 / HOLDOUT 1.756, best month 29.5%).
That one is close on concentration and would be the candidate to watch - but it is one of 40 tried on the same
history, it has 76 trades in 30 months, and it was not the pre-registered pick, so it is reported, not claimed.

## Bottom line
The exit design was broken and is now understood: use R:R <= 2.0 if targets are meant to fill, and move the flat to
15:00. Neither fixes BankNifty's real problem - ~2.5 trades a month, no configuration with 100 trades, and profit
concentrated in a third of the months. Running gate total: 0 of 514.
