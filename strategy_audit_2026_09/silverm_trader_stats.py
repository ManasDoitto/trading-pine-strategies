"""Risk statistics for a SILVERM trader: signal source (SILVER1 as deployed, or SILVERM1's own bars) x strategy (live v4.1, E3, candidate #3).
Production config incl. the 15-17h exclusion. Points, net of 0.02%/side. Trades are measured on the series that generated the signal
(SILVER1 prices vs SILVERM prices differ by a few % basis only, so SILVER1-signal rows are a close proxy for a SILVERM option trade)."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
STRATS = {"live v4.1": dict(earliest=0, rr=3.0, min_sl=2.5, dl=350), "E3 (no entry <12:00)": dict(earliest=12, rr=3.0, min_sl=2.5, dl=350),
          "#3 (RR4, floor 3.0, dl 500)": dict(earliest=0, rr=4.0, min_sl=3.0, dl=500)}
SOURCES = {"SILVER1 signals (as deployed)": "MCX_SILVER1", "SILVERM1 own signals": "MCX_SILVERM1"}


def run(bars, c):
    p = dict(LIVE_P, rr=c["rr"], min_sl=c["min_sl"], day_loss_limit_pts=c["dl"])
    f = rs.v40.v40_frame(bars, p)
    early = (f.time.dt.hour * 60 + f.time.dt.minute) < c["earliest"] * 60
    f["ok_l"] &= ~early
    f["ok_s"] &= ~early
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    return t


def longest_run(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def runs(flags):
    out, cur = [], 0
    for v in flags:
        if v:
            cur += 1
        elif cur:
            out.append(cur); cur = 0
    if cur:
        out.append(cur)
    return out


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def stats(t, first, last):
    months = pd.period_range(first, last, freq="M")
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0.0)
    losing = (mo < 0).to_numpy()
    eq = t.set_index("exit_time").net.cumsum()
    daily = eq.resample("D").last().ffill()
    under = daily < daily.cummax()
    spells, cur_start, longest_days = [], None, 0
    for d, u in under.items():
        if u and cur_start is None:
            cur_start = d
        if not u and cur_start is not None:
            longest_days = max(longest_days, (d - cur_start).days); cur_start = None
    if cur_start is not None:
        longest_days = max(longest_days, (daily.index[-1] - cur_start).days)
    dd = (daily.cummax() - daily).max()
    cur_dd = daily.cummax().iat[-1] - daily.iat[-1]
    tl = (t.net < 0).to_numpy()
    roll = {k: mo.rolling(k).sum().dropna() for k in (3, 6, 12)}
    rng = np.random.default_rng(1)
    sim = {k: 0 for k in (2, 3, 4, 5)}
    neg12, longest_sum, N = 0, 0, 20000
    arr = mo.to_numpy()
    for _ in range(N):
        s = rng.choice(arr, 12)
        r = longest_run(s < 0)
        longest_sum += r
        neg12 += s.sum() < 0
        for k in sim:
            sim[k] += r >= k
    out = {"months covered": len(months), "trades": len(t), "win %": round(100 * (t.net > 0).mean(), 1), "PF points": pf(t.net),
           "net points": round(t.net.sum()), "expectancy R": round(t.R.mean(), 3), "avg / month points": round(mo.mean()),
           "months positive": f"{int((mo > 0).sum())} ({100*(mo > 0).mean():.0f}%)", "months negative": f"{int((mo < 0).sum())} ({100*(mo < 0).mean():.0f}%)",
           "months flat (no trades)": int((mo == 0).sum()), "LONGEST LOSING-MONTH RUN": longest_run(losing),
           "losing-month runs (lengths)": sorted(runs(losing), reverse=True)[:8], "runs of 2+ / 3+ losing months": f"{sum(r >= 2 for r in runs(losing))} / {sum(r >= 3 for r in runs(losing))}",
           "worst month": round(mo.min()), "best month": round(mo.max()), "monthly std": round(mo.std()),
           "worst rolling 3 / 6 / 12 months": " / ".join(f"{roll[k].min():,.0f}" for k in (3, 6, 12)),
           "rolling windows negative 3 / 6 / 12m %": " / ".join(f"{100*(roll[k] < 0).mean():.0f}" for k in (3, 6, 12)),
           "max drawdown points": round(dd), "net / max DD": round(t.net.sum() / dd, 2), "longest time underwater (days)": longest_days,
           "drawdown now (points)": round(cur_dd), "longest losing STREAK (trades)": longest_run(tl),
           "avg losing streak (trades)": round(float(np.mean(runs(tl))), 1),
           "MC 12-month: P(losing run >= 2 / 3 / 4 / 5 months)": " / ".join(f"{100*sim[k]/N:.0f}%" for k in sim),
           "MC 12-month: avg longest losing run": round(longest_sum / N, 1), "MC 12-month: P(net negative)": f"{100*neg12/N:.0f}%",
           "worst day (points)": round(t.groupby(t.exit_time.dt.date).net.sum().min())}
    return out, mo


pd.set_option("display.width", 250, "display.max_rows", 100, "display.max_colwidth", 60)
first, last = pd.Period("2024-01", "M"), pd.Period("2026-09", "M")
allstats, monthly = {}, {}
for sname, f in SOURCES.items():
    bars = rs.load(f)
    for cname, c in STRATS.items():
        t = run(bars, c)
        t = t[t.exit_time >= "2024-01-01"]
        allstats[f"{sname[:7]} | {cname}"], monthly[f"{sname[:7]} | {cname}"] = stats(t, first, last)
S = pd.DataFrame(allstats)
S.to_csv("research_data/silverm_trader_stats.csv")
print(S.to_string())
M = pd.DataFrame(monthly).round(0)
M.to_csv("research_data/silverm_trader_monthly.csv")
print("\nMONTHLY NET POINTS")
print(M.to_string())
