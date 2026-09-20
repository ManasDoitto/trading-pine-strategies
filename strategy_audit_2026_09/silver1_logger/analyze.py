"""Offline re-simulation + enhancement screen for the SILVER1! baseline, from the v12 signal-path log.

Usage: python analyze.py <best.json> [out.txt]

Signal record fields (comma-separated): dir,sigSec,close,atr,rawRisk,sep,dist,atrRatio,runup20,rangeAtr,body,regAge,
sigBar,fill,barsTracked, favHit[48] (fav excursion >= 0.5,1.0..24 ATR), advHit[23] (adverse >= 1.0,1.25..6.5 ATR),
beRet[7] (offset when price returned to entry after fav reached 1,2,3,4,5,6,8 ATR), cx[7] (close excursion at bars 6,12,24,48,96,192,288).
Excursions are from the SIGNAL CLOSE in ATR-at-signal units. Grid resolution is handled conservatively
(stops: earlier grid level, targets: later grid level), so every variant, baseline included, is slightly pessimistic.
"""
import json, math, sys, bisect
from collections import defaultdict

SPLIT = 1743465600  # 2025-04-01 00:00 UTC: train = signals before, holdout = after
COMM = 0.0002       # 0.02% per side of price (matches the strategy tester's points)
BE_LV = [1, 2, 3, 4, 5, 6, 8]
CP_OFF = [6, 12, 24, 48, 96, 192, 288]


def load(path):
    snap = json.load(open(path))
    sigs = []
    for r in snap['recs']:
        p = r.split(',')
        f = lambda x: float(x)
        fav = [int(x) for x in p[15].split(':')]
        adv = [int(x) for x in p[16].split(':')]
        be = [int(x) for x in p[17].split(':')]
        cx = [float(x) for x in p[18].split(':')]
        sigs.append(dict(dir=int(p[0]), sec=int(p[1]), close=f(p[2]), atr=f(p[3]), raw=f(p[4]), sep=f(p[5]), dist=f(p[6]),
                         atrRatio=f(p[7]), runup=f(p[8]), rng=f(p[9]), body=f(p[10]), regAge=int(p[11]), bar=int(p[12]),
                         fill=f(p[13]), tracked=int(p[14]), fav=fav, adv=adv, be=be, cx=cx))
    sigs.sort(key=lambda s: s['bar'])
    days = sorted((int(a), int(b)) for a, b in (d.split(',') for d in snap['days']))
    act = [tuple(float(x) for x in a.split(',')) for a in snap['act']]
    return snap, sigs, days, act


class Cal:
    def __init__(self, days):
        self.bars = [d[0] for d in days]
        self.secs = [d[1] for d in days]

    def sec(self, bar):
        i = max(0, bisect.bisect_right(self.bars, bar) - 1)
        return self.secs[i] + (bar - self.bars[i]) * 300

    def day(self, bar):
        return (self.sec(bar) + 19800) // 86400


def ist(sec):
    t = sec + 19800
    return (t // 3600) % 24, (t // 86400 + 3) % 7  # hour, weekday (Mon=0)


def outcome(s, cfg):
    """returns (pnl, exitOffset) or None (skipped)."""
    a, c, d, fill = s['atr'], s['close'], s['dir'], s['fill']
    R = max(s['raw'], cfg['minSL'] * a)
    if R > cfg['maxSL'] * a:
        return None
    sA, tA = R / a, cfg['rr'] * R / a
    i = min(22, max(0, int(math.floor((sA - 1.0) / 0.25 + 1e-9)))) if sA >= 1.0 else 0
    tStop = s['adv'][i] if sA <= 6.5 else -1
    j = int(math.ceil(tA / 0.5 - 1e-9)) - 1
    tTgt = s['fav'][j] if 0 <= j < 48 else -1
    beT = cfg.get('be')
    tBE = -1
    if beT is not None:
        k = BE_LV.index(beT)
        tBE = s['be'][k]
        kf = int(math.ceil(beT / 0.5 - 1e-9)) - 1
        tTrig = s['fav'][kf]
    tm = cfg.get('tstop')
    tTime = -1
    if tm is not None:
        tTime = tm
    events = []
    if tStop >= 0:
        events.append((tStop, 0, 'stop'))
    if tTgt >= 0:
        events.append((tTgt, 1, 'tgt'))
    if beT is not None and tBE >= 0 and tTrig >= 0 and (tStop < 0 or tTrig < tStop):
        events.append((tBE, 0.5, 'be'))  # BE stop only valid once trigger reached; same-bar counted as stopped
    if tTime > 0:
        events.append((tTime, 2, 'time'))
    if not events:
        ex = s['cx'][-1] if not math.isnan(s['cx'][-1]) else 0.0
        px = c + d * ex * a
        return d * (px - fill) - COMM * (fill + px), max(s['tracked'], 1)
    events.sort()
    off, _, kind = events[0]
    if kind == 'stop':
        px = c - d * R
    elif kind == 'tgt':
        px = c + d * cfg['rr'] * R
    elif kind == 'be':
        px = c
    else:
        q = CP_OFF.index(tm)
        ex = s['cx'][q]
        px = c + d * (0.0 if math.isnan(ex) else ex) * a
    return d * (px - fill) - COMM * (fill + px), max(off, 1)


def simulate(sigs, cal, cfg, keep=None):
    trades, closed = [], []  # closed: (exitBar, day, pnl)
    busy_until = -1
    for s in sigs:
        if keep is not None and not keep(s):
            continue
        if s['bar'] < busy_until:
            continue
        lim = cfg.get('dayLimit')
        if lim:
            sd = cal.day(s['bar'])
            tot = sum(p for (eb, dy, p) in closed if dy == sd and eb <= s['bar'])
            if tot <= -lim:
                continue
        o = outcome(s, cfg)
        if o is None:
            continue
        pnl, off = o
        eb = s['bar'] + off
        busy_until = eb
        closed.append((eb, cal.day(eb), pnl))
        trades.append(dict(sec=s['sec'], bar=s['bar'], exit=eb, pnl=pnl, dir=s['dir']))
    return trades


def metrics(tr):
    if not tr:
        return dict(n=0, net=0, pf=0, dd=0, win=0)
    sw = sum(t['pnl'] for t in tr if t['pnl'] > 0)
    sl = -sum(t['pnl'] for t in tr if t['pnl'] <= 0)
    eq = pk = dd = 0.0
    for t in sorted(tr, key=lambda x: x['exit']):
        eq += t['pnl']
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dict(n=len(tr), net=sw - sl, pf=(sw / sl if sl > 0 else 99), dd=dd, win=100.0 * sum(1 for t in tr if t['pnl'] > 0) / len(tr))


def split(tr):
    return metrics([t for t in tr if t['sec'] < SPLIT]), metrics([t for t in tr if t['sec'] >= SPLIT])


def fmt(m):
    return f"n={m['n']:4d} net={m['net']:+9.0f} PF={m['pf']:.2f} DD={m['dd']:8.0f} win={m['win']:.0f}%"


def main():
    path = sys.argv[1]
    out = open(sys.argv[2], 'w') if len(sys.argv) > 2 else None

    def P(*a):
        s = ' '.join(str(x) for x in a)
        print(s)
        if out:
            out.write(s + '\n')

    snap, sigs, days, act = load(path)
    cal = Cal(days)
    P(f"signals={len(sigs)} actualTrades={len(act)} days={len(days)} AUD={snap['aud']}")
    base = dict(minSL=2.5, maxSL=5.0, rr=3.0, dayLimit=350)
    bt = simulate(sigs, cal, base)
    ba = metrics([dict(sec=a[1], exit=a[2], pnl=a[3]) for a in act])
    P('ACTUAL baseline (strategy tester log):', fmt(ba))
    P('SIMULATED baseline (from logged paths):', fmt(metrics(bt)))
    tr, ho = split(bt)
    P('  simulated train / holdout:', fmt(tr), '||', fmt(ho))
    # trade-level match check
    act_secs = sorted(int(a[1]) for a in act)
    def near(x):
        i = bisect.bisect_left(act_secs, x - 300)
        return i < len(act_secs) and act_secs[i] <= x + 300
    matched = sum(1 for t in bt if near(t['sec'] + 300))
    P(f'  simulated trades matching an actual entry time (+-1 bar): {matched}/{len(bt)} (actual {len(act)})')

    rows = []

    def add(name, cfg=None, keep=None):
        c = dict(base)
        if cfg:
            c.update(cfg)
        t = simulate(sigs, cal, c, keep)
        a, (tr_, ho_) = metrics(t), split(t)
        rows.append((name, a, tr_, ho_))

    add('baseline (sim)')
    for lim in [None, 500, 700, 1000, 1500, 2500]:
        add(f'dayLimit={lim}', dict(dayLimit=lim))
    for rr in [2.0, 2.5, 3.5, 4.0, 5.0]:
        add(f'rr={rr}', dict(rr=rr))
    for mn in [2.0, 3.0, 3.5]:
        add(f'minSL={mn}', dict(minSL=mn))
    for mx in [4.0, 6.0, 6.5]:
        add(f'maxSL={mx}', dict(maxSL=mx))
    for be in BE_LV:
        add(f'breakeven after +{be} ATR', dict(be=be))
    for ts in CP_OFF:
        add(f'time stop {ts} bars', dict(tstop=ts))
    for h in range(9, 24):
        add(f'skip entry hour {h}', keep=(lambda s, h=h: ist(s['sec'])[0] != h))
    for a_, b_ in [(10, 13), (10, 12), (11, 14), (12, 15), (9, 11), (20, 23)]:
        add(f'skip hours {a_}-{b_}', keep=(lambda s, a_=a_, b_=b_: not (a_ <= ist(s['sec'])[0] < b_)))
    for dw in range(5):
        add(f'skip weekday {dw}', keep=(lambda s, dw=dw: ist(s['sec'])[1] != dw))
    add('long only', keep=lambda s: s['dir'] == 1)
    add('short only', keep=lambda s: s['dir'] == -1)
    for q in [0.8, 0.9, 1.0, 1.1, 1.25]:
        add(f'atrRatio >= {q}', keep=(lambda s, q=q: math.isnan(s['atrRatio']) or s['atrRatio'] >= q))
        add(f'atrRatio <= {q}', keep=(lambda s, q=q: math.isnan(s['atrRatio']) or s['atrRatio'] <= q))
    for q in [0.1, 0.2, 0.3, 0.5]:
        add(f'ema sep >= {q}', keep=(lambda s, q=q: s['sep'] >= q))
        add(f'ema sep <= {q}', keep=(lambda s, q=q: s['sep'] <= q))
    for q in [0.5, 1.0, 1.5, 2.0, 3.0]:
        add(f'dist from EMA22 <= {q}', keep=(lambda s, q=q: s['dist'] <= q))
        add(f'dist from EMA22 >= {q}', keep=(lambda s, q=q: s['dist'] >= q))
    for q in [-1.0, 0.0, 1.0]:
        add(f'runup20 >= {q}', keep=(lambda s, q=q: s['runup'] >= q))
        add(f'runup20 <= {q}', keep=(lambda s, q=q: s['runup'] <= q))
    for q in [3, 6, 12, 24, 48]:
        add(f'regime age >= {q}', keep=(lambda s, q=q: s['regAge'] >= q))
        add(f'regime age <= {q}', keep=(lambda s, q=q: s['regAge'] <= q))
    for q in [1.0, 1.5, 2.0]:
        add(f'flip bar range <= {q} ATR', keep=(lambda s, q=q: s['rng'] <= q))
        add(f'flip bar range >= {q} ATR', keep=(lambda s, q=q: s['rng'] >= q))
    add('flip bar body with trade (>0)', keep=lambda s: s['body'] > 0)
    add('flip bar body against (<0)', keep=lambda s: s['body'] < 0)

    b = rows[0]
    P('\nVARIANTS (points). Score = improves net AND PF in BOTH train (Apr24-Mar25) and holdout (Apr25-Sep26) vs simulated baseline')
    P(f"{'variant':34s} | {'ALL':52s} | {'TRAIN':52s} | {'HOLDOUT':52s}")
    P('-' * 200)
    for name, a, tr_, ho_ in rows:
        ok = (name != 'baseline (sim)' and tr_['net'] > b[2]['net'] and ho_['net'] > b[3]['net'] and tr_['pf'] > b[2]['pf'] and ho_['pf'] > b[3]['pf'])
        P(f"{('* ' if ok else '  ') + name:34s} | {fmt(a)} | {fmt(tr_)} | {fmt(ho_)}")
    P('\n* = improves net and PF in both halves. Number of variants tested:', len(rows) - 1, '(multiple-testing warning: expect several false positives).')
    if out:
        out.close()


if __name__ == '__main__':
    main()
