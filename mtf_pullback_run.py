import json, os
import numpy as np, pandas as pd
import mtf_pullback as M

ROOT = os.path.dirname(os.path.abspath(__file__)); CRY = os.path.join(ROOT, "research_data", "crypto")
SPLIT_TR = pd.Timestamp("2022-01-01"); SPLIT_HO = pd.Timestamp("2024-07-01")

def load_crypto_1h(sym):
    raw = json.load(open(os.path.join(CRY, f"{sym.lower()}usdt_perp_1h.json")))
    d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in ("open", "high", "low", "close"): d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms"); d = d[["time", "open", "high", "low", "close"]].reset_index(drop=True)
    fr = pd.DataFrame(json.load(open(os.path.join(CRY, f"{sym.lower()}usdt_funding.json"))))
    ft = pd.to_datetime(fr["fundingTime"], unit="ms").to_numpy(); o = np.argsort(ft)
    return d, (ft[o], np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])]))

def load_crypto_15m(sym):
    raw = json.load(open(os.path.join(CRY, f"{sym.lower()}usdt_perp_15m.json")))
    d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in ("open", "high", "low", "close"): d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms"); return d[["time", "open", "high", "low", "close"]].reset_index(drop=True)

def load_gold_1m():
    d = pd.read_pickle(os.path.join(ROOT, "research_data", "gold", "xauusd_1m.pkl")); d["time"] = pd.to_datetime(d["time"])
    return d[["time", "open", "high", "low", "close"]].reset_index(drop=True)

def tstat(x): return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 and x.std() > 0 else np.nan

def split_stats(tr):
    if len(tr) == 0: return dict(n=0)
    a, b, h = tr[tr.entry_time < SPLIT_TR], tr[(tr.entry_time >= SPLIT_TR) & (tr.entry_time < SPLIT_HO)], tr[tr.entry_time >= SPLIT_HO]
    return dict(n=len(tr), win=(tr.net_r > 0).mean(), gross=tr.gross_r.mean(), net=tr.net_r.mean(), t=tstat(tr.net_r),
               n_tr=len(a), R_tr=a.net_r.mean() if len(a) else np.nan, n_va=len(b), R_va=b.net_r.mean() if len(b) else np.nan,
               n_ho=len(h), R_ho=h.net_r.mean() if len(h) else np.nan, t_ho=tstat(h.net_r) if len(h) > 3 else np.nan,
               hold_h=((tr.exit_time - tr.entry_time).dt.total_seconds().mean() / 3600))

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    print("===== PRIMARY: 1h entries / 4h bias / 16h slow-ADX (4x ratio, matches original's 3m/15m) =====")
    cost_c = lambda en: 2 * 0.0007 * en; cost_g = lambda en: np.full_like(en, 1.0)
    rows = []; all_tr = {}
    for sym in ("ETH", "SOL", "BNB", "XRP"):
        ltf, fund = load_crypto_1h(sym)
        htf = M.resample(ltf, "4h"); slow = M.resample(ltf, "16h")
        tr = M.simulate(ltf, htf, slow, htf_minutes=240, slow_minutes=960, cost_fn=cost_c, fund=fund)
        all_tr[sym] = tr; s = split_stats(tr); s["mkt"] = sym; rows.append(s)
    gold = load_gold_1m(); gltf = M.resample(gold, "1h")
    ghtf = M.resample(gltf, "4h"); gslow = M.resample(gltf, "16h")
    trg = M.simulate(gltf, ghtf, gslow, htf_minutes=240, slow_minutes=960, cost_fn=cost_g)
    all_tr["XAU"] = trg; s = split_stats(trg); s["mkt"] = "XAU"; rows.append(s)
    R = pd.DataFrame(rows).set_index("mkt")
    print(R[["n", "win", "gross", "net", "n_tr", "R_tr", "n_va", "R_va", "n_ho", "R_ho", "t_ho", "hold_h"]].round(3).to_string())
    pool = pd.concat([t.assign(m=k) for k, t in all_tr.items() if len(t)])
    print(f"\nPOOLED (ETH SOL BNB XRP XAU): {len(pool)} trades, win {(pool.net_r>0).mean():.0%}, "
          f"gross R {pool.gross_r.mean():+.3f}, net R {pool.net_r.mean():+.3f}")
    for lbl, sub in (("train", pool[pool.entry_time < SPLIT_TR]), ("validation", pool[(pool.entry_time >= SPLIT_TR) & (pool.entry_time < SPLIT_HO)]),
                    ("HOLDOUT", pool[pool.entry_time >= SPLIT_HO])):
        if len(sub): print(f"  {lbl:12} n={len(sub):4} net R {sub.net_r.mean():+.3f}  t={tstat(sub.net_r):+.2f}")

    print("\n===== SECONDARY (shorter TF spot-check): 15m entries / 1h bias / 4h slow-ADX, BTC + XAU =====")
    rows2 = []
    b15 = load_crypto_15m("btc")
    bhtf = M.resample(b15, "1h"); bslow = M.resample(b15, "4h")
    _, fundb = load_crypto_1h("btc")
    trb = M.simulate(b15, bhtf, bslow, htf_minutes=60, slow_minutes=240, cost_fn=cost_c, fund=fundb)
    s = split_stats(trb); s["mkt"] = "BTC"; rows2.append(s)
    g15 = M.resample(gold, "15min")
    ghtf2 = M.resample(g15, "1h"); gslow2 = M.resample(g15, "4h")
    trg2 = M.simulate(g15, ghtf2, gslow2, htf_minutes=60, slow_minutes=240, cost_fn=cost_g)
    s = split_stats(trg2); s["mkt"] = "XAU"; rows2.append(s)
    R2 = pd.DataFrame(rows2).set_index("mkt")
    print(R2[["n", "win", "gross", "net", "n_tr", "R_tr", "n_va", "R_va", "n_ho", "R_ho", "t_ho", "hold_h"]].round(3).to_string())

    import pickle
    pickle.dump({"primary": all_tr, "secondary": {"BTC": trb, "XAU": g15}}, open("research_data/mtf_pullback_trades.pkl", "wb"))
