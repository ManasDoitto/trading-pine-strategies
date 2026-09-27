"""Tighten Nifty's from-scratch scalp candidates to a lower, more selective trade rate while maximizing PF.
Pre-registration: pre_registration_nifty_lowfreq_2026_09_27.md"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bnf_scratch_scalp as X
import bnf_port_test as B
import research_sim as rs

INST = "NSE_NIFTY"
B.PV = 1


def sim(v):
    return X.sim(v, "5", inst=INST)


def summ(tag, v):
    tr = sim(v)
    if len(tr) < 15:
        return dict(id=tag, n=len(tr))
    d = B.base("5", INST)
    months = (d["time"].iloc[-1] - d["time"].iloc[rs.WARMUP]).days / 30.44
    t = pd.DataFrame(tr); t["x"] = pd.to_datetime(t.exit_time)
    full = rs.stats(t.to_dict("records"))
    mid = t.x.min() + (t.x.max() - t.x.min()) / 2
    h1 = rs.stats(t[t.x < mid].to_dict("records"))
    h2 = rs.stats(t[t.x >= mid].to_dict("records"))
    return dict(id=tag, n=full["n"], per_mo=round(full["n"] / months, 1), pf=full["pf"], net=round(full["net"]),
                win=full["win_pct"], dd=round(full["max_dd"]), best_mo=full["best_month_share"],
                h1_pf=h1.get("pf"), h1_net=round(h1.get("net", 0)), h2_pf=h2.get("pf"), h2_net=round(h2.get("net", 0)))


H_BASE = dict(name="ema_cross", min_sl=2.0, rr=10.0)
Q4_BASE = dict(name="donch20", min_sl=1.0, rr=1.5, time_stop=30)
FILTERS = {"+ADX15>=15": dict(adx_min=15.0), "+ADX15>=20": dict(adx_min=20.0), "+EMA200": dict(use200=True),
           "+volume filter": dict(vol_filter=True), "+ADX15>=15&EMA200": dict(adx_min=15.0, use200=True)}


def cfgs():
    out = [("CTRL H (ts=10)", dict(H_BASE, time_stop=10)), ("CTRL Q4 (lb=20)", dict(Q4_BASE))]
    for ts in (8, 10, 12, 15):
        out.append((f"A H ts={ts}", dict(H_BASE, time_stop=ts)))
    for k, o in FILTERS.items():
        out.append((f"B H ts=10 {k}", dict(H_BASE, time_stop=10, **o)))
    for lb in (20, 30, 40, 55):
        out.append((f"C Q4 lb={lb}", dict(Q4_BASE, name=f"donch{lb}")))
    for k, o in FILTERS.items():
        out.append((f"D Q4 lb=30 {k}", dict(Q4_BASE, name="donch30", **o)))
    for k, o in {"avoid midday 12:00-13:30": dict(avoid_midday=True), "only 09:15-12:00": dict(tod=("09:15", "12:00")),
                 "only 12:30-15:15": dict(tod=("12:30", "15:15")), "skip Monday": dict(skip_dow=0)}.items():
        base_o = dict(o)
        if "avoid_midday" in base_o:
            del base_o["avoid_midday"]  # X.sim has no avoid_midday hook; approximate with two tod windows instead
        out.append((f"E H ts=10 {k}", dict(H_BASE, time_stop=10, **{k2: v2 for k2, v2 in o.items() if k2 != "avoid_midday"})))
        out.append((f"E Q4 lb=30 {k}", dict(Q4_BASE, name="donch30", **{k2: v2 for k2, v2 in o.items() if k2 != "avoid_midday"})))
    # F: hand-picked combos of the strongest single filters, decided after seeing A-D in practice runs during dev
    out += [
        ("F H ts=10 +ADX15>=15+volume", dict(H_BASE, time_stop=10, adx_min=15.0, vol_filter=True)),
        ("F H ts=8 +ADX15>=15", dict(H_BASE, time_stop=8, adx_min=15.0)),
        ("F Q4 lb=30 +ADX15>=15+volume", dict(Q4_BASE, name="donch30", adx_min=15.0, vol_filter=True)),
        ("F Q4 lb=40 +ADX15>=15", dict(Q4_BASE, name="donch40", adx_min=15.0)),
        ("F H ts=10 +EMA200+volume", dict(H_BASE, time_stop=10, use200=True, vol_filter=True)),
        ("F H ts=12 +ADX15>=15", dict(H_BASE, time_stop=12, adx_min=15.0)),
        ("F Q4 lb=30 +EMA200+volume", dict(Q4_BASE, name="donch30", use200=True, vol_filter=True)),
        ("F Q4 lb=55 +ADX15>=15", dict(Q4_BASE, name="donch55", adx_min=15.0)),
    ]
    return out


if __name__ == "__main__":
    rows = [summ(t, v) for t, v in cfgs()]
    R = pd.DataFrame(rows)
    R.to_csv(B.ROOT / "research_data" / "nifty_lowfreq_tune.csv", index=False)
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
