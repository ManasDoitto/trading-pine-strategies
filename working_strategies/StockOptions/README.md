# Stock options — Stocks-in-Play MA Base Breakout v1.0

A new intraday strategy for buying options on liquid NSE stocks. It is not tied to one
script: one set of rules runs across all 210 stock-option underlyings, with every
threshold ATR- or percent-normalised.

Source idea: the 9 EMA / 20 SMA / 200 SMA day-trading method (YouTube `2e4WayvjLJo`).
The video's rules were turned into code and tested on Dhan 5m history, Jan 2018 to Sep 2026.
The rules that didn't survive testing were dropped.

## Rules (5m chart)

| Step | Rule |
|---|---|
| Stock in play | Gap ≥ 0.75% (either way) **and** 09:15–09:45 volume ≥ 1.25× its 20-day average |
| Daily bias | Longs only if yesterday closed above the daily 20 SMA; shorts only if below |
| Trend | 9 EMA above a rising 20 SMA (slope ≥ 0.15 ATR over 10 bars); mirror for shorts |
| Not extended | Close within 2.5 ATR of the 20 SMA |
| Base | Last 15 bars (75 min) have a range ≤ 2.5 ATR and sit on the 9/20 zone |
| Volume | Signal bar volume ≥ its 20-day same-time-of-day average |
| Entry | Buy-stop 1 tick above the base high (sell-stop below the low for shorts), valid 3 bars |
| Stop | 0.15 ATR beyond the base (at least 0.8 ATR away) |
| Exit | 5R target, otherwise flat at 15:15. No trailing |
| Session | Entries 09:45–13:15, max 2 trades per stock per day |
| **A+ tier** | All of the above **plus** the stock beats NIFTY since the open by ≥ 1.5% in the trade direction |

For option buying: a long signal means buy an ATM/1-ITM CE, a short signal means buy an ATM PE.
The stop and target are levels on the underlying.

## A+ screened (recommended tier)

A third tier on top of A+: only trade the 131 symbols (of 202) where A+ trades were already
PF>1 and net%>0 over 2018–2024 — screened on that window only, never on 2025–26 or the held-out
stocks. This is the tier actually in `stockopt/strategy_v1.json` and wired into the live scanner
(`is_aplus()` requires both the rel-strength gate and allowlist membership). It's the only tier
that stayed above the option hurdle in **every one of 9 tested years**, with enough trades/month
(~12–13) to actually act on. Core and A+ full remain useful as the wider, always-on comparison
points below. See `strategy_v1.json`'s `aplus.symbol_allowlist_note` for the exact screen and the
131-symbol list.

## Results (locked spec, 1 unit, gross, no costs)

The spec was frozen before any out-of-sample run. The universe was split into set A (105 stocks,
used for development) and set B (105 stocks never looked at). Time was split into IS (2018–22,
for tuning), VAL (2023–24) and OOS (2025-01 to 2026-09). **Updated 2026-09-29** after fixing an
EOD-flatten bug — see "Data integrity fix" below; numbers here are post-fix.

| Tier | Period | Trades | Win % | PF | Avg move / trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|
| Core | IS 2018–22 | 2,363 | 46.0 | 1.71 | +0.31% | +1.66% | −0.84% |
| Core | VAL 2023–24 | 847 | 46.2 | 1.64 | +0.23% | +1.29% | −0.68% |
| Core | **OOS 2025–26** | **925** | **49.5** | **1.53** | **+0.20%** | +1.08% | −0.66% |
| A+ | IS 2018–22 | 953 | 50.8 | 2.04 | +0.48% | +1.90% | −0.99% |
| A+ | VAL 2023–24 | 306 | 47.7 | 1.68 | +0.32% | +1.55% | −0.81% |
| A+ | **OOS 2025–26** | **387** | **53.5** | **1.82** | **+0.28%** | +1.18% | −0.76% |
| A+ screened | IS 2018–22 | 676 | 57.1 | 2.97 | +0.78% | +2.10% | −0.99% |
| A+ screened | VAL 2023–24 | 211 | 57.8 | 2.75 | +0.64% | +1.69% | −0.80% |
| A+ screened | **OOS 2025–26** | **259** | **57.1** | **2.09** | **+0.35%** | +1.18% | −0.77% |

- **Never-seen stocks (set B):** Core OOS PF 1.55, A+ OOS PF 1.83, A+ screened OOS PF 2.14 (119 trades). The edge carries over to stocks that played no part in development.
- **Every calendar year 2018–2026 clears the option hurdle** for Core and A+ screened. A+ (full, unscreened) dips to +0.07%/trade in 2024, just under the 0.09% hurdle — the screen exists partly to fix this.
- 162 of 210 stocks are net positive on Core.
- Median hold is about 2h40m and 90% of trades close within 4h. Most exits happen at 15:15, most of the rest at the stop, a small fraction at the 5R target.
- **Load:** a median of 2 trades a day on Core. On 95% of days there are 8 or fewer open at once, with a worst case of 25 on market-wide gap days. On heavy days, take A+ screened signals first, then A+, then the highest gap × volume.

"Points" here are gross points per stock, and each stock's table in `research_data/stockopt/final/*/per_symbol.csv` is in points. Summing points across stocks priced from ₹20 to ₹15,000 is meaningless, which is why the portfolio view uses % move and R.

## Is it worth it after option costs?

An ATM buyer has to recover the spread, about an hour of theta and charges. At delta ≈ 0.5, that
needs roughly a **0.09% underlying move per trade** just to break even.

- Core OOS makes +0.20% per trade, about 2× the hurdle. A+ OOS makes +0.28%, about 3×. A+ screened makes +0.35%, about 4×.
- Dhan's `charts/rollingoption` endpoint *does* serve real individual stock-option premium history (confirmed live 2026-09-29 — an earlier note in this repo claiming index-only was wrong). A small real-premium check on 19 recent A+ screened signals (Aug–Sep 2026) showed 73.7% win, PF 3.00 — consistent with the underlying-based estimate above, though this is a very small sample so treat it as a sanity check, not a validation.

## What was tested and rejected

- **The video's pullback setup.** PF fell from 1.87 to 1.24 and the per-trade move dropped below the option hurdle.
- **Trailing the stop under the 20 SMA after +1R.** Win rate rose to about 53–57%, but out-of-sample PF and move per trade fell. A higher win rate is available, but it costs edge.
- **A 15m higher-timeframe gate, an upper cap on slope, and a 15m chart instead of 5m.** None of them helped.
- **NIFTY-direction alignment.** Its effect flipped sign between IS and VAL.

## Data integrity fix (2026-09-29)

The engine's "flat by 15:15" rule checked `minutes_since_open >= 360`. Dhan's intraday data for
most history has a bar reaching ~15:25/15:30, so that fired correctly — but for **every trading
day from 2026-08-03 to 2026-09-28** (confirmed with a fresh live pull, not stale data — this is
an ongoing Dhan data-finalization lag on recent days), the feed stops at ~15:10, the threshold is
never reached, and the position silently rolled into the next day instead of closing. 47/4,135
Core trades (1.1%) and 14/259 A+-screened OOS trades (5.4%) were affected, concentrated almost
entirely in that six-week window. Fixed by force-flattening on the last bar Dhan actually has for
each calendar day (`engine.py`'s `last_of_day`), not a literal minute count. All numbers on this
page are post-fix; the fix made every tier's OOS stats slightly *better* (uncontrolled multi-day
holds were, on balance, more often extending losers than winners) — the strategy's live
"flat same day" character was already what the numbers implied, this just makes the backtest
honor its own rule. **This also matters live**: today's session likely has the same truncation,
so anything downstream of the scanner should flatten on wall-clock time, not on waiting for
Dhan's own bar data to reach a specific timestamp.

## Caveats

- **The strategy weakens from IS to OOS**: Core PF goes from 1.71 to 1.53, A+ from 2.04 to 1.82, A+ screened from 2.97 to 2.09. Plan for the OOS numbers, not the IS ones.
- **2026 year-to-date is the weakest year for Core and A+ full** (though both still clear the hurdle post-fix: +0.107% and +0.169%/trade). A+ full's worst year is actually 2024, at +0.073% — just under the hurdle. A+ screened clears every year including 2026 (+0.174%). Weak stretches can last months.
- **Survivorship:** the universe is today's F&O list, which slightly flattens older years.
- **The OOS window and set B are now used up.** Any further change needs a live forward test, not another backtest run on this data.
- **The Pine script has not been compiled on TradingView.** Paste it into a *new* script yourself. The repo's notes record the TV MCP overwriting live scripts.

## Files

- `1_v1.0_MA_base_breakout.pine.txt` — TradingView strategy for one chart. It includes the stats table and the A+ toggle.
- `../../stockopt/strategy_v1.json` — the locked spec.
- `../../stockopt/scan_live.py` — read-only scanner across all 210 stocks. It **places no orders** and matches the backtest 100% on every entry checked.
  - `python -m stockopt.scan_live` — scan once now.
  - `python -m stockopt.scan_live --loop` — rescan every 5 minutes until 13:20.
  - `python -m stockopt.scan_live --replay 2026-09-28` — list a past session's signals.
- `../../stockopt/engine.py` — numba backtest kernel.
- `../../stockopt/research.py`, `sweep.py`, `final_eval.py` — the research protocol, staged sweeps and one-shot evaluation.
- `../../stockopt/harvest_nse_5m.py` — resumable Dhan 5m downloader. The data lands in `research_data/nse5m/`, which is gitignored.
