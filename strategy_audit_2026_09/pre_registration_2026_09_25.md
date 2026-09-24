# Pre-registration: fast-intraday option-buying research (written 2026-09-25, BEFORE any test)

Purpose: fix the hypotheses, parameters and pass/fail rules now, so no result can move them. Results are
reported in POINTS (repo convention), net of a cost of 0.02% per side (the audit scripts' commission);
option-level P&L is judged separately in the shadow book (Step 5), never here.

## Why these ideas (the only evidence used to pick them)
The trader's own 370 classified closed trades, by hold time (journal facts 2026-09-18, all-time):

| Hold | n | net INR | PF |
|---|---|---|---|
| < 5 min | 43 | +44,303 | 3.40 |
| 5-30 min | 130 | +80,627 | 1.71 |
| 30 min-2 hr | 120 | +66,961 | 1.30 |
| 2 hr-1 day | 63 | -48,799 | 0.83 |
| > 1 day | 14 | -531,140 | 0.22 |

Held <= 2h: 293 trades, +191,891. Held longer: 77 trades, -579,939. Option buying pays theta on every minute held.
v4.0 uses a fixed-RR bracket with no time stop; its recent crude trades were held ~18h and ~21h.
This is a hypothesis source, NOT a validation: it is in-sample, discretionary, and the <5min bucket is small.

## Hypotheses (maximum three; no others may be added after results are seen)

**H1 - time stop on existing v4.0 (crude, silver, silverM).**
Same entries, stops and targets as the deployed v4.0 strategies. Added rules: (a) if neither stop nor target has been
hit N minutes after the fill, exit at the open of the next bar; (b) no position is carried across a session close
(force-flat at the open of the 23:25 bar on MCX). N is chosen from exactly {90, 120, 180}. One parameter.

**H2 - opening-range breakout with volatility expansion (BankNifty futures, 5m).**
Opening range = high/low of the 09:15-09:45 bars. From 09:45 until 14:30, go long on the first 5m close above the
range high, or short on the first 5m close below the range low; one trade per session. Take the trade only if
ATR14(5m) at the breakout bar >= M x the median, over the previous 20 sessions, of each session's mean ATR14(5m).
Stop at the opposite range extreme; R = entry-to-stop distance; target = 2R; time stop 120 min; flat at the open of
the 15:20 bar. Parameter: M from exactly {1.0, 1.25, 1.5}. One parameter.

**H3 - compression to expansion (crude futures, 5m).**
The previous session's range (high - low) must be among the 7 smallest of the 20 sessions ending with that session.
After the first 30 minutes of the session, go long on the first 5m close above the previous session high, or short
on the first close below its low; one trade per session. Stop = 1.0 x ATR14(5m) from entry; R = that distance;
target = 2R; time stop 120 min; flat at the open of the 23:25 bar. No tunable parameter.

Trial count is per instrument: H1 = 3 per instrument (the three values of N). Any variant beyond these is a new
trial and raises the bar (see below).

## Data and split
- Primary: TradingView 5m tiled walk-forward windows (BankNifty ~35.6 months, crude ~32.3 months, silver ~32 months;
  silverM as far as TradingView serves it). Cross-check: Dhan 5m bars for the most recent ~3 months, run in Python.
- Split by time, per instrument: oldest 60% = TRAIN, next 20% = VALIDATION, newest 20% = HOLDOUT.
- The parameter (N or M) is chosen on TRAIN only, from the listed values. VALIDATION confirms. HOLDOUT is run once,
  after the choice is frozen, and is never re-run.

## Method (added before any test)
Replaying 32 months on TradingView costs about 3 hours per configuration per instrument (the SILVERM flip-only audit took
~3h). H1 alone is 9 configurations. So: harvest 5m bars once per instrument from TradingView into a local, gitignored
folder (market data, not account data), then run every variant in the Python simulator in seconds.

**Replication gate (must pass before any hypothesis result counts).** The Python simulator, run on the harvested bars,
must reproduce the documented TradingView baselines: SILVER1! wide-ATR + 350-pt limit (PF 1.35, +160,845 pts, 12 windows)
and CRUDE v4.0 RR4.0 (PF 1.12, +2,811 pts, 12 windows), each within +/-0.05 PF and +/-15% net points. If the port does not
replicate, it is fixed first, or that test moves back to TradingView. SILVERM flip-only (PF 1.148, +73,565 pts) is
reported alongside but is not a gate, because its overlap is double-counted by ~0.6 month.

## Pass criteria (all must hold, for a given instrument + hypothesis)
1. PF >= 1.25 in TRAIN, in VALIDATION and in HOLDOUT, each net of costs.
2. At least 150 trades in total across the three segments.
3. At least 70% of calendar-month windows positive.
4. No single window contributes more than 25% of total net points.
5. Robustness: moving the chosen parameter one step either way (or +/-20% for a continuous one) keeps PF >= 1.10.
6. Multiple-testing haircut: if more than 5 variants were tried on that instrument, criterion 1 becomes PF >= 1.30.

A hypothesis that fails any criterion is dropped and recorded as failed. It is not re-tuned.

## Standing constraints (from earlier findings; not to be re-litigated without a materially new idea)
- No tuning toward a target PF. Earlier requests for PF > 1.3 / 1.5 by re-tuning were declined as overfitting.
- The SHA-flip family tops out around PF 1.05-1.14; H1 tests whether a time stop changes that, nothing more.
- Do not stack strategies expecting additive results (v0.4 + v13 promised +2,317 pts, delivered +964).
- Never modify the protected TradingView script "Crude 5 min profitable draft" (must stay v162); test only in the
  shared slot. Check no other Claude session is using the TradingView tab before any run.

## After a pass: option reality check (Step 5)
Passing strategies run in the shadow book for one calendar month, then the existing verdict rules apply
(>= 15 trades, net > 0, PF >= 1.2, no single trade > 50% of net). No real money before that.

## Risk layer (applies to everything, independent of strategy)
Intraday only; 1-2 lots; never add to a loser; one premium stop per trade; INR 10,000 daily stop; size only ever shrinks.
