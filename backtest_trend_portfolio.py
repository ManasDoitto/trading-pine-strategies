"""Diversified daily trend-following portfolio (option 1).
Universe (fixed in advance, ETFs/indices/crypto to avoid unadjusted futures roll gaps): GLD SLV PPLT CPER USO UNG DBA SPY QQQ EEM TLT
Nifty BankNifty BTC ETH. 8 pre-set rules; rule chosen on data <= 2014-12-31 only, judged on 2015-2026.
Position = signal(-1/0/+1) x min(20% / realised vol, 3); equal weight across live markets; costs on every weight change;
crypto pays/receives real perp funding. Signal at close t earns the return of day t+1 (no lookahead)."""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__)); TR = os.path.join(ROOT, "research_data", "trend"); CRY = os.path.join(ROOT, "research_data", "crypto")
SPLIT = pd.Timestamp("2015-01-01"); VOL_T = 0.20; CAP = 3.0
CLASS = {"gld": "metals", "slv": "metals", "pplt": "metals", "cper": "metals", "uso": "energy", "ung": "energy", "dba": "agri", "spy": "equity", "qqq": "equity",
         "eem": "equity", "nsei": "equity", "nsebank": "equity", "tlt": "bonds", "btc": "crypto", "eth": "crypto"}
COST = {k: 0.0003 for k in CLASS}; COST.update({"nsei": 0.0002, "nsebank": 0.0002, "btc": 0.0007, "eth": 0.0007})

def load_all():
    m = {}
    for k in CLASS:
        if k in ("btc", "eth"):
            raw = json.load(open(os.path.join(CRY, f"{k}usdt_perp_1h.json"))); d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
            for c in ("open", "high", "low", "close"): d[c] = d[c].astype(float)
            d["time"] = pd.to_datetime(d["t"], unit="ms"); d = d.set_index("time")
            dd = d.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
        else:
            dd = pd.read_pickle(os.path.join(TR, f"{k}.pkl"))
        m[k] = dd.sort_values("time").reset_index(drop=True)
    fund = {}
    for k in ("btc", "eth"):
        fr = pd.DataFrame(json.load(open(os.path.join(CRY, f"{k}usdt_funding.json")))); fr["day"] = pd.to_datetime(fr["fundingTime"], unit="ms").dt.normalize()
        fund[k] = fr.groupby("day")["fundingRate"].apply(lambda x: x.astype(float).sum())
    return m, fund

def adx14(d):
    h, l, c = d["high"], d["low"], d["close"]; up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = c.shift(1); tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    w = lambda s: s.ewm(alpha=1 / 14, adjust=False).mean()
    atr = w(tr); p = 100 * w(pd.Series(pdm, index=d.index)) / atr; mn = 100 * w(pd.Series(mdm, index=d.index)) / atr
    return 100 * w((p - mn).abs() / (p + mn).replace(0, np.nan))

def donchian(d, n, adx_gate=None):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy(); N = len(d)
    hi_n = pd.Series(h).rolling(n).max().shift(1).to_numpy(); lo_n = pd.Series(l).rolling(n).min().shift(1).to_numpy()
    hi_x = pd.Series(h).rolling(max(n // 2, 2)).max().shift(1).to_numpy(); lo_x = pd.Series(l).rolling(max(n // 2, 2)).min().shift(1).to_numpy()
    gate = (adx14(d) >= adx_gate).to_numpy() if adx_gate else np.ones(N, bool)
    pos = np.zeros(N); cur = 0
    for i in range(N):
        if cur == 1 and c[i] < lo_x[i]: cur = 0
        elif cur == -1 and c[i] > hi_x[i]: cur = 0
        if cur == 0 and gate[i]:
            if c[i] > hi_n[i]: cur = 1
            elif c[i] < lo_n[i]: cur = -1
        pos[i] = cur
    return pd.Series(pos, index=d.index)

RULES = {
    "TSMOM126": lambda d: np.sign(d["close"] / d["close"].shift(126) - 1).fillna(0),
    "TSMOM252": lambda d: np.sign(d["close"] / d["close"].shift(252) - 1).fillna(0),
    "DON50": lambda d: donchian(d, 50), "DON100": lambda d: donchian(d, 100),
    "MA50/200": lambda d: np.sign(d["close"].rolling(50).mean() - d["close"].rolling(200).mean()).fillna(0),
    "MA20/100": lambda d: np.sign(d["close"].rolling(20).mean() - d["close"].rolling(100).mean()).fillna(0),
    "DON50+ADX25": lambda d: donchian(d, 50, 25), "DON100+ADX25": lambda d: donchian(d, 100, 25),
}

def market_pnl(d, name, sig, fund):
    r = d["close"].pct_change().fillna(0.0)
    vol = r.ewm(span=30).std() * np.sqrt(252); tgt = (VOL_T / vol.shift(1)).clip(upper=CAP).fillna(0).to_numpy()
    s = sig.shift(1).fillna(0).to_numpy()           # signal known at close t-1 -> position for day t
    w = np.zeros(len(d)); cur = 0.0; cs = 0.0
    for i in range(len(d)):
        if s[i] != cs or (s[i] != 0 and cur == 0) or (cur != 0 and s[i] != 0 and abs(tgt[i] * abs(s[i]) / abs(cur) - 1) > 0.3): cur = s[i] * tgt[i]
        elif s[i] == 0: cur = 0.0
        cs = s[i]; w[i] = cur
    w = pd.Series(w, index=d.index); w_prev = w.shift(1).fillna(0)
    pnl = w * r - COST[name] * (w - w_prev).abs()      # w_t earns r_t (w already encodes yesterday's signal)
    if name in fund:
        fs = d["time"].map(fund[name]).fillna(0.0)
        pnl = pnl - w * fs
    pnl.index = d["time"]; return pnl

def run_rule(rule, mk, fund, skip=()):
    pn = {k: market_pnl(d, k, RULES[rule](d), fund) for k, d in mk.items() if k not in skip}
    # a market is live after 300 bars of history
    live = {k: pd.Series(1.0, index=p.index).where(pd.Series(np.arange(len(p)), index=p.index) >= 300) for k, p in pn.items()}
    P = pd.DataFrame(pn).sort_index(); Lv = pd.DataFrame(live).reindex(P.index)
    n_live = Lv.notna().sum(axis=1).replace(0, np.nan)
    port = (P.where(Lv.notna(), 0.0)).sum(axis=1) / n_live
    return port.dropna(), P, Lv

def stats(r):
    r = r.dropna()
    if len(r) < 100: return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, mdd=np.nan, years=0)
    eq = (1 + r).cumprod(); yrs = len(r) / 252
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(252), sharpe=r.mean() / r.std() * np.sqrt(252), mdd=(eq / eq.cummax() - 1).min(), years=yrs)

if __name__ == "__main__":
    mk, fund = load_all()
    print("markets:", {k: f"{d.time.iloc[0].date()}..{len(d)}" for k, d in mk.items()})
    res = {}
    rows = []
    for rule in RULES:
        port, P, Lv = run_rule(rule, mk, fund); res[rule] = (port, P, Lv)
        tr, te = port[port.index < SPLIT], port[port.index >= SPLIT]
        a, b = stats(tr), stats(te)
        rows.append(dict(rule=rule, tr_sharpe=a["sharpe"], tr_cagr=a["cagr"], te_sharpe=b["sharpe"], te_cagr=b["cagr"], te_vol=b["vol"], te_mdd=b["mdd"]))
    R = pd.DataFrame(rows).set_index("rule"); pd.set_option("display.width", 200)
    print("\nAll 8 rules (portfolio at its natural vol; TRAIN <=2014, TEST 2015-2026):"); print(R.round(3).to_string())
    best = R["tr_sharpe"].idxmax(); print(f"\nRULE CHOSEN ON TRAIN ONLY: {best}  -> test Sharpe {R.loc[best,'te_sharpe']:.2f}  | median test Sharpe of all 8 = {R.te_sharpe.median():.2f}; positive test Sharpe: {(R.te_sharpe>0).sum()}/8")
    import pickle; pickle.dump({k: v[0] for k, v in res.items()}, open(os.path.join(ROOT, "research_data", "trend", "portfolio_returns.pkl"), "wb"))
