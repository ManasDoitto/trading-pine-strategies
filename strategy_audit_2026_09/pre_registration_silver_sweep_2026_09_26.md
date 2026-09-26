# Pre-registration: large silver parameter search, MCX 5m (written 2026-09-26, BEFORE the sweep)

User asked to "tune or test as many parameter values as we can to get a better strategy ... it should give me better
numbers". A search this size WILL produce better full-history numbers whether or not an edge exists - with ~1,500
draws the best full-sample PF is mostly selection noise. This design is therefore built so the result answers a
different, answerable question: **does anything found by tuning survive on data it was not chosen on?**

Standing context: the repo declined unbounded re-tuning on 13 Sep 2026 for exactly this reason
(`protected-crude-script.md`). This run does not overturn that; it measures it.

## Harness (frozen)
`research_sim.simulate` on `research_data/bars/MCX_SILVER1_5m.csv`, window 2024-03-25 -> 2026-09-24 (30 months),
**gross points, commission 0**, qty 1, gap fills as TradingView, first 400 bars skipped. Entry family is v5.0
(SHA flip + EMA9/22 + EMA200 + optional ADX/vol/pullback/ATR gates), signal on close, fill next open.
The fast frame builder in `silver_sweep.py` is asserted equal to `signals_v50.v50_frame` on the shipped config
before any sweeping (`validate_fast()`).

## Split (fixed now)
By exit time: **TRAIN = first 60%, VALIDATION = next 20%, HOLDOUT = last 20%** of trades, per config.
Selection touches TRAIN only. VALIDATION and HOLDOUT are read once, after the pick is fixed.

## Search space (randomized search, 1,500 draws, seed 20260926)
sha_len1 {5,10,15,20} | sha_len2 {5,10,15,20} | sha_min_hold {1,2,3,5,8} | sw_len {5,10,15,20} | sw_buf {0.0,0.1,0.25}
min_sl {1.0,1.5,2.0,2.5,3.0} | max_sl {3.0,4.0,5.0,6.0,8.0} (kept only if max_sl > min_sl) | rr {1.5,2.0,2.5,3.0,3.5,4.0,5.0}
adx_min {0=off,15,20,25,30,35,40} | pb_atr_mult {0.25,0.5,1.0,1.5,3.0=effectively off} | atr_min_pts {0,20,50}
use_vol_filter {T,F} x vol_sma_len {30,50,80} | day_loss_limit {0,250,350,500,1000}
session/force-flat {("09:15-23:30", flat 22:45), ("09:15-23:30", flat 23:25), ("17:00-23:30", flat 23:25) = COMEX-active}
Randomized rather than full-grid: the full cross product is ~50M and random search covers a high-dimensional space
far better than a coarse grid at equal cost.

## Selection rule (fixed now)
PICK = highest **TRAIN** PF among configs with **>= 60 TRAIN trades**. Ties broken by more TRAIN trades.
Then VALIDATION and HOLDOUT are read once for that config, and for the top 10 by TRAIN PF.

## Selection-bias controls (all fixed now, reported whether they flatter the result or not)
1. **Train-to-holdout decay.** Mean TRAIN PF of the top 10 vs their mean HOLDOUT PF. If tuning is finding noise, the
   holdout mean collapses toward the population median.
2. **Rank correlation** (Spearman) between TRAIN PF and HOLDOUT PF across all configs. Near zero = tuning on TRAIN
   carries no information about the future.
3. **Population baseline.** Median HOLDOUT PF across all configs. The pick must beat this to have earned anything.
4. **Cross-contract check.** The pick is re-run unchanged on MCX:SILVERM1 (different contract, same metal, never used
   for selection). This is the closest thing to out-of-sample data available.
5. **Shipped baseline.** v5.0 as configured: PF 1.968, +39,577.2 pts, maxDD 6,958.6, 112 trades,
   TRAIN/VALID/HOLDOUT 1.064 / 3.133 / 1.464.

## Pass criteria (1,500 trials, so the PF >= 1.30 multiple-testing haircut applies, and it is weak at this trial count)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT.  2. >= 100 trades.  3. >= 70% of months positive.
4. No month > 25% of total net.  5. Beat the shipped HOLDOUT PF (1.464) and not exceed its max drawdown (6,958.6).
Plus, specific to this run: **6. the pick must also clear PF >= 1.30 on SILVERM1** without re-tuning.
Fail any = not a pass. Nothing here goes to real money; a pass goes to the shadow book for a month.

## Prior
0 of 514 tested strategies have passed these gates. Expect a config with a spectacular TRAIN PF and an unremarkable
HOLDOUT PF; the informative output is control 1 and 2, not the winner's headline number.
