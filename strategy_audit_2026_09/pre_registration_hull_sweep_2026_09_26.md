# Pre-registration: Hull Suite Strategy parameter sweep on CRUDEOIL 5m (written 2026-09-26, BEFORE the sweep)

User request: "test this strategy with multiple different values of HMA in 5 min TF and get the best one".
"This strategy" = the deployed public Hull Suite Strategy (PUB;p6LLNvabNCx9xxBVh43i5UtOrXQYEySv, Pine v2), read
off the chart with getInputValues(): direction=long, src=close, mode=Hma, length=55, 100% of equity, commission 0.
Logic replicated as published: while HULL > HULL[2] enter long, while HULL < HULL[2] enter short; a disallowed
direction closes instead of reversing. Hma = WMA(2*WMA(n/2)-WMA(n), round(sqrt n)); Ehma same with EMA;
Thma(n/2) = WMA(3*WMA(m/3) - WMA(m/2) - WMA(m), m), m=n/2 (integer division as in Pine v2).

## Harness
Same bars as every audit: research_data/bars/MCX_CRUDEOIL1_5m.csv, 2024-01-08 -> 2026-09-24. Signal on bar close,
fill at next bar open (TradingView default). Points per 1 unit, 0.02%/side (NOT the chart's 0), qty 1, first 400
bars skipped. Fixed calendar splits for every combo (the Hull pre-registration's boundaries): TRAIN exits before
2025-09-12 09:00, VALIDATION before 2026-03-11 15:10, HOLDOUT after.

## Grid (252 combos, fixed now)
mode {Hma, Ehma, Thma} x length {9,14,21,34,55,70,89,120,144,180,200,250,300,400}
x direction {long, short, all} x exit {as-published (holds overnight), intraday (flat at the 23:25 bar's open, no
position 23:25-close; re-enters next session per the state rule)}.

## Selection rule (fixed now - this is what "the best one" means)
The PICK = highest TRAIN PF among combos with >= 100 TRAIN trades. VALIDATION and HOLDOUT are then read once,
untouched. Also reported, labelled as in-sample and NOT a selection: best full-sample PF, and a neighbour check
(same mode/direction/exit, adjacent lengths) to show whether the pick sits on a plateau or a spike.

## Pass criteria (unchanged from pre_registration_hull_2026_09_26.md; 252 trials so the 1.30 haircut applies)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT.  2. >= 150 trades.  3. >= 70% months positive.
4. No month > 25% of total net.  5. Beat v4.0 baseline HOLDOUT PF 1.312 and max DD <= 2,280.0.
Every combo is checked against all five; the count that pass is reported. A pick that fails is still reported as
"best of the Hull Suite on 5m", but it is not a candidate for the shadow book.
