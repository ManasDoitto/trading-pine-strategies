"""Round 8: raise crude v4.2's win rate while holding net points and drawdown close to reference.
Pre-registration: pre_registration_crude_round8_2026_09_27.md"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_round7 as R7
import crude_50cfg as C
import research_sim as rs
import silver_sweep as SS

def sim(v, comm=0.0):
    """v4.2 base (SHA flip + EMA9/22, no fixed target, reversal exit), 09:15, plus round-8 knobs."""
    d = R7.base()
    tmin = d["tmin"]
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in ("09:15", "23:30")]
    in_sess = (tmin >= s0m) & (tmin < s1m)
    atr = d["atr"]; c = d["close"]
    min_sl, max_sl = v.get("min_sl", 1.5), v.get("max_sl", 3.0)
    cap = max_sl * atr
    L = d["e9"] > d["e22"]; S = d["e9"] < d["e22"]
    if "flip_up" not in d.columns:
        _, fu, fd, _ = SS.sha(d, 10, 10, 0)
        d["flip_up"], d["flip_dn"] = fu, fd
    flipL, flipS = d["flip_up"], d["flip_dn"]
    ml = flipL & L; ms = flipS & S
    swlo, swhi = SS.swings(d, 10)
    risk_l = (c - (swlo - 0.1 * atr)).clip(lower=min_sl * atr)
    risk_s = ((swhi + 0.1 * atr) - c).clip(lower=min_sl * atr)
    g = d.copy()
    g["ok_l"] = in_sess & ml.fillna(False) & (risk_l <= cap)
    g["ok_s"] = in_sess & ms.fillna(False) & (risk_s <= cap) & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=1000.0, day_loss_limit_pts=0.0)
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    kw = dict(reversal_exit=True, be_at_r=v.get("be"), trail_start_r=v.get("trail_r"), trail_dist_r=v.get("trail_d", 1.0),
              scale_r=v.get("scale_r"), scale_frac=v.get("scale_frac", 0.5), min_hold_bars_rev=v.get("min_hold", 0))
    return rs.simulate(g, p, start=s0, commission=comm, **kw)

def summ(tag, v):
    tr = sim(v)
    if len(tr) < 20:
        return dict(id=tag, n=len(tr))
    s = rs.stats(tr)
    return dict(id=tag, n=s["n"], pf=s["pf"], net=round(s["net"]), win=s["win_pct"], dd=round(s["max_dd"]),
                best_mo=s["best_month_share"], hold_h=s["avg_hold_h"])

def cfgs():
    out = [("CTRL (v4.2 as confirmed)", {})]
    for be in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        out.append((f"A be={be}R", dict(be=be)))
    for tr_, td in ((1.5, 1.0), (2.0, 1.0), (2.0, 1.5), (2.5, 1.5), (3.0, 2.0), (1.5, 0.5)):
        out.append((f"B be1.0R+trail({tr_},{td})", dict(be=1.0, trail_r=tr_, trail_d=td)))
    for sr in (1.0, 1.5, 2.0, 2.5, 3.0):
        for sf in (0.33, 0.5, 0.67):
            out.append((f"C scale_r={sr} frac={sf}", dict(scale_r=sr, scale_frac=sf)))
    for mn, mx in ((1.0, 3.0), (1.25, 3.0), (1.75, 3.0), (2.0, 3.0), (1.5, 2.5), (1.5, 3.5)):
        out.append((f"D minSL={mn} maxSL={mx}", dict(min_sl=mn, max_sl=mx)))
    for mh in (3, 6, 12, 24):
        out.append((f"E min_hold_rev={mh}", dict(min_hold=mh)))
    for tr_, td in ((1.0, 1.0), (1.5, 1.5), (2.0, 2.0), (1.0, 0.5), (1.5, 1.0), (2.5, 2.0)):
        out.append((f"F trail-only({tr_},{td})", dict(trail_r=tr_, trail_d=td)))
    out += [
        ("G be1.0+scale(2.0,0.5)", dict(be=1.0, scale_r=2.0, scale_frac=0.5)),
        ("G be1.0+scale(1.5,0.5)", dict(be=1.0, scale_r=1.5, scale_frac=0.5)),
        ("G scale(1.5,0.5)+trail(2.5,1.5)", dict(scale_r=1.5, scale_frac=0.5, trail_r=2.5, trail_d=1.5)),
        ("G be0.75+minSL1.75", dict(be=0.75, min_sl=1.75)),
        ("G scale(2.0,0.33)+trail(2.0,1.0)", dict(scale_r=2.0, scale_frac=0.33, trail_r=2.0, trail_d=1.0)),
        ("G scale_r=1.0 frac=0.25", dict(scale_r=1.0, scale_frac=0.25)),
        ("G scale_r=3.5 frac=0.5", dict(scale_r=3.5, scale_frac=0.5)),
    ]
    return out

if __name__ == "__main__":
    rows = [summ(t, v) for t, v in cfgs()]
    R = pd.DataFrame(rows)
    R.to_csv(C.ROOT / "research_data" / "crude_round8.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
