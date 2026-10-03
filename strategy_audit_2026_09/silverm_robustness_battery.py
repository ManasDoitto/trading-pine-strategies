"""Robustness battery for the deployed SILVERM strategy (v4.1 + min_stop_pct 0.35 + 350 brake) - NO retuning, only stress tests.
A parameter-sensitivity map, a transfer test to other markets with the same rules, cost stress, entry-delay stress, bootstrap confidence and rolling-window limits."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P0 = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = rs.load("MCX_SILVERM1")
pd.set_option("display.width", 250, "display.max_rows", 200)


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def run(bars, p, **kw):
    f = rs.v40.v40_frame(bars, p)
    t = pd.DataFrame(rs.simulate(f, p, **kw))
    if t.empty:
        return t
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def row(t):
    if len(t) < 5:
        return dict(trades=len(t))
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq = t.net.cumsum()
    return dict(trades=len(t), win=round(100 * (t.net > 0).mean(), 1), PF=pf(t.net), net=round(t.net.sum()), expR=round(t.R.mean(), 3),
                maxDD=round((eq.cummax() - eq).max()), months_pos=f"{int((mo > 0).sum())}/{len(mo)}", hold_h=round(t.hold_h.mean(), 1))


base = run(BARS, P0)
B = row(base)
print("BASELINE (deployed):", B)

# ---------------------------------------------------------------- A. sensitivity
print("\n=== A. PARAMETER SENSITIVITY (one setting changed at a time; baseline PF %.2f, net %s) ===" % (B["PF"], f"{B['net']:,}"))
grid = {"rr": [2.5, 3.0, 3.5], "min_sl": [2.0, 2.5, 3.0], "max_sl": [4.0, 5.0, 6.0], "sw_len": [8, 10, 12], "bo_lookback": [2, 3, 4],
        "min_stop_pct": [0.25, 0.30, 0.35, 0.40, 0.45], "day_loss_limit_pts": [250, 350, 500, 700], "sw_buf": [0.05, 0.1, 0.2]}
rows, neigh = [], []
for k, vals in grid.items():
    for v in vals:
        r = row(run(BARS, dict(P0, **{k: v})))
        rows.append(dict(setting=f"{k}={v}", **r, is_base=(P0.get(k) == v)))
        if P0.get(k) != v:
            neigh.append(r)
S = pd.DataFrame(rows)
print(S.drop(columns="is_base").to_string(index=False))
good = [r for r in neigh if r["PF"] >= 1.2 and r["net"] >= 0.7 * B["net"]]
print(f"\nneighbours with PF >= 1.2 and net >= 70% of baseline: {len(good)} of {len(neigh)} ({100*len(good)/len(neigh):.0f}%); worst neighbour PF {min(r['PF'] for r in neigh)}, worst net {min(r['net'] for r in neigh):,}")

# ---------------------------------------------------------------- B. transfer to other markets, same rules, no retuning
print("\n=== B. SAME RULES ON OTHER MARKETS (no retuning; daily brake off because its points are silver-specific) ===")
tr = {}
for name, key, sess in (("MCX CRUDE", "MCX_CRUDEOIL1", ["09:15", "23:30"]), ("BANKNIFTY fut", "NSE_BANKNIFTY1", ["09:15", "15:30"])):
    bars = rs.load(key)
    for lab, extra in (("v4.1 rules", dict(min_stop_pct=None)), ("v4.1 + 0.35% stop filter", dict())):
        p = dict(P0, session=sess, day_loss_limit_pts=0, exclude_hours=[], **extra)
        tr[f"{name} | {lab}"] = row(run(bars, p))
print(pd.DataFrame(tr).T.to_string())

# ---------------------------------------------------------------- C. costs
print("\n=== C. COST STRESS (commission per side; deployed cost is 0.02%) ===")
cs = {f"{c*100:.2f}% per side": row(run(BARS, P0, commission=c)) for c in (0.0002, 0.0005, 0.0010, 0.0020)}
print(pd.DataFrame(cs).T.to_string())

# ---------------------------------------------------------------- D. entry delay
print("\n=== D. ENTRY DELAY (you enter this many 5-minute bars after the normal fill; same stop and target levels) ===")
ds = {f"{d} bar(s) = {5*d} min": row(run(BARS, P0, entry_delay_bars=d)) for d in (0, 1, 2, 3, 6)}
print(pd.DataFrame(ds).T.to_string())

# ---------------------------------------------------------------- E. bootstrap confidence
print("\n=== E. BOOTSTRAP CONFIDENCE (4,000 month-block resamples of the 34 months) ===")
months = sorted(base.exit_time.dt.to_period("M").unique())
G = {m: g for m, g in base.groupby(base.exit_time.dt.to_period("M"))}
rng = np.random.default_rng(2)
out = []
for _ in range(4000):
    x = pd.concat([G[months[i]] for i in rng.choice(len(months), len(months))])
    out.append((pf(x.net), x.net.sum(), x.R.mean()))
a = np.array(out)
print(f"PF   median {np.median(a[:,0]):.2f}, 90% range [{np.percentile(a[:,0],5):.2f}, {np.percentile(a[:,0],95):.2f}], P(PF<1) {100*np.mean(a[:,0]<1):.1f}%, P(PF<1.2) {100*np.mean(a[:,0]<1.2):.0f}%")
print(f"net  median {np.median(a[:,1]):,.0f}, 90% range [{np.percentile(a[:,1],5):,.0f}, {np.percentile(a[:,1],95):,.0f}], P(net<0) {100*np.mean(a[:,1]<0):.1f}%")
print(f"expR median {np.median(a[:,2]):.3f}, 90% range [{np.percentile(a[:,2],5):.3f}, {np.percentile(a[:,2],95):.3f}], P(expR<=0) {100*np.mean(a[:,2]<=0):.1f}%")
print(f"without the 10 best trades: net {base.net.sum()-base.net.nlargest(10).sum():,.0f}, PF {pf(base.net.drop(base.net.nlargest(10).index))}")

# ---------------------------------------------------------------- F. rolling windows and review limits
print("\n=== F. WHAT NORMAL LOOKS LIKE (rolling windows over the deployed history) ===")
net = base.net.reset_index(drop=True)
for w in (30, 60, 100):
    rp = [pf(net.iloc[i:i + w]) for i in range(0, len(net) - w + 1, 5)]
    rn = [net.iloc[i:i + w].sum() for i in range(0, len(net) - w + 1, 5)]
    print(f"rolling {w:>3} trades: PF 5th/25th/median/75th pct = {np.percentile(rp,5):.2f} / {np.percentile(rp,25):.2f} / {np.percentile(rp,50):.2f} / {np.percentile(rp,75):.2f}"
          f" | share of windows with PF<1: {100*np.mean(np.array(rp)<1):.0f}% | worst window net {min(rn):,.0f}")
eq = net.cumsum()
dd = (eq.cummax() - eq)
under = (eq < eq.cummax()).astype(int)
longest = max((len(list(g)) for k, g in __import__("itertools").groupby(under) if k == 1), default=0)
print(f"max drawdown {dd.max():,.0f}; longest stretch below a previous peak: {longest} trades (~{longest/ (len(net)/34):.1f} months); longest losing streak {max((len(list(g)) for k, g in __import__('itertools').groupby((net<0).astype(int)) if k==1), default=0)} trades")
