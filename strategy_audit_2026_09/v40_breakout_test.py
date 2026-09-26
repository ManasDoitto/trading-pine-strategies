"""Donchian breakout entry on the v4.0 base (silver). Pre-reg: pre_registration_v40_breakout_2026_09_26.md
Base frozen at working_strategies/Silver #1; the ONLY change is entry = SHA flip OR Donchian breakout."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals as v40
from trading_agents.core import signals_v50 as v50

T0 = pd.Timestamp("2024-03-25")
WIN = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in (
    ("2024-03-25", "2024-08-25"), ("2024-08-25", "2025-01-25"), ("2025-01-25", "2025-06-25"),
    ("2025-06-25", "2025-11-25"), ("2025-11-25", "2026-04-25"), ("2026-04-25", "2026-09-25"))]
BASE = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=2.5, max_sl=5.0, rr=3.0,
            session=["09:15", "23:30"])
DAY_LIMIT = 350.0
BAR_NET, BAR_CONC, BAR_DD = 222240.5, 61.4, 33692.8


def build(bars="MCX_SILVER1", lookback=None, use_flip=True, adx_min=0.0):
    f = v40.v40_frame(rs.load(bars), BASE).copy()
    cap = BASE["max_sl"] * f["atr"]
    tl, ts = (f["e9"] > f["e22"]), (f["e9"] < f["e22"])
    L = f["flip_up"].copy() if use_flip else pd.Series(False, index=f.index)
    S = f["flip_dn"].copy() if use_flip else pd.Series(False, index=f.index)
    if lookback:
        dc_hi = f["high"].rolling(lookback).max().shift(1)
        dc_lo = f["low"].rolling(lookback).min().shift(1)
        L = L | (f["close"] > dc_hi)
        S = S | (f["close"] < dc_lo)
    if adx_min > 0:
        adx = v50.adx_15m_prev(rs.load(bars))
        ok = (adx >= adx_min).fillna(False)
        L, S = L & ok, S & ok
    f["ok_l"] = f["in_sess"] & L & tl & (f["risk_l"] <= cap)
    f["ok_s"] = f["in_sess"] & S & ts & (f["risk_s"] <= cap) & ~f["ok_l"]
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(f, dict(BASE, day_loss_limit_pts=DAY_LIMIT), start=s0, commission=0.0)


def row(tag, tr):
    if not tr:
        return dict(variant=tag, n=0)
    s = rs.stats(tr)
    t = pd.DataFrame(tr); t["exit_time"] = pd.to_datetime(t["exit_time"])
    wn = [float(t[(t.exit_time >= a) & (t.exit_time < b)].net.sum()) for a, b in WIN]
    conc = 100 * max(wn) / s["net"] if s["net"] > 0 else None
    return dict(variant=tag, n=s["n"], per_mo=round(s["n"] / 30, 1), pf=s["pf"], net=s["net"],
                max_dd=s["max_dd"], win=s["win_pct"], pos_m=s["pos_months_pct"],
                conc=round(conc, 1) if conc else None,
                **{f"w{i+1}": round(x) for i, x in enumerate(wn)},
                P1_net=s["net"] > BAR_NET, P2_trades=s["n"] >= 600,
                P3_conc=(conc is not None and conc <= BAR_CONC), P4_dd=s["max_dd"] <= BAR_DD)


if __name__ == "__main__":
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    rows = [row("INCUMBENT (flip only)", build(lookback=None))]
    for lb in (3, 5, 10, 20):
        rows.append(row(f"B{ {3:1,5:2,10:3,20:4}[lb] } flip OR breakout({lb})", build(lookback=lb)))
    rows.append(row("B5 breakout-only(5)", build(lookback=5, use_flip=False)))
    rows.append(row("B6 flip OR bo(5) + ADX25", build(lookback=5, adx_min=25.0)))
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "v40_breakout.csv", index=False)
    print(R[["variant","n","per_mo","pf","net","max_dd","win","pos_m","conc"]].to_string(index=False))
    print("\nper-window net points:")
    print(R[["variant","w1","w2","w3","w4","w5","w6"]].to_string(index=False))
    print("\npre-registered gates (bar: net>222,240.5 | >=600 trades | conc<=61.4% | dd<=33,692.8):")
    print(R[["variant","P1_net","P2_trades","P3_conc","P4_dd"]].to_string(index=False))
