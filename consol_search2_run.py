import os, sys, time, pickle
import numpy as np, pandas as pd
import consol_search2 as S2
from consol_search import SPACE, draw

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 200)
N = int(os.environ.get("NCOMB", 1_000_000)); t0 = time.time(); names = list(SPACE)
DS = {}
for tf in ("4h", "1h"):
    mks = S2.all_markets(tf); DS[tf] = (list(mks), S2.build_multi(mks))
    print(f"{tf}: markets {list(mks)} rows/K {DS[tf][1]['lens'].tolist()}  ({time.time()-t0:.0f}s)", flush=True)
rng = np.random.default_rng(7); P = draw(N, rng); print(f"drew {N:,} combos ({time.time()-t0:.0f}s)", flush=True)
RES = {}
for tf, (mk, D) in DS.items():
    t1 = time.time(); RES[tf] = S2.run_mkt(P, D); print(f"searched {tf} in {time.time()-t1:.0f}s", flush=True)
pickle.dump({"P": P, "names": names, "mk": {tf: DS[tf][0] for tf in DS}}, open("research_data/search2_meta.pkl", "wb"))

def table(St, mk):
    n, m, t = S2.pooled(St); d = pd.DataFrame(P, columns=names)
    for p, nm in enumerate(("tr", "va", "ho")): d[f"n_{nm}"] = n[:, p]; d[f"R_{nm}"] = m[:, p]; d[f"t_{nm}"] = t[:, p]
    d["n_all"] = n.sum(axis=1)
    pm = St.sum(axis=2); cnt = pm[:, :, 0]; mean = np.divide(pm[:, :, 1], cnt, out=np.full_like(cnt, np.nan), where=cnt > 50)
    d["mkts_pos"] = np.nansum(mean > 0, axis=1); d["mkts_used"] = (cnt > 50).sum(axis=1)
    pmho = St[:, :, 2, :]; cho = pmho[:, :, 0]; mho = np.divide(pmho[:, :, 1], cho, out=np.full_like(cho, np.nan), where=cho > 30)
    d["mkts_pos_ho"] = np.nansum(mho > 0, axis=1); d["mkts_used_ho"] = (cho > 30).sum(axis=1)
    return d

T = {tf: table(RES[tf], DS[tf][0]) for tf in RES}
for tf, d in T.items():
    ok = d[(d.n_tr >= 60) & (d.n_va >= 30) & (d.n_ho >= 20) & (d.n_all >= 150)]
    print(f"\n===== {tf}: {len(ok):,} of {N:,} combos have enough trades in every period =====")
    print(f"mean net R over ALL combos: train {ok.R_tr.mean():+.4f}  val {ok.R_va.mean():+.4f}  HOLDOUT {ok.R_ho.mean():+.4f}")
    print(f"share positive: train {(ok.R_tr>0).mean():.1%}  val {(ok.R_va>0).mean():.1%}  holdout {(ok.R_ho>0).mean():.1%}")
    print(f"best train t {ok.t_tr.max():.2f} | best val t {ok.t_va.max():.2f} | best holdout t (hindsight) {ok.t_ho.max():.2f}")
    top = ok.sort_values("t_tr", ascending=False).head(2000)
    sel = top[(top.R_va > 0) & (top.t_va > 0.5)].sort_values("t_va", ascending=False).head(50)
    print(f"selected on train->val: {len(sel)} | their HOLDOUT mean {sel.R_ho.mean():+.4f} | best single pick holdout {sel.iloc[0].R_ho:+.4f} (n={int(sel.iloc[0].n_ho)})")
    T[tf] = d

print("\n===== NULL CALIBRATION (same 1M combos, shuffled outcomes, 4h) =====")
mk4, D4 = DS["4h"]; rows = []
for s in range(2):
    Rn = S2.null_R(D4, np.random.default_rng(500 + s)); Sn = S2.run_mkt(P, D4, Rn); dn = table(Sn, mk4)
    okn = dn[(dn.n_tr >= 60) & (dn.n_va >= 30) & (dn.n_ho >= 20) & (dn.n_all >= 150)]
    topn = okn.sort_values("t_tr", ascending=False).head(2000); seln = topn[(topn.R_va > 0) & (topn.t_va > 0.5)].sort_values("t_va", ascending=False).head(50)
    rows.append(dict(best_train_t=okn.t_tr.max(), best_val_t=okn.t_va.max(), best_hold_t=okn.t_ho.max(),
                     sel_R_tr=seln.R_tr.mean(), sel_R_va=seln.R_va.mean(), sel_R_ho=seln.R_ho.mean(), base_ho=okn.R_ho.mean()))
ok4 = T["4h"][(T["4h"].n_tr >= 60) & (T["4h"].n_va >= 30) & (T["4h"].n_ho >= 20) & (T["4h"].n_all >= 150)]
top4 = ok4.sort_values("t_tr", ascending=False).head(2000); sel4 = top4[(top4.R_va > 0) & (top4.t_va > 0.5)].sort_values("t_va", ascending=False).head(50)
rows.append(dict(best_train_t=ok4.t_tr.max(), best_val_t=ok4.t_va.max(), best_hold_t=ok4.t_ho.max(),
                 sel_R_tr=sel4.R_tr.mean(), sel_R_va=sel4.R_va.mean(), sel_R_ho=sel4.R_ho.mean(), base_ho=ok4.R_ho.mean()))
print(pd.DataFrame(rows, index=["null_1", "null_2", "REAL"]).round(4).to_string())

print("\n===== MARGINAL EFFECT OF EACH PARAMETER VALUE (4h, averaged over all qualifying combos) =====")
print("holdout mean net R by value; 'lift' = value's holdout mean minus the overall holdout mean")
for tf in ("4h", "1h"):
    d = T[tf]; ok = d[(d.n_tr >= 60) & (d.n_va >= 30) & (d.n_ho >= 20) & (d.n_all >= 150)]
    base = ok.R_ho.mean(); out = []
    for p in names:
        for v in sorted(ok[p].unique()):
            sub = ok[ok[p] == v]
            if len(sub) < 200: continue
            out.append(dict(tf=tf, param=p, value=v, combos=len(sub), R_tr=sub.R_tr.mean(), R_va=sub.R_va.mean(), R_ho=sub.R_ho.mean(), lift=sub.R_ho.mean() - base,
                            mkts_pos_ho=sub.mkts_pos_ho.mean(), n_med=sub.n_all.median()))
    M = pd.DataFrame(out); M.to_pickle(f"research_data/search2_marginal_{tf}.pkl")
    print(f"\n--- {tf} (overall holdout mean {base:+.4f}) --- top 12 lifts and bottom 6")
    MM = M.sort_values("lift", ascending=False)
    print(pd.concat([MM.head(12), MM.tail(6)])[["param", "value", "combos", "R_tr", "R_va", "R_ho", "lift", "mkts_pos_ho", "n_med"]].round(4).to_string(index=False))

for tf in T: T[tf].to_pickle(f"research_data/search2_table_{tf}.pkl")
print(f"\ntotal {time.time()-t0:.0f}s")
