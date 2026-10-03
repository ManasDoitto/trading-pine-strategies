import sys, time, pickle
import numpy as np, pandas as pd
import consol_search as S

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
t0 = time.time()
mk = {s.upper(): S.load4h(s) for s in ("btc", "eth", "sol", "bnb", "xrp")}
D = S.build(mk, lambda en: 2 * 0.0007 * en); print(f"crypto signals built {time.time()-t0:.0f}s; rows per K: {D['lens'].tolist()}", flush=True)
names = list(S.SPACE)
# 1) replicate the earlier filtered config: K2.5 far RR3 hold12 EMA120 body>=.6 range>=1 (earlier crypto-only: n=2232, mean ~ +0.061)
base = np.array([[3, 0, 2, 1, 2, 0, 0, .6, 1.0, 0, 0, -99, 0, 4, 0]], float)
n, m, t = S.summarize(S.run(base, D)); print(f"REPLICATION: n={int(n[0].sum())} mean net R={(m[0]*n[0]).sum()/n[0].sum():+.3f}  (earlier standalone sim: n=2232, +0.061)", flush=True)
# 2) 100k random tweaks
rng = np.random.default_rng(2026); P = S.draw(100_000, rng); t1 = time.time()
St = S.run(P, D); n, m, t = S.summarize(St); print(f"100k combos searched in {time.time()-t1:.0f}s", flush=True)
df = pd.DataFrame(P, columns=names);
for p, nm in enumerate(("tr", "va", "ho")): df[f"n_{nm}"] = n[:, p]; df[f"R_{nm}"] = m[:, p]; df[f"t_{nm}"] = t[:, p]
df["n_all"] = n.sum(axis=1); df["R_all"] = (St[:, :, 1].sum(axis=1)) / np.maximum(df["n_all"], 1)
pickle.dump((P, St), open("research_data/consol_search_real.pkl", "wb"))

def pipeline(df, label):
    ok = df[(df.n_tr >= 60) & (df.n_va >= 30) & (df.n_ho >= 20) & (df.n_all >= 150)]
    top = ok.sort_values("t_tr", ascending=False).head(500)                         # step 1: train only
    both = top[(top.R_va > 0) & (top.t_va > 0.5)].sort_values("t_va", ascending=False).head(20)  # step 2: validation only
    pick = both.iloc[0] if len(both) else None
    return ok, top, both, pick

ok, top, both, pick = pipeline(df, "real")
print(f"\ncombos with enough trades in every period: {len(ok)} of 100000")
print(f"share positive in TRAIN: {(ok.R_tr>0).mean():.1%}  VALIDATION: {(ok.R_va>0).mean():.1%}  HOLDOUT: {(ok.R_ho>0).mean():.1%} | positive in train AND validation: {((ok.R_tr>0)&(ok.R_va>0)).mean():.1%}; all three: {((ok.R_tr>0)&(ok.R_va>0)&(ok.R_ho>0)).mean():.1%}")
print(f"mean net R across all combos: train {ok.R_tr.mean():+.3f}  val {ok.R_va.mean():+.3f}  holdout {ok.R_ho.mean():+.3f}")
print(f"best TRAIN t-stat found among 100k: {ok.t_tr.max():.1f}  | best VAL t-stat: {ok.t_va.max():.1f} | best HOLDOUT t-stat (hindsight, not used): {ok.t_ho.max():.1f}")
cols = ["k", "stop", "rr", "hold", "ema", "strength", "adx", "body", "rngm", "cpos", "vol", "imp", "dr", "nmin", "hour", "n_tr", "R_tr", "t_tr", "n_va", "R_va", "t_va", "n_ho", "R_ho", "t_ho"]
print("\nTop-5 picks after TRAIN (top 500 by t) then VALIDATION selection -> HOLDOUT:"); print(both.head(5)[cols].round(3).to_string(index=False))
if pick is not None:
    print(f"\nFINAL PICK: train {pick.R_tr:+.3f} (n={int(pick.n_tr)}) | validation {pick.R_va:+.3f} (n={int(pick.n_va)}) | HOLDOUT {pick.R_ho:+.3f} (n={int(pick.n_ho)}, t={pick.t_ho:.1f})")
    print(f"avg HOLDOUT net R of the top-20 shortlisted: {both.R_ho.mean():+.3f}   (all-combos baseline holdout {ok.R_ho.mean():+.3f})")
# 3) luck benchmark: identical pipeline on shuffled outcomes
print("\n=== NULL (shuffled outcomes, same 100k combos, same pipeline) ===")
nulls = []
for s in range(3):
    Rn = S.null_R(D, np.random.default_rng(100 + s)); Sn = S.run(P, D, Rn); nn, mn, tn = S.summarize(Sn)
    dn = pd.DataFrame(P, columns=names)
    for p, nm in enumerate(("tr", "va", "ho")): dn[f"n_{nm}"] = nn[:, p]; dn[f"R_{nm}"] = mn[:, p]; dn[f"t_{nm}"] = tn[:, p]
    dn["n_all"] = nn.sum(axis=1); okn, topn, bothn, pickn = pipeline(dn, f"null{s}")
    nulls.append(dict(best_train_t=okn.t_tr.max(), best_val_t=okn.t_va.max(), pos_train_and_val=((okn.R_tr > 0) & (okn.R_va > 0)).mean(),
                      pick_train=pickn.R_tr if pickn is not None else np.nan, pick_val=pickn.R_va if pickn is not None else np.nan, pick_hold=pickn.R_ho if pickn is not None else np.nan,
                      top20_hold=bothn.R_ho.mean() if len(bothn) else np.nan, base_hold=okn.R_ho.mean()))
print(pd.DataFrame(nulls).round(3).to_string())
print("REAL for comparison:", dict(best_train_t=round(ok.t_tr.max(), 2), best_val_t=round(ok.t_va.max(), 2), pos_train_and_val=round(((ok.R_tr > 0) & (ok.R_va > 0)).mean(), 3),
      pick_train=round(pick.R_tr, 3), pick_val=round(pick.R_va, 3), pick_hold=round(pick.R_ho, 3), top20_hold=round(both.R_ho.mean(), 3), base_hold=round(ok.R_ho.mean(), 3)))
# 4) does fewer trades help? average holdout R by trade-count bucket (all combos, no selection)
ok2 = ok.copy(); ok2["bucket"] = pd.cut(ok2.n_all, [149, 300, 600, 1200, 2400, 10**6], labels=["150-300", "300-600", "600-1200", "1200-2400", ">2400"])
g = ok2.groupby("bucket", observed=True).agg(combos=("R_ho", "size"), R_train=("R_tr", "mean"), R_val=("R_va", "mean"), R_holdout=("R_ho", "mean"), pct_hold_pos=("R_ho", lambda x: (x > 0).mean()))
sel = ok2[(ok2.R_tr > 0) & (ok2.R_va > 0)].groupby("bucket", observed=True).agg(combos_pos_tr_va=("R_ho", "size"), R_holdout_of_those=("R_ho", "mean"), pct_hold_pos=("R_ho", lambda x: (x > 0).mean()))
print("\n=== FEWER TRADES? (no selection: average over all combos in each trade-count bucket) ==="); print(g.round(3).to_string())
print("\n=== same, only combos that were positive in BOTH train and validation (selected without holdout) ==="); print(sel.round(3).to_string())
df.to_pickle("research_data/consol_search_table.pkl"); pickle.dump(both, open("research_data/consol_search_picks.pkl", "wb"))
print(f"\ntotal {time.time()-t0:.0f}s")
