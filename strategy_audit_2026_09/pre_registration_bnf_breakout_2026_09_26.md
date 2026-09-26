# Pre-registration: BankNifty v5.1 flip+breakout, and principled adjustments (written 2026-09-26, BEFORE the run)

File under test: `working_strategies/BankNifty/5_v5.1_flip_breakout.pine.txt`. Its own header says: best sweep config
"126 trades, PF 0.94 ... The BankNifty v5.0 default (flip only) remains the recommended script." The README calls it
"not recommended". So the shipped result is expected to be poor; the question is whether the design can be repaired.

## Harness (frozen)
`research_sim.simulate`, `research_data/bars/NSE_BANKNIFTY1_5m.csv` (BANKNIFTY futures), window 2024-03-25 -> 2026-09-24
(30 months), **gross points (user convention)**, qty 1, gap fills as TradingView, signal on close / fill next open,
six fixed calendar windows (2024-03-25, 08-25, 2025-01-25, 06-25, 11-25, 2026-04-25, 09-25). Net of 0.02%/side is reported
as an aside because BankNifty's points-per-trade are small and ~22 pts of round-trip cost (0.02% x ~55,000 x 2) can swing a verdict.

## Stage 1 — the file exactly as shipped (S0)
SHA 10/10 flip (stability>=3) OR Donchian(5) breakout; EMA9>EMA22 AND close>EMA200; 15m ADX>=20; vol regime ATR>SMA80; ATR floor
50 pts; EMA9 pullback proximity 1.0 ATR; stops min 1.5 / max 3.0 ATR, swing 10, buffer 0.1; RR 4.0; daily limit 500;
entries 09:30-15:00, force-flat 14:30.

## Stage 2 — one-at-a-time ablations of S0 (7 runs; each cites prior evidence, nothing else is tried)
| id | change | evidence it comes from |
|---|---|---|
| a | flat at 15:00 instead of 14:30 | `bnf_exit_results`: 15:00 beat 14:30/15:15/15:20 at 9 of 10 (RR, ADX) pairs |
| b | RR 2.0 instead of 4.0 | same: at RR 4.0 only 1.8% of exits were targets; RR 1.5-2.0 gave 18-36% |
| c | drop EMA200 | silver: repo's point-earning v4.0 base has no EMA200; `signals_v50` hardcodes it |
| d | drop EMA9 pullback gate | silver frequency probe: the pullback gate, not ADX, starved trade count |
| e | drop 15m ADX gate | BankNifty ADX gate: PF +0.04, drawdown worse, off in all 8 combos clearing the PF gate |
| f | drop vol regime | untested on this entry; shown for completeness |
| g | drop ATR floor | config.toml `atr_min_pts=50` came from v0.4, not from this strategy |

## Stage 3 — the "silver recipe" on a clean base (12 runs, fixed now)
Base: EMA9>EMA22 only (NO EMA200, pullback, ADX, vol regime, ATR floor), stops min 1.5 / max 3.0, daily limit 500,
entries 09:30-15:00, flat 15:00. Entry in {flip only [the ancestor], flip OR breakout(3), (5), (10)} x RR in {2.0, 3.0, 4.0}.
Nothing outside this list is run.

Total 20 trials -> the multiple-testing haircut applies.

## Selection and gates (fixed now)
Primary criterion is NET POINTS (gross), per the user's standing instruction. Report the best full-sample, and separately the
walk-forward pick (choose on windows 1..i-1 by cumulative net points across all 20, score on window i).
Gates: (1) beats S0 AND beats the same-exit flip-only ancestor on net points; (2) gross PF >= 1.15; (3) >= 100 trades;
(4) best month <= 40% of net; (5) **still positive after 0.02%/side**; (6) walk-forward picks beat holding S0 over W2-W6.
Informational: v0.4's README figure (+1,277 pts, PF 1.29, 74 trades, a different cost convention) is the repo's BankNifty best.

## Prior
BankNifty v4.0-style flips lose on this instrument (plain flip: PF 0.886 net / 1.053 gross earlier today), and every filtered
version fell below 100 trades. A breakout raises trade count; whether it raises points per trade above the ~22-pt cost is the
open question. 0 of 4,714 tested strategies have passed this repo's gates.
