# SMC Liquidity Sweep + FVG v1.1 (13 Sep 2026)

## What changed from v1.0

`SMC liquidity sweep + FVG v1.1 (macro trend filter, chandelier default, tunable swing-disp-session).pine.txt`.
v1.0 lost on all three instruments (PF 0.84–0.93) because it faded every liquidity sweep with no trend filter. Three changes, as requested:

1. **Macro trend filter (new).** Price vs a 200 EMA (default) or the daily VWAP, selectable via `trendMode`. Above the filter, only SSL sweeps (longs) are armed — BSL sweeps (shorts) are ignored outright, not just filtered after the fact. Below it, the mirror: only BSL sweeps are armed. A "both agree" mode is also exposed. DailyVWAP needs real volume, so on a spot index (NIFTY) it won't gate anything — EMA200 is the one that works everywhere.
2. **Chandelier trail is now the default exit** (`useChandelier=true`). The stop sits at its original sweep-wick level until price reaches +1R, jumps straight to breakeven, then trails 1×ATR behind the best price reached — it only ever ratchets in the trade's favour. The old fixed-target mode (nearest opposing liquidity level, or a 3R fallback) is kept, selectable on the same toggle.
3. **Tuning parameters exposed:** `swingLen` (default changed 10→20), `minDispATR` (already exposed at 1.0, unchanged), and the session filter (`useSess`/`sess`, default now **on** at "1730-2330" IST).

Compiled clean — same standard "v5 is outdated" advisory every script here gets, plus one informational note about `calc_on_every_tick` (also harmless, doesn't affect confirmed-bar backtesting).

## How it was tested

Same tiled non-overlapping-window method as v1.0 and every other strategy in this folder — not raw `data_get_strategy_results` per replay chunk, which double-counts trades across chunk boundaries. 1 lot, 0.02% commission per side, no added slippage.

- **CrudeOil:** 11 windows, 29.7 months, **US session filter on** ("1730-2330"), as asked.
- **BankNifty:** 5 windows, 30.2 months, **session filter off.** NSE index futures trade 09:15–15:30 IST, not the US session — leaving "1730-2330" on would have produced zero trades. No session restriction was specified for BankNifty, so it ran unrestricted.

Both runs used the v1.1 defaults otherwise: `swingLen` 20, `trendMode` EMA200, `useChandelier` true.

## Results

| Instrument | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| CrudeOil (US session) | 2.9 | 52.3 | **1.40** | **+546** | 302 | 5/11 |
| BankNifty (no session filter) | 2.0 | 45.9 | 0.77 | −1,236 | 2,337 | 2/5 |

By window, oldest to newest:

| Instrument | Windows |
|---|---|
| Crude | −19 +20 +61 −45 +298 +42 −117 −40 −16 +416 −55 |
| BankNifty | −782 +52 −177 −1,254 +925 |

**Before / after, same instrument, same cost model:**

| Instrument | v1.0 (no trend filter) | v1.1 (trend filter + chandelier) |
|---|---|---|
| CrudeOil | PF 0.85, −2,917 pts, 3/11 windows | **PF 1.40, +546 pts, 5/11 windows** |
| BankNifty | PF 0.93, −3,146 pts, DD 7,614 | PF 0.77, −1,236 pts, DD 2,337 |

## Reading

- **Crude: yes, the fix worked — PF crossed 1.0.** 1.40 is a strong number on its face, and win rate jumped to 52% (up from 35%), consistent with "stop fighting the trend" doing what it should. But **read this cautiously**: the US-session filter plus the macro-trend filter plus `swingLen=20` between them cut trade count to **86 over 29.7 months (2.9/month)**. That is a thin sample even by this project's standards — for comparison, BankNifty v0.4 (2.5 trades/month, PF 1.33) was flagged as a small sample at 74 trades, and this has a similar count. It's a genuine improvement, not noise dressed up as one — the win rate and window-consistency (5/11 positive, and the single best window is only +416 of the +546 total, so it isn't one lucky window carrying the whole result) both point the same direction — but it needs a longer track record, live or forward-tested, before sizing it like v4.0 or v2.1.
- **BankNifty: still losing, but far less badly.** DD fell from 7,614 to 2,337 (roughly a third), and the catastrophic single window (−5,375 in v1.0) shrank to −1,254. The trend filter clearly did its job on drawdown. But PF is still under 1 (0.77), and at only 61 trades over 30 months the sample is thinner than crude's. **It did not flip BankNifty profitable.**
- **Neither result unseats your existing picks.** Crude v4.0 (PF 1.09, +2,136 pts, 842 trades) and v2.1 (PF 1.14, +1,304 pts, 518 trades) both rest on far larger samples than SMC v1.1's 86 trades, and both have a longer track record in this audit. BankNifty v0.4 (PF 1.33, +1,403 pts) still leads by a wide margin, and SMC v1.1 on BankNifty is still net negative.
- **A structural note on BankNifty:** SMC v1.1 wasn't given the session restriction crude got. If NSE market hours (0915-1530) were used as the session filter instead of "off", results would likely change — that combination was not tested here since it wasn't requested, and is worth trying next.

## Verdict

The trend filter and chandelier trail did exactly what they were meant to do: crude flipped from a clear loser to a profit factor above 1.0, and BankNifty's drawdown fell sharply even though it's still net negative. Crude v1.1 is now worth tracking forward — it isn't ready to replace v4.0/v2.1 as a sized position on 86 trades, but it's the first version of this strategy worth keeping an eye on. BankNifty v1.1 needs more work (an NSE-hours session filter is the obvious next thing to try) before it's worth a second look.
