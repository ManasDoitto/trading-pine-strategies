import sys
sys.path.insert(0, r"D:\Trading code-Claude")
sys.path.insert(0, r"D:\Trading code-Claude\strategy_audit_2026_09")
import pandas as pd, research_sim as rs
from trading_agents.core import signals as v40
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()
T0 = pd.Timestamp("2024-03-25")
RUNS = (("CRUDEOIL", "MCX:CRUDEOIL1!", "MCX_CRUDEOIL1"),
        ("BANKNIFTY", "NSE:BANKNIFTY1!", "NSE_BANKNIFTY1"))

def gated(f, p, use_adx):
    cap = p["max_sl"] * f["atr"]
    vol = f["vol_regime_ok"] if p.get("use_vol_filter") else True
    base = f["in_sess"] & f["sha_stable"] & f["atr_ok"] & vol & ~f["in_flat_window"]
    if use_adx:
        base = base & f["adx_ok"]
    tl = (f["e9"] > f["e22"]) & (f["close"] > f["e200"])
    ts = (f["e9"] < f["e22"]) & (f["close"] < f["e200"])
    g = f.copy()
    g["ok_l"] = base & f["flip_up"] & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    g["ok_s"] = base & f["flip_dn"] & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~g["ok_l"]
    return g

def split(tr):
    t = pd.DataFrame(tr).sort_values("exit_time").reset_index(drop=True)
    n = len(t); a, b = int(n*.6), int(n*.8)
    return {k: rs.stats(v.to_dict("records")) for k, v in
            (("FULL", t), ("TRAIN", t[:a]), ("VALID", t[a:b]), ("HOLDOUT", t[b:]))}, t

def gates(S):
    F = S["FULL"]
    g = dict(pf3=all(S[k].get("pf",0) >= 1.30 for k in ("TRAIN","VALID","HOLDOUT")),
             n100=F["n"] >= 100, m70=F["pos_months_pct"] >= 70,
             c25=(F["best_month_share"] is not None and F["best_month_share"] <= 25))
    return [k for k, v in g.items() if not v]

def line(tag, S):
    F = S["FULL"]
    print(f"{tag:24s} n={F['n']:4d} PF={F['pf']:6.3f} net={F['net']:+10.1f} maxDD={F['max_dd']:9.1f} "
          f"win={F['win_pct']:4.1f}% posM={F['pos_months_pct']:4.1f}% bestM={str(F['best_month_share']):>6} "
          f"hold={F['avg_hold_h']:5}h | TR {S['TRAIN']['pf']:.3f} VA {S['VALID']['pf']:.3f} HO {S['HOLDOUT']['pf']:.3f}"
          f" | fails={gates(S)}")

for key, disp, bars in RUNS:
    p = dict(v50.V50_INSTRUMENT_PARAMS[key])
    p["atr_min_pts"] = cfg["strategy"].get(key, {}).get("atr_min_pts", 0)
    df = rs.load(bars)
    f = v50.v50_frame(df, p)
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    print(f"\n===== {disp}  30 months, gross points (no costs) =====")
    print(f"params: minSL={p['min_sl']} maxSL={p['max_sl']} rr={p['rr']} adx>={p['adx_min']} pb={p['pb_atr_mult']} "
          f"dayLimit={p['day_loss_limit']} atrMin={p['atr_min_pts']} volFilter={p['use_vol_filter']} "
          f"sess={p['session']} flat={p['force_flat_window']}")
    keep = {}
    for use_adx in (True, False):
        tr = rs.simulate(gated(f, p, use_adx), dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                         start=s0, flat_at=p["force_flat_window"][0], commission=0.0)
        if not tr:
            print(("ADX on " if use_adx else "ADX off") + "  NO TRADES"); continue
        S, t = split(tr); keep[use_adx] = (S, t)
        line("ADX>=%g (shipped)" % p["adx_min"] if use_adx else "ADX gate OFF", S)
    # net-of-cost reference for the shipped config
    trn = rs.simulate(gated(f, p, True), dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                      start=s0, flat_at=p["force_flat_window"][0], commission=0.0002)
    if trn:
        line("  shipped, net of cost", split(trn)[0])
    q = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=p["min_sl"],
             max_sl=p["max_sl"], rr=p["rr"], session=p["session"])
    line("  ancestor v4.0 (gross)", split(rs.simulate(v40.v40_frame(df, q), q, start=s0, commission=0.0))[0])
    if True in keep:
        t = keep[True][1]
        m = t.groupby(pd.to_datetime(t.exit_time).dt.to_period("M")).net.sum().sort_values()
        print(f"  months={len(m)} positive={(m>0).sum()} | worst {m.index[0]} {m.iloc[0]:+.1f}, {m.index[1]} {m.iloc[1]:+.1f}"
              f" | best {m.index[-1]} {m.iloc[-1]:+.1f}, {m.index[-2]} {m.iloc[-2]:+.1f}")
        print(f"  exits: {pd.Series([x['result'] for x in keep[True][1].to_dict('records')]).value_counts().to_dict()}")
