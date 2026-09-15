import json
from collections import defaultdict, deque
from datetime import datetime

PATH = r"C:\Users\Manas\AppData\Local\Temp\claude\D--Trading-code-Claude\6c946a7d-c9ea-4c87-8de8-e707d932880d\scratchpad\dhan\trade_history_full.json"

with open(PATH, encoding="utf-8") as f:
    trades = json.load(f)

for t in trades:
    t["_dt"] = datetime.fromisoformat(t["exchangeTime"])
    t["_costs"] = (t.get("sebiTax", 0) or 0) + (t.get("stt", 0) or 0) + (t.get("brokerageCharges", 0) or 0) \
        + (t.get("serviceTax", 0) or 0) + (t.get("exchangeTransactionCharges", 0) or 0) + (t.get("stampDuty", 0) or 0)

trades.sort(key=lambda t: t["_dt"])

# FIFO match buys/sells per symbol to get realized round trips
by_symbol = defaultdict(list)
for t in trades:
    by_symbol[t["customSymbol"]].append(t)

closed = []  # each: symbol, side(long/short), entry_time, exit_time, qty, entry_px, exit_px, pnl, costs
for sym, legs in by_symbol.items():
    buys = deque()
    sells = deque()
    for leg in legs:
        qty = leg["tradedQuantity"]
        px = leg["tradedPrice"]
        side = leg["transactionType"]
        cost_per_unit = leg["_costs"] / qty if qty else 0
        remaining = qty
        if side == "BUY":
            # first close any open shorts (sells queue), else open a long
            while remaining > 0 and sells:
                s = sells[0]
                m = min(remaining, s["qty"])
                pnl = (s["px"] - px) * m  # short: sold high, buy back low = profit
                cost = m * (cost_per_unit + s["cost_per_unit"])
                closed.append(dict(symbol=sym, side="SHORT", entry_time=s["time"], exit_time=leg["_dt"],
                                    qty=m, entry_px=s["px"], exit_px=px, gross_pnl=pnl, costs=cost,
                                    net_pnl=pnl - cost, instrument=leg.get("drvOptionType"),
                                    underlying="BANKNIFTY" if "BANKNIFTY" in sym else ("SILVER" if "SILVER" in sym else "CRUDEOIL")))
                s["qty"] -= m
                remaining -= m
                if s["qty"] <= 0:
                    sells.popleft()
            if remaining > 0:
                buys.append(dict(qty=remaining, px=px, time=leg["_dt"], cost_per_unit=cost_per_unit))
        else:  # SELL
            while remaining > 0 and buys:
                b = buys[0]
                m = min(remaining, b["qty"])
                pnl = (px - b["px"]) * m  # long: bought low, sold high = profit
                cost = m * (cost_per_unit + b["cost_per_unit"])
                closed.append(dict(symbol=sym, side="LONG", entry_time=b["time"], exit_time=leg["_dt"],
                                    qty=m, entry_px=b["px"], exit_px=px, gross_pnl=pnl, costs=cost,
                                    net_pnl=pnl - cost, instrument=leg.get("drvOptionType"),
                                    underlying="BANKNIFTY" if "BANKNIFTY" in sym else ("SILVER" if "SILVER" in sym else "CRUDEOIL")))
                b["qty"] -= m
                remaining -= m
                if b["qty"] <= 0:
                    buys.popleft()
            if remaining > 0:
                sells.append(dict(qty=remaining, px=px, time=leg["_dt"], cost_per_unit=cost_per_unit))

closed.sort(key=lambda c: c["exit_time"])

open_legs = []
for sym, legs in by_symbol.items():
    pass  # (open/unmatched positions not computed in detail here; total qty check below)

print(f"Total raw trade legs: {len(trades)}")
print(f"Closed round-trips (FIFO matched): {len(closed)}")

total_net = sum(c["net_pnl"] for c in closed)
total_gross = sum(c["gross_pnl"] for c in closed)
total_costs = sum(c["costs"] for c in closed)
wins = [c for c in closed if c["net_pnl"] > 0]
losses = [c for c in closed if c["net_pnl"] <= 0]
print(f"\n=== OVERALL ===")
print(f"Net P&L: {total_net:,.2f}  (gross {total_gross:,.2f}, costs {total_costs:,.2f})")
print(f"Win rate: {len(wins)}/{len(closed)} = {100*len(wins)/len(closed):.1f}%")
print(f"Avg win: {sum(c['net_pnl'] for c in wins)/len(wins):,.2f}" if wins else "no wins")
print(f"Avg loss: {sum(c['net_pnl'] for c in losses)/len(losses):,.2f}" if losses else "no losses")
if wins and losses:
    pf = sum(c["net_pnl"] for c in wins) / abs(sum(c["net_pnl"] for c in losses))
    print(f"Profit factor: {pf:.2f}")

print(f"\n=== BY UNDERLYING ===")
by_und = defaultdict(list)
for c in closed:
    by_und[c["underlying"]].append(c)
for und, cs in by_und.items():
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    l = [c for c in cs if c["net_pnl"] <= 0]
    pf = (sum(c["net_pnl"] for c in w) / abs(sum(c["net_pnl"] for c in l))) if l and sum(c["net_pnl"] for c in l) != 0 else float('inf')
    print(f"{und}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f} PF={pf:.2f}")

print(f"\n=== BY OPTION SIDE (CALL/PUT) ===")
by_opt = defaultdict(list)
for c in closed:
    by_opt[c["instrument"]].append(c)
for k, cs in by_opt.items():
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    print(f"{k}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f}")

print(f"\n=== BY LONG/SHORT ===")
by_ls = defaultdict(list)
for c in closed:
    by_ls[c["side"]].append(c)
for k, cs in by_ls.items():
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    print(f"{k}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f}")

print(f"\n=== TOP 10 WORST TRADES ===")
for c in sorted(closed, key=lambda c: c["net_pnl"])[:10]:
    hold_min = (c["exit_time"] - c["entry_time"]).total_seconds() / 60
    print(f"{c['exit_time'].date()} {c['symbol']:30s} {c['side']:5s} qty={c['qty']:5.0f} entry={c['entry_px']:8.2f} exit={c['exit_px']:8.2f} net={c['net_pnl']:10,.2f} hold={hold_min:.0f}min")

print(f"\n=== TOP 10 BEST TRADES ===")
for c in sorted(closed, key=lambda c: -c["net_pnl"])[:10]:
    hold_min = (c["exit_time"] - c["entry_time"]).total_seconds() / 60
    print(f"{c['exit_time'].date()} {c['symbol']:30s} {c['side']:5s} qty={c['qty']:5.0f} entry={c['entry_px']:8.2f} exit={c['exit_px']:8.2f} net={c['net_pnl']:10,.2f} hold={hold_min:.0f}min")

print(f"\n=== HOLD TIME BUCKETS ===")
buckets = defaultdict(list)
for c in closed:
    mins = (c["exit_time"] - c["entry_time"]).total_seconds() / 60
    if mins < 5:
        b = "<5min (scalp)"
    elif mins < 30:
        b = "5-30min"
    elif mins < 120:
        b = "30min-2hr"
    elif mins < 1440:
        b = "2hr-1day"
    else:
        b = ">1day"
    buckets[b].append(c)
for b in ["<5min (scalp)", "5-30min", "30min-2hr", "2hr-1day", ">1day"]:
    cs = buckets.get(b, [])
    if not cs:
        continue
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    print(f"{b}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f}")

print(f"\n=== BY DAY OF WEEK ===")
dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
by_dow = defaultdict(list)
for c in closed:
    by_dow[c["exit_time"].weekday()].append(c)
for d in range(7):
    cs = by_dow.get(d, [])
    if not cs:
        continue
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    print(f"{dow_names[d]}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f}")

print(f"\n=== MONTHLY ===")
by_month = defaultdict(list)
for c in closed:
    by_month[c["exit_time"].strftime("%Y-%m")].append(c)
for m in sorted(by_month):
    cs = by_month[m]
    net = sum(c["net_pnl"] for c in cs)
    w = [c for c in cs if c["net_pnl"] > 0]
    print(f"{m}: n={len(cs)} net={net:,.2f} win%={100*len(w)/len(cs):.1f}")

# check unmatched open legs (still-open positions at data end)
print(f"\n=== UNMATCHED (still-open at data end, or unresolved) ===")
open_qty = 0
for sym, legs in by_symbol.items():
    buys = deque()
    sells = deque()
    for leg in legs:
        qty = leg["tradedQuantity"]
        px = leg["tradedPrice"]
        side = leg["transactionType"]
        remaining = qty
        if side == "BUY":
            while remaining > 0 and sells:
                s = sells[0]
                m = min(remaining, s["qty"])
                s["qty"] -= m; remaining -= m
                if s["qty"] <= 0: sells.popleft()
            if remaining > 0:
                buys.append(dict(qty=remaining, px=px))
        else:
            while remaining > 0 and buys:
                b = buys[0]
                m = min(remaining, b["qty"])
                b["qty"] -= m; remaining -= m
                if b["qty"] <= 0: buys.popleft()
            if remaining > 0:
                sells.append(dict(qty=remaining, px=px))
    resid = sum(b["qty"] for b in buys) - sum(s["qty"] for s in sells)
    if resid != 0:
        print(f"{sym}: net open qty = {resid}")
        open_qty += 1
print(f"symbols with residual open position: {open_qty}")

# save closed trades to csv for further reference
import csv
csv_path = r"C:\Users\Manas\AppData\Local\Temp\claude\D--Trading-code-Claude\6c946a7d-c9ea-4c87-8de8-e707d932880d\scratchpad\dhan\closed_trades.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["symbol","underlying","side","instrument","entry_time","exit_time","qty","entry_px","exit_px","gross_pnl","costs","net_pnl"])
    for c in closed:
        w.writerow([c["symbol"], c["underlying"], c["side"], c["instrument"], c["entry_time"], c["exit_time"], c["qty"], c["entry_px"], c["exit_px"], round(c["gross_pnl"],2), round(c["costs"],2), round(c["net_pnl"],2)])
print(f"\nSaved closed trades CSV to {csv_path}")
