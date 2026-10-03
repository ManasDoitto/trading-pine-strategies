"""Stage 1+2 runner (parallel): every repo strategy family + extras on gold, two session regimes, trades stored.
Each worker process builds the gold frames once (initializer) and then executes (job, session) tasks."""
import sys, os, time, pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np, pandas as pd
import gold_all_strategies as G
import gold_extra_strategies as E
from gold_all_strategies import B, X, N, rs

OUT = G.ROOT / "research_data" / "gold" / os.environ.get("GOLD_OUT", "repo_modules_trades.pkl")
SESSIONS = (("ALL24h", G.ANY_TIME), ("ACTIVE", G.ACTIVE))
_EXTRA = {}

def job_list():
    jobs = []
    for tag, v in B.ALL.items(): jobs.append(("port", tag, v, "5"))
    for tag, v in X.CONFIGS.items(): jobs.append(("scratch", tag, v, "5"))
    for name in N.NAMES: jobs.append(("newfam", name, dict(name=name, rr=1.5, time_stop=30), "5"))
    for tag, v in B.ALL.items(): jobs.append(("port15", tag, v, "15"))
    return jobs

def init_worker():
    d1 = G.load_1m()
    for tf, mins in (("5", 5), ("15", 15)):
        B._D[(G.INST, tf)] = G.make_base(G.resample(d1, mins))
    _EXTRA.update(E.build_extra_signals(B._D[(G.INST, "5")]))

def run_task(task):
    kind, ref, sess_name = task
    sess = dict(SESSIONS)[sess_name]
    try:
        if kind == "repo":
            grp, tag, v, tf = ref
            G.set_session(sess)
            fn = {"port": B.sim, "port15": B.sim, "scratch": X.sim, "newfam": N.sim}[grp]
            return (grp, tag, sess_name), G.trades_to_frame(fn(v, tf, 0.0, G.INST)), None
        L, S, rl, rsx, rr, ts, mpd = _EXTRA[ref]
        d5 = B._D[(G.INST, "5")]
        L = L if isinstance(L, pd.Series) else pd.Series(L, index=d5.index)
        S = S if isinstance(S, pd.Series) else pd.Series(S, index=d5.index)
        return (ref[0], ref[1], sess_name), G.trades_to_frame(E.run_frame(d5, L, S, rl, rsx, rr, sess, ts, mpd)), None
    except Exception as e:
        return (kind, str(ref)[:60], sess_name), pd.DataFrame(), repr(e)[:200]

def main(workers=3):
    t0 = time.time()
    jobs = job_list()
    extra_keys = [("lab", f"V{v+1:02d}") for v in range(32)] + [("v50", t) for t in (
        "v5.0 flip CRUDE params", "v5.0 breakout CRUDE params", "v5.0 flip SILVER params", "v5.0 flip BANKNIFTY params",
        "v5.3 loose sweep-winner", "v5.2 flip+BO HMA55 (SILVER cfg)")] + [("scalp", "supertrend live params"), ("scalp", "tenkan live params")] + [
        ("session", t) for t in ("VWAP drift pullback RR1.5", "VWAP drift pullback 2:1-against (RR0.5)", "RSI14 20/80 fade",
                                  "Donchian12 breakout RR1.5", "Donchian36 breakout RR1.5")]
    tasks = [("repo", j, s) for s, _ in SESSIONS for j in jobs] + [("extra", k, s) for s, _ in SESSIONS for k in extra_keys]
    if os.environ.get("SMOKE"):
        tasks = tasks[:2] + [t for t in tasks if t[0] == "extra"][:3]
    print(f"{len(tasks)} tasks, {workers} workers", flush=True)
    res, fails = {}, []
    with ProcessPoolExecutor(workers, initializer=init_worker) as ex:
        futs = [ex.submit(run_task, t) for t in tasks]
        for k, f in enumerate(as_completed(futs)):
            key, t, err = f.result()
            if err: fails.append((key, err)); print("FAIL", key, err, flush=True)
            else: res[key] = t
            if k % 10 == 0:
                print(f"{k+1}/{len(tasks)} done {time.time()-t0:.0f}s", flush=True); pickle.dump(res, open(OUT, "wb"))
    pickle.dump(res, open(OUT, "wb"))
    print("DONE", len(res), "ok,", len(fails), "failed", f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()
