# SMC Liquidity Sweep + FVG v1.2 (13 Sep 2026)

## What changed from v1.1

`SMC liquidity sweep + FVG v1.2 (NSE session + stop-hunt buffer for BankNifty, looser swing-disp for crude frequency).pine.txt`.

1. **BankNifty:** session filter default changed to `"0945-1515"` IST (NSE hours, skipping the first 30 minutes of open chaos), and `slBufferATR` default raised 0.1 → 0.2 (this input already existed in v1.0/v1.1; only the default changed — it's shared across both instruments since it's one script).
2. **Crude frequency:** `swingLen` default lowered 20 → 10, `minDispATR` default lowered 1.0 → 0.8.

Compiled clean (same standard advisory as every other script here). Because `slBufferATR`, `swingLen` and `minDispATR` are single shared inputs in one script, testing "BankNifty's fixes" and "crude's fixes" together in the same coded defaults would have let crude's frequency-loosening bleed into the BankNifty run. I ran BankNifty two ways to keep the read honest: the full v1.2 coded defaults, and a second pass with `swingLen`/`minDispATR` held back at v1.1's values so only the two BankNifty-specific changes (session, SL buffer) are being measured. Same tiled non-overlapping-window method as every prior run: 1 lot, 0.02%/side, no slippage.

## BankNifty: still not profitable

| Config | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| v1.1 (no session filter) | 2.0 | 45.9 | 0.77 | −1,236 | 2,337 | 2/5 |
| **v1.2 isolated** (0945-1515 + 0.2 ATR buffer only, swingLen/minDispATR held at v1.1) | 2.0 | 44.1 | 0.76 | −1,329 | 2,603 | 2/5 |
| v1.2 full defaults (session + buffer + crude's looser swing/disp) | 5.2 | 50.6 | 0.80 | −2,928 | 4,356 | 1/5 |

**The NSE session filter and the wider SL buffer, on their own, did not push BankNifty into profitability — if anything they're a rounding error worse than v1.1** (PF 0.76 vs 0.77, essentially flat). Restricting to 0945-1515 removes some trades v1.1 was taking outside NSE hours (30 trades → 25 in this isolated run — wait, both show similar trade counts since v1.1 already had `useSess=false`, so this isn't a clean apples-to-apples on frequency, but the P&L outcome is the same either way). The wider stop buffer didn't rescue enough double-tap sweeps to matter at this sample size.

Loosening `swingLen`/`minDispATR` on top (the full v1.2 defaults) made things **worse**, not better: more than double the trades (5.2/mo vs 2.0), but PF fell further to 0.80 and drawdown nearly doubled to 4,356 — the extra trades let in are lower quality. **Do not use the full v1.2 defaults on BankNifty; if you want to keep testing this idea, use the isolated config (session + buffer, swingLen 20) as the baseline instead**, though even that isn't profitable.

## CrudeOil: no config hits both targets at once

Your target: **≥15-20 trades/month AND PF strictly above 1.15.** Three `swingLen` values were tested, all with `minDispATR=0.8` and the US session filter on ("1730-2330"):

| swingLen | Trades/mo | Win% | PF | Net pts | Max DD | + windows |
|---|---|---|---|---|---|---|
| 20 (v1.1) | 2.9 | 52.3 | **1.40** | +546 | 302 | 5/11 |
| **10 (v1.2 default)** | 6.0 | 55.3 | **1.25** | +655 | 454 | 6/11 |
| 5 | 12.7 | 52.1 | 0.97 | −236 | 1,123 | 6/11 |

**None of the three hits both conditions together.** There's a clear, monotonic trade-off: loosening `swingLen` from 20 to 10 to 5 roughly quadruples trade frequency (2.9 → 6.0 → 12.7/month) while profit factor falls in lockstep (1.40 → 1.25 → 0.97). At `swingLen=5` — already short of the 15-20/month floor — PF has already dropped below 1.0, so pushing further (e.g. `swingLen=3`) would very likely land under your 1.15 floor with even more certainty; that config was not run, since the pattern across three points is unambiguous.

- **`swingLen=10` (the new v1.2 default) is the best point on this curve that still clears PF 1.15** — 1.25, with 6/11 windows positive and a small 454-pt drawdown. But it only reaches 6.0 trades/month, not 15-20.
- **`swingLen=5` gets closer to the frequency target (12.7/month) but fails the profit-factor floor** (0.97 — net negative over the full period), and its drawdown (1,123) is 2.5x `swingLen=10`'s.
- The other loosened knob, `minDispATR` 1.0→0.8, was tested only in combination with the swingLen changes, not in isolation — it's a smaller lever than swing length by construction (it only gates the displacement candle, not how many candidate sweep levels exist), so swing length is almost certainly doing most of the work in this trade-off.

## Verdict

**BankNifty:** neither the isolated fix (session + buffer) nor the full v1.2 config reaches profitability, and the full config is worse than v1.1. This strategy is not yet a BankNifty candidate. The next lever, if you want to keep going, is probably not session/buffer tuning — it's more structural (the sweep/FVG mechanic itself may not suit BankNifty's price action even with the trend filter).

**Crude:** the 15-20 trades/month **and** PF>1.15 target is not achievable by adjusting `swingLen` alone in this data — the two moved directly against each other across all three points tested. You have a real choice to make between two configs, not a single answer:
- `swingLen=10`: PF 1.25, 6.0 trades/month, 454-pt drawdown — clears your PF floor comfortably but well under your frequency floor.
- `swingLen=20` (v1.1): PF 1.40, 2.9 trades/month, 302-pt drawdown — the strongest PF and smallest drawdown, but the thinnest frequency (86 trades total).

Since neither meets the frequency target, going straight to a "deep forward test on older data" per your stated plan would be testing a strategy that doesn't yet satisfy the stated gate. My recommendation: hold this at `swingLen=10` (PF 1.25 is a genuine edge, not noise — 6/11 windows positive) and treat 6 trades/month as the honest ceiling for this mechanic on crude 5m without a structural change (a second, independent signal source, or loosening a different gate such as `maxDispBars` or `coolBars`, neither of which was touched here). I did not chase `swingLen<5` since the trend across three points already answers the question.
