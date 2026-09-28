# BankNifty tested on Dhan's full 5.1-year history (2026-09-28)
Data: `DHAN_BANKNIFTY_5m.csv`, 97,422 bars, 4 Aug 2021 - 28 Sep 2026. Same discipline as the Nifty search: price-action only (Dhan's index volume field is 91% zero/broken on BankNifty too -- confirmed again here), require
year-by-year robustness, not just a train/holdout split. Code `bnf_dhan_fresh.py`, data `research_data/bnf_dhan_fresh.csv`. **Important scope limit: the live BankNifty pick (Supertrend+volume filter) cannot be fairly re-tested
here at all** -- its edge depends on real futures volume, which Dhan's index feed doesn't have, and Dhan's futures historical data only covers the 3 currently-listed monthly contracts (~3 months), not a multi-year series
(no accessible historical scrip master for expired BankNifty futures contracts to stitch a longer series together). So this round answers "does a volume-free BankNifty edge exist over 5 years", not "is the live pick better than X".

## Headline finding: a genuine, multi-year bad regime exists (2021 - mid 2024) -- this is not a data artifact
Screened the same 36 price-action families as the Nifty round. **35 of 36 are net-negative over the full 5.1 years**; the one exception (Tenkan/Kijun) is barely positive (PF 1.006). Splitting at 1 Jun 2024 shows why: almost every
family has a clearly negative TRAIN half (2021 - mid 2024) and a positive HOLDOUT half (mid 2024 - now) -- e.g. Supertrend(10,3): TRAIN PF 0.811 / HOLD PF 1.168; Donchian(20): TRAIN 0.849 / HOLD 1.117; Tenkan/Kijun: TRAIN 0.949 / HOLD 1.076.
This is a **consistent pattern across unrelated signal types**, not one strategy's quirk -- BankNifty's intraday character appears to have genuinely shifted around mid-2024 (plausibly tied to the major SEBI/NSE F&O regulatory changes
phased in through late 2024 -- fewer weekly expiries, larger lot sizes -- though this is not independently confirmed here). **This is the same period the live TV-confirmed strategy was validated on** (TradingView's BankNifty
futures data only goes back to Sep 2023), so the two findings triangulate: an entirely different, volume-free, index-only data source shows the same recent period is favorable for trend-following on BankNifty.

## Best recent-regime candidate found (price-action only, no volume)
**Supertrend(10, mult=4) flip, RR 1.5, 45-minute time-stop, no other filters** (adding EMA200 or ADX filters, which helped on the futures data, actually hurt here -- a real, counter-intuitive difference between the two data sources):

| | trades/mo | PF (recent regime, mid-2024+) | net pts | DD | years positive |
|---|---|---|---|---|---|
| Live BankNifty pick, for reference (TV-confirmed, full period) | 28.9 | 1.284 | +14,450 | 1,719 | 6/6 windows |
| **This candidate, mid-2024 onward only** | 24.0 | **1.247** | +8,288 (~2.3yr) | 2,873 | **3/3** |

Checked as a real, if modest, plateau: multiplier 4-5 consistently outperforms the default 3 in this recent window (mult=3: PF 1.168; mult=4: PF 1.247; mult=5: PF 1.230), RR 1.5-2.5 all give similar results, and a 45-60 minute
time-stop is better than 30. All 3 individual years (2024, 2025, 2026) are positive; 61% of individual months are positive.

## Honest conclusion: this does not beat the live pick, and full-history robustness is NOT established
- **PF is lower than what's already live** (1.247 vs 1.284) and net points are far lower (+8,288 over 2.3yr vs +14,450 over the live pick's full validated period) -- this is not a strictly better candidate.
- **Full 5.1-year robustness is NOT achievable with what's been tried** -- unlike Nifty's "positive every year" result, BankNifty has a real, multi-year unfavorable stretch in its recent history that cannot be filtered away without destroying the edge entirely (every attempted filter made the pre-2024 period worse, not better).
- **The genuinely useful takeaway**: the live pick's favorable period is corroborated by an independent, volume-free data source, which is reassuring -- but it also means the live pick's edge has real regime risk. If BankNifty's
  market character reverts to its pre-mid-2024 pattern, this whole family of trend-following approaches (including the live pick) would likely struggle again. This is not something that can be filtered or tuned away; it is
  a property of the instrument's own history.

## Recommendation
Do not switch the live BankNifty pick based on this round -- nothing found here beats it, and the exercise mainly served to test whether a materially more robust, full-history-validated alternative exists (it does not, at least
among price-action-only signals). Keep the forward test running and treat the mid-2024-onward regime as the operating assumption, with the awareness (now better documented) that it has not always held.
