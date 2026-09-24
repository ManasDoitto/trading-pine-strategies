# Pre-registration: same 50 entries, wide-stop / high-RR exit (written 2026-09-25, BEFORE the run)

Follow-up to pre_registration_std50_2026_09_25.md (0 of 200 passed with stop 1.5xATR / 2R / 120-min time stop).
Hypothesis: the v4.0 edge comes from its wide stop + high RR + long hold, so those exits might rescue some standard entries.
Everything else is unchanged: same 50 entry rules (std50.py, frozen), same data, split, costs (0.02%/side), gap fills,
entry windows, max 2 trades/day, first 250 bars skipped, results in points.

## ONE exit template (no tuning, no grid)
- Stop = 3.0 x ATR14 from the signal bar's close; target = 4R (12 x ATR). Both in one bar -> stop.
- No time stop. Flat at the open of the 15:20 bar (BankNifty) / 23:25 bar (MCX): intraday only, as the trader requires.
  (v4.0 itself carries overnight; this test deliberately does not, so it is not a v4.0 clone.)

## Gates (unchanged, all must hold) and controls
PF >= 1.30 in TRAIN, VALIDATION, HOLDOUT (net); >= 150 trades; >= 70% months positive; no month > 25% of net.
Trial count: 200 more (400 cumulative across the two templates) -> the 1.30 bar already reflects the haircut.
Random-direction control (100 seeded random strategies per instrument, same exits) run through the same gates.
Failing = dropped, no re-tuning. If any pass, they still go to the shadow book for a month before real money.
