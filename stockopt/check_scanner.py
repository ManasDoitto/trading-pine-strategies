"""Consistency check: the live scanner's rule mirror must reproduce every backtest entry.

For each base-breakout trade the kernel took, some bar in the 3 bars before the fill
must carry a scanner signal in the same direction whose trigger the fill respects.
Run:  python -m stockopt.check_scanner [SYMBOL ...]
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import json
import re

from stockopt import engine, run as R  # noqa: E402
from stockopt.scan_live import base_signal, is_aplus, load_spec  # noqa: E402

UNIVERSE = os.path.join(ROOT, "stockopt", "universe.json")


def original_name(sanitized_sym: str) -> str:
    """R.symbols() returns parquet filenames (sanitized, e.g. GVT_D); the live scanner and
    the spec's allowlist both use the real ticker (GVT&D, from universe.json). Only special
    characters differ -- map back before any allowlist comparison."""
    uni = json.load(open(UNIVERSE))
    table = {re.sub(r"[^A-Za-z0-9_.-]", "_", k): k for k in uni}
    return table.get(sanitized_sym, sanitized_sym)


def check(sym: str, cfg: dict) -> tuple[int, int]:
    p = R.load_prep(sym)
    tr = engine.run(p, **cfg)
    tr = tr[tr.setup == 2]
    idx = pd.Index(p["dt"])
    ok = 0
    for t in tr.itertuples():
        ei = idx.get_loc(t.entry_dt)
        hit = False
        for j in range(ei - cfg["arm_bars"], ei):
            d, px, stp = base_signal(p, j, cfg)
            if d == t.dir and (px <= t.entry + 1e-9 if d == 1 else px >= t.entry - 1e-9):
                hit = True
                break
        ok += hit
    return ok, len(tr)


def check_aplus(sym: str, cfg: dict, spec: dict) -> tuple[int, int]:
    """The scanner's is_aplus() (rel-strength gate + allowlist) must classify every bar
    exactly as engine.run() with the A+ kernel config would, filtered to allowlist symbols
    -- this is the scanner-vs-backtest sync that the 2026-09-29 allowlist depends on.

    For a symbol ON the allowlist: every kernel A+ trade must have a matching scanner
    is_aplus() signal, same as check(). For a symbol OFF the allowlist: is_aplus() must
    never fire, however the kernel's rel-strength-only signal reads at any bar.
    """
    p = R.load_prep(sym)
    real = original_name(sym)  # is_aplus() and the spec's allowlist both use the real ticker
    on_list = real in (spec["aplus"].get("symbol_allowlist") or [real])

    if not on_list:
        n = sum(
            1 for i in range(p["warm"], len(p["c"]))
            for d_ in (1, -1)
            if is_aplus(real, d_, p, i, spec)
        )
        return (0 if n else 1), 1  # 1 "trade" = the whole-symbol assertion; ok iff never fired

    aplus_cfg = dict(cfg)
    aplus_cfg.update(spec["aplus"])
    tr = engine.run(p, **aplus_cfg)
    tr = tr[tr.setup == 2]
    idx = pd.Index(p["dt"])
    ok = 0
    for t in tr.itertuples():
        ei = idx.get_loc(t.entry_dt)
        hit = False
        for j in range(ei - cfg["arm_bars"], ei):
            d_, px, stp_ = base_signal(p, j, cfg)
            if d_ == t.dir and is_aplus(real, d_, p, j, spec) and \
                    (px <= t.entry + 1e-9 if d_ == 1 else px >= t.entry - 1e-9):
                hit = True
                break
        ok += hit
    return ok, len(tr)


if __name__ == "__main__":
    spec = load_spec()
    cfg = dict(engine.DEFAULTS)
    cfg.update(spec["kernel"])
    syms = sys.argv[1:] or R.symbols()[:12]
    tot_ok = tot = 0
    for s in syms:
        ok, n = check(s, cfg)
        tot_ok += ok
        tot += n
        print(f"{s:12s} {ok}/{n}")
    print(f"MATCH {tot_ok}/{tot} = {100.0 * tot_ok / max(tot, 1):.2f}%")

    print("\n--- A+ allowlist sync ---")
    a_ok = a_tot = 0
    for s in syms:
        ok, n = check_aplus(s, cfg, spec)
        a_ok += ok
        a_tot += n
        print(f"{s:12s} {ok}/{n}")
    print(f"A+ MATCH {a_ok}/{a_tot} = {100.0 * a_ok / max(a_tot, 1):.2f}%")
