"""Tune BankNifty's Supertrend flip scalp for higher PF.
Pre-registration: pre_registration_bnf_supertrend_tune_2026_09_27.md"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS
import bnf_port_test as B
import bnf_scratch_scalp as X

SESSION = ("09:15", "15:20")
FLAT = ["15:20", "15:30"]
SPLIT = pd.Timestamp("2025-06-25")
_ST_CACHE = {}


def supertrend(d, period, mult):
    key = (id(d), period, mult)
    if key in _ST_CACHE:
        return _ST_CACHE[key]
    h, l, c = d["high"], d["low"], d["close"]
    atrP = SS.wilder(SS.true_range(h, l, c), period)
    hl2 = (h + l) / 2
    up_b, dn_b = hl2 + mult * atrP, hl2 - mult * atrP
    st_dir = np.ones(len(d))
    fub, flb = up_b.to_numpy().copy(), dn_b.to_numpy().copy()
    cc = c.to_numpy()
    for i in range(1, len(d)):
        if cc[i - 1] <= fub[i - 1]:
            fub[i] = min(up_b.iat[i], fub[i - 1])
        if cc[i - 1] >= flb[i - 1]:
            flb[i] = max(dn_b.iat[i], flb[i - 1])
        st_dir[i] = -1 if (st_dir[i - 1] == 1 and cc[i] < flb[i - 1]) else (1 if (st_dir[i - 1] == -1 and cc[i] > fub[i - 1]) else st_dir[i - 1])
    st = pd.Series(st_dir, index=d.index)
    L = (st == 1) & (st.shift(1) == -1)
    S = (st == -1) & (st.shift(1) == 1)
    _ST_CACHE[key] = (L, S)
    return L, S


def sim(v, tf="5", comm=0.0):
    d = B.base(tf)
    d = X.extra(d)  # adds rsi/bb/etc (harmless, cached) -- we mainly need atr/e9/e22/e200/adx15_prev already in base()
    atr = d["atr"]
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))
    if v.get("tod"):
        t0, t1 = [int(x[:2]) * 60 + int(x[3:]) for x in v["tod"]]
        in_sess = in_sess & (d["tmin"] >= t0) & (d["tmin"] < t1)
    if v.get("avoid_midday"):
        m0, m1 = 12 * 60, 13 * 60 + 30
        in_sess = in_sess & ~((d["tmin"] >= m0) & (d["tmin"] < m1))
    if v.get("skip_dow") is not None:
        in_sess = in_sess & (d["time"].dt.dayofweek != v["skip_dow"])

    L, S = supertrend(d, v.get("st_period", 10), v.get("st_mult", 3))
    if v.get("use200"):
        L = L & (d["close"] > d["e200"])
        S = S & (d["close"] < d["e200"])
    if v.get("adx_min"):
        gate = d["adx15_prev"] >= v["adx_min"]
        L, S = L & gate, S & gate
    if v.get("vol_filter"):
        vf = d["volume"] > d["volume"].rolling(20).mean()
        L, S = L & vf, S & vf
    if v.get("consolidation"):
        squeeze = atr < atr.shift(10)
        L, S = L & squeeze, S & squeeze

    swlo, swhi = SS.swings(d, 10)
    min_sl = v.get("min_sl", 1.0)
    c = d["close"]
    if v.get("close_swing"):
        swlo_c, swhi_c = c.rolling(10).min(), c.rolling(10).max()
        risk_l = (c - (swlo_c - 0.1 * atr)).clip(lower=min_sl * atr)
        risk_s = ((swhi_c + 0.1 * atr) - c).clip(lower=min_sl * atr)
    else:
        risk_l = (c - (swlo - 0.1 * atr)).clip(lower=min_sl * atr)
        risk_s = ((swhi + 0.1 * atr) - c).clip(lower=min_sl * atr)

    g = d.copy()
    g["ok_l"] = in_sess & L.fillna(False)
    g["ok_s"] = in_sess & S.fillna(False) & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=v.get("rr", 1.5), day_loss_limit_pts=0.0)
    kw = dict(time_stop_min=v.get("time_stop", 45), flat_at=FLAT[0], cooldown_bars=v.get("cooldown"),
              be_at_r=v.get("be"))
    return rs.simulate(g, p, start=rs.WARMUP, commission=comm, **kw)


def summ(tag, v):
    tr = sim(v)
    if len(tr) < 20:
        return dict(id=tag, n=len(tr))
    t = pd.DataFrame(tr); t["x"] = pd.to_datetime(t.exit_time)
    full = rs.stats(t.to_dict("records"))
    tr_s = rs.stats(t[t.x < SPLIT].to_dict("records"))
    ho_s = rs.stats(t[t.x >= SPLIT].to_dict("records"))
    d = B.base("5")
    months = (d["time"].iloc[-1] - d["time"].iloc[rs.WARMUP]).days / 30.44
    return dict(id=tag, n=full["n"], per_mo=round(full["n"] / months, 1), pf=full["pf"], net=round(full["net"]),
                win=full["win_pct"], dd=round(full["max_dd"]), best_mo=full["best_month_share"],
                tr_pf=tr_s.get("pf"), tr_net=round(tr_s.get("net", 0)), ho_pf=ho_s.get("pf"), ho_net=round(ho_s.get("net", 0)))


def cfgs():
    out = [("CTRL (current best)", {})]
    for per, mult in ((7, 2), (7, 3), (10, 2), (10, 4), (14, 2), (14, 3), (20, 3)):
        out.append((f"A st({per},{mult})", dict(st_period=per, st_mult=mult)))
    for k, o in {"+EMA200": dict(use200=True), "+ADX15>=15": dict(adx_min=15.0), "+ADX15>=20": dict(adx_min=20.0),
                 "+volume filter": dict(vol_filter=True), "+ADX15>=15 & EMA200": dict(adx_min=15.0, use200=True)}.items():
        out.append((f"B {k}", o))
    for rr in (1.0, 1.25, 2.0, 2.5):
        out.append((f"C rr={rr}", dict(rr=rr)))
    for ts in (30, 60, 75, 90):
        out.append((f"C time_stop={ts}", dict(time_stop=ts)))
    for sl in (0.5, 0.75, 1.5, 2.0):
        out.append((f"D min_sl={sl}", dict(min_sl=sl)))
    out.append(("D close-based swing stop", dict(close_swing=True)))
    for k, o in {"skip Monday": dict(skip_dow=0), "skip Friday": dict(skip_dow=4),
                 "avoid midday 12:00-13:30": dict(avoid_midday=True), "only 09:15-12:00": dict(tod=("09:15", "12:00")),
                 "only 12:30-15:15": dict(tod=("12:30", "15:15"))}.items():
        out.append((f"E {k}", o))
    out.append(("F be=0.75R", dict(be=0.75)))
    out.append(("F be=1.0R", dict(be=1.0)))
    out.append(("F cooldown6", dict(cooldown=6)))
    out.append(("F cooldown12", dict(cooldown=12)))
    out.append(("F consolidation-before-flip", dict(consolidation=True)))
    # G: hand-picked combos, decided after seeing A-F single-knob leaders (st(14,2) and ADX15>=15 and time_stop=60 looked promising in dev)
    out += [
        ("G st(14,2)+ADX15>=15", dict(st_period=14, st_mult=2, adx_min=15.0)),
        ("G st(14,2)+time_stop=60", dict(st_period=14, st_mult=2, time_stop=60)),
        ("G ADX15>=15+time_stop=60", dict(adx_min=15.0, time_stop=60)),
        ("G st(14,2)+ADX15>=15+time_stop=60", dict(st_period=14, st_mult=2, adx_min=15.0, time_stop=60)),
        ("G avoid_midday+ADX15>=15", dict(avoid_midday=True, adx_min=15.0)),
    ]
    return out


if __name__ == "__main__":
    rows = [summ(t, v) for t, v in cfgs()]
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "bnf_supertrend_tune.csv", index=False)
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
