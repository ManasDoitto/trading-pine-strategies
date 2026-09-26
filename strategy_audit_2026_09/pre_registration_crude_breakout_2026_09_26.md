# Pre-registration: CrudeOil v5.1 flip+breakout, with principled adjustments (written 2026-09-26, BEFORE the run)

File: `working_strategies/CrudeOil/5_v5.1_flip_breakout.pine.txt`. Header/README claim: "ADX=15, SHA=2, RR=3.0, BO5 -> 71 trades,
PF 1.58, net +2,721 pts" (README: "high-frequency", "L/W ~0.55, does not meet the <40% constraint"). Note the file's own default
is shaMinHold = 3, not the "SHA=2" in its header.

## Harness (frozen)
`research_sim.simulate`, `research_data/bars/MCX_CRUDEOIL1_5m.csv`, 2024-03-25 -> 2026-09-24 (30 months), **gross points**, qty 1, gap
fills as TradingView, signal on close / fill next open, six calendar windows. Net of 0.02%/side reported alongside because crude's
edge per trade is small (working_strategies #1 earns ~+7 pts/trade against ~3-4 pts of round-trip cost).

## Provenance check on the claim (diagnostic, not a trial)
Reproduce the header on the original Dhan cache `journal_data/cache/backtest/CRUDEOIL_5min.csv` (3.2 months) with shaMinHold 2 and 3,
to see whether "71 trades / PF 1.58 / +2,721" comes from that truncated sample, as the v5.0 claims did.

## Stage 1 - the file as shipped (S0)
SHA10/10 flip (stability 3) OR Donchian(5) breakout; EMA9>EMA22 AND close>EMA200; 15m ADX>=15; no vol regime, no ATR floor; EMA9
pullback proximity 1.0 ATR; stops min 1.5 / max 3.0 ATR; RR 3.0; daily limit 300; entries 09:15-23:30, force-flat 22:45.

## Stage 2 - one-at-a-time ablations (6 runs, each from prior evidence)
a) no force-flat (hold overnight, as working_strategies #1 does) | b) RR 4.0 (crude #1 is the RR4.0 recal) | c) no EMA200 |
d) no pullback gate | e) no ADX gate | f) no daily limit (crude #1 has none).

## Stage 3 - the recipe on crude working_strategies #1's own base (8 runs)
Base = crude #1 exactly: SHA flip + EMA9>EMA22 only, min 1.5 / max 3.0 ATR, no daily limit, no force-flat, session 09:15-23:30.
Entry in {flip only [the incumbent], flip OR breakout(3), (5), (10)} x RR in {3.0, 4.0}.

Total 15 trials -> multiple-testing haircut applies.

## Gates (fixed now)
1. beats S0 AND the same-RR flip-only incumbent on net points; 2. gross PF >= 1.15; 3. >= 100 trades; 4. best month <= 40% of net;
5. positive after 0.02%/side; 6. **beats crude working_strategies #1 (+5,614 pts, RR4.0) on net points**; 7. walk-forward picks beat holding #1
over W2-W6. Also record gross-to-net cost gap per trade for every trial: an anomalously small gap (see the silver bo(3) finding today) flags
a path-dependent net figure that must not be quoted as a like-for-like result.

## Prior
The breakout multiplied silver's trades and failed on BankNifty. Crude sits between: high-volume and trending, but with an edge of only
~7 pts/trade. Expect the breakout to raise trade count; whether it raises points above the incumbent is the open question. Option buying on
crude was already ruled out (premium 31x the edge), so this is a futures-points question only.
