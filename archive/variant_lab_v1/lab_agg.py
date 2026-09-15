"""Aggregate VARIANT LAB v1 window dumps into per-instrument/per-TF results.

Input: lab_raw.txt -- blocks of one 'LAB|sym|tf|first=..|from=..|last=..|nD=..|uIn=..'
header followed by 32 'Vnn|n|w|sumW|sumL|cost|maxDD|sumDaily^2|caught' rows.
Windows tile exactly (each counts trades from its own UTC-midnight 'from').
"""
import json, math, sys, os
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "lab_raw_window_dumps.txt")

LABEL = {
 1: "v3.0 final (SHA+RSI3 pb, 30/70, RR2.4)", 2: "v3.0 + EOD flat", 3: "v3.0 RR1.5",
 4: "v3.0 RR2.0", 5: "v3.0 RR3.0", 6: "v3.0 + EMA200", 7: "v3.0 trig RSI>50",
 8: "v3.0 trig high-break", 9: "v3.0 RSI 20/80", 10: "v3.0 RSI 40/60",
 11: "v3.0 minSL 1.2", 12: "v3.0 max 2/day", 13: "v3.0 no SHA-age",
 14: "v3.0 pullback win 6", 15: "v3.0 no EMA9/22", 16: "v3.0 EOD+2/day+RR2",
 17: "EMA-touch pb RR2 (crude v1 idea)", 18: "EMA-touch +SHA RR2.4", 19: "EMA-touch RR1.5 EOD",
 20: "SHA flip RR2", 21: "SHA flip RR3", 22: "SHA flip +EMA200 RR2",
 23: "Donchian20 +SHA RR2", 24: "Donchian20 +SHA RR3", 25: "Donchian10 +SHA RR2",
 26: "RSI3 snap-back 10/90 RR1", 27: "RSI3 snap-back 5/95 RR1.5",
 28: "Sweep-fade RR2 (BN v13 idea)", 29: "Sweep-fade RR3", 30: "Sweep-fade RR6",
 31: "Sweep with-trend (SHA) RR2", 32: "v3.0-lite EOD minSL1.5 RR2",
}
FAMILY = {**{i: "A SHA+RSI3 pullback" for i in list(range(1, 17)) + [32]},
          17: "B EMA-touch", 18: "B EMA-touch", 19: "B EMA-touch",
          20: "C SHA flip", 21: "C SHA flip", 22: "C SHA flip",
          23: "D Breakout", 24: "D Breakout", 25: "D Breakout",
          26: "E RSI3 snap-back", 27: "E RSI3 snap-back",
          28: "F Sweep-fade", 29: "F Sweep-fade", 30: "F Sweep-fade", 31: "F Sweep-fade"}


def parse():
    blocks, cur = [], None
    for line in open(RAW, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("LAB|"):
            p = line.split("|")
            kv = dict(x.split("=") for x in p[3:])
            cur = {"sym": p[1], "tf": p[2], **{k: int(float(v)) for k, v in kv.items()}, "rows": {}}
            blocks.append(cur)
        elif line.startswith("V"):
            p = line.split("|")
            cur["rows"][int(p[0][1:])] = [float(x) for x in p[1:]]
    return blocks


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def aggregate(blocks):
    out = {}
    groups = defaultdict(list)
    for b in blocks:
        groups[(b["sym"], b["tf"])].append(b)
    for key, bl in groups.items():
        bl.sort(key=lambda b: b["from"])
        # tiling check: each window's 'last' must be < next window's 'from'
        overlaps = [(ts(a["last"]), ts(c["from"])) for a, c in zip(bl, bl[1:]) if a["last"] >= c["from"]]
        start, end = bl[0]["from"], bl[-1]["last"]
        months = (end - start) / (1000 * 86400 * 30.44)
        nD = sum(b["nD"] for b in bl)
        uIn = sum(b["uIn"] for b in bl)
        res = {}
        for v in range(1, 33):
            n = w = sW = sL = cost = sD2 = caught = 0.0
            dd = 0.0
            wins_pos = 0
            wnet = []
            for b in bl:
                r = b["rows"][v]
                n += r[0]; w += r[1]; sW += r[2]; sL += r[3]; cost += r[4]
                dd = max(dd, r[5]); sD2 += r[6]; caught += r[7]
                wn = r[2] + r[3]
                wnet.append(round(wn))
                wins_pos += wn > 0
            net = sW + sL
            mean = net / nD if nD else 0
            var = sD2 / nD - mean * mean if nD else 0
            sharpe = mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0
            avgPx = cost / (0.0004 * n) if n else 0
            res[v] = {
                "n": int(n), "tpm": n / months if months else 0,
                "win": 100 * w / n if n else 0,
                "pf": sW / -sL if sL < 0 else float("inf"),
                "net": net, "gross": net + cost, "cost": cost,
                "avgW": sW / w if w else 0, "avgL": sL / (n - w) if n > w else 0,
                "bps": (net / n) / avgPx * 1e4 if n and avgPx else 0,
                "sharpe": sharpe, "worstDD": dd, "posWin": int(wins_pos),
                "nWin": len(bl), "wnet": wnet, "caught": int(caught),
            }
        out[f"{key[0]} {key[1]}m"] = {"start": ts(start), "end": ts(end), "months": months,
                                      "days": nD, "uIn": uIn, "overlaps": overlaps,
                                      "windows": len(bl), "res": res}
    return out


def md(out):
    lines = []
    for k, g in out.items():
        lines.append(f"\n### {k}  ({g['start']} -> {g['end']}, {g['months']:.1f} months, "
                     f"{g['windows']} windows, {g['days']} trading days"
                     + (f", user trades in range {g['uIn']}" if g['uIn'] else "") + ")")
        if g["overlaps"]:
            lines.append(f"WARNING overlaps: {g['overlaps']}")
        lines.append("| # | Variant | Trades | /month | Win% | PF | Net pts | bps/trade | Sharpe(d) | Worst-win DD | +windows | Caught |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        order = sorted(g["res"], key=lambda v: -g["res"][v]["sharpe"])
        for v in order:
            r = g["res"][v]
            lines.append(f"| V{v:02d} | {LABEL[v]} | {r['n']} | {r['tpm']:.0f} | {r['win']:.1f} | {r['pf']:.2f} | "
                         f"{r['net']:+,.0f} | {r['bps']:+.1f} | {r['sharpe']:+.2f} | {r['worstDD']:,.0f} | "
                         f"{r['posWin']}/{r['nWin']} | {r['caught'] if g['uIn'] else '-'} |")
    return "\n".join(lines)


if __name__ == "__main__":
    out = aggregate(parse())
    json.dump(out, open(os.path.join(HERE, "lab_agg.json"), "w"), indent=1, default=str)
    print(md(out) if "--md" in sys.argv else "\n".join(
        f"{k}: {g['windows']} win, {g['start']}->{g['end']}, overlaps={g['overlaps']}" for k, g in out.items()))
