# Crude #1: round 2 (50 configs around EMA 9/34), 2026-09-27
Pre-registration: `pre_registration_crude_round2_2026_09_27.md`. Data: `research_data/crude_round2.csv`. Harness, gross points, TRAIN < 2025-06-25 <= HOLDOUT. Cumulative trials: 100.
Controls: 09:15 785 tr, PF 1.263, +5,614 (2,270 / 3,344); 17:30 429 tr, PF 1.476, +6,558 (2,447 / 4,111).

**Test 1 (plateau, needs 5 of 7 slow values beating the 09:15 control in BOTH halves): FAILED, 3 of 7.**
slow 28 (2,315 / 3,988) yes; 30 (2,382 / 2,412) no; 32 (2,378 / 2,556) no; 36 (2,443 / 3,244) no; 40 (2,628 / 3,351) yes by 7 pts; 45 (2,612 / 3,562) yes; 50 (2,583 / 2,750) no.
The 9/34 result was a point that happened to be good, not a plateau: neighbours 30 and 32 fall to +4,794 / +4,934, below the control.
**Test 2 (candidate):** at 09:15 the configs with TRAIN above control and the best HOLDOUT are slow 28 (+6,303, PF 1.333) and minSL 2.0 on 9/34 (+6,282); both gains over the control (+700) are inside the noise seen in round 1 (Spearman +0.008).
At 17:30 no config beat the control's TRAIN (2,447); all the large full-period gains (9/34 +hold 4 +7,696, +rr 4.5 +7,410, +be 2R +7,425) come from HOLDOUT only.
Counting the whole 17:30 group: 20 of 23 configs have higher PF than the control (mostly because the 34-period EMA rejects weak trends) but the TRAIN half is lower for 19 of 23, so it is a shift of profit between halves, not a better strategy.
**Verdict: no configuration of the 100 tried is a demonstrated improvement over crude #1 (or over crude #1 at 17:30). Nothing goes to TradingView replay.**
The only tweak with support across every test remains the later entry start (Part 4 of the 17:30 document): efficiency per trade up, total points unchanged.
