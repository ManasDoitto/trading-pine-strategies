"""Port the top 15 crude + top 15 silver configurations tested this project onto BankNifty futures (NSE:BANKNIFTY1!),
3m and 5m, and see whether any beats the current BankNifty best (v0.4 EMA pullback, PF 1.33, +1,403 pts, 2.5 tr/mo).

Data: research_data/bars/NSE_BANKNIFTY1_5m.csv (3 years, Sep 2023-Sep 2026) and NSE_BANKNIFTY1_3m.csv (~3.9mo,
Jun-Sep 2026 -- TradingView's own floor for 3m intraday history on this feed, confirmed by paging to "no older data").
Session capped to the real market hours 09:15-15:30, force-flat 15:20-15:30. day_loss_limit is deliberately OFF on every
ported config: it is a nominal-point circuit breaker calibrated to each commodity's own price scale (silver's 350 has no
meaning on BankNifty's index-point scale) and would need its own recalibration, not a blind port.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS
from trading_agents.core import signals_v50 as v50
from trading_agents.core.levels import true_range, wilder

BARS = ROOT / "research_data" / "bars"
PV = 30  # NSE:BANKNIFTY1! point value, 1 lot
SESSION = ("09:15", "15:20")
FLAT = ["15:20", "15:30"]
_D = {}


def load_tf(name, tf):
    df = pd.read_csv(BARS / f"{name}_{tf}m.csv")
    df["time"] = pd.to_datetime(df["time"], unit="s") + pd.Timedelta(hours=5, minutes=30)
    return df[["time", "open", "high", "low", "close", "volume"]]


def base(tf):
    if tf not in _D:
        df = load_tf("NSE_BANKNIFTY1", tf)
        d = df.reset_index(drop=True).copy()
        d["e9"] = v50.ema(d["close"], 9)
        d["e22"] = v50.ema(d["close"], 22)
        d["e200"] = v50.ema(d["close"], 200)
        d["atr"] = wilder(true_range(d["high"], d["low"], d["close"]), 14)
        d["adx15_prev"] = v50.adx_15m_prev(df.reset_index(drop=True))
        r500 = d["atr"].rolling(500)
        d["atr_p90"] = r500.quantile(0.9)
        d["tmin"] = d["time"].dt.hour * 60 + d["time"].dt.minute
        _D[tf] = d
    return _D[tf]


def sim(v, tf, comm=0.0):
    d = base(tf)
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))

    _, fu, fd, stable = SS.sha(d, v.get("sha_len1", 10), v.get("sha_len2", 10), v.get("sha_min_hold", 0))
    e9, e22, e200 = d["e9"], d["e22"], d["e200"]
    trendL = (e9 > e22) if not v.get("use200") else ((e9 > e22) & (c > e200))
    trendS = (e9 < e22) if not v.get("use200") else ((e9 < e22) & (c < e200))

    flipL, flipS = fu & stable, fd & stable
    if v.get("entry") == "flip+bo":
        lb = v.get("bo_lookback", 5)
        boL = c > h.rolling(lb).max().shift(1)
        boS = c < l.rolling(lb).min().shift(1)
        L, S = flipL | boL, flipS | boS
    else:
        L, S = flipL, flipS

    if v.get("adx_min"):
        gate_adx = d["adx15_prev"] >= v["adx_min"]
        L, S = L & gate_adx, S & gate_adx
    if v.get("atr_lt_p90"):
        gate_v = atr < d["atr_p90"]
        L, S = L & gate_v, S & gate_v

    sw_len = v.get("sw_len", 10)
    swlo, swhi = SS.swings(d, sw_len)
    swbuf = v.get("sw_buf", 0.1)
    min_sl, max_sl = v.get("min_sl", 1.5), v.get("max_sl", 3.0)
    risk_l = (c - (swlo - swbuf * atr)).clip(lower=min_sl * atr)
    risk_s = ((swhi + swbuf * atr) - c).clip(lower=min_sl * atr)
    cap = max_sl * atr

    g = d.copy()
    ml, ms = L.fillna(False), S.fillna(False)
    if v.get("dir") == "long":
        ms = ms & False
    if v.get("dir") == "short":
        ml = ml & False
    g["ok_l"] = in_sess & ml & (risk_l <= cap)
    g["ok_s"] = in_sess & ms & (risk_s <= cap) & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s

    p = dict(rr=v.get("rr", 4.0), day_loss_limit_pts=0.0)
    if v.get("rr_l") is not None:
        p["rr_l"], p["rr_s"] = v["rr_l"], v["rr_s"]
    if v.get("no_target"):
        p["rr"] = 1000.0
    kw = dict(reversal_exit=bool(v.get("reversal")), cooldown_bars=v.get("cooldown"),
              trail_start_r=v.get("trail_r"), trail_dist_r=v.get("trail_d", 1.0),
              be_at_r=v.get("be"), min_hold_bars_rev=v.get("min_hold_rev", 0), flat_at=FLAT[0])
    s0 = rs.WARMUP
    return rs.simulate(g, p, start=s0, commission=comm, **kw)


def summ(tag, v, tf):
    tr = sim(v, tf)
    d = base(tf)
    months = (d["time"].iloc[-1] - d["time"].iloc[rs.WARMUP]).days / 30.44
    if len(tr) < 10:
        return dict(id=tag, tf=tf, n=len(tr), months=round(months, 1))
    s = rs.stats(tr)
    return dict(id=tag, tf=tf, n=s["n"], per_mo=round(s["n"] / months, 1), pf=s["pf"], net=round(s["net"]),
                win=s["win_pct"], dd=round(s["max_dd"]), best_mo=s["best_month_share"], months=round(months, 1))


CRUDE_FAMILY = {
    "C1 crude#1 baseline": dict(entry="flip"),
    "C2 crude v4.2 (reversal, no target)": dict(entry="flip", no_target=True, reversal=True),
    "C3 v4.2 + cooldown6": dict(entry="flip", no_target=True, reversal=True, cooldown=6),
    "C4 v4.2b (trail 2.5R/2.0R win-rate)": dict(entry="flip", no_target=True, reversal=True, trail_r=2.5, trail_d=2.0),
    "C5 crude RR3.5": dict(entry="flip", rr=3.5),
    "C6 crude RR4.5": dict(entry="flip", rr=4.5),
    "C7 crude minSL2.0": dict(entry="flip", min_sl=2.0),
    "C8 crude maxSL2.75": dict(entry="flip", max_sl=2.75),
    "C9 crude EMA9/34-style wide trend (use200)": dict(entry="flip", use200=True),
    "C10 crude long RR4/short RR3": dict(entry="flip", rr_l=4.0, rr_s=3.0),
    "C11 crude ATR<p90 filter": dict(entry="flip", atr_lt_p90=True),
    "C12 crude sha_min_hold=2": dict(entry="flip", sha_min_hold=2),
    "C13 crude sw_len=15": dict(entry="flip", sw_len=15),
    "C14 crude v4.2 + min_hold_rev=6": dict(entry="flip", no_target=True, reversal=True, min_hold_rev=6),
    "C15 crude long-only": dict(entry="flip", dir="long"),
}

SILVER_FAMILY = {
    "S1 silver#1 wide-ATR RR3": dict(entry="flip", min_sl=2.5, max_sl=5.0, rr=3.0),
    "S2 silver bo(3)": dict(entry="flip+bo", bo_lookback=3, min_sl=2.5, max_sl=5.0, rr=3.0),
    "S3 silver bo(5)": dict(entry="flip+bo", bo_lookback=5, min_sl=2.5, max_sl=5.0, rr=3.0),
    "S4 silver bo(10)": dict(entry="flip+bo", bo_lookback=10, min_sl=2.5, max_sl=5.0, rr=3.0),
    "S5 silver v5.0 SHA-ADX hybrid": dict(entry="flip", adx_min=20.0, sha_min_hold=3, rr=4.0, min_sl=1.5, max_sl=3.0),
    "S6 silver v5.1 (v5.0+bo5)": dict(entry="flip+bo", bo_lookback=5, adx_min=20.0, sha_min_hold=3, rr=4.0, min_sl=1.5, max_sl=3.0),
    "S7 silver v4.1 fwd-test (bo5, wide-ATR)": dict(entry="flip+bo", bo_lookback=5, min_sl=2.5, max_sl=5.0, rr=3.0),
    "S8 silver wide-ATR RR4": dict(entry="flip", min_sl=2.5, max_sl=5.0, rr=4.0),
    "S9 silver vanilla (narrow ATR)": dict(entry="flip", min_sl=1.5, max_sl=3.0, rr=3.0),
    "S10 silver v5.3-style loose (bo10, RR3)": dict(entry="flip+bo", bo_lookback=10, min_sl=1.0, max_sl=5.0, rr=3.0),
    "S11 silver bo(3) tight stop": dict(entry="flip+bo", bo_lookback=3, min_sl=1.5, max_sl=3.0, rr=3.0),
    "S12 silver short-only wide-ATR": dict(entry="flip", min_sl=2.5, max_sl=5.0, rr=3.0, dir="short"),
    "S13 silver long-only wide-ATR": dict(entry="flip", min_sl=2.5, max_sl=5.0, rr=3.0, dir="long"),
    "S14 silver bo(3) RR4": dict(entry="flip+bo", bo_lookback=3, min_sl=2.5, max_sl=5.0, rr=4.0),
    "S15 silver mid-ATR RR3.5": dict(entry="flip", min_sl=2.0, max_sl=4.0, rr=3.5),
}

ALL = {**CRUDE_FAMILY, **SILVER_FAMILY}

if __name__ == "__main__":
    rows = []
    for tf in ("5", "3"):
        for i, (tag, v) in enumerate(ALL.items()):
            rows.append(summ(tag, v, tf))
            if (i + 1) % 10 == 0:
                print(f"tf={tf}m {i + 1}/{len(ALL)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "bnf_port_test.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
