"""Stage 3: report. Selection uses TRAIN (entries < 2022-01-01) only; TEST (>= 2022-01-01) is judged afterwards."""
import sys, pickle
import numpy as np, pandas as pd
import gold_all_strategies as G

PKL = sys.argv[1] if len(sys.argv) > 1 else str(G.ROOT / "research_data" / "gold" / "repo_modules_trades.pkl")
COST_KEY = sys.argv[2] if len(sys.argv) > 2 else "$1.00"
cost = [v for k, v in G.COSTS.items() if k.startswith(COST_KEY)][0]
res = pickle.load(open(PKL, "rb"))
rows = []
for (grp, tag, sess), t in res.items():
    t0_n = len(t); t = G.clean(t)
    if len(t) < 30:
        rows.append(dict(grp=grp, tag=tag, sess=sess, n=len(t))); continue
    s = G.stat_row(t, cost); s.update(grp=grp, tag=tag, sess=sess, dropped=t0_n - len(t))
    # long vs short test R
    r = G.summarize(t, cost); te = t["entry_time"] >= G.SPLIT
    s["R_te_long"] = r[te & (t.side_n == 1)].mean() if (te & (t.side_n == 1)).any() else np.nan
    s["R_te_short"] = r[te & (t.side_n == -1)].mean() if (te & (t.side_n == -1)).any() else np.nan
    rows.append(s)
R = pd.DataFrame(rows)
ok = R.dropna(subset=["R_tr", "R_te"]).copy()
ok = ok[(ok.n_tr >= 30) & (ok.n_te >= 30)]
print(f"cost scenario {COST_KEY} {cost} | strategies x session runs with enough trades: {len(ok)} of {len(R)}")
print(f"net R POSITIVE in train: {(ok.R_tr>0).mean():.0%} | in test: {(ok.R_te>0).mean():.0%} | BOTH: {((ok.R_tr>0)&(ok.R_te>0)).mean():.0%}  "
      f"(if all were pure noise ~25% would be positive in both)")
print(f"median net R: train {ok.R_tr.median():+.3f}  test {ok.R_te.median():+.3f}   median gross R {ok.gross_R.median():+.3f}")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400)
cols = ["grp", "tag", "sess", "n", "per_wk", "win", "gross_R", "net_R", "n_tr", "R_tr", "n_te", "R_te", "t_te", "R_te_long", "R_te_short", "hold_h"]
fmt = lambda d: d[cols].round(3).to_string(index=False)
print("\n=== TOP 15 by TRAIN net R (min 30 trades each side of split) -> what they did in TEST ===")
print(fmt(ok.sort_values("R_tr", ascending=False).head(15)))
print("\n=== of strategies positive in TRAIN, share still positive in TEST:",
      f"{(ok[ok.R_tr>0].R_te>0).mean():.0%} (n={len(ok[ok.R_tr>0])})")
print("\n=== MOST FREQUENT (>= 3 trades/week): best test net R ===")
fq = ok[ok.per_wk >= 3].sort_values("R_te", ascending=False).head(10); print(fmt(fq))
print("\n=== best 10 in TEST by hindsight (NOT tradable selection) ===")
print(fmt(ok.sort_values("R_te", ascending=False).head(10)))
R.to_csv(str(G.ROOT / "research_data" / "gold" / "report_table.csv"), index=False)
