# SMC Liquidity Sweep + FVG v1.0 vs the EMA-pullback picks (13 Sep 2026)

## The strategy

`SMC liquidity sweep + FVG v1.0 (BSL-SSL sweep, 3-bar FVG entry, ATR chandelier or dynamic liquidity target).pine.txt`.
Pure Smart Money Concepts mechanics — no EMA, VWAP, or RSI anywhere in the logic:

1. **Liquidity:** the most recent confirmed swing high/low (10-bar pivot) plus the previous day's high/low.
2. **Sweep:** a bar's wick pierces one of those levels and its close snaps back inside — the level is marked "swept."
   - a swept high (BSL) arms a watch for a **short**; a swept low (SSL) arms a watch for a **long**.
3. **Displacement / FVG:** within 5 bars of the sweep, a 3-bar Fair Value Gap in the reversal direction, gated to a displacement candle range ≥ 1×ATR14 (filters noise gaps).
4. **Entry:** a stop order at the FVG's near edge — fills on the first pullback that taps the gap. Cancelled if price closes back through the sweep wick, or 10 bars pass with no tap.
5. **Risk:** stop just beyond the sweep wick (+0.1×ATR buffer). Target = the nearest opposing liquidity level ahead of entry if it clears 1.5R, else a 3R fallback. A chandelier-trail mode (1×ATR, per your spec) is built in but was not the mode tested — the fixed-target mode was.
6. **Session:** configurable, left off for this run so the raw mechanic could be judged on its own before hours are tuned per instrument.

It compiled clean on the first attempt — the only compiler message on every run was the standard "Pine v5 is outdated, use v6" advisory every script in this repo gets. Full source is in the repo; a trimmed audit copy (visuals stripped, tiled-window scoreboard appended) is what was actually tested, for the same reason every other strategy here was tested that way: `data_get_strategy_results` per replay chunk double-counts trades across chunk boundaries, so the tiled non-overlapping-window method was used instead to keep this comparable to the rest of `strategy_audit_2026_09/`.

## Setup

Same method, same costs, same windows as every other strategy in this folder: 1 lot, 0.02% commission per side, no added slippage, non-overlapping replay windows.

- **CrudeOil (MCX:CRUDEOIL1!):** 11 windows, Mar 2024–Sep 2026, 29.7 months.
- **BankNifty (NSE:BANKNIFTY1!):** 5 windows, Mar 2024–Sep 2026, 30.2 months.
- **Nifty 50 spot (NSE:NIFTY):** 5 windows, Jan 2024–Sep 2026, 31.7 months. This strategy has no volume/VWAP dependency, so — unlike the earlier VWAP-based scripts — it ran on the spot index without needing a futures volume substitute.

## Results

| Instrument | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| CrudeOil | 33.2 | 35.3 | 0.85 | **−2,917** | 3,210 | 3/11 |
| BankNifty | 13.5 | 37.3 | 0.93 | **−3,146** | **7,614** | 2/5 |
| Nifty 50 | 14.9 | 33.5 | 0.84 | **−3,082** | 4,486 | 1/5 |

By window, oldest to newest:

| Instrument | Windows |
|---|---|
| Crude | −247 −630 −993 +304 +194 −106 +50 −294 −56 −814 −326 |
| BankNifty | −68 **−5,375** −996 +1,282 +2,011 |
| Nifty 50 | +529 −345 −993 −1,040 −1,233 |

## Against your existing picks

| Instrument | Strategy | PF | Net pts | Max DD |
|---|---|---|---|---|
| Crude | **v4.0 SHA flip RR3** | 1.09 | +2,136 | 2,339 |
| Crude | v2.1 EMA pullback | 1.14 | +1,304 | 900 |
| Crude | SMC sweep+FVG | 0.85 | −2,917 | 3,210 |
| BankNifty | **v0.4 pullback + 15m ADX** | 1.33 | +1,403 | 1,620 |
| BankNifty | SMC sweep+FVG | 0.93 | −3,146 | 7,614 |
| Nifty 50 | (no viable EMA strategy found) | — | — | — |
| Nifty 50 | SMC sweep+FVG | 0.84 | −3,082 | 4,486 |

## Reading

- **Loses on all three instruments, in 6 of 21 windows total positive.** It is not close to any of the existing picks.
- **BankNifty's drawdown is the standout problem:** one window alone lost 5,375 points, more than 3x v0.4's entire 30-month drawdown.
- **The trade rate is reasonable** (13–33/month) but win rate sits at 33–37% against roughly a 1.5–3R target, so it needs a materially better win rate than it's getting to clear costs.
- **Likely cause, by construction:** the strategy fades a liquidity sweep — it bets the sweep was a stop-hunt and price reverses. But it has no broader trend filter (no EMA/HTF bias check), so it fades sweeps inside strong trends just as often as at real turning points, and in a trending market that means repeatedly fighting the trend. Every survivor in this project's audit (v4.0, v2.0/v2.1, v0.4) carries an explicit trend or regime gate; this one deliberately doesn't, per the "purely SMC-based" brief.
- **Not tuned.** No parameter sweep was run (swing length, displacement ATR multiple, target R, chandelier mode) — this is the mechanic as specified, tested once. It's possible a trend filter or the chandelier-trail mode changes the picture, but that's future work, not a claim made here.

## Verdict

Do not add this to the crude or BankNifty lineup. v4.0 (crude) and v0.4 (BankNifty) remain the picks. If you want to keep developing the SMC idea, the first thing worth adding is a trend/regime filter — the missing piece every profitable strategy in this project shares.
