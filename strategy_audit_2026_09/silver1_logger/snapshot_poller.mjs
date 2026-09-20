// Polls the TradingView page (CDP 9222) for the Pine table cells of the trade-logger study and saves
// snapshots to disk. Keeps best.json = snapshot with the most trade records (survives replay-end table reset).
// Usage: node snapshot_poller.mjs <outDir> [intervalSec] [studyFilter]
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
const require = createRequire('C:/Users/Manas/Downloads/tradingview-mcp-main/tradingview-mcp-main/package.json');
const CDP = require('chrome-remote-interface');

const OUT = process.argv[2] || '.';
const INTERVAL = (Number(process.argv[3]) || 60) * 1000;
const FILTER = process.argv[4] || 'Silver v12';
fs.mkdirSync(OUT, { recursive: true });

const EXPR = `(function(){
  var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
  var sources = chart.model().model().dataSources();
  var out = [];
  for (var si = 0; si < sources.length; si++) {
    var s = sources[si];
    if (!s.metaInfo) continue;
    try {
      var meta = s.metaInfo();
      var name = meta.description || meta.shortDescription || '';
      if (!name || name.indexOf(${JSON.stringify(FILTER)}) === -1) continue;
      var g = s._graphics; if (!g || !g._primitivesCollection) continue;
      var outer = g._primitivesCollection.dwgtablecells; if (!outer) continue;
      var coll = outer.get('tableCells'); if (!coll) continue;
      if (!coll._primitivesDataById && typeof coll.get === 'function') coll = coll.get(false);
      if (!coll || !coll._primitivesDataById) continue;
      coll._primitivesDataById.forEach(function(v){ out.push({tid: v.tid||0, row: v.row, col: v.col, t: v.t||''}); });
    } catch(e) {}
  }
  return JSON.stringify(out);
})()`;

let bestN = -1;
let lastArchive = 0;

async function pickTarget() {
  const list = await CDP.List({ host: '127.0.0.1', port: 9222 });
  return list.find(t => t.type === 'page' && /tradingview\.com\/chart/.test(t.url));
}

async function once() {
  const target = await pickTarget();
  if (!target) throw new Error('no chart target');
  const client = await CDP({ host: '127.0.0.1', port: 9222, target: target.id });
  try {
    const r = await client.Runtime.evaluate({ expression: EXPR, returnByValue: true });
    const cells = JSON.parse(r.result.value || '[]');
    const aud = (cells.find(c => c.t.startsWith('AUD|')) || {}).t || null;
    const body = cells.filter(c => !c.t.startsWith('AUD|') && c.t).sort((a, b) => (a.tid - b.tid) || ((a.row * 1000 + a.col) - (b.row * 1000 + b.col))).map(c => c.t);
    const act = body.filter(t => t.split(',').length === 4);
    const days = body.filter(t => t.split(',').length === 2);
    const recs = body.filter(t => t.split(',').length > 5);
    const snap = { ts: new Date().toISOString(), aud, n: recs.length, nAct: act.length, nDays: days.length, recs, act, days };
    fs.writeFileSync(path.join(OUT, 'latest.json'), JSON.stringify(snap));
    if (recs.length >= bestN && recs.length > 0) {
      bestN = recs.length;
      fs.writeFileSync(path.join(OUT, 'best.json'), JSON.stringify(snap));
    }
    if (Date.now() - lastArchive > 15 * 60 * 1000 && recs.length > 0) {
      lastArchive = Date.now();
      fs.writeFileSync(path.join(OUT, `snap_${snap.ts.replace(/[:.]/g, '-')}.json`), JSON.stringify(snap));
    }
    fs.appendFileSync(path.join(OUT, 'poller.log'), `${snap.ts} n=${recs.length} act=${act.length} days=${days.length} best=${bestN} ${aud}\n`);
  } finally {
    await client.close();
  }
}

(async () => {
  for (;;) {
    try { await once(); } catch (e) {
      fs.appendFileSync(path.join(OUT, 'poller.log'), `${new Date().toISOString()} ERROR ${e.message}\n`);
    }
    await new Promise(r => setTimeout(r, INTERVAL));
  }
})();
