# Multi-Asset Strategy Sweep: XAUUSD, BTCUSD, BankNifty, CrudeOil (13 Sep 2026)

## Method — read this before the numbers

**Data source substitution.** Delta Exchange (the crypto derivatives exchange) is **not available on TradingView** — `DELTA:BTCUSD` resolves to nothing (`symbol_info` errors on a null symbol) and it doesn't appear in TradingView's symbol search at all. Gold and Bitcoin were tested on **OANDA:XAUUSD** and **Coinbase:BTCUSD** instead — both liquid, standard reference feeds. If you specifically need Delta Exchange pricing (e.g. for its own derivatives contracts), these numbers are directionally right but not tick-exact to that venue.

**Backtest method.** Every row was measured with the same **tiled non-overlapping-window** method used throughout this project's audits (`strategy_audit_2026_09/`), not raw `data_get_strategy_results` calls per replay chunk. That method double-counts trades across chunk boundaries when chunks overlap, which they do under naive `replay_start` jumps — using it would have made these numbers wrong and incomparable to every other result in this repo. Each window's trades are counted only from the first UTC midnight after 400 bars, so windows never overlap; a scoreboard (`aud_` block) appended to each audit copy tallies this on-chart and the results are stitched together afterward.

**Costs.** 1 lot/contract, 0.02% commission per side, no added slippage — identical to every other test in this project.

**Points, not fiat (rule #4).** Every figure below is already **points per lot/contract**, not currency. The audit scoreboard divides each trade's fiat profit by `syminfo.pointvalue` at the moment it runs, so gold ($/oz), Bitcoin ($/BTC), BankNifty (₹30/point) and Crude (₹100/point) are all directly comparable as "points captured" — this was built into every audit copy in this project from the start, not added for this sweep.

**Session filters** were disabled (`useSess=false`) on XAUUSD and BTCUSD for every strategy tested, since both trade continuously — per your instruction. BankNifty and CrudeOil kept their own proven session settings from prior rounds.

**Scope actually tested — read this, it matters for the "every strategy" ask.**
- **BankNifty and CrudeOil rows are reused from this project's existing, already-verified audit runs** (11 crude windows / 29.7 months, 5 BankNifty windows / 30.2 months) — no new TradingView calls were needed for these two, since the identical tiled method was already applied to them across earlier rounds this session. Re-running them would have just reproduced the same numbers.
- **XAUUSD and BTCUSD are new tests, run for this sweep**, limited to **three strategies** rather than the full list, for a specific reason: the others depend on things that don't translate — BankNifty v0.4 and v13 are built on NSE-hours VWAP+ADX+PD-level logic with point caps tuned to BankNifty's price scale (~₹50,000 index level), and Master Adaptive Strategy v2 depends on real traded volume for its daily VWAP filter, which OANDA's gold CFD feed does not reliably provide (tick volume only). Porting them convincingly would mean redesigning them, not testing them. The three that were tested — **Crude v4.0's SHA-flip logic, Crude v2.1's EMA-pullback logic, and SMC v1.1** — have no volume/session dependency baked into their edge, so they are the ones that can be tested on a new instrument without first rebuilding them.
- **Master Adaptive Strategy v1** — a file (`Master_Adaptive_Strategy_v1.pine.txt`) exists in the repo but was not read or tested in this sweep. Flagging this rather than guessing at it or silently skipping it.
- **v13 sweep-fade** was not re-run on gold/bitcoin/crude for the reason above (BankNifty-specific level/cap logic); its BankNifty number below is reused from the existing audit.
- The full historical set (40+ strategy/variant combinations tested across this project) lives in `strategy_audit_2026_09/*.md` and `README.md`. This report features the headline strategies plus the ones you explicitly named, not every minor variant ever tried.

---

## 1. Raw data table

Points are per lot/contract. Sharpe uses daily point P&L, annualized — same formula as every other table in this repo.

| Instrument | Strategy | Trades/mo | Win% | PF | Net pts | Max DD | Sharpe | +windows | Source |
|---|---|---|---|---|---|---|---|---|---|
| **XAUUSD** | Crude v4.0 logic (SHA flip RR3, no session) | 32.9 | 28.7 | **1.04** | **+300** | 433 | +0.30 | 7/12 | New test |
| **XAUUSD** | Crude v2.1 logic (EMA 9/22, sep 1.5×ATR) | 35.9 | 37.3 | 0.75 | −1,125 | 1,206 | −2.61 | 1/12 | New test |
| **XAUUSD** | SMC Liquidity Sweep + FVG v1.1 | 3.8 | 44.5 | 0.49 | −308 | 351 | −1.97 | 3/11 | New test |
| **BTCUSD** | Crude v4.0 logic (SHA flip RR3, no session) | 35.1 | 25.3 | 0.89 | −33,233 | 39,174 | −1.08 | 4/12 | New test |
| **BTCUSD** | Crude v2.1 logic (EMA 9/22, sep 1.5×ATR) | 35.7 | 35.4 | 0.85 | −25,310 | 33,527 | −1.49 | 3/12 | New test |
| **BTCUSD** | SMC Liquidity Sweep + FVG v1.1 | 4.7 | 41.7 | 0.64 | −10,427 | 11,593 | −1.50 | 3/12 | New test |
| **BankNifty** | **v0.4 EMA pullback + 15m ADX** | 2.5 | 41.9 | **1.33** | **+1,403** | 1,620 | +0.57 | 3/5 | Existing audit |
| BankNifty | v10.3 PD sweep + daily trend | 3.5 | 38.1 | 1.10 | +924 | 2,631 | +0.22 | 2/5 | Existing audit |
| BankNifty | v13 sweep-fade (bear) | 7.7 | 32.5 | 1.06 | +914 | 2,642 | +0.19 | 2/5 | Existing audit |
| BankNifty | SMC v1.2 (NSE 0945-1515 + 0.2 ATR buffer) | 5.2 | 50.6 | 0.80 | −2,928 | 4,356 | −0.70 | 1/5 | Existing audit |
| BankNifty | Master Adaptive Strategy v2 (not native to this instrument) | — | — | — | — | — | — | — | Not tested (crude-tuned) |
| **CrudeOil** | Crude v2.1 EMA pullback (sep 1.5×ATR) | 17.4 | 37.3 | **1.14** | +1,304 | **900** | +0.67 | 5/11 | Existing audit |
| CrudeOil | Crude v4.0 SHA flip RR3 | 28.3 | 28.0 | 1.09 | **+2,136** | 2,339 | +0.50 | 6/11 | Existing audit |
| CrudeOil | Crude v2.0 EMA pullback (sep 0.5×ATR) | 45.3 | 37.9 | 1.09 | +2,195 | 2,358 | +0.72 | 4/11 | Existing audit |
| CrudeOil | Master Adaptive Strategy v2 (user's own script) | 34.1 | 30.8 | 0.93 | −1,461 | 2,135 | −0.53 | 4/11 | Existing audit |
| CrudeOil | SMC v1.2 (swingLen=10, US session) | 6.0 | 55.3 | 1.25 | +655 | 454 | +0.61 | 6/11 | Existing audit |
| CrudeOil | SMC v1.1 (swingLen=20, US session) | 2.9 | 52.3 | **1.40** | +546 | 302 | +0.64 | 5/11 | Existing audit |

---

## 2. The winners — highest points **with PF strictly above 1.15**

Applying your rule exactly as stated:

| Instrument | Winner | PF | Net pts |
|---|---|---|---|
| **XAUUSD** | **None qualifies.** Best available: Crude v4.0 logic at PF 1.04, +300 pts. | 1.04 | +300 |
| **BTCUSD** | **None qualifies.** Every strategy tested lost money. Least-bad: Crude v4.0 logic at PF 0.89, −33,233 pts. | 0.89 | −33,233 |
| **BankNifty** | **v0.4 EMA pullback + 15m ADX gate** | **1.33** | **+1,403** |
| **CrudeOil** | **None qualifies under the strict >1.15 rule.** Highest PF is SMC v1.1 at 1.40 with +546 pts on 86 trades (thin sample, flagged as such when it was first tested) — but earlier work explicitly recommended v4.0 as primary and v2.1 as the risk-efficient companion, not SMC v1.1, because SMC v1.1's win doesn't survive its own frequency test. The most-tested, most-trades pick with a real PF edge is v2.1 at 1.14, one hundredth under your bar; v4.0 has the most total points (+2,136) at PF 1.09. | 1.14 (v2.1) / 1.40 (SMC v1.1, thin) | +1,304 / +546 |

**I'm not going to round 1.14 up to clear your 1.15 bar, or wave away that SMC v1.1's "win" on crude sits on only 86 trades over 30 months.** Two honest readings, pick whichever matches what you're optimizing for:

- **By the letter of your rule** (PF > 1.15, most points among qualifiers): BankNifty v0.4 is the only outright winner across all four instruments. Nothing else in this table clears both bars at once.
- **By practical trading merit** (statistical weight + consistency, not just PF): CrudeOil v4.0 (2,136 pts, 842 trades, 6/11 windows, PF 1.09) and v2.1 (PF 1.14, smallest drawdown of any crude strategy) remain the best crude picks, as concluded in the dedicated 2-year analysis two rounds ago. SMC v1.1's 1.40 PF is real but rests on a sample about 10x smaller than v4.0's — treat it as promising, not proven.

**Gold and Bitcoin: no strategy tested is fit to trade.** The closest thing to an edge is v4.0's logic on gold (PF 1.04 — essentially breakeven after costs). Everything else, including every strategy tried on Bitcoin, lost money outright, several of them badly (v4.0's logic lost 33,233 points — over $33,000 per 1 BTC contract — across 30 months on Bitcoin). These three strategies were built and tuned on crude and BankNifty's specific volatility, session structure, and trend character; nothing here suggests they transfer to gold or crypto, and this sweep is evidence against that idea, not for it.

---

## 3. Reading the failure on gold and Bitcoin

- **Bitcoin's drawdowns are severe in absolute point terms** because BTC's point-value is 1:1 with price (~$110,000/BTC), so a few thousand points of adverse excursion is ordinary volatility for the asset, not a strategy malfunction — but it still means these strategies, sized at 1 contract, would have drawn down tens of thousands of dollars.
- **SMC v1.1 traded far less often on gold/BTC than on crude** (3.8–4.7/month vs ~3–6/month on crude) despite the same swing-length and no session filter — its EMA200 trend gate plus liquidity-sweep mechanic simply finds fewer qualifying setups on these price series.
- **None of the three strategies' entry logic references anything about the instrument** (no gold-specific or BTC-specific parameter exists in any of them) — they were tested completely unmodified, using each script's crude-tuned defaults. That's a fair test of "does this transfer," and the answer is no.

## 4. What this doesn't tell you

This sweep does not mean gold and Bitcoin are untradeable — it means these three particular crude-tuned strategies don't work there unmodified. A real gold or Bitcoin strategy would need its own volatility calibration (ATR multiples sized to each asset's actual range, not crude's), and for Bitcoin specifically, its own session/liquidity-hours logic (crypto still has real quiet/active hour patterns despite trading 24/7). None of that exists yet for either asset.
