import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))

trades = json.loads(r'''[{"side":"L","entryTm":1782119400000,"entryPx":237909,"exitTm":1782138600000,"exitPx":236573,"exitType":"lx","pnl":-42926.89},{"side":"S","entryTm":1782212700000,"entryPx":226742,"exitTm":1782274200000,"exitPx":222011,"exitType":"sx","pnl":139237.48},{"side":"S","entryTm":1782312300000,"entryPx":218285,"exitTm":1782358200000,"exitPx":210308,"exitType":"sx","pnl":236738.44},{"side":"S","entryTm":1782362700000,"entryPx":213784,"exitTm":1782374400000,"exitPx":216139,"exitType":"sx","pnl":-73229.54},{"side":"L","entryTm":1782397500000,"entryPx":220126,"exitTm":1782801000000,"exitPx":227643,"exitType":"lx","pnl":222823.39},{"side":"L","entryTm":1782811500000,"entryPx":225980,"exitTm":1782828900000,"exitPx":229534,"exitType":"lx","pnl":103886.914},{"side":"L","entryTm":1782912600000,"entryPx":228520,"exitTm":1782995400000,"exitPx":233488,"exitType":"lx","pnl":146267.95},{"side":"L","entryTm":1783061700000,"entryPx":237424,"exitTm":1783081200000,"exitPx":236976,"exitType":"lx","pnl":-16286.4},{"side":"S","entryTm":1783317600000,"entryPx":235997,"exitTm":1783323600000,"exitPx":236934,"exitType":"sx","pnl":-30947.586},{"side":"S","entryTm":1783410600000,"entryPx":231774,"exitTm":1783426200000,"exitPx":232832,"exitType":"sx","pnl":-34527.637},{"side":"S","entryTm":1783494600000,"entryPx":230002,"exitTm":1783499400000,"exitPx":227149,"exitType":"sx","pnl":82847.09},{"side":"S","entryTm":1783517400000,"entryPx":223716,"exitTm":1783576800000,"exitPx":225102,"exitType":"sx","pnl":-44272.906},{"side":"S","entryTm":1783655400000,"entryPx":226048,"exitTm":1783661700000,"exitPx":222930,"exitType":"sx","pnl":90846.13},{"side":"S","entryTm":1783681500000,"entryPx":222597,"exitTm":1783685700000,"exitPx":223629,"exitType":"sx","pnl":-33637.355},{"side":"L","entryTm":1783686300000,"entryPx":222805,"exitTm":1783693800000,"exitPx":221834,"exitType":"lx","pnl":-31797.834},{"side":"S","entryTm":1783694700000,"entryPx":222750,"exitTm":1783913400000,"exitPx":218651,"exitType":"sx","pnl":120321.59},{"side":"S","entryTm":1783922400000,"entryPx":218705,"exitTm":1783928100000,"exitPx":219844,"exitType":"sx","pnl":-36801.293},{"side":"L","entryTm":1783942800000,"entryPx":220409,"exitTm":1783950600000,"exitPx":219326,"exitType":"lx","pnl":-35128.41},{"side":"S","entryTm":1783957800000,"entryPx":218668,"exitTm":1784003700000,"exitPx":219765,"exitType":"sx","pnl":-35540.598},{"side":"S","entryTm":1784093100000,"entryPx":222470,"exitTm":1784100900000,"exitPx":220562,"exitType":"sx","pnl":54581.81},{"side":"S","entryTm":1784111700000,"entryPx":220800,"exitTm":1784117700000,"exitPx":221717,"exitType":"sx","pnl":-30165.102},{"side":"S","entryTm":1784174400000,"entryPx":219753,"exitTm":1784206500000,"exitPx":216133,"exitType":"sx","pnl":105984.69},{"side":"S","entryTm":1784214600000,"entryPx":216667,"exitTm":1784518200000,"exitPx":220080,"exitType":"sx","pnl":-105010.484},{"side":"L","entryTm":1784623800000,"entryPx":223361,"exitTm":1784631600000,"exitPx":222703,"exitType":"lx","pnl":-22416.385},{"side":"S","entryTm":1784702100000,"entryPx":225615,"exitTm":1784727000000,"exitPx":226512,"exitType":"sx","pnl":-29622.762},{"side":"S","entryTm":1784787300000,"entryPx":225909,"exitTm":1784790600000,"exitPx":223914,"exitType":"sx","pnl":57151.062},{"side":"S","entryTm":1784799300000,"entryPx":222778,"exitTm":1784811000000,"exitPx":220399,"exitType":"sx","pnl":68710.94},{"side":"S","entryTm":1784819100000,"entryPx":219664,"exitTm":1784876700000,"exitPx":220822,"exitType":"sx","pnl":-37382.914},{"side":"S","entryTm":1785138900000,"entryPx":224000,"exitTm":1785209400000,"exitPx":216592,"exitType":"sx","pnl":219596.45},{"side":"S","entryTm":1785226500000,"entryPx":216984,"exitTm":1785303000000,"exitPx":217979,"exitType":"sx","pnl":-32459.777},{"side":"S","entryTm":1785398100000,"entryPx":215970,"exitTm":1785399600000,"exitPx":216883,"exitType":"sx","pnl":-29987.117},{"side":"S","entryTm":1785477300000,"entryPx":218832,"exitTm":1785762000000,"exitPx":215293,"exitType":"sx","pnl":103565.25},{"side":"L","entryTm":1785827700000,"entryPx":219580,"exitTm":1785834300000,"exitPx":219079,"exitType":"lx","pnl":-17661.953},{"side":"L","entryTm":1785923400000,"entryPx":226328,"exitTm":1785924000000,"exitPx":225786,"exitType":"lx","pnl":-18972.684},{"side":"S","entryTm":1785993900000,"entryPx":227287,"exitTm":1786006800000,"exitPx":228144,"exitType":"sx","pnl":-28442.586},{"side":"S","entryTm":1786109100000,"entryPx":233544,"exitTm":1786372500000,"exitPx":235536,"exitType":"sx","pnl":-62574.48},{"side":"S","entryTm":1786451400000,"entryPx":236501,"exitTm":1786505400000,"exitPx":237973,"exitType":"sx","pnl":-47006.844},{"side":"S","entryTm":1786600500000,"entryPx":235998,"exitTm":1786717500000,"exitPx":237749,"exitType":"sx","pnl":-55372.48},{"side":"L","entryTm":1786953000000,"entryPx":238002,"exitTm":1786953900000,"exitPx":237338,"exitType":"lx","pnl":-22772.04},{"side":"S","entryTm":1787039100000,"entryPx":235777,"exitTm":1787064000000,"exitPx":233580,"exitType":"sx","pnl":63093.86},{"side":"S","entryTm":1787075700000,"entryPx":232549,"exitTm":1787110200000,"exitPx":229945,"exitType":"sx","pnl":75345.04},{"side":"L","entryTm":1787133300000,"entryPx":229700,"exitTm":1787141400000,"exitPx":231013,"exitType":"lx","pnl":36625.723},{"side":"L","entryTm":1787196600000,"entryPx":240041,"exitTm":1787196600000,"exitPx":240041,"exitType":"lx","pnl":-2880.492},{"side":"L","entryTm":1787207100000,"entryPx":239736,"exitTm":1787226300000,"exitPx":238537,"exitType":"lx","pnl":-38839.637},{"side":"L","entryTm":1787298600000,"entryPx":246150,"exitTm":1787542200000,"exitPx":245066,"exitType":"lx","pnl":-35467.297},{"side":"S","entryTm":1787643600000,"entryPx":243675,"exitTm":1787664300000,"exitPx":240886,"exitType":"sx","pnl":80762.63},{"side":"S","entryTm":1787739300000,"entryPx":243151,"exitTm":1787745600000,"exitPx":243991,"exitType":"sx","pnl":-28122.852},{"side":"S","entryTm":1787809500000,"entryPx":238989,"exitTm":1787845800000,"exitPx":240823,"exitType":"sx","pnl":-57898.87},{"side":"S","entryTm":1787895600000,"entryPx":239695,"exitTm":1787897700000,"exitPx":240329,"exitType":"sx","pnl":-21900.145},{"side":"S","entryTm":1788179700000,"entryPx":241824,"exitTm":1788249900000,"exitPx":238338,"exitType":"sx","pnl":101699.03},{"side":"S","entryTm":1788261900000,"entryPx":235963,"exitTm":1788277800000,"exitPx":237079,"exitType":"sx","pnl":-36318.254},{"side":"S","entryTm":1788280800000,"entryPx":236070,"exitTm":1788406200000,"exitPx":238610,"exitType":"sx","pnl":-79048.08},{"side":"S","entryTm":1788520800000,"entryPx":241029,"exitTm":1788524700000,"exitPx":241688,"exitType":"sx","pnl":-22666.303},{"side":"L","entryTm":1788759300000,"entryPx":237625,"exitTm":1788760500000,"exitPx":236569,"exitType":"lx","pnl":-34525.164},{"side":"S","entryTm":1788865800000,"entryPx":238500,"exitTm":1788867300000,"exitPx":239409,"exitType":"sx","pnl":-30137.453},{"side":"L","entryTm":1788925800000,"entryPx":239474,"exitTm":1788959700000,"exitPx":241626,"exitType":"lx","pnl":61673.4},{"side":"S","entryTm":1788967200000,"entryPx":241271,"exitTm":1788973500000,"exitPx":244967,"exitType":"sx","pnl":-113797.43},{"side":"L","entryTm":1789017600000,"entryPx":243789,"exitTm":1789024500000,"exitPx":242876,"exitType":"lx","pnl":-30309.99},{"side":"L","entryTm":1789111200000,"entryPx":233635,"exitTm":1789119600000,"exitPx":232718,"exitType":"lx","pnl":-30308.117},{"side":"L","entryTm":1789465800000,"entryPx":230697,"exitTm":1789476600000,"exitPx":233286,"exitType":"lx","pnl":74886.1},{"side":"S","entryTm":1789489200000,"entryPx":231724,"exitTm":1789494900000,"exitPx":232068,"exitType":"sx","pnl":-13102.752}]''')

for t in trades:
    t["_entry_dt"] = datetime.fromtimestamp(t["entryTm"]/1000, tz=IST)
    t["_exit_dt"] = datetime.fromtimestamp(t["exitTm"]/1000, tz=IST)
    t["_hold_min"] = (t["exitTm"] - t["entryTm"]) / 60000

print(f"Total trades: {len(trades)}")
total_pnl = sum(t["pnl"] for t in trades)
print(f"Total P&L: {total_pnl:,.0f}")
print()

# By entry hour (IST)
print("=== By entry hour (IST) ===")
by_hour = defaultdict(list)
for t in trades:
    by_hour[t["_entry_dt"].hour].append(t)
for h in sorted(by_hour):
    cs = by_hour[h]
    net = sum(c["pnl"] for c in cs)
    wins = [c for c in cs if c["pnl"] > 0]
    print(f"{h:02d}:00-{h:02d}:59  n={len(cs):2d}  net={net:11,.0f}  win%={100*len(wins)/len(cs):5.1f}")

print()
print("=== By day of week ===")
dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
by_dow = defaultdict(list)
for t in trades:
    by_dow[t["_entry_dt"].weekday()].append(t)
for d in range(7):
    cs = by_dow.get(d, [])
    if not cs: continue
    net = sum(c["pnl"] for c in cs)
    wins = [c for c in cs if c["pnl"] > 0]
    print(f"{dow_names[d]}: n={len(cs):2d}  net={net:11,.0f}  win%={100*len(wins)/len(cs):5.1f}")

print()
print("=== By hold-time bucket ===")
buckets = defaultdict(list)
for t in trades:
    m = t["_hold_min"]
    if m < 30: b = "<30min"
    elif m < 120: b = "30min-2hr"
    elif m < 360: b = "2-6hr"
    elif m < 1440: b = "6-24hr"
    else: b = ">1day"
    buckets[b].append(t)
for b in ["<30min","30min-2hr","2-6hr","6-24hr",">1day"]:
    cs = buckets.get(b, [])
    if not cs: continue
    net = sum(c["pnl"] for c in cs)
    wins = [c for c in cs if c["pnl"] > 0]
    print(f"{b:10s}: n={len(cs):2d}  net={net:11,.0f}  win%={100*len(wins)/len(cs):5.1f}")

print()
print("=== First trade of each day: how many minutes after session open (09:15)? ===")
by_day = defaultdict(list)
for t in trades:
    by_day[t["_entry_dt"].date()].append(t)
first_trade_offsets = []
for day, cs in sorted(by_day.items()):
    cs.sort(key=lambda t: t["_entry_dt"])
    first = cs[0]
    session_open = first["_entry_dt"].replace(hour=9, minute=15, second=0, microsecond=0)
    mins_after_open = (first["_entry_dt"] - session_open).total_seconds() / 60
    first_trade_offsets.append(mins_after_open)
avg_offset = sum(first_trade_offsets) / len(first_trade_offsets)
print(f"n days with a trade: {len(first_trade_offsets)}")
print(f"avg minutes after 09:15 session open for first trade of the day: {avg_offset:.0f} min ({avg_offset/60:.1f} hrs)")
print(f"median-ish spread: min={min(first_trade_offsets):.0f}min, max={max(first_trade_offsets):.0f}min")
late_days = [o for o in first_trade_offsets if o > 240]
print(f"days where first trade came >4hrs after open: {len(late_days)} of {len(first_trade_offsets)}")
