"""Fresh BankNifty search on Dhan's real 5.1-year history (Aug 2021 - Sep 2026, 97,422 5m bars).
Same discipline as nifty_dhan_fresh.py: price-action only (Dhan's index volume field is 91% zero/broken --
confirmed on both instruments), requires positive performance in a clear majority of individual calendar years,
not just a train/holdout split, before trusting anything. The live BankNifty pick (Supertrend+volume filter) can't
be fairly re-tested here since its edge depends on real futures volume that Dhan's index feed doesn't have.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bnf_port_test as B
import bnf_scratch_scalp as X
import bnf_new_families as N
import research_sim as rs

INST = "DHAN_BANKNIFTY"
B.PV = 30
SPLIT = pd.Timestamp("2024-06-01")  # ~2.8yr train, ~2.3yr holdout (5.1yr total)

EXCLUDE = {"M3 VWAP extension fade", "Q8 VWAP-cross continuation"}
EXCLUDE2 = {"vwap_reclaim"}

SESSION = X.SESSION
FLAT = X.FLAT


def sim_old_family(name, v):
    d = X.extra(B.base("5", INST))
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))
    L, S, risk_l, risk_s = X.build(d, name, v.get("min_sl", 1.0), v.get("max_sl"))
    if v.get("adx_min"):
        gate = d["adx15_prev"] >= v["adx_min"]; L, S = L & gate, S & gate
    if v.get("use200"):
        L, S = L & (d["close"] > d["e200"]), S & (d["close"] < d["e200"])
    g = d.copy()
    g["ok_l"] = in_sess & L; g["ok_s"] = in_sess & S & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=v.get("rr", 1.5), day_loss_limit_pts=0.0)
    return rs.simulate(g, p, start=rs.WARMUP, commission=0.0, time_stop_min=v.get("time_stop", 30), flat_at=FLAT[0])


def sim_new_family(name, v):
    d = N.extra2(B.base("5", INST))
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))
    L, S, risk_l, risk_s = N.build2(d, name)
    if v.get("adx_min"):
        gate = d["adx15_prev"] >= v["adx_min"]; L, S = L & gate, S & gate
    if v.get("use200"):
        L, S = L & (d["close"] > d["e200"]), S & (d["close"] < d["e200"])
    g = d.copy()
    g["ok_l"] = in_sess & L; g["ok_s"] = in_sess & S & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=v.get("rr", 1.5), day_loss_limit_pts=0.0)
    return rs.simulate(g, p, start=rs.WARMUP, commission=0.0, time_stop_min=v.get("time_stop", 30), flat_at=FLAT[0])


def summ(tag, tr):
    if len(tr) < 30:
        return dict(id=tag, n=len(tr))
    t = pd.DataFrame(tr); t["x"] = pd.to_datetime(t.exit_time)
    full = rs.stats(t.to_dict("records"))
    mo = (t.x.max() - t.x.min()).days / 30.44
    tr_s = rs.stats(t[t.x < SPLIT].to_dict("records"))
    ho_s = rs.stats(t[t.x >= SPLIT].to_dict("records"))
    years = t.x.dt.year
    pos_years = sum(1 for yr in years.unique() if rs.stats(t[years == yr].to_dict("records")).get("net", 0) > 0)
    n_years = years.nunique()
    return dict(id=tag, n=full["n"], per_mo=round(full["n"] / mo, 1), pf=full["pf"], net=round(full["net"]),
                win=full["win_pct"], dd=round(full["max_dd"]), tr_pf=tr_s.get("pf"), tr_net=round(tr_s.get("net", 0)),
                ho_pf=ho_s.get("pf"), ho_net=round(ho_s.get("net", 0)), pos_years=f"{pos_years}/{n_years}")


if __name__ == "__main__":
    rows = []
    names_old = [k for k in X.CONFIGS if k not in EXCLUDE]
    for i, tag in enumerate(names_old):
        v = X.CONFIGS[tag]
        tr = sim_old_family(v["name"], v)
        rows.append(summ(tag, tr))
        if (i + 1) % 8 == 0:
            print(f"old {i + 1}/{len(names_old)}", flush=True)
    names_new = [n for n in N.NAMES if n not in EXCLUDE2]
    for i, name in enumerate(names_new):
        tr = sim_new_family(name, dict(rr=1.5, time_stop=30))
        rows.append(summ(f"NEW {name}", tr))
        if (i + 1) % 8 == 0:
            print(f"new {i + 1}/{len(names_new)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(B.ROOT / "research_data" / "bnf_dhan_fresh.csv", index=False)
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
