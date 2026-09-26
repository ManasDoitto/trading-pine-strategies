# Pre-registration: BankNifty v5.0 R:R and force-flat window (written 2026-09-26, BEFORE the run)

Reason for the test (from `crude_bnf_v50_results_2026_09_26.md`): the shipped BankNifty config exits 56 trades as
**35 force-flat / 20 stop / 1 take-profit**. A 4R target on a 1.5-3.0 ATR stop is unreachable when entries are allowed
09:30-14:30 and every position is closed at 14:30, so the R:R input is not doing what it claims. Only the exit side
changes here; the ENTRY signal is frozen exactly as tested (SHA flip + EMA9/22 + EMA200, ATR floor 50, vol-regime ON,
pullback 1.0 ATR, minSL 1.5 / maxSL 3.0, daily limit 500).

Reference point for the choice of levels: `config.toml [strategy.BANKNIFTY]` (the proven v0.4 config) uses
`entry_window ["09:30","15:00"]`, `flat_window ["15:15","15:30"]`, `flat_exit_at "15:20"`, `rr 2.5`. The instrument
trades to 15:30, so the shipped 14:30 flat forfeits the last hour.

## Harness (frozen, identical to the runs it is compared against)
`research_sim.simulate` on `research_data/bars/NSE_BANKNIFTY1_5m.csv`, window 2024-03-25 -> 2026-09-24 (30 months),
**gross points, commission 0** (user's standing instruction; a net-of-cost line is reported for the pick only),
qty 1, gap fills as TradingView, first 400 bars skipped, split 60/20/20 by exit time.

## Grid (40 combos, fixed now; nothing added after seeing results)
- `flatAt` in {14:30 (shipped), 15:00, 15:15, 15:20}; entries stop at min(flatAt, 15:00), positions close at flatAt.
- `rr` in {1.5, 2.0, 2.5, 3.0, 4.0 (shipped)}.
- ADX gate in {>=20 (shipped), off} - included because the previous run showed the gate is near-inert on BankNifty
  (PF 1.441 -> 1.484) and makes drawdown worse.

## Selection rule (fixed now - this is what "the best one" means)
PICK = highest **TRAIN** PF among combos with **>= 40 trades** (the pre-registered >=100 gate is unreachable on a
~2-trade/month instrument over 30 months; 40 is stated here in advance, and a combo that fails the 100 gate is still
recorded as failing it). VALIDATION and HOLDOUT are read ONCE, after the pick. Also reported, explicitly labelled as
in-sample and NOT a selection: best full-sample PF, and the take-profit share, which is the thing this test is meant to fix.

## Pass criteria (unchanged; 40 trials, so the PF >= 1.30 multiple-testing haircut applies)
1. PF >= 1.30 in TRAIN, VALIDATION and HOLDOUT.  2. >= 100 trades.  3. >= 70% of months positive.
4. No month > 25% of total net.  5. Beat the shipped config's HOLDOUT PF (1.688) and its max drawdown (1,358.1).
Fail any = not a pass, no retuning. Shipped baseline to beat: PF 1.484, +1,980.2 pts, maxDD 1,358.1, 56 trades,
TRAIN/VALID/HOLDOUT 1.568 / 1.015 / 1.688.

## Prior
Changing an exit to make targets reachable should raise the take-profit share and change the win/size mix; it does not
by itself create an edge. 0 of 474 tested strategies have passed these gates. Expect the trade-count gate to fail
regardless. Run it to learn whether the 4R target was the binding problem, not to find a winner.
