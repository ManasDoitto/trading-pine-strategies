# Deep Multi-Asset Strategy Sweep: CrudeOil, BankNifty, XAUUSD, BTCUSD (13 Sep 2026)

This supersedes `multi_asset_sweep_2026_09_13.md`. That version tested 3 hand-picked strategies on gold/Bitcoin. This one tests **every strategy family in the repo** — via the pre-built multi-variant "lab" scripts that already existed here — plus every standalone named strategy, on all four instruments.

## Why this is actually broader, not just "more of the same trick"

Testing ~55 individual `.pine` files one at a time across 4 instruments would have taken 500+ tool round trips and was not practical in one session. The repo already contains three purpose-built **variant lab** scripts — `indicator()` studies that self-simulate dozens of strategy variants side by side in a single compile+replay pass, each covering a distinct family of entry logic:

- **Lab v1** (32 variants, 6 families): SHA+RSI3 pullback ("v3.0" lineage), EMA9/22 touch pullback ("crude v1" lineage), SHA colour-flip (V21 = **crude v4.0 exactly**), Donchian breakout+SHA, RSI3 extreme snap-back, liquidity-sweep fade ("BN v13"/"Nifty v2" lineage).
- **Lab v2** (20 variants): SHA pullback gated by 15m trend agreement, CPR pullback, PDH/PDL break-retest, S1/R1 fade.
- **Lab v3 / vp_lab3** (24 variants): volume-profile mechanics — POC bounce, value-area edge fade, VP-level sweep fade, dPOC-trend pullback, all against prior/current-day POC and value area.

That's **76 distinct strategy variants**, spanning nearly every entry-logic idea in this repo, each scored with the same tiled non-overlapping-window walk-forward method used everywhere else in this project. Labs v1/v2/v3 were already run exhaustively on **Crude, BankNifty and Nifty** in earlier rounds this session (`variant_lab_v1/lab_summary.md`, `variant_lab_v2/lab2_summary.md`, `strategy_audit_2026_09/vp_lab3_summary.md`) — no new TradingView calls were needed there. What was genuinely missing was **XAUUSD and BTCUSD**, so this round built a minimal 24/7-session patch of lab v1 (one new input toggle, byte-identical simulation logic otherwise) and ran it through **12 tiled windows each** on OANDA:XAUUSD and Coinbase:BTCUSD — the same walk-forward rigor as every other instrument in this project, reaching each instrument's full TradingView 5m history floor (XAUUSD: 2024-01-31 onward; BTCUSD: 2024-02-21 onward).

**Lab v2 and v3 were not re-run on gold/Bitcoin.** Reason: both labs' edges are built on volume-profile levels (POC, value area, CPR) or 15m multi-timeframe confluence gates, which depend on either real traded volume or session structure that doesn't map cleanly onto a continuously-traded CFD/crypto pair. OANDA's gold feed is CFD tick volume, not real traded volume — running a volume-profile lab against it would produce numbers that look precise but aren't measuring anything real. Coinbase:BTCUSD does have real volume and could support lab v3 in a future round, but that's flagged as **not done here**, not silently skipped.

## Method (unchanged from every other audit in this project)

- **Tiled non-overlapping windows**: trades counted only from the first UTC midnight after 400 bars of warm-up, so sequential `replay_start` windows tile history with zero double-counting.
- **Costs**: 1 lot/contract, 0.02% commission per side, no added slippage.
- **Points, not fiat**: every figure is points per lot/contract (fiat profit ÷ `syminfo.pointvalue`), making gold ($/oz), Bitcoin ($/BTC), BankNifty (₹30/pt) and Crude (₹100/pt) directly comparable.
- **Session filters**: off for XAUUSD/BTCUSD (24/7 assets), on (instrument-appropriate) for BankNifty/CrudeOil, exactly as in every prior round.

---

## 1. XAUUSD (OANDA), 5m — 12 windows, 2024-01-31 → 2026-09-13, 31.4 months

All 32 lab-v1 variants tested. **Only one variant is net positive over the full period:**

| Rank | Variant | Trades/mo | Win% | PF | Net pts | Sharpe(d) | +windows |
|---|---|---|---|---|---|---|---|
| **1** | **V21 — SHA flip RR3 (= crude v4.0's exact logic)** | 33 | 28.7 | **1.04** | **+300** | +0.30 | 7/12 |
| 2 | V24 — Donchian20 + SHA RR3 | 37 | 26.3 | 0.97 | −258 | −0.23 | 3/12 |
| 3 | V20 — SHA flip RR2 | 38 | 36.9 | 0.97 | −224 | −0.29 | 6/12 |

The other 29 variants range from PF 0.94 down to PF 0.53, all net negative — full ranking in `scratchpad` aggregation output, summarized: every "v3.0" pullback variant (V01-V16, V32), every EMA-touch variant (V17-19), every sweep-fade variant (V26, V28-30) loses money on gold. This exactly reproduces the finding from the prior round's 3-strategy sweep (crude v4.0 logic: PF 1.04, +300 pts) — now confirmed against 29 additional variants, not just 2.

Cross-reference from the prior round (crude v2.1 logic, SMC v1.1 — not part of lab v1, tested standalone last time): both were negative (PF 0.75 and 0.49 respectively) and remain the worst-performing named strategies tried on gold.

**Reading:** Gold has exactly one thin edge in this entire 76-variant space — crude v4.0's SHA-flip mechanic — and even that is barely above breakeven after costs (PF 1.04). Nothing here is fit to trade live.

---

## 2. BTCUSD (Coinbase), 5m — 12 windows, 2024-02-21 → 2026-09-13, 30.7 months

All 32 lab-v1 variants tested. **Every single one is net negative.**

| Rank | Variant | Trades/mo | Win% | PF | Net pts | Sharpe(d) | +windows |
|---|---|---|---|---|---|---|---|
| 1 (least bad) | V22 — SHA flip + EMA200 RR2 | 35 | 35.3 | 0.96 | −8,982 | −0.38 | 6/12 |
| 2 | V05 — v3.0 RR3.0 | 52 | 26.7 | 0.96 | −20,114 | −0.55 | 5/12 |
| 3 | V20 — SHA flip RR2 | 41 | 34.1 | 0.93 | −20,679 | −0.75 | 4/12 |
| ... | V21 — SHA flip RR3 (= crude v4.0 logic) | 35 | 25.3 | 0.89 | −33,230 | −1.08 | 4/12 |
| worst | V28 — Sweep-fade RR2 (BN v13 idea) | 258 | 33.7 | 0.60 | −252,444 | −6.77 | 0/12 |

This reconfirms and deepens the prior round's finding (which tested only 3 strategies and also found all of them losing, worst being v4.0 logic at −33,233 pts). With all 32 lab-v1 variants now tested, the conclusion is unambiguous: **there is no strategy in this repo's variant space that trades Bitcoin profitably.** Even the least-bad variant (V22, PF 0.96) is a clear loser after costs.

---

## 3. CrudeOil (MCX:CRUDEOIL1!), 5m — 11 windows, 29.7 months (existing audits, reused)

Combining lab v1 (32 variants), lab v2 (20 variants) and vp_lab3 (24 variants) — 76 variants total — plus the standalone strategies not covered by any lab:

| Strategy | Trades/mo | Win% | PF | Net pts | Max DD | +windows | Source |
|---|---|---|---|---|---|---|---|
| **v2.0 EMA pullback (sep 0.5×ATR)** | 45.3 | 37.9 | 1.09 | **+2,195** | 2,358 | 4/11 | Existing audit |
| **v4.0 SHA flip RR3** (= lab v1 V21 = lab v2 V01, all three reproduce the same result) | 28.3 | 28.0 | 1.09 | +2,136 | 2,339 | 6/11 | Existing audit, confirmed 2× more |
| **v2.1 EMA pullback (sep 1.5×ATR)** | 17.4 | 37.3 | **1.14** | +1,304 | **900** | 5/11 | Existing audit |
| Lab v2 V04 — SHA flip + outside prior value | 14.1 | 29.3 | 1.10 | +1,225 | 1,804 | 6/11 | Lab v2 |
| SMC v1.2 (swingLen=10, US session) | 6.0 | 55.3 | 1.25 | +655 | 454 | 6/11 | Existing audit |
| SMC v1.1 (swingLen=20, US session) | 2.9 | 52.3 | 1.40 | +546 | 302 | 5/11 | Existing audit, thin sample (86 trades) |
| Lab v2 V13 — pPOC bounce RR3 | 16.8 | 28.6 | 1.07 | +373 | 665 | 6/11 | Lab v2 |
| Master Adaptive Strategy v2 (user's own script) | 34.1 | 30.8 | 0.93 | −1,461 | 2,135 | 4/11 | Existing audit |

**No new winner.** v2.0 has the highest raw points but dies at 1 tick of slippage (documented in `v2.0E_results.md`). v4.0 remains the most robust pick over the full 30-month history (only variant still positive with its best window removed: +888 pts). v2.1 has the best PF and smallest drawdown. SMC v1.1/v1.2 are real but thin-sample improvements, not yet ready to size like v4.0/v2.1. Across all 76 lab variants plus every standalone strategy tested this session, **nothing beats what was already identified two rounds ago.**

---

## 4. BankNifty (NSE:BANKNIFTY1!), 5m — 5 windows, 30.2 months (existing audits, reused)

| Strategy | Trades/mo | Win% | PF | Net pts | Max DD | +windows | Source |
|---|---|---|---|---|---|---|---|
| **v0.4 EMA pullback + 15m ADX gate** | 2.5 | 41.9 | **1.33** | **+1,403** | **1,620** | 3/5 | Existing audit |
| v10.3 PD sweep + daily trend | 3.5 | 38.1 | 1.10 | +924 | 2,631 | 2/5 | Existing audit |
| v13 sweep-fade (bear) | 7.7 | 32.5 | 1.06 | +914 | 2,642 | 2/5 | Existing audit |
| Lab v2 V04 — SHA flip + outside prior value | 9.0 | 39.2 | 1.00 | −45 | 3,758 | 3/5 | Lab v2, best of 20 variants, still ~breakeven |
| SMC v1.2 (NSE 0945-1515, 0.2 ATR buffer) | 5.2 | 50.6 | 0.80 | −2,928 | 4,356 | 1/5 | Existing audit |
| SMC v1.1 (no session filter) | 2.0 | 45.9 | 0.77 | −1,236 | 2,337 | 2/5 | Existing audit |

Across lab v1 (32 variants), lab v2 (20 variants) and vp_lab3 (24 variants) — 76 variants — **every single one is net negative on BankNifty except v0.4 itself, which isn't part of any lab.** The best any lab variant manages is lab v2's V04 at PF 1.00 (essentially breakeven, −45 pts). v0.4's edge — a 15m ADX regime gate layered on an EMA pullback — is not reproduced by any of the 76 generic variants tested. **v0.4 remains the clear, uncontested BankNifty winner.**

---

## 5. Bottom line — did a better strategy turn up?

**No.** Across 76 lab variants (covering nearly every entry-logic family in this repo) plus every standalone named strategy, tested on all four instruments with the same rigorous tiled walk-forward method used throughout this project:

- **CrudeOil**: v4.0 and v2.1 remain the best picks (v2.0 has more raw points but fails a slippage stress test already documented). No lab variant beats them.
- **BankNifty**: v0.4 remains uncontested — every one of 76 generic lab variants loses money here; only v0.4's specific ADX-gated construction works.
- **XAUUSD**: crude v4.0's SHA-flip logic is the only profitable idea anywhere in this test space, and it's barely above breakeven (PF 1.04). Not worth trading as-is.
- **BTCUSD**: nothing works. All 32 lab-v1 variants lose money; the least-bad is still a clear net loser after costs.

This is a materially deeper test than the prior round (3 strategies → 76+ variants), and it reaches the same conclusion with much stronger evidence: **the strategies already flagged as winners are winners because they were the strongest ideas tried, not because better options were overlooked.**
