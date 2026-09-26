# Pre-registration: SILVER v4.1 flip+breakout FORWARD TEST (written 2026-09-26, BEFORE any forward data exists)

Script: `working_strategies/Silver/6_v4.1_flip_breakout_forwardtest.pine.txt`. MCX:SILVER1!, 5m.
Same shape as the crude v4.0 forward test (`[[crude-v4-forward-test]]`): rules fixed now, never moved later.

## What is being tested and why
`v40_breakout_results_2026_09_26.md` found that adding a Donchian breakout as a second entry to the frozen
working_strategies/Silver #1 base beats the incumbent on the 30-month harness:

| | trades | PF | net pts | maxDD | conc | months +ve |
|---|---|---|---|---|---|---|
| incumbent (flip only) | 747 | 1.503 | +222,240 | 33,693 | 61.4% | 58.1% |
| **B2, lookback 5 (the default)** | 825 | 1.519 | **+307,265** | **30,646** | 72.0% | **74.2%** |
| B1, lookback 3 | 836 | 1.563 | +337,941 | 71,324 | 55.4% | 67.7% |

**The lookback was chosen from six values on this same history, so none of that is out-of-sample.** A walk-forward
check over six windows did pass (+277,934 vs +215,834 for holding the incumbent), but the pool was seven configs.
This forward test is the only thing that can settle it.

## Boundary
**Forward period starts 2026-09-27 00:00 IST.** Every bar before that is backtest and was used in selection;
everything after is out-of-sample. The script's on-chart table splits the two and never mixes them. The backtest
column exists only to confirm the script reproduces the harness - it is not evidence.

## Pass / fail rules (fixed now, never to be moved)
Judge only after **>= 60 forward trades** (about 2.5 months at 27.5 trades/month).
- **KEEP** if forward PF >= 1.20 AND forward max drawdown stays under **35,000 pts**.
- **DROP** if forward drawdown ever exceeds **35,000 pts**, or forward PF is below **0.90** after 60 trades.
- **INCONCLUSIVE** (keep running, do not promote) if PF lands between 0.90 and 1.20.
- A losing streak of 8-10 is normal at a ~30% win rate and is not a fail on its own.
Drawdown bar of 35,000 pts is set just above the incumbent's own 33,693, i.e. the variant is not allowed to be worse
on risk than what it would replace. At 30 kg/lot, 35,000 pts is about Rs 1.05 million on one lot.

## Secondary readings (recorded, not pass/fail)
1. Split of forward trades between FLIP and BREAKOUT entries. If the breakout contributes little forward, the whole
   premise is wrong regardless of PF.
2. Whether forward results concentrate in one month the way the backtest concentrates in window 5 (72% for B2).
3. B1 (lookback 3) is NOT being forward tested at first; only the default B2 runs. Running both at once on one slot
   would double the multiple-testing problem for no extra information.

## What this forward test cannot tell us
It is futures points, not option premium. Option translation (`option_premium_results_2026_09_26.md`) keeps roughly
40-47% of futures points at a 1%/side spread and dies near 2%. A forward pass here is necessary, not sufficient.

## Prior
The incumbent itself has never been forward tested either. If v4.1 fails, that says nothing good about the base.
Expect W5-style concentration to be absent from any 2-3 month forward sample, so forward PF will likely look worse
than +307,265 implies.
