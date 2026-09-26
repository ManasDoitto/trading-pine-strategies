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


---
## AMENDMENT (written 2026-09-26, BEFORE any sweep result was read; the first launch crashed on a NameError and
## produced no output, and the relaunch was stopped after ~3 minutes, so nothing was seen)

The user challenged the 60/20/20 trade-count split as potentially misleading. The challenge is correct, on two counts,
and the design is changed rather than defended:

1. **The boundary moved with the config.** Splitting at 60%/80% of each config's own trade list puts the TRAIN/HOLDOUT
   boundary at a different CALENDAR DATE for every config - a 400-trade config and a 40-trade config were being scored
   over different stretches of market and then compared to each other. Replaced with **six fixed calendar windows**,
   identical for every config: 2024-03-25, 2024-08-25, 2025-01-25, 2025-06-25, 2025-11-25, 2026-04-25, 2026-09-25
   (five months each).
2. **Selecting on the first 60% selects for a dead regime.** Silver's profit is concentrated in Jan-Feb 2026, which sits
   in window 5. A single early-train split therefore picks whatever suited the quiet 2024 stretch and then asks it to
   prove itself in the volatile one. Selecting on the whole history overfits; selecting on the early part alone is
   biased the other way. Neither single split answers the real question.

**Replacement primary analysis: walk-forward.** For each window i in 2..6, select the config with the best cumulative
PF over windows 1..i-1 (minimum 30 trades in that history), then record what that config did in window i, which it was
not selected on. Aggregating those five out-of-sample window results measures the PROCEDURE "tune on the past, trade the
winner" rather than the luck of one config. Reported alongside: the shipped config's result in the same windows, and
the median config's, so the tuned pick has something to beat.

Pass criteria are unchanged. The single 60/20/20 split is dropped entirely; per-window figures replace it.


---
## AMENDMENT 2 (written 2026-09-26, BEFORE any sweep result was read - the runs were stopped and restarted)

The user set a frequency requirement, revised once: first ">= 20 trades/month for each script", then
"including all 3 scripts if i get average 40 trades a month, that will be the sweet spot". The binding
version is **>= 40 trades/month COMBINED across silver + crude + BankNifty over 30 months = >= 1,200 trades**.

Measured trade-frequency ceilings on the v5.0 family, 30 months, gross points (probe before the sweep):

| | as shipped | ADX off | ADX off + pullback off | everything loosened |
|---|---|---|---|---|
| SILVER1 | 112 (3.7/mo) PF 1.968 | 329 (11.0/mo) PF 1.438 | **834 (27.8/mo) PF 1.345, +111,456 pts** | 1,723 (57.4/mo) PF 1.192 |
| CRUDEOIL1! | 155 (5.2/mo) PF 1.575 | 544 (18.1/mo) PF 1.166 | 606 (20.2/mo) PF 1.160 | 1,604 (53.5/mo) PF 1.124 |
| BANKNIFTY1! | 56 (1.9/mo) PF 1.484 | 73 (2.4/mo) PF 1.441 | 80 (2.7/mo) PF 1.456 | **620 (20.7/mo) PF 0.944, -2,253 pts** |

Two findings that set the design:
1. **The EMA9 pullback proximity gate, not the ADX gate, is what starves this family of trades.** On silver, turning
   the pullback off takes 11.0 -> 27.8 trades/month and nearly triples net points (+46,332 -> +111,456) for 0.09 of PF.
2. **BankNifty cannot supply 20 trades/month profitably.** The only way to reach it is to strip every filter, and at
   20.7/mo it is a net loser (PF 0.944). So the 40/mo target is enforced on the TRIPLE, not per instrument, and
   BankNifty is expected to contribute the smallest share.

## Revised design
Sweep each instrument separately (1,000 draws each, same seed, same six calendar windows, same harness), with
`pb_atr_mult` extended to {0.5 ... 99=off} and `adx_min` down to 0 so the high-frequency region is actually reachable.
Per-config floor for eligibility: 90 trades (3/mo). BankNifty draws use NSE sessions.

**Portfolio selection (fixed now):** choose one config per instrument, subject to combined trades >= 1,200 (40/mo),
maximising the walk-forward criterion below. The three run as separate scripts on separate instruments, so their
trades do not compete for one position (unlike the 2026-09-13 bnf v0.4+v13 single-script portfolio); combined trade
count is a true sum. Shared margin is a real-money concern and is noted, not modelled.

**Walk-forward remains the primary analysis** (amendment 1): select on windows 1..i-1, score on window i, aggregate
the five out-of-sample results, compare against the shipped configs and the median config.

Pass criteria unchanged, plus: **7. combined >= 40 trades/month.** A config that only reaches 40/mo by going net
negative (as BankNifty does) is reported as failing, not as meeting the target.


---
## AMENDMENT 3 (written 2026-09-26, BEFORE any sweep result was read; the run was stopped again)

The user reframed the objective: "think from net points earned perspective, if some strategy is not getting as many
points earned over the periods like the best strategies we already have in repo, then no fruitful result will come."
Correct, and it invalidates PF as the selection criterion - PF rewards rare, small, high-quality trades, which is
exactly how v5.0 arrived at 112 trades and +39,577 points.

## The bar, re-measured on THIS harness (30 months, gross points, qty 1) so it is comparable
| strategy | trades | /mo | PF | **net pts** | maxDD |
|---|---|---|---|---|---|
| **SILVER working_strategies #1: v4.0 wide-ATR + fixed 350 limit** | 747 | 24.9 | 1.503 | **+222,240.5** | 33,692.8 |
| SILVER #2: v4.0 wide-ATR, no breaker | 1,014 | 33.8 | 1.277 | +198,885.8 | 79,620.7 |
| SILVER #3: v4.0 vanilla | 984 | 32.8 | 1.173 | +87,282.3 | 43,067.4 |
| SILVER #1 params on SILVERM1 | 732 | 24.4 | 1.278 | +126,575.1 | 82,673.7 |
| **CRUDE working_strategies #1: v4.0 SHA flip RR4.0** | 785 | 26.2 | 1.263 | **+5,614.5** | 2,175.6 |
| CRUDE v4.0 RR3.0 | 856 | 28.5 | 1.205 | +4,480.7 | 2,001.4 |
| *silver v5.0 shipped* | 112 | 3.7 | 1.968 | *+39,577.2* | 6,958.6 |
| *silver v5.0, pullback+ADX off* | 834 | 27.8 | 1.345 | *+111,455.9* | 23,741.4 |
| *crude v5.0 shipped* | 155 | 5.2 | 1.575 | *+1,347.0* | 2,175.6 |

**v5.0 is not competitive on points and never was.** Silver v5.0 as shipped earns **18%** of what the repo's existing
silver #1 earns; even with its two starving filters removed it reaches 50%. Crude v5.0 earns **24%** of crude #1.
The existing v4.0 strategies also already satisfy the frequency target on their own: silver 24.9/mo + crude 26.2/mo
+ BankNifty v0.4 ~2.5/mo = **~54 trades/month combined**, comfortably past the 40/mo sweet spot.

So the honest statement of where this stands: **the thing to beat is +222,240 pts (silver) and +5,614 pts (crude) at
~25 trades/month each, not v5.0's numbers.** v5.0's high PF was never evidence of a better strategy.

## Design changes
1. **Selection criterion is now net points**, not PF, evaluated walk-forward (select on windows 1..i-1 by cumulative
   net points, score on window i), subject to the frequency floor. PF, drawdown and month-concentration are still
   reported and still gate, but they no longer choose.
2. **`use200` is added to the search space.** `signals_v50.v50_frame` hardcodes `close > e200` into trend_l, so every
   configuration reachable by the previous sweep carried the EMA200 filter. The repo's point-earning v4.0 strategies do
   NOT use it. With it off and v4.0-like parameters the sweep region reaches n=978 (32.6/mo), PF 1.248, +102,234 pts -
   i.e. the winning region was unreachable before this fix. (Pine note: the rewritten .pine files hardcode EMA200 ON to
   match the Python, so they inherit the same restriction.)
3. **New pass criterion 8: the pick must beat its instrument's working_strategies #1 on net points** over the same
   window, on this harness, or it is reported as not worth switching to.
