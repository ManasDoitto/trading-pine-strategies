"""Make walk-forward AUDIT copies of every BankNifty / CrudeOil strategy file.

Normalises costs so every script is judged the same way (qty 1, 0.02%/side,
no extra slippage) and appends a tiled-window scoreboard that prints
AUD|ticker|tf|from=|last=|nD=|pv=|n,w,sW,sL,dd,d2,pk,mn  (points per lot).
"""
import os, re, glob
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_copies")
BLOCK = r'''
// ===== AUDIT BLOCK (appended for the walk-forward audit; not part of the strategy) =====
var int aud_from = na
if bar_index == 400
    aud_from := (math.floor(time / 86400000.0) + 1) * 86400000
var float aud_n = 0.0
var float aud_w = 0.0
var float aud_sw = 0.0
var float aud_sl = 0.0
var float aud_eq = 0.0
var float aud_pk = 0.0
var float aud_mn = 0.0
var float aud_dd = 0.0
var float aud_d2 = 0.0
var float aud_dayP = 0.0
var int aud_nD = 0
var int aud_dayStart = 0
aud_newDay = ta.change(time("D")) != 0
if aud_newDay
    if not na(aud_from) and aud_dayStart >= aud_from
        aud_nD += 1
        aud_d2 += aud_dayP * aud_dayP
    aud_dayP := 0.0
    aud_dayStart := time
aud_nc = strategy.closedtrades - nz(strategy.closedtrades[1])
if aud_nc > 0
    for aud_k = 0 to aud_nc - 1
        aud_i = strategy.closedtrades - 1 - aud_k
        if not na(aud_from) and strategy.closedtrades.entry_time(aud_i) >= aud_from
            aud_sz = math.abs(strategy.closedtrades.size(aud_i))
            aud_p = strategy.closedtrades.profit(aud_i) / syminfo.pointvalue / (aud_sz > 0 ? aud_sz : 1)
            aud_n += 1
            if aud_p > 0
                aud_w += 1
                aud_sw += aud_p
            else
                aud_sl += aud_p
            aud_eq += aud_p
            aud_pk := math.max(aud_pk, aud_eq)
            aud_mn := math.min(aud_mn, aud_eq)
            aud_dd := math.max(aud_dd, aud_pk - aud_eq)
            aud_dayP += aud_p
if barstate.islastconfirmedhistory or barstate.islast
    var table aud_t = table.new(position.bottom_center, 1, 1, bgcolor=color.new(color.black, 10))
    aud_incl = not na(aud_from) and aud_dayStart >= aud_from
    table.cell(aud_t, 0, 0, "AUD|" + syminfo.ticker + "|" + timeframe.period + "|from=" + str.tostring(aud_from) + "|last=" + str.tostring(time) + "|nD=" + str.tostring(aud_nD + (aud_incl ? 1 : 0)) + "|pv=" + str.tostring(syminfo.pointvalue) + "|" + str.tostring(aud_n) + "," + str.tostring(aud_w) + "," + str.tostring(aud_sw, "#.#") + "," + str.tostring(aud_sl, "#.#") + "," + str.tostring(aud_dd, "#.#") + "," + str.tostring(aud_d2 + (aud_incl ? aud_dayP * aud_dayP : 0), "#.#") + "," + str.tostring(aud_pk, "#.#") + "," + str.tostring(aud_mn, "#.#"), text_color=color.yellow, text_size=size.tiny, text_halign=text.align_left)
'''
skip = ("nifty", "user trade diag", "variant lab")
rows = []
for f in sorted(glob.glob(os.path.join(REPO, "*.pine.txt"))):
    name = os.path.basename(f)
    if name.lower().startswith(skip):
        continue
    src = open(f, encoding="utf-8").read()
    m = re.search(r"//@version=(\d+)", src)
    ver = m.group(1) if m else "?"
    is_strat = re.search(r"^strategy\(", src, re.M) is not None
    sym = "BN" if name.startswith("bnf") else "CRUDE"
    tf = "3" if re.search(r"3 ?min|3m", name) else "5" if re.search(r"5 ?min|5m", name) else "?"
    s2 = re.sub(r"default_qty_value\s*=\s*[\d.]+", "default_qty_value=1", src)
    s2 = re.sub(r"commission_value\s*=\s*[\d.]+", "commission_value=0.02", s2)
    s2 = re.sub(r"slippage\s*=\s*\d+", "slippage=0", s2)
    aid = f"A{len(rows)+1:02d}"
    if is_strat and ver == "5":
        open(os.path.join(OUT, aid + ".pine"), "w", encoding="utf-8").write(s2.rstrip() + "\n" + BLOCK)
    rows.append((aid, sym, tf, ver, is_strat, src.count("\n") + 1, name))
with open(os.path.join(OUT, "manifest.txt"), "w", encoding="utf-8") as fh:
    for r in rows:
        line = "|".join(str(x) for x in r)
        fh.write(line + "\n")
        print(line)
