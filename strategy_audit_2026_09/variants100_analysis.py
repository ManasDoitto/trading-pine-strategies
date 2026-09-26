"""Analysis of the 100-variant searches. Pre-registration: pre_registration_100variants_2026_09_26.md"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import variants100 as V

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 40)
COLS = ["id", "entry", "lb", "rr", "min_sl", "max_sl", "trend", "pb", "adx", "sess", "flat", "day",
        "full_n", "full_pf", "tr_net", "ho_net", "tr_cost_net", "ho_cost_net", "ho_pf", "ho_conc"]


def spearman(a, b):
    return float(np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1])


def bnf_v04_split():
    from trading_agents.core import signals_v04 as v04
    from trading_agents.core.config import load_config
    cfg = load_config()["strategy"]["BANKNIFTY"]
    bars = rs.load("NSE_BANKNIFTY1")
    f = v04.v04_frame(bars, cfg)
    s0 = max(int((f["time"] >= V.T0).idxmax()), v04.WARMUP_BARS)
    t = pd.DataFrame(v04.simulate(f, cfg, start=s0)["trades"])
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    t["g"] = (t["exit"] - t["entry"]) * t["side"].map({"LONG": 1, "SHORT": -1, "long": 1, "short": -1})
    t["n"] = t["g"] - 0.0002 * (t["entry"] + t["exit"])
    out = {}
    for tag, sub in (("tr", t[t.exit_time < V.SPLIT]), ("ho", t[t.exit_time >= V.SPLIT])):
        out[tag] = dict(n=len(sub), gross=float(sub.g.sum()), net=float(sub.n.sum()))
    return out


def analyse(inst):
    R = pd.read_csv(ROOT / "research_data" / f"variants100_{inst}.csv")
    ctrl = R[R.id.str.startswith("CTRL")]
    V100 = R[~R.id.str.startswith("CTRL")].copy()
    print(f"\n{'=' * 40} {inst}: {len(V100)} variants + {len(ctrl)} controls {'=' * 40}")
    print("controls:")
    print(ctrl[COLS].to_string(index=False))

    # ---- transfer measurement, all variants ----
    rho = spearman(V100.tr_net, V100.ho_net)
    print(f"\nTRANSFER: Spearman(TRAIN net, HOLDOUT net) across all {len(V100)} = {rho:+.3f}")
    print(f"  median TRAIN net {V100.tr_net.median():+,.0f} | median HOLDOUT net {V100.ho_net.median():+,.0f} | "
          f"variants profitable after costs on HOLDOUT: {(V100.ho_cost_net > 0).sum()} of {len(V100)}, on TRAIN: {(V100.tr_cost_net > 0).sum()}")

    # ---- selection ----
    elig = V100[(V100.full_n >= 100) & (V100.tr_cost_net > 0)].sort_values("tr_net", ascending=False)
    print(f"\neligible (>=100 trades and positive after costs on TRAIN): {len(elig)} of {len(V100)}")
    if elig.empty:
        print("  NO ELIGIBLE VARIANT - nothing passes even the selection filter")
        return R, None
    print("top 10 by TRAIN net (holdout shown for information; the pick is #1 only):")
    print(elig.head(10)[COLS].to_string(index=False))
    pick = elig.iloc[0]

    # ---- incumbent and gates ----
    if inst == "CRUDE":
        inc = R[R.id == "CTRL crude#1"].iloc[0]
        inc_tr, inc_ho, inc_ho_cost = inc.tr_net, inc.ho_net, inc.ho_cost_net
        label = "crude #1"
    else:
        v04 = bnf_v04_split()
        inc_tr, inc_ho, inc_ho_cost = v04["tr"]["gross"], v04["ho"]["gross"], v04["ho"]["net"]
        label = "BankNifty v0.4"
        print(f"\nBankNifty v0.4 same split: TRAIN gross {v04['tr']['gross']:+,.0f} ({v04['tr']['n']} tr) | "
              f"HOLDOUT gross {v04['ho']['gross']:+,.0f} ({v04['ho']['n']} tr), after costs {v04['ho']['net']:+,.0f}")
    print(f"\nPICK = {pick.id}: {dict((k, pick[k]) for k in ['entry','lb','rr','min_sl','max_sl','trend','pb','adx','sess','flat','day'])}")
    print(f"  TRAIN {pick.tr_net:+,.0f} (after costs {pick.tr_cost_net:+,.0f}) -> HOLDOUT {pick.ho_net:+,.0f} "
          f"(after costs {pick.ho_cost_net:+,.0f}), HOLDOUT PF {pick.ho_pf:.3f}, holdout best month {pick.ho_conc}%")
    print(f"  {label} on the same split: TRAIN {inc_tr:+,.0f} -> HOLDOUT {inc_ho:+,.0f} (after costs {inc_ho_cost:+,.0f})")
    gates = {"1 positive after costs on HOLDOUT": pick.ho_cost_net > 0,
             f"2 beats {label} on HOLDOUT net points": pick.ho_net > inc_ho,
             "3 HOLDOUT gross PF >= 1.15": pick.ho_pf >= 1.15,
             "4 >= 100 trades total": pick.full_n >= 100,
             "5 best HOLDOUT month <= 40%": (pick.ho_conc is not None and not pd.isna(pick.ho_conc) and pick.ho_conc <= 40)}
    for k, ok in gates.items():
        print(f"  gate {k}: {'PASS' if ok else 'fail'}")
    # would ANY variant beat the incumbent in holdout after being selected honestly?
    beat = V100[V100.ho_net > inc_ho]
    print(f"\n  variants (any) that beat {label} on HOLDOUT gross: {len(beat)} of {len(V100)}; "
          f"of those, TRAIN rank among all 100: {sorted(V100.tr_net.rank(ascending=False)[beat.index].astype(int).tolist())[:12]}")
    return R, pick


if __name__ == "__main__":
    for inst in sys.argv[1:] or ["CRUDE", "BANKNIFTY"]:
        analyse(inst)
