"""Translate futures-points backtests into OPTION-BUYING premium P&L (Black-76).

Every strategy number in this repo is futures points. The trader buys options, so the question is whether a
+297-points-per-trade futures edge survives premium, theta and spread. This prices an ATM option at entry and
re-prices it at exit on the same futures path.

Anchors measured from the live Dhan chain 2026-09-26 (MCX SILVER, expiry 2026-10-27, underlying 231,793):
ATM CE IV 29.6%, delta 0.553, premium 9,000 pts; median plausible near-ATM CE IV 28.1%; strike step 1,000.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals as v40
from trading_agents.core import black76

T0 = pd.Timestamp("2024-03-25")
R_RATE = 0.065
MIN_DTE = 7           # never buy an option with less than a week left


def monthly_expiries(start, end):
    """MCX silver option expiries approximate the 25th-28th monthly (observed: 27Oct, 27Nov, 28Dec, 25Jan, 26Feb)."""
    d = pd.date_range(pd.Timestamp(start) - pd.DateOffset(months=1),
                      pd.Timestamp(end) + pd.DateOffset(months=3), freq="MS")
    return pd.DatetimeIndex([x + pd.Timedelta(days=25) for x in d])


def pick_expiry(t, expiries):
    e = expiries[expiries >= t + pd.Timedelta(days=MIN_DTE)]
    return e[0] if len(e) else None


def option_pnl(trades, sigma, strike_step=1000, spread_pct=0.0, right_map=("CE", "PE")):
    """Buy ATM CE for a long futures signal, ATM PE for a short. Returns a per-trade frame in PREMIUM POINTS."""
    t = pd.DataFrame(trades).copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"]); t["exit_time"] = pd.to_datetime(t["exit_time"])
    exps = monthly_expiries(t.entry_time.min(), t.exit_time.max())
    rows = []
    for r in t.itertuples():
        exp = pick_expiry(r.entry_time, exps)
        if exp is None:
            continue
        K = round(r.entry / strike_step) * strike_step
        T_in = max((exp - r.entry_time).total_seconds() / (365 * 86400), 1e-6)
        T_out = max((exp - r.exit_time).total_seconds() / (365 * 86400), 1e-6)
        right = right_map[0] if r.side == "LONG" else right_map[1]
        p_in = black76.price(r.entry, K, T_in, sigma, R_RATE, right)
        p_out = black76.price(r.exit, K, T_out, sigma, R_RATE, right)
        cost = spread_pct * (p_in + p_out)
        rows.append(dict(entry_time=r.entry_time, exit_time=r.exit_time, side=r.side,
                         fut_net=r.net, K=K, dte_in=T_in * 365, hold_h=(r.exit_time - r.entry_time).total_seconds() / 3600,
                         prem_in=p_in, prem_out=p_out, opt_gross=p_out - p_in, cost=cost,
                         opt_net=p_out - p_in - cost))
    return pd.DataFrame(rows)


def summarise(o, tag):
    if o.empty:
        print(f"{tag:34s} no trades"); return None
    w, l = o.loc[o.opt_net > 0, "opt_net"].sum(), -o.loc[o.opt_net < 0, "opt_net"].sum()
    eq = o.sort_values("exit_time").opt_net.cumsum()
    pf = w / l if l else float("inf")
    print(f"{tag:34s} n={len(o):4d} PF={pf:6.3f} net={o.opt_net.sum():+11.1f} "
          f"maxDD={(eq.cummax()-eq).max():9.1f} win={100*(o.opt_net>0).mean():4.1f}% "
          f"avg_prem={o.prem_in.mean():8.1f} avg_pnl={o.opt_net.mean():+8.1f}")
    return dict(tag=tag, n=len(o), pf=round(pf, 3), net=round(o.opt_net.sum(), 1),
                max_dd=round(float((eq.cummax() - eq).max()), 1), win=round(100 * (o.opt_net > 0).mean(), 1),
                avg_prem=round(o.prem_in.mean(), 1), avg_pnl=round(o.opt_net.mean(), 1))


def silver_incumbent_trades():
    p = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=2.5, max_sl=5.0, rr=3.0,
             session=["09:15", "23:30"])
    f = v40.v40_frame(rs.load("MCX_SILVER1"), p)
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(f, dict(p, day_loss_limit_pts=350), start=s0, commission=0.0)


if __name__ == "__main__":
    tr = silver_incumbent_trades()
    fut = rs.stats(tr)
    print(f"FUTURES baseline (silver working_strategies #1): n={fut['n']} PF={fut['pf']:.3f} "
          f"net={fut['net']:+.1f} maxDD={fut['max_dd']:.1f} win={fut['win_pct']:.1f}% "
          f"avg_hold={fut['avg_hold_h']}h\n")
    out = []
    print("--- OPTION BUYING, ATM, Black-76, strike step 1000, r=6.5%, min 7 DTE ---")
    for sigma in (0.22, 0.28, 0.34):
        for sp in (0.0, 0.01, 0.02):
            o = option_pnl(tr, sigma, spread_pct=sp)
            s = summarise(o, f"IV {sigma*100:.0f}%  spread {sp*100:.0f}%/side")
            if s: out.append(dict(s, iv=sigma, spread=sp))
    pd.DataFrame(out).to_csv(ROOT / "research_data" / "option_premium_sim.csv", index=False)
    o = option_pnl(tr, 0.28, spread_pct=0.01)
    print(f"\nat IV 28% / 1% spread: avg premium paid {o.prem_in.mean():.0f} pts, "
          f"avg DTE at entry {o.dte_in.mean():.1f} d, avg hold {o.hold_h.mean():.1f} h")
    print(f"futures winners that are ALSO option winners: "
          f"{100*((o.fut_net>0)&(o.opt_net>0)).sum()/max((o.fut_net>0).sum(),1):.1f}%")
    print(f"futures losers that are option winners:       "
          f"{100*((o.fut_net<0)&(o.opt_net>0)).sum()/max((o.fut_net<0).sum(),1):.1f}%")
