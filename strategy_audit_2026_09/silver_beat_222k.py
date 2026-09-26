"""Can anything beat silver working_strategies #1 (+222,240.5 pts) on net points?
Focused grid around the incumbent v4.0 wide-ATR + fixed-350 config, on the SAME harness that measured it.
Selection criterion: net points, walk-forward (choose on windows 1..i-1, score on window i)."""
import sys, itertools
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals as v40

T0 = pd.Timestamp("2024-03-25")
WINDOWS = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in (
    ("2024-03-25", "2024-08-25"), ("2024-08-25", "2025-01-25"), ("2025-01-25", "2025-06-25"),
    ("2025-06-25", "2025-11-25"), ("2025-11-25", "2026-04-25"), ("2026-04-25", "2026-09-25"))]
INCUMBENT = dict(min_sl=2.5, max_sl=5.0, rr=3.0, sw_len=10, sw_buf=0.1, day_loss_limit_pts=350)

GRID = dict(min_sl=[1.5, 2.0, 2.5, 3.0], max_sl=[4.0, 5.0, 6.0, 8.0],
            rr=[2.0, 2.5, 3.0, 3.5, 4.0], day_loss_limit_pts=[0, 250, 350, 500, 700],
            sw_len=[5, 10, 15], sw_buf=[0.1])


def run_one(bars_cache, bars, p):
    key = (bars, p["sw_len"], p["sw_buf"])
    if key not in bars_cache:
        q = dict(sha_len1=10, sha_len2=10, sw_len=p["sw_len"], sw_buf=p["sw_buf"],
                 min_sl=1.0, max_sl=99.0, rr=3.0, session=["09:15", "23:30"])
        bars_cache[key] = v40.v40_frame(rs.load(bars), q)
    f = bars_cache[key].copy()
    # re-derive risk caps for this min_sl/max_sl without rebuilding the frame
    atr = f["atr"]
    import numpy as np
    f["risk_l"] = np.maximum(f["close"] - (f["sw_lo"] - p["sw_buf"] * atr), p["min_sl"] * atr)
    f["risk_s"] = np.maximum((f["sw_hi"] + p["sw_buf"] * atr) - f["close"], p["min_sl"] * atr)
    cap = p["max_sl"] * atr
    f["ok_l"] = f["in_sess"] & f["flip_up"] & (f["e9"] > f["e22"]) & (f["risk_l"] <= cap)
    f["ok_s"] = f["in_sess"] & f["flip_dn"] & (f["e9"] < f["e22"]) & (f["risk_s"] <= cap) & ~f["ok_l"]
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(f, dict(rr=p["rr"], day_loss_limit_pts=p["day_loss_limit_pts"]),
                       start=s0, commission=0.0)


def stats_row(p, tr):
    t = pd.DataFrame(tr); t["exit_time"] = pd.to_datetime(t["exit_time"])
    F = rs.stats(tr)
    row = dict(p, n=F["n"], pf=F["pf"], net=F["net"], max_dd=F["max_dd"], win=F["win_pct"],
               pos_m=F["pos_months_pct"], best_m=F["best_month_share"])
    for i, (a, b) in enumerate(WINDOWS, 1):
        w = t[(t.exit_time >= a) & (t.exit_time < b)]
        row[f"w{i}_net"] = float(w.net.sum()) if len(w) else 0.0
        row[f"w{i}_n"] = len(w)
    return row


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    cache, rows = {}, []
    keys = list(GRID)
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    combos = [c for c in combos if c["max_sl"] > c["min_sl"]]
    print(f"{len(combos)} combos", flush=True)
    for i, c in enumerate(combos, 1):
        tr = run_one(cache, "MCX_SILVER1", c)
        if tr:
            rows.append(stats_row(c, tr))
        if i % 50 == 0:
            print(f"  {i}/{len(combos)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "silver_beat_222k.csv", index=False)
    print(f"DONE: {len(R)} rows -> research_data/silver_beat_222k.csv", flush=True)
