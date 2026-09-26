# Pre-registration: SILVER v4.1 breakout(3) FORWARD TEST — RESTART (written 2026-09-26, before any forward data)

Supersedes `pre_registration_silver_v41_forwardtest_2026_09_26.md`, which ran **breakout(5)**. That variant was chosen
before the per-variant significance testing was done, and the evidence now says it was the wrong one
(`breakout_three_variants_verdict_2026_09_26.md`): bo(5) fails its sign test (p = 0.473), takes ~60% of its edge from
one month, and **loses to the incumbent on TradingView's own replay engine**. bo(5)'s forward run is abandoned with
zero forward trades recorded, so nothing is lost and nothing is being reinterpreted after the fact.

## Why breakout(3)
It is the only silver variant today where two independent engines agree:
| | harness (gross, 30mo) | TradingView replay (gross, 13 windows) |
|---|---|---|
| Silver #1 incumbent | 222,240 | PF 1.548, +266,172, 11/13 windows +ve |
| **breakout(3)** | **337,941 (+115,701)** | **PF 1.487, +341,764 (+75,592), 11/13 windows +ve, beats #1 in 9/13** |
Paired monthly vs #1: better in **20 of 31 months**, sign test p = 0.150. Its single most extreme month is a **loss**
(2026-02, −53,625); excluding it the edge **grows** to +169,326 (+2,178/month). That shape is the opposite of bo(5)'s.
It still does not clear a conventional significance bar: bootstrap 95% CI [−70,548 , +302,217] spans zero, and 11.1%
of resamples have it losing. **That is precisely what this forward test exists to resolve.**

## Setup
Script `6_v4.1_flip_breakout_forwardtest` (`USER;81dddb8a44dd413890eb0882d509c316`), study `l7BgGR`, MCX:SILVER1! 5m.
Inputs: **boLookback = 3**, breakout ON, commission **0.02%/side**, everything else frozen at working_strategies
Silver #1 (SHA 10/10 flip, EMA9/22, minSL 2.5, maxSL 5.0, RR 3.0, daily limit 350, session 09:15–23:30).
**Forward boundary: 2026-09-27 00:00 IST.** The AUD/FWD table splits backtest from forward and never mixes them.

## Thresholds, derived from bo(3)'s own 13-window history (not invented)
Per-window PF: median 1.245; 8 of 13 at or above 1.20; **2 of 13 below 0.90** (0.680, 0.701).
Per-window drawdown: median 8,274; **2 of 13 above 35,000**; **0 of 13 above 71,329** (the observed maximum).
Trades per ~81-day window: median 75, minimum 63.

## Pass / fail rules (fixed now, never to be moved)
Judge only after **>= 60 forward trades** (~1 window at this rate, about 2.5 months).
- **KEEP** if forward PF >= **1.20** AND forward max drawdown stays under **75,000 pts**.
- **DROP** if forward PF < **0.90** after 60 trades, OR forward drawdown exceeds **75,000 pts**.
- **INCONCLUSIVE** between 0.90 and 1.20 — keep running, do not promote.
- Losing streaks of 8–10 are normal at a ~31% win rate and are not a fail.
Historical false-positive rate of the DROP rule: 2 of 13 windows (15%) on PF, 0 of 13 on drawdown.
**The 75,000-pt line is deliberately permissive** — it sits just above the worst drawdown bo(3) has ever produced
(71,329), so it fires only on behaviour never seen in 30 months. At 30 kg/lot that is about **Rs 2.25 million on one
lot**, which is the real risk being accepted and is why this is a shadow-book test, not a capital allocation.

## The comparison that actually decides it (fixed now)
Profitability alone is not the question — **beating Silver #1 is**. At judging time, re-harvest MCX:SILVER1! 5m bars
for the forward period and run the incumbent (breakout OFF, identical everything else) over the **same trade window**
on `research_sim`, then compare paired. bo(3) is promoted only if it clears the rules above **and** out-earns the
incumbent over the same forward bars. A profitable bo(3) that trails the incumbent is a fail.

## Secondary readings (recorded, not pass/fail)
1. Share of forward trades from FLIP vs BREAKOUT entries — if the breakout contributes little, the premise is wrong.
2. Whether forward profit concentrates in one month, as it does in backtest for every variant tested.
3. Option-premium translation at judging: bo(3) has not been run through the option model at all.

## Prior
0 of 4,714 tested strategies have passed this repo's gates. Silver #1 has never been forward tested either. Expect the
forward window to lack a Dec 2025–Mar 2026-style move, so forward PF will likely look worse than +337,941 suggests.
