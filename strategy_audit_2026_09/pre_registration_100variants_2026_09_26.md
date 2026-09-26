# Pre-registration: 100 variants each of the crude and BankNifty breakout strategies (written 2026-09-26, BEFORE the run)

User request: "if you dont get good results then try to run 100 different variants of these strategies and check on all available
data in tradingview, and get the better result like silver you already did." Crude v5.1 lost to crude #1 on both the harness and the
TradingView replay (TV: crude #1 PF 1.229 / +5,672 vs +breakout(5) PF 1.076 / +4,074; B beats A in 3 of 13 windows); BankNifty v5.1 lost to v0.4.

## Honest framing
- Silver's improvement was ONE idea tested on ONE strategy, not a search, and it is still unproven (paired monthly p = 0.150). A 100-variant
  search per instrument is the process this repo has measured ~25 times not to transfer out of sample. It is run because the user asked;
  the design below is what makes the answer informative rather than a cherry-pick.
- TradingView cannot screen 100 variants directly (each needs a 13-window replay, ~40 tool calls). All 100 are screened on the Python harness
  (validated against TradingView to 0.03% on drawdown and matching trade counts on overlapping windows, and against v0.4's README) using the
  TradingView-harvested 5m bars, i.e. the same data. FINALISTS are then confirmed with TradingView tiled replay across all available months.

## Data split (fixed now)
Window 2024-03-25 -> 2026-09-24 (30 months). **TRAIN = 2024-03-25 -> 2025-06-25 (15 mo). HOLDOUT = 2025-06-25 -> 2026-09-25 (15 mo).**
Trades assigned by exit time. Selection touches TRAIN only; HOLDOUT is read once, after the pick.

## Search space (seeded random draw of 100 per instrument, seed 20260926; controls added separately)
entry {flip, flip OR breakout, breakout only} | breakout lookback {2,3,5,8,12,20} | RR {1.5,2,2.5,3,4,5} | minSL {1.0,1.5,2.0} x ATR |
maxSL {3,4,5} x ATR (>minSL) | swing {5,10,15} | SHA stability {0,3} | trend filter {none, EMA9/22, EMA9/22+EMA200} |
EMA9 pullback gate {off, 1.0, 2.0} | 15m ADX {off, 15, 20} | session {3 options per instrument} | force-flat {2 options} | daily limit {2 options}.
CRUDE sessions: full 09:15-23:30, US 17:00-23:30, day 09:15-17:00; flat {none, 22:45}; daily limit {0, 150}.
BANKNIFTY sessions: full 09:30-15:00, late 10:00-15:00, early 09:30-13:00; flat {15:00, 14:30}; daily limit {0, 300}.
Controls (not counted in the 100): crude working_strategies #1; crude v5.1 as shipped; BankNifty v0.4 (its own engine); BankNifty v5.1 as shipped.

## Selection rule (fixed now)
Eligible = >= 100 trades over 30 months AND positive after 0.02%/side on TRAIN. PICK = highest TRAIN net points (gross, per the user's convention)
among eligible. Also report the top 10 by TRAIN.

## Pass criteria
1. PICK is positive after costs on HOLDOUT.  2. PICK beats the incumbent's HOLDOUT net points (crude #1; BankNifty v0.4).
3. PICK gross PF >= 1.15 on HOLDOUT.  4. >= 100 trades total.  5. Best single month <= 40% of HOLDOUT net.
6. Confirmed on TradingView replay across all available months (crude: as far as the loaded study's inputs can express the pick; else stated).
Transfer measurement: Spearman rank correlation TRAIN net vs HOLDOUT net across all 100, and median HOLDOUT net, reported whether or not it flatters.
200 trials + controls -> the multiple-testing haircut is heavy; a pass is a candidate for forward testing, never for capital.

## Prior
Crude and BankNifty per-trade edges (~+6 and ~+20 pts) are the same size as the cost (~2.6 and ~22 pts); silver's (~+370 pts vs ~60) is not. Expect the
TRAIN winner to decay in HOLDOUT and most variants to lose after costs. 0 of ~4,750 strategies tested have passed this repo's gates.
