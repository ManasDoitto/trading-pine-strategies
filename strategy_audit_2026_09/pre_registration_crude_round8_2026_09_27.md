# Pre-registration: round 8, raise crude v4.2's win rate without giving up net points or drawdown (2026-09-27)
Base = crude v4.2 (SHA flip + EMA9/22, 10-bar swing stop 1.5-3.0xATR, no fixed target, exit on stop or reversal), entries 09:15 (the only TradingView-confirmed start). Harness, 30 months, gross points.
Reference (harness, corrected engine): 758 trades, PF 1.727, +12,105, win 20.7%, worst DD 2,027. (TradingView replay of the same config: 885 trades, PF 1.541, +10,623, win 20%, DD 1,279 -- the harness is the search tool here; anything promising gets replayed after.)
Two new engine hooks added to research_sim.simulate this round: `scale_r`/`scale_frac` (realise a fraction of the position once the running favourable move reaches scale_r x the original risk, same no-lookahead convention as the existing be_at_r/trail hooks; remainder rides to the normal exit) and `min_hold_bars_rev` (ignore a reversal signal until the position has been open this many bars). Control re-run after adding them: unchanged (758 trades).
50 configs, all at 09:15, all combined with reversal_exit + no fixed target:
A (6) break-even at R in {0.5, 0.75, 1.0, 1.25, 1.5, 2.0}.
B (6) break-even 1.0R + trailing: (trail_start_r, trail_dist_r) in {(1.5,1.0), (2.0,1.0), (2.0,1.5), (2.5,1.5), (3.0,2.0), (1.5,0.5)}.
C (15) partial scale-out: scale_r in {1.0, 1.5, 2.0, 2.5, 3.0} x scale_frac in {0.33, 0.5, 0.67}.
D (6) initial stop width: (minSL, maxSL) in {(1.0,3.0), (1.25,3.0), (1.75,3.0), (2.0,3.0), (1.5,2.5), (1.5,3.5)}.
E (4) minimum hold before a reversal can fire: min_hold_bars_rev in {3, 6, 12, 24}.
F (6) trailing stop alone (no break-even): (trail_start_r, trail_dist_r) in {(1.0,1.0), (1.5,1.5), (2.0,2.0), (1.0,0.5), (1.5,1.0), (2.5,2.0)}.
G (7) hand-picked combinations of the above once single-knob results are in, plus 2 extra scale-out corners (scale_r=1.0/frac=0.25, scale_r=3.5/frac=0.5) to reach 50.
This is exploratory, not a single pass/fail pick -- multiple objectives (win rate up, net pts and drawdown held close to the reference) trade off against each other. A config is flagged as a genuine candidate only if: win rate >= 28% (meaningfully above the 20.7% reference), net pts >= 10,289 (within 15% of reference), and worst drawdown <= 2,432 (within 20% of reference). Any candidate goes to TradingView tiled replay before being called real, exactly like v4.2 itself was. Report full table regardless of whether anything clears the bar.
