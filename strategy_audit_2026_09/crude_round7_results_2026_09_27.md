## Correction (2026-09-27, same day): reversal-exit had a one-bar lookahead bug, now fixed
The original `reversal_exit` engine hook closed a position **at bar i's open using a signal that needs bar i's own close** (the SHA-flip/EMA state at the moment of exit) &mdash; that signal cannot be known before bar i's open in real trading.
Every other exit in this harness (stop, target, flat, time) only ever uses information available at the moment it acts (a pre-set stop/target level, or the current bar's own open), so this was a genuine one-bar lookahead, isolated to the two "reversal exit" rows.
Fixed in `research_sim.simulate`: a reversal signal seen at bar i's close now only fires at bar i+1's open, mirroring exactly how ordinary entries already work. The crude #1 control was re-run afterwards and is byte-identical (785 / 429 trades) &mdash; no other result in this project is affected.
**"Reversal exit, no target" still passes the pre-registered rule at both starts with the corrected, causally-valid logic** &mdash; if anything slightly stronger at 09:15, slightly weaker at 17:30. All numbers below are the corrected ones; the table further down (with PF 1.535/1.552) was superseded and has been replaced.

# Crude #1: round 7, new mechanisms (2026-09-27), 28 of 30 pre-registered configs run. Cumulative trials 326.
Pre-registration: `pre_registration_crude_round7_2026_09_27.md`. Code `crude_round7.py`, data `research_data/crude_round7.csv`. Engine hooks added to `research_sim.simulate` this round: `cooldown_bars`, `reversal_exit`
(control re-run afterwards and unchanged: 785 / 429 trades, confirming no regression). **Deviation from pre-registration: the "adaptive RR" idea (#12) was dropped before running** &mdash; `research_sim.simulate` only
accepts one RR value (or one long/short pair) per run, not a per-bar regime-dependent value, and building that properly needs a real engine change, not a quick patch. Everything else pre-registered ran (14 ideas x 2 starts = 28 configs).
Controls: 09:15: 785 tr, PF 1.263, +5,614 (TRAIN 2,270 / HOLDOUT 3,344, after-cost HOLDOUT 2,191). 17:30: 429 tr, PF 1.476, +6,558 (TRAIN 2,447 / HOLDOUT 4,111, after-cost HOLDOUT 3,487).

## Two configs pass the pre-registered rule (PF, HOLDOUT gross, HOLDOUT after-cost all higher at BOTH starts, >=15 trades/month) for the first time in 7 rounds (326 trials)

### 1. "Reversal exit, no target" &mdash; clears by a wide margin, the strongest lead of the whole search
Same SHA-flip entry and same stop as crude #1, but **no fixed 4R target**: the position is closed only by its original stop-loss, or by an opposite SHA-flip+trend signal (a "reversal exit"), whichever comes first &mdash; i.e. ride the trend until it reverses instead of capping the winner at 4R.

| | trades (/mo) | PF | gross pts | TRAIN | HOLDOUT | after-cost HOLDOUT | worst DD | win% |
|---|---|---|---|---|---|---|---|---|
| 09:15 control | 785 (26.2) | 1.263 | +5,614 | 2,270 | 3,344 | 2,191 | 2,176 | 24.3 |
| **09:15 + reversal/no-target** | 758 (25.3) | **1.727** | **+12,105** | 2,426 | 9,679 | 8,536 | 2,027 | 20.7 |
| 17:30 control | 429 (16.0) | 1.476 | +6,558 | 2,447 | 4,111 | 3,487 | 1,398 | 27.5 |
| **17:30 + reversal/no-target** | 396 (13.2) | **1.582** | **+6,950** | 1,451 | 5,499 | 4,909 | 1,826 | 18.7 |

- **Robust across every session start tested** (09:15/15:00/16:00/17:00/17:30/18:00): PF ranges 1.48&ndash;1.727, all above their respective controls (control PF range was 1.229&ndash;1.478).
- **Not a single-trade fluke**: largest win is capped near +2,340 pts (about 3% of total profit at 09:15), largest loss capped near -413 (the fixed stop still applies) &mdash; 453 stop exits vs 305 reversal exits at 09:15.
- **Fixes crude #1's weak short side**: long +8,782 (392 trades, +22.4/trade), short +3,323 (366 trades, +9.1/trade) &mdash; both sides now clearly profitable, unlike crude #1 where shorts were roughly breakeven.
- **Concentration is milder than crude #1's own baseline**: best month is 47.2% of total profit (crude #1's baseline concentrates ~85% of profit in its best 3 months), and 58% of months are profitable. Max hold ~188h (~7.8 days) at 09:15.
- **Caveats**: (a) win rate drops to 18&ndash;21% (fewer, much bigger wins) &mdash; a real behavioural/psychological change from crude #1's 24&ndash;28%. (b) At 09:15 both TRAIN and HOLDOUT beat the control (2,426 vs 2,270; 9,679 vs 3,344) &mdash; the more convincing case. **At 17:30 TRAIN is clearly below the control (1,451 vs 2,447, -41%)** while HOLDOUT and PF are both far above &mdash; the gain there leans heavily on the second half, the same pattern that killed several earlier round leads, and this shortfall is larger than it first looked before the lookahead fix. (c) Drawdown is mixed: -7% at 09:15 (2,027 vs 2,176) but **+31% at 17:30** (1,826 vs 1,398) &mdash; letting winners run also means giving back more before a reversal triggers. (d) Trade count and holding character change materially (fewer trades at 17:30: 396 vs 429, 13.2/mo vs 16.0/mo; average hold rises to 13&ndash;23h depending on start). (e) **Not yet confirmed on TradingView** &mdash; needs a Pine change (add the reversal-exit rule, remove the fixed target), not just an input tweak, so it needs a new script version and a new slot from you.
- **This is a genuine mechanism change, not a parameter tweak** &mdash; it is the first thing in 326 trials to look like a real second edge rather than noise around crude #1's existing edge, and the 09:15 case (both halves improving) is the stronger of the two starts.

### 2. "Cooldown 6 bars after a stop-loss" &mdash; passes, much smaller effect
Blocks new entries for 6 bars (30 min) after a stop-out, on the theory that a stop-out often means the market is choppy and about to produce another false signal.

| | trades (/mo) | PF | gross pts | HOLDOUT | after-cost HOLDOUT | worst DD |
|---|---|---|---|---|---|---|
| 09:15 control | 785 (26.2) | 1.263 | +5,614 | 3,344 | 2,191 | 2,176 |
| 09:15 + cooldown 6 | 760 (25.5) | 1.292 | +5,978 | 4,361 | 3,251 | 1,914 |
| 17:30 control | 429 (16.0) | 1.476 | +6,558 | 4,111 | 3,487 | 1,398 |
| 17:30 + cooldown 6 | 410 (13.7) | 1.510 | +6,679 | 4,559 | 3,963 | 1,173 |

Small, consistent gain (+6&ndash;7% gross, PF +0.02&ndash;0.03, drawdown down at both starts) for almost no downside (only 3&ndash;5% fewer trades). Real but modest &mdash; a candidate for combining with a later session start, not a standalone finding.
Cooldown 24 bars, and cooldown-6-combined-with-reversal-exit, were both worse than plain cooldown 6 &mdash; the effect does not scale with a longer cooldown.

## Everything else in round 7 failed
"Reversal exit" **with the fixed target kept** (no_target=False) passes at 09:15 (PF 1.313, HOLDOUT +5,395) but **fails at 17:30** (PF 1.315 < control's 1.476) &mdash; the win is specifically from removing the target, not from adding the reversal exit on its own.
15m SHA/EMA agreement gates, dual-length (5/20) SHA confirmation, the silver cross-asset trend filter, round-number-magnet skip, ATR-regime-adaptive stop cap, close-based swing stop, two-bar confirmation and delayed entry all failed at one or both starts &mdash; most by cutting trade count sharply
without enough PF gain to compensate (two-bar confirm: 336/180 trades, PF ~1.05&ndash;1.07, barely profitable). The silver trend-agreement filter is worth noting as a clean rejection: crude's edge does not depend on silver's own trend (PF 1.03 / 1.19, both far below control).
Selection transfer across the 28 configs: Spearman(TRAIN, HOLDOUT) = +0.51, the highest of any round so far &mdash; consistent with this round's ideas being more mechanism-level (session-wide effects) than the noisy entry-filter tweaks of earlier rounds.

## What this means for the crude search
After 6 rounds (298 trials) of nothing, round 7's "reversal exit, no target" is the first candidate that: beats crude #1 on PF, HOLDOUT profit and after-cost profit at every one of 6 session starts tested, is not a single-trade or single-month artifact,
and fixes a known weakness (the dead short side). It is **not yet a finding** &mdash; it has not been replayed on TradingView, the 17:30 TRAIN-half shortfall and the drawdown increase at several starts need to be weighed, and it changes the strategy's character (much lower win rate, much longer holds).
Recommended next step: build a Pine version with the reversal-exit rule (exit on an opposite SHA-flip+trend signal that would itself be a valid entry) and no fixed target, and TradingView-replay it the way the session-start tweak was confirmed, before treating it as real.
