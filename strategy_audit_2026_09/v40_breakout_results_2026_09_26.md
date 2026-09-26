# Results: Donchian breakout on the v4.0 base, silver (run 2026-09-26)

Pre-registration: `pre_registration_v40_breakout_2026_09_26.md`. Code: `v40_breakout_test.py`.
Raw: `research_data/v40_breakout.csv`. 30 months, gross points, qty 1, six fixed calendar windows.
Base frozen at silver working_strategies #1; the only change is `entry = SHA flip OR Donchian breakout`.

## Verdict: the first real candidate today. 5 of 6 variants beat +222,240 on points, but none passes all four gates.

| variant | trades | /mo | PF | **net pts** | maxDD | win | months +ve | concentration |
|---|---|---|---|---|---|---|---|---|
| **INCUMBENT (flip only)** | 747 | 24.9 | 1.503 | **+222,240.5** | **33,692.8** | 30.5% | 58.1% | 61.4% |
| **B1 flip OR breakout(3)** | 836 | 27.9 | **1.563** | **+337,941.4** | 71,324.1 | 30.9% | **67.7%** | **55.4%** |
| B2 flip OR breakout(5) | 825 | 27.5 | 1.519 | +307,264.8 | **30,646.1** | 30.2% | **74.2%** | 72.0% |
| B3 flip OR breakout(10) | 840 | 28.0 | 1.515 | +317,138.0 | 37,206.8 | 30.6% | 71.0% | 70.1% |
| B4 flip OR breakout(20) | 813 | 27.1 | 1.484 | +289,945.5 | 37,877.5 | 30.6% | 67.7% | 68.1% |
| B5 breakout-only(5) | 845 | 28.2 | 1.472 | +282,454.0 | 35,388.1 | 28.9% | 61.3% | 77.6% |
| B6 flip OR bo(5) + ADX25 | 690 | 23.0 | 1.278 | +153,953.7 | 85,849.9 | 29.1% | 64.5% | 57.5% |

**The diagnosis from v5.1 was right.** The same breakout idea that earned only 65% of the incumbent's points bolted
onto the v5.0 filter stack earns **+52% MORE** than the incumbent on the v4.0 base. The filters were the problem,
not the entry.

## Gate results - no clean pass
| variant | net > 222,240 | >= 600 trades | conc <= 61.4% | dd <= 33,693 |
|---|---|---|---|---|
| B1 | PASS | PASS | **PASS (55.4%)** | **FAIL (2.1x)** |
| B2 | PASS | PASS | FAIL (72.0%) | **PASS (30,646)** |
| B3, B4, B5 | PASS | PASS | FAIL | FAIL |
| B6 | FAIL | PASS | PASS | FAIL |

**B1 and B2 each fail exactly one gate, and they fail different ones.** B1 earns the most and is *less* concentrated
than the incumbent (55.4% vs 61.4%) with more positive months (67.7% vs 58.1%), but its drawdown is **2.1x**
(71,324 vs 33,693). B2 keeps drawdown *below* the incumbent's (30,646) and has the best months-positive of any
variant (74.2%), but 72% of its profit is one window.

## Criterion 5 (walk-forward) PASSES - the first time in this session
Selecting among these seven configs on windows 1..i-1 by net points and trading the pick in window i:

| window | picked | its past net | earned | incumbent |
|---|---|---|---|---|
| W2 | B1 | +12,190 | +4,705 | +17,786 |
| W3 | INCUMBENT | +24,193 | +4,921 | +4,921 |
| W4 | B1 | +29,315 | **+35,640** | +12,519 |
| W5 | B2 | +74,596 | **+221,187** | +136,555 |
| W6 | B2 | +295,783 | +11,481 | +44,052 |
| | | **total W2-W6** | **+277,934** | **+215,834** |

Walk-forward selection beat holding the incumbent by **+62,100 points (+29%)**. Every other walk-forward test today
lost to doing nothing; this one does not. The pool is only seven configs rather than a thousand, which is exactly why
- there is very little to overfit to.

## B1 beats the incumbent in 5 of 6 windows
W1 +12,190 vs +6,407 | W2 +4,705 vs +17,786 | W3 +12,420 vs +4,921 | W4 +35,640 vs +12,519 |
W5 +187,246 vs +136,555 | W6 +85,739 vs +44,052. Only W2 is worse. This is not a one-window artefact - it is the
first variant today whose advantage is spread across the period.

## The honest cost, and the ADX confirmation
B1's efficiency is **worse**: 4.74 points per unit of drawdown vs the incumbent's 6.60. It earns more by risking more.
A 71,324-point drawdown at 30 kg/lot is roughly **Rs 2.14 million** on one lot - that is the number to judge, not the
+52%. B2 is the risk-conscious alternative: +38% more points than the incumbent with slightly *less* drawdown.
Separately, **B6 confirms the ADX finding a third time**: adding the 15m ADX>=25 gate to the best base cuts net from
+307,265 to +153,954 and triples drawdown. Do not use that gate on SHA-flip entries.

## What this is and is not
It IS: a genuine, pre-registered, walk-forward-positive improvement on the repo's best silver strategy, from a
six-variant test (mild multiple-testing, not a 1,200-config search).
It is NOT: validated out of sample. The lookback was chosen from six values on this same history, and silver's W5
still dominates every variant. It has not been run in TradingView, and not been translated to option premium.
**Next steps, in order: (1) option-premium translation of B1 and B2, since that is what would actually be traded;
(2) a drawdown control for B1 - the 350-pt daily limit was tuned for the flip-only book and may be wrong for a
book with 12% more trades; (3) TradingView verification.**

## Bottom line
Adding a 3-bar Donchian breakout to silver v4.0 earns **+337,941 vs +222,240 (+52%)**, with better concentration and
more winning months, at 2.1x the drawdown. B2 (5-bar) earns +38% more at slightly lower drawdown than the incumbent.
This is the first thing tested today that is worth taking further.
