# Silver wide-ATR: daily loss circuit breaker (14 Sep 2026)

## Two designs tested, per the user's own follow-up: why fixed, not script-dependent?

That's a fair challenge to a fixed-point limit -- volatility regimes shift over 32 months, so a static
number calibrated on the average could be too loose in quiet periods and too tight (or too loose) in
volatile ones. Tested both:

1. **Fixed**: 350 points (~2x the wide-ATR version's own average daily profit of 167 pts/day, per the
   original brief's own recommendation for sizing a circuit breaker).
2. **ATR-scaled**: `7.5 x ATR14`, recomputed every bar -- sized as roughly 3x the strategy's own typical
   single-trade risk (`minSL` = 2.5xATR), so the breaker trips after about 3 average-sized losing trades in
   one day, adapting automatically as silver's volatility changes.

Both: same tiled non-overlapping-window method, 12 windows / 32.3mo, 0.02%/side commission, no slippage, 5m.
On breach, the breaker force-closes any open position immediately (not just blocks new entries) and locks
out new entries for the rest of that session day.

## Results

| | Trades/mo | PF | Net pts | Max single-window DD |
|---|---|---|---|---|
| No breaker (prior result) | 33.1 | 1.15 | +116,096 | 76,863 |
| **Fixed 350 pts** | 24.2 | **1.35** | **+160,845** | **24,551 (-68%)** |
| **ATR-scaled (7.5x)** | 31.9 | 1.18 | +125,529 | 62,493 (-19%) |

## The fixed cap wins on every metric -- and here's why that isn't a coincidence

**The fixed 350-pt limit outperforms the ATR-scaled 7.5x version on PF, net points, AND drawdown
reduction.** This is worth explaining rather than just reporting, because the intuition behind
"make it script-dependent" is reasonable in general risk management -- it just doesn't hold for this
specific job.

Look at the single worst window (2026-03-31 to 2026-06-24), the one responsible for most of the damage in the
unrestricted version:
- No breaker: that window lost -55,713 pts.
- Fixed 350: that window lost only -126 pts (essentially flat) -- the breaker fired early and often, capping
  losses hard.
- ATR-scaled 7.5x: that window still lost -41,343 pts, with a 62,493-pt drawdown -- barely better than no
  breaker at all.

**The reason: this was exactly the window where ATR itself spiked.** An ATR-scaled breaker's own threshold
expands right along with realized volatility -- so on the days that matter most (the volatility-spike days
that produce the big losses), the breaker becomes *more* permissive, not less, defeating its own purpose. A
fixed cap doesn't care what the market is doing; it trips at the same absolute point loss regardless of
regime, which is exactly the property you want from a circuit breaker whose job is to survive regime shifts.

This doesn't mean "always use fixed limits" as a general rule -- for normal position sizing (e.g. stop
distances, which this strategy already does via `minSL`/`maxSL` in ATR multiples), scaling with volatility is
correct, because you want risk *per trade* to stay proportional to normal price movement. But a *circuit
breaker* exists specifically to catch abnormal, regime-breaking days -- and an indicator that moves with the
abnormality it's supposed to guard against is the wrong tool for that job.

## Updated recommendation

**Use the fixed 350-pt daily loss limit (`A98_silver_daily_limit_fixed350.pine.txt`), not the ATR-scaled
version.** With it: PF 1.35, net +160,845 pts over 32.3 months, max single-window drawdown of 24,551 pts (down
from 76,863 without any breaker) -- this is now a genuinely stronger, more risk-controlled result than the
wide-ATR recalibration alone, and it's the best PF found anywhere in this entire multi-day retuning exercise,
crude included.

**Still worth knowing before sizing this:** 24,551 pts is still a real drawdown at 1 lot (~₹7.4 lakh at
pv=30). The 350-pt limit was calibrated on this exact 32-month backtest's own average daily profit -- a
number that could look different on the next 32 months. Reasonable next step if pursued further: test the
fixed limit's sensitivity (e.g. 250 vs 350 vs 450 pts) to see how much the result depends on this specific
choice, rather than treating 350 as uniquely correct.
