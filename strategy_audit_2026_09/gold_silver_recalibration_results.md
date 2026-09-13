# Gold and Silver instrument-specific recalibration (14 Sep 2026)

## What was tested

One highest-conviction hypothesis per instrument, per the retuning brief's own suggestions, on plain
v4.0 (no ADX gate -- that idea was closed out separately). Same tiled non-overlapping-window method,
0.02%/side commission, no added slippage, 5m, full available history (12 windows / 32.3mo each).

- **Gold**: session filter "0915-2330" (crude's default) -> **"1730-0030"** (COMEX-active hours, per the
  brief's own note that gold's real volatility windows are the COMEX open ~18:30-19:00 IST through early NY
  hours, not crude's daytime MCX session).
- **Silver**: stop-distance multiples `minSL` 1.5->**2.5**, `maxSL` 3.0->**5.0** (per the brief's own note that
  silver's ATR/price ratio is higher than crude's, so crude's stop multiples likely skip or whipsaw on valid
  silver setups).

## Results

| | Trades/mo | Win% | PF | Net pts | Windows |
|---|---|---|---|---|---|
| **Gold**, baseline (crude session) | 30.3 | 29.7% | 1.07 | +13,152 | 12 / 32.3mo |
| **Gold**, COMEX session | 16.6 | 31.0% | **1.13** | **+16,312** | 12 / 32.3mo |
| **Silver**, baseline (crude ATR mults) | 31.9 | 28.7% | 1.06 | +32,815 | 12 / 32.3mo |
| **Silver**, wide ATR mults | 33.1 | 28.7% | **1.15** | **+116,096** | 12 / 32.3mo |

## Reading

**Both are genuine improvements, and Silver's is the best single finding across the entire retuning exercise
today** (ADX gate at two thresholds, Crude RR test, these two) -- it's the first strategy besides BankNifty
v0.4 to cross this project's PF>=1.15 bar.

**Gold**: trading only during COMEX-active hours cut frequency by about half (30->17/mo) but raised both PF
(1.07->1.13) and total net points (+13,152->+16,312, +24%) together -- unlike the ADX gate, which always
traded off quantity against quality without net benefit. This confirms the brief's own hypothesis: gold's
edge really does concentrate in COMEX hours, and crude's daytime session was diluting it with lower-quality
signals during quiet Asian/early-European hours.

**Silver**: widening the stop multiples did NOT reduce trade frequency at all (33.1/mo vs 31.9/mo baseline --
essentially unchanged) while PF jumped from 1.06 to 1.15 and net points nearly quadrupled (+32,815->+116,096,
+254%). This also confirms the brief's hypothesis directly: crude's tight 1.5x/3.0x ATR stops were forcing
silver's naturally wider price swings into premature stop-outs on trades that would otherwise have run to
target -- widening them let more of silver's real moves play out.

## The honest caveat -- read this before sizing either of these

**Silver's result is still heavily concentrated in a handful of windows**, more so than before the change, not
less. One window alone (2026-01-08 to 2026-03-30) contributed +134,977 pts -- more than the entire 32-month
net. The immediately following window (2026-03-31 to 2026-06-24) lost -55,713 pts, and the single-window max
drawdown is now 76,863 pts -- a genuinely severe equity swing at 1 lot. Widening the stops didn't just capture
more of silver's real trend moves -- it also let losing trades run further before being cut, so the tail risk
per trade grew alongside the average win. This is the same "most of the edge is a few extreme windows, not a
steady signal" issue already flagged for crude and for the untuned gold/silver baselines -- wider stops made
the average result much better without curing that underlying fragility.

**Gold's result is more evenly distributed** across windows than Silver's (its single best window, +18,819,
is only about 1.15x the full-period net, versus the untuned baseline where one window alone was 1.8x the
net) -- the COMEX-session filter appears to have genuinely improved robustness, not just concentrated luck
further.

## Recommendation

- **Adopt the Gold COMEX-session filter.** Real improvement in both PF and points, and it appears to reduce
  (not worsen) the window-concentration problem that was flagged for the untuned baseline.
- **Silver's wide-ATR result is promising but needs the concentration issue addressed before sizing it.**
  PF 1.15 with a 76,863-pt single-window drawdown at 1 lot is not something to trade as-is. Worth testing a
  hard daily/window loss limit on top of this change before treating it as deployable, consistent with the
  original brief's own point that daily loss limits are non-negotiable for live trading.
- Neither result has been combined with the Crude RR=4.0 finding into one consolidated "final" recommendation
  per instrument yet -- that synthesis, plus the option-buying cost model from the original brief, remains
  open if you want to carry this further.
