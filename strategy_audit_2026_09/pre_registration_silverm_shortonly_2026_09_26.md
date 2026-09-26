# Pre-registration: SILVERM short-only option-buying variant (written 2026-09-26, BEFORE the run)

Origin, stated plainly: this hypothesis came FROM an in-sample observation - in
`option_premium_results_2026_09_26.md`, 86% of SILVERM's option profit at 1%/side spread came from the PE (short
signal) side, +44,832 of +52,051, on 331 of 732 trades. Selecting a direction after seeing which direction paid is
circular, so this test is designed to distinguish two explanations rather than to confirm the observation.

## Competing explanations
**H1 (skew, structural):** puts are simply cheaper. Measured live 2026-09-26 on MCX SILVERM, expiry 2026-10-27:
CE IV 31.4% vs PE IV ~21.5%. At the same ATM distance calls cost 4,517 pts against puts at 2,949, so every long
option trade starts ~1,570 pts behind. If H1 is right, the PE advantage should appear in MOST windows, and the
underlying FUTURES strategy should show no comparable long/short asymmetry.
**H2 (signal, in-sample luck):** the strategy's short signals were simply better over this particular history. If H2
is right, the futures long/short split will show the same asymmetry, and the option result adds nothing.

## The decisive control (fixed now)
Decompose BOTH the futures P&L and the option P&L by side, per calendar window (the same six five-month windows).
- If futures long ~ futures short while option PE >> option CE, in most windows -> H1, the skew is real and tradeable.
- If futures short >> futures long -> H2, this is the signal, the skew explains little, and "short-only" is just
  curve-fitting to a directional run in silver.
Silver rose strongly over this period, which makes H2 a live risk: a short-biased result in a rising market would be
surprising, and a long-biased futures book combined with a put-biased option book is the signature of H1.

## Variants tested (exactly three, nothing added afterwards)
V1 both sides (the existing result, restated as the baseline) | V2 **short-only** (take PE on short signals, skip
long signals entirely) | V3 long-only (CE only) - included so the comparison is symmetric and V2 cannot be flattered
by omission.
Each at spreads 0 / 0.5 / 1 / 2 %/side, with the measured skew CE 31.4% / PE 21.5%. Harness, window, bars and the
underlying v4.0 wide-ATR + 350 signal are all unchanged.

## Pass criteria
Standard gates, plus specific to this test:
- **A. The PE advantage must hold in >= 4 of the 6 windows.** One or two windows is noise.
- **B. The futures long/short split must NOT show the same asymmetry** (if it does, the finding is H2, not skew).
- **C. V2 must beat V1 on net points at 1%/side spread AFTER halving the trade count** - i.e. it must be better,
  not merely smaller.
Failing A or B means the short-only variant is reported as unsupported, regardless of its headline number.

## Prior
The skew itself is real and measured, so some PE advantage is expected. Whether it survives per-window decomposition
is the open question. A single-window result would be the third time in this session that a strong-looking number
turned out to be one silver move in disguise.
