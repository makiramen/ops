/* ============================================================
   PERIOD VIEW  (This week / Last week / Month / Quarter / Year)
   AM Control Centre, This Week tab.
   Added 13/10/2026. Reads the same all_sites_wc_<monday>.json
   files the weekly view uses, so there is no new data pipe.
   Rules:
     - a week belongs to the month / quarter / year its Monday falls in
     - Sales, covers are summed; SPH = sales / covers
     - wage % and food % are sales-weighted (= total £ / total sales)
     - score is the plain average of site efficiency scores
     - "vs prior period" is like for like: the same number of
       weeks from the start of the previous month / quarter / year
     - Month and Quarter tables run one row per week; Year runs one
       row per month (weeks rolled up) so nothing has to scroll sideways
   ============================================================ */
(function () {
  'use strict';
  var DATA = (typeof DATA_DIR === 'string' ? DATA_DIR : './data/');
  var tab = document.getElementById('tab-week');
  if (!tab) return;

  /* ---------- styles ---------- */
  var css = '\
  #period-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 14px;padding:10px 12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}\
  #period-bar .pv-lab{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);margin-right:2px}\
  #period-bar .pv-break{flex-basis:100%;height:0}\
  .pv-pill{background:var(--surface);border:1px solid var(--line);color:var(--ink-2);padding:7px 14px;border-radius:999px;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;font-family:inherit}\
  .pv-pill:hover{border-color:var(--maki-orange);color:var(--ink)}\
  .pv-pill.active{background:var(--maki-orange);border-color:var(--maki-orange);color:#fff}\
  .pv-pill.region.active{background:var(--maki-ink);border-color:var(--maki-ink)}\
  .pv-pill small{font-weight:500;opacity:.8;margin-left:4px}\
  .pv-sel{font:inherit;font-size:13px;font-weight:600;padding:7px 10px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);cursor:pointer}\
  .pv-sel:focus{outline:none;border-color:var(--maki-orange);box-shadow:0 0 0 3px var(--maki-orange-ring)}\
  #period-view{display:none}\
  .pv-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:16px 18px;margin-bottom:18px;overflow:hidden}\
  .pv-card h2{margin:0 0 4px;font-size:17px;font-weight:700;letter-spacing:-.01em}\
  .pv-card .hint{color:var(--ink-3);font-size:12px;margin-bottom:12px}\
  table.pv{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px;table-layout:fixed}\
  table.pv th{background:var(--surface-2);color:var(--ink-2);font-weight:700;font-size:11px;letter-spacing:.04em;text-transform:uppercase;padding:9px 6px;border-bottom:1px solid var(--line);text-align:center;vertical-align:middle;line-height:1.25}\
  table.pv td{padding:9px 6px;border-bottom:1px solid var(--line);text-align:center;vertical-align:middle;line-height:1.3;overflow-wrap:anywhere}\
  table.pv tr:last-child td{border-bottom:0}\
  table.pv td.name{font-weight:700;color:var(--ink)}\
  table.pv td.name span{display:block;font-weight:500;color:var(--ink-3);font-size:11px}\
  table.pv td.txt{font-size:11.5px;color:var(--ink-2)}\
  table.pv td.txt b{display:block;font-size:13px;color:var(--ink)}\
  table.pv.dense{font-size:11px} table.pv.dense th{font-size:10px;padding:7px 3px} table.pv.dense td{padding:6px 3px}\
  table.pv tr.cluster td{background:var(--maki-orange-bg);color:var(--maki-ink);font-weight:800;font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:7px 10px}\
  table.pv tr.sub td{background:var(--surface-2);font-weight:700}\
  table.pv tr.total td{background:var(--maki-ink);color:#fff;font-weight:800;border-bottom:0}\
  table.pv tr.total .pv-wow{color:#fff;opacity:.9}\
  table.pv tr.total td.txt,table.pv tr.total td.txt b,table.pv tr.total td.name span{color:#fff}\
  table.pv tr.pv-site-row{cursor:pointer} table.pv tr.pv-site-row:hover td{filter:brightness(.97)}\
  .pv-wow{display:block;font-size:10.5px;font-weight:700;margin-top:2px}\
  .pv-wow.up{color:var(--green)} .pv-wow.down{color:var(--red)} .pv-wow.flat,.pv-wow.na{color:var(--ink-3);font-weight:500}\
  .pv-tint-green{background:var(--green-bg)} .pv-tint-amber{background:var(--amber-bg)} .pv-tint-red{background:var(--red-bg)}\
  .pv-r{color:var(--red);font-weight:800} .pv-a{color:var(--amber);font-weight:800} .pv-g{color:var(--green);font-weight:800}\
  td.pv-x{cursor:pointer} td.pv-x .pv-sum{font-weight:800;font-size:13px;color:var(--ink)} td.pv-x .pv-sum:after{content:" ▸";font-size:10px;color:var(--ink-3)} td.pv-x.open .pv-sum:after{content:" ▾"}\
  td.pv-x .pv-detail{display:none;margin-top:5px;text-align:left;font-size:11px;line-height:1.5;color:var(--ink-2)} td.pv-x.open .pv-detail{display:block}\
  td.pv-x .pv-detail div{display:flex;justify-content:space-between;gap:6px;border-top:1px solid rgba(0,0,0,.05);padding:1px 0} table.pv td.txt .pv-detail b{display:inline;font-size:11px;font-weight:700;color:var(--ink)} table.pv td.txt .pv-detail b.pv-r{color:var(--red)} table.pv td.txt .pv-detail b.pv-a{color:var(--amber)} table.pv td.txt .pv-detail b.pv-g{color:var(--green)}\
  table.pv tr.total td.pv-x .pv-sum,table.pv tr.total td.pv-x .pv-detail,table.pv tr.total td.pv-x .pv-sum:after{color:#fff}\
  .pv-metrics{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}\
  .pv-rl-dots{display:flex;gap:2px;flex-wrap:wrap;justify-content:center;margin-bottom:3px}\
  .pv-rld{display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--line)}\
  .pv-rld.red{background:var(--red)} .pv-rld.amber{background:var(--amber)} .pv-rld.green{background:var(--green)} .pv-rld.na{background:var(--line)}\
  .pv-empty{padding:30px;text-align:center;color:var(--ink-3)}\
  .pv-foot{font-size:11.5px;color:var(--ink-3);margin-top:10px;line-height:1.5}\
  @media (max-width:720px){table.pv{font-size:11px}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  /* ---------- helpers ---------- */
  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  var MON3 = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function d(iso){ return new Date(iso + 'T00:00:00Z'); }
  function wcLabel(iso){ var x = d(iso); return 'w/c ' + x.getUTCDate() + ' ' + MON3[x.getUTCMonth()]; }
  function rangeLabel(iso){ var a = d(iso), b = d(iso); b.setUTCDate(b.getUTCDate() + 6);
    return a.getUTCDate() + (a.getUTCMonth() === b.getUTCMonth() ? '' : ' ' + MON3[a.getUTCMonth()]) + ' to ' + b.getUTCDate() + ' ' + MON3[b.getUTCMonth()]; }
  function monthKey(iso){ return iso.slice(0, 7); }
  function quarterKey(iso){ var x = d(iso); return x.getUTCFullYear() + '-Q' + (Math.floor(x.getUTCMonth() / 3) + 1); }
  function yearKey(iso){ return iso.slice(0, 4); }
  function keyOf(iso, m){ return m === 'month' ? monthKey(iso) : m === 'quarter' ? quarterKey(iso) : yearKey(iso); }
  function monthLabel(k){ return MONTHS[+k.slice(5, 7) - 1] + ' ' + k.slice(0, 4); }
  function quarterLabel(k){ var q = +k.slice(6); var m = (q - 1) * 3; return 'Q' + q + ' ' + k.slice(0, 4) + ' (' + MON3[m] + ' to ' + MON3[m + 2] + ')'; }
  function yearLabel(k){ return k + ' year to date'; }
  function labelOf(k, m){ return m === 'month' ? monthLabel(k) : m === 'quarter' ? quarterLabel(k) : yearLabel(k); }
  function prevKey(k, mode){
    if (mode === 'month'){ var y = +k.slice(0, 4), m = +k.slice(5, 7) - 1; if (m === 0){ y--; m = 12; } return y + '-' + (m < 10 ? '0' : '') + m; }
    if (mode === 'year') return String(+k - 1);
    var yy = +k.slice(0, 4), q = +k.slice(6) - 1; if (q === 0){ yy--; q = 4; } return yy + '-Q' + q;
  }
  function gbp(n){ if (n == null || isNaN(n)) return 'n/a'; return '£' + Math.round(n).toLocaleString('en-GB'); }
  function gbp2(n){ if (n == null || isNaN(n)) return 'n/a'; return '£' + n.toFixed(2); }
  function int(n){ if (n == null || isNaN(n)) return 'n/a'; return Math.round(n).toLocaleString('en-GB'); }
  function pct1(n){ if (n == null || isNaN(n)) return 'n/a'; return n.toFixed(1) + '%'; }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pctChange(cur, prev){ if (cur == null || prev == null || !prev) return null; return (cur - prev) / Math.abs(prev) * 100; }
  function sgn(v, dp, suf){ return (v > 0 ? '+' : '') + v.toFixed(dp == null ? 1 : dp) + (suf || ''); }

  var METRICS = {
    sales:  { label: 'Sales',   fmt: gbp,  upGood: true,  how: 'sum',  wowAbs: false },
    covers: { label: 'Covers',  fmt: int,  upGood: true,  how: 'sum',  wowAbs: false },
    sph:    { label: 'SPH',     fmt: gbp2, upGood: true,  how: 'calc', wowAbs: false },
    wage:   { label: 'Wage %',  fmt: pct1, upGood: false, how: 'wavg', wowAbs: true },
    food:   { label: 'Food %',  fmt: pct1, upGood: false, how: 'wavg', wowAbs: true },
    score:  { label: 'Score',   fmt: int,  upGood: true,  how: 'avg',  wowAbs: true }
  };
  // One RAG band set for every cell, the same bands the weekly view uses
  // (wageRag / foodRag / sphRag / efficiencyRag / weeklyRatingRag / DELIV_METRIC_DEFS in index.html).
  function sphTargetFor(code){ if (typeof sphTarget === 'function') return sphTarget(code); return 22; }
  function band(metric, v, ctx){
    ctx = ctx || {};
    if (v == null || isNaN(v)) return '';
    if (metric === 'sales'){ var t = ctx.target; if (!t) return ''; var vt = pctChange(v, t); return vt >= 0 ? 'green' : vt >= -10 ? 'amber' : 'red'; }
    if (metric === 'vst')   return v >= 0 ? 'green' : v >= -10 ? 'amber' : 'red';
    if (metric === 'covers'){ if (ctx.prev == null) return ''; var cw = pctChange(v, ctx.prev); return cw == null ? '' : cw >= 0 ? 'green' : cw >= -5 ? 'amber' : 'red'; }
    if (metric === 'sph'){ var st = ctx.sphT != null ? ctx.sphT : 22; return v >= st ? 'green' : v >= st - 2 ? 'amber' : 'red'; }
    if (metric === 'wage')   return (typeof wageRag === 'function') ? wageRag(v) : (v <= 21 ? 'green' : v <= 23 ? 'amber' : 'red');
    if (metric === 'food')   return (typeof foodRag === 'function') ? foodRag(v) : (v <= 25 ? 'green' : v <= 28 ? 'amber' : 'red');
    if (metric === 'score')  return v >= 95 ? 'green' : v >= 80 ? 'amber' : 'red';
    if (metric === 'rating') return v >= 4.7 ? 'green' : v >= 4.5 ? 'amber' : 'red';
    if (metric === 'prep')   return v <= 15 ? 'green' : v <= 18 ? 'amber' : 'red';
    return '';
  }
  function tint(metric, v, ctx){ var b = band(metric, v, ctx); return b ? 'pv-tint-' + b : ''; }
  function tintDelta(cur, prv, metric){
    var m = METRICS[metric]; if (cur == null || prv == null) return '';
    var dl = m.wowAbs ? cur - prv : pctChange(cur, prv); if (dl == null) return '';
    if (Math.abs(dl) < 0.05) return 'pv-tint-amber';
    var up = dl > 0, good = m.upGood ? up : !up; return good ? 'pv-tint-green' : 'pv-tint-red';
  }
  // Deliveroo: canonical thresholds from index.html where present.
  var DELIV = (typeof DELIV_METRIC_DEFS !== 'undefined' && DELIV_METRIC_DEFS) ? DELIV_METRIC_DEFS :
    [['rating', 'rating', 4.7, 4.0, true], ['open_hours_pct', 'open', 98, 95, true], ['avg_prep_min', 'prep', 15, 18, false], ['inaccuracy_pct', 'inacc', 2, 3, false], ['rider_wait_5min_pct', 'rider', 2, 4, false]];
  function delivBand1(v, g, a, hb){ if (v == null) return ''; if (hb) return v >= g ? 'green' : v >= a ? 'amber' : 'red'; return v <= g ? 'green' : v <= a ? 'amber' : 'red'; }
  // Same rollup as the weekly Deliveroo RAG: any red = red, all five green = green, otherwise amber (a missing metric blocks green).
  function delivBand(dv){
    if (!dv || !dv.n) return '';
    var bands = DELIV.map(function (m) { return delivBand1(dv[m[0]], m[2], m[3], m[4]) || 'missing'; });
    if (bands.indexOf('red') >= 0) return 'red';
    return bands.every(function (b) { return b === 'green'; }) ? 'green' : 'amber';
  }
  var DELIV_NAME = { rating: 'Rating', open_hours_pct: 'Open hours', avg_prep_min: 'Prep time', inaccuracy_pct: 'Inaccurate', rider_wait_5min_pct: 'Rider wait' };
  function delivFmt(k, v){ if (v == null) return 'n/a'; if (k === 'rating') return v.toFixed(2) + '★'; if (k === 'avg_prep_min') return v.toFixed(1) + ' min'; return v.toFixed(1) + '%'; }
  function bandCls(b){ return b === 'red' ? 'pv-r' : b === 'amber' ? 'pv-a' : b === 'green' ? 'pv-g' : ''; }
  // Deliveroo cell: the rollup in one line (rating, how many metrics off), click for all five.
  function delivCell(dv, extraCls){
    var b = delivBand(dv), cls = 'txt' + (extraCls ? ' ' + extraCls : '') + (b ? ' pv-tint-' + b : '');
    if (!dv || !dv.n) return '<td class="' + cls + '"><span class="pv-wow na">no storefront</span></td>';
    var reds = 0, ambers = 0, lines = '';
    DELIV.forEach(function (m) { var k = m[0], mb = delivBand1(dv[k], m[2], m[3], m[4]); if (mb === 'red') reds++; if (mb === 'amber') ambers++;
      lines += '<div><span>' + DELIV_NAME[k] + '</span><b class="' + bandCls(mb) + '">' + delivFmt(k, dv[k]) + '</b></div>'; });
    var sum = (dv.rating != null ? dv.rating.toFixed(2) + '★' : 'n/a');
    var sub = reds ? reds + ' red' + (ambers ? ', ' + ambers + ' amber' : '') : ambers ? ambers + ' amber' : b === 'green' ? 'all green' : 'missing data';
    return '<td class="' + cls + ' pv-x"><span class="pv-sum">' + sum + '</span><span class="pv-wow ' + (reds ? 'down' : 'na') + '">' + sub + '</span><div class="pv-detail">' + lines + '</div></td>';
  }
  // Complaints band: share of the period's reviews that carry a complaint.
  function complaintBand(th, nReviews){
    if (th == null) return '';
    if (!th.n) return 'green';
    if (!nReviews) return th.n > 2 ? 'red' : 'amber';
    var r = th.n / nReviews * 100; return r <= 2 ? 'green' : r <= 6 ? 'amber' : 'red';
  }
  // WoW / MoM chip. Percent change for £ / counts, absolute points for % and score.
  function wow(cur, prev, metric, word){
    var m = METRICS[metric]; word = word || 'WoW';
    if (cur == null || prev == null) return '<span class="pv-wow na">no ' + word + '</span>';
    var delta = m.wowAbs ? (cur - prev) : pctChange(cur, prev);
    if (delta == null) return '<span class="pv-wow na">no ' + word + '</span>';
    if (Math.abs(delta) < 0.05) return '<span class="pv-wow flat">flat</span>';
    var up = delta > 0, good = m.upGood ? up : !up;
    var txt = (up ? '+' : '') + delta.toFixed(1) + (m.wowAbs ? (metric === 'score' ? ' pts' : ' pp') : '%');
    return '<span class="pv-wow ' + (good ? 'up' : 'down') + '">' + (up ? '▲ ' : '▼ ') + txt + '</span>';
  }

  /* ---------- site naming (JSON code -> display) ---------- */
  var EXTRA_NAMES = { M19: 'Shoreditch', M20: 'Southampton', M21: 'Birmingham', MakiNori: 'Maki Nori', IKI2: 'Ikigai Ramen' };
  function siteName(code, jsonName){
    var disp = (typeof jsonToDisplay === 'function') ? jsonToDisplay(code) : code;
    var list = (typeof SITES !== 'undefined' && SITES) || window.SITES || []; var hit = list.filter(function (s) { return s.code === disp; })[0];
    var nm = (hit && hit.name) || EXTRA_NAMES[code] || jsonName || code;
    return { code: disp, name: nm === disp ? '' : nm };
  }

  /* ---------- data ---------- */
  var weeksIndex = [];      // [{monday,label,file}] newest first
  var cache = {};           // monday -> json | null
  function fetchWeek(monday){
    if (cache[monday] !== undefined) return Promise.resolve(cache[monday]);
    return fetch(DATA + 'all_sites_wc_' + monday + '.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (j) { cache[monday] = j; return j; });
  }
  // One flat record per site per week.
  function siteRec(s, code){
    var k = s.kpis || {}, dv = s.deliveroo || null;
    var sales = k.sales && k.sales.actual, covers = k.covers && k.covers.actual;
    var sph = (k.sph && k.sph.actual != null) ? k.sph.actual : (sales != null && covers ? sales / covers : null);
    var hasDv = dv && (dv.rating != null || dv.open_hours_pct != null || dv.avg_prep_min != null || dv.inaccuracy_pct != null || dv.rider_wait_5min_pct != null);
    return {
      sales: sales, target: k.sales && k.sales.target, covers: covers, sph: sph,
      wage: k.wage_pct && k.wage_pct.actual, food: k.food_pct && k.food_pct.actual,
      score: s.efficiency_score && s.efficiency_score.score,
      rag: (s.efficiency_score && s.efficiency_score.rag) || null,
      red: !!(s.red_light && s.red_light.status === 'red'),
      triggers: (s.red_light && s.red_light.triggers) || [],
      varPct: k.sales && k.sales.var_pct,
      rating: s.reviews && s.reviews.week_avg_rating, nReviews: s.reviews && s.reviews.new_reviews,
      prep: dv && dv.avg_prep_min,
      dv: hasDv ? { rating: dv.rating, open_hours_pct: dv.open_hours_pct, avg_prep_min: dv.avg_prep_min, inaccuracy_pct: dv.inaccuracy_pct, rider_wait_5min_pct: dv.rider_wait_5min_pct, n: 1 } : null,
      sphT: sphTargetFor(code != null ? ((typeof jsonToDisplay === 'function') ? jsonToDisplay(code) : code) : null)
    };
  }
  // Aggregate a list of site records (one or many sites, one or many weeks).
  function aggregate(recs){
    var a = { sales: 0, target: 0, nTarget: 0, covers: 0, wageNum: 0, wageDen: 0, foodNum: 0, foodDen: 0, scoreSum: 0, scoreN: 0, red: 0, amber: 0, green: 0, n: 0, redSites: [], sphTNum: 0, sphTDen: 0, ratNum: 0, ratDen: 0, nRev: 0, revKnown: false,
      dv: { rating: 0, nR: 0, open_hours_pct: 0, nO: 0, avg_prep_min: 0, nP: 0, inaccuracy_pct: 0, nI: 0, rider_wait_5min_pct: 0, nW: 0, n: 0 }, nRed: 0, trig: {}, nSales: 0, nCovers: 0 };
    recs.forEach(function (r) {
      a.n++;
      if (r.sales != null){ a.sales += r.sales; a.nSales++; if (r.target != null){ a.target += r.target; a.nTarget++; } }
      if (r.covers != null){ a.covers += r.covers; a.nCovers++; if (r.sphT != null){ a.sphTNum += r.sphT * r.covers; a.sphTDen += r.covers; } }
      if (r.nReviews != null){ a.nRev += r.nReviews; a.revKnown = true; }
      if (r.rating != null && r.nReviews){ a.ratNum += r.rating * r.nReviews; a.ratDen += r.nReviews; }
      if (r.wage != null && r.sales != null){ a.wageNum += r.wage * r.sales; a.wageDen += r.sales; }
      if (r.food != null && r.sales != null){ a.foodNum += r.food * r.sales; a.foodDen += r.sales; }
      if (r.score != null){ a.scoreSum += r.score; a.scoreN++; }
      if (r.rag === 'red') a.red++; else if (r.rag === 'amber') a.amber++; else if (r.rag === 'green') a.green++;
      if (r.red){ a.nRed++; if (a.redSites.indexOf(r.label) < 0) a.redSites.push(r.label); r.triggers.forEach(function (t) { a.trig[t.split(' ')[0]] = t; }); }
      if (r.dv){ var v = r.dv; a.dv.n++;
        if (v.rating != null){ a.dv.rating += v.rating; a.dv.nR++; } if (v.open_hours_pct != null){ a.dv.open_hours_pct += v.open_hours_pct; a.dv.nO++; } if (v.avg_prep_min != null){ a.dv.avg_prep_min += v.avg_prep_min; a.dv.nP++; }
        if (v.inaccuracy_pct != null){ a.dv.inaccuracy_pct += v.inaccuracy_pct; a.dv.nI++; } if (v.rider_wait_5min_pct != null){ a.dv.rider_wait_5min_pct += v.rider_wait_5min_pct; a.dv.nW++; } }
    });
    var dv = a.dv.n ? { n: a.dv.n, rating: a.dv.nR ? a.dv.rating / a.dv.nR : null, open_hours_pct: a.dv.nO ? a.dv.open_hours_pct / a.dv.nO : null, avg_prep_min: a.dv.nP ? a.dv.avg_prep_min / a.dv.nP : null, inaccuracy_pct: a.dv.nI ? a.dv.inaccuracy_pct / a.dv.nI : null, rider_wait_5min_pct: a.dv.nW ? a.dv.rider_wait_5min_pct / a.dv.nW : null } : { n: 0 };
    var out = {
      sales: a.nSales ? a.sales : null, target: a.nTarget ? a.target : null,
      covers: a.nCovers ? a.covers : null, sph: a.covers && a.nSales ? a.sales / a.covers : null,
      wage: a.wageDen ? a.wageNum / a.wageDen : null, food: a.foodDen ? a.foodNum / a.foodDen : null,
      score: a.scoreN ? a.scoreSum / a.scoreN : null,
      red: a.red, amber: a.amber, green: a.green, redSites: a.redSites, n: a.n, nRed: a.nRed,
      triggers: Object.keys(a.trig).map(function (k) { return a.trig[k]; }),
      sphT: a.sphTDen ? a.sphTNum / a.sphTDen : 22, rating: a.ratDen ? a.ratNum / a.ratDen : null, nReviews: a.revKnown ? a.nRev : null,
      dv: dv, prep: dv.avg_prep_min, nWk: a.nSales
    };
    out.varPct = out.target ? pctChange(out.sales, out.target) : null;
    return out;
  }

  /* ---------- state ---------- */
  var mode = 'this';        // this | last | month | quarter | year
  var periodKey = null;     // e.g. 2026-10, 2026-Q4, 2026
  var metric = 'sales';
  var scope = 'all';        // all | <cluster name> | site:<jsonCode>
  var DIR = { order: [], seen: {}, clusterOf: {}, clusters: [] };   // site directory from the newest week

  /* ---------- bar ---------- */
  var bar = document.createElement('div'); bar.id = 'period-bar';
  var view = document.createElement('div'); view.id = 'period-view';
  tab.insertBefore(view, tab.firstChild);
  tab.insertBefore(bar, tab.firstChild);

  function periodsFor(m){
    var seen = {}, out = [];
    weeksIndex.forEach(function (w) { var k = keyOf(w.monday, m); if (!seen[k]){ seen[k] = 1; out.push(k); } });
    return out; // newest first
  }
  function isPeriod(m){ return m === 'month' || m === 'quarter' || m === 'year'; }
  function renderBar(){
    var thisW = weeksIndex[0], lastW = weeksIndex[1];
    var h = '<span class="pv-lab">View</span>';
    h += '<button class="pv-pill' + (mode === 'this' ? ' active' : '') + '" data-mode="this">This week' + (thisW ? '<small>' + wcLabel(thisW.monday) + '</small>' : '') + '</button>';
    h += '<button class="pv-pill' + (mode === 'last' ? ' active' : '') + '" data-mode="last">Last week' + (lastW ? '<small>' + wcLabel(lastW.monday) + '</small>' : '') + '</button>';
    h += '<button class="pv-pill' + (mode === 'month' ? ' active' : '') + '" data-mode="month">Month</button>';
    h += '<button class="pv-pill' + (mode === 'quarter' ? ' active' : '') + '" data-mode="quarter">Quarter</button>';
    h += '<button class="pv-pill' + (mode === 'year' ? ' active' : '') + '" data-mode="year">Year to date</button>';
    if (isPeriod(mode)){
      var ps = periodsFor(mode);
      h += '<select class="pv-sel" id="pv-period">' + ps.map(function (k) {
        return '<option value="' + k + '"' + (k === periodKey ? ' selected' : '') + '>' + labelOf(k, mode) + '</option>';
      }).join('') + '</select>';
      if (DIR.clusters.length){
        var siteSel = scope.indexOf('site:') === 0;
        h += '<span class="pv-break"></span><span class="pv-lab">Region</span>';
        h += '<button class="pv-pill region' + (scope === 'all' ? ' active' : '') + '" data-scope="all">All sites<small>' + DIR.order.length + '</small></button>';
        DIR.clusters.forEach(function (cl) { h += '<button class="pv-pill region' + (scope === cl ? ' active' : '') + '" data-scope="' + esc(cl) + '">' + esc(cl) + '<small>' + DIR.order.filter(function (c) { return DIR.clusterOf[c] === cl; }).length + '</small></button>'; });
        h += '<span class="pv-lab" style="margin-left:auto">Site</span><select class="pv-sel" id="pv-site"><option value="">All</option>' + DIR.order.map(function (c) { var nm = DIR.seen[c]; return '<option value="site:' + c + '"' + (scope === 'site:' + c ? ' selected' : '') + '>' + esc(nm.label + (nm.name ? ' ' + nm.name : '')) + '</option>'; }).join('') + '</select>';
      }
    }
    bar.innerHTML = h;
    bar.querySelectorAll('.pv-pill[data-mode]').forEach(function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-mode')); }); });
    bar.querySelectorAll('.pv-pill[data-scope]').forEach(function (b) { b.addEventListener('click', function () { scope = b.getAttribute('data-scope'); renderBar(); renderPeriod(); }); });
    var sel = bar.querySelector('#pv-period');
    if (sel) sel.addEventListener('change', function () { periodKey = sel.value; renderPeriod(); });
    var ss = bar.querySelector('#pv-site');
    if (ss) ss.addEventListener('change', function () { scope = ss.value || 'all'; renderBar(); renderPeriod(); });
  }

  function showWeekly(show){
    Array.prototype.forEach.call(tab.children, function (ch) {
      if (ch === bar || ch === view) return;
      if (!show){
        if (ch.dataset.pvDisp === undefined) ch.dataset.pvDisp = ch.style.display || '';
        ch.style.display = 'none';
      } else if (ch.dataset.pvDisp !== undefined){
        ch.style.display = ch.dataset.pvDisp; delete ch.dataset.pvDisp;
      }
    });
    view.style.display = show ? 'none' : 'block';
  }

  function setMode(m, opts){
    opts = opts || {};
    mode = m;
    if (m === 'this' || m === 'last'){
      showWeekly(true);
      var w = weeksIndex[m === 'this' ? 0 : 1];
      if (w && !opts.silent && typeof window.applyWeek === 'function' && window.currentWeekKey !== w.monday){
        window.applyWeek(w.monday);
        document.dispatchEvent(new Event('week-changed'));
      }
      renderBar();
    } else {
      var ps = periodsFor(m);
      if (!periodKey || ps.indexOf(periodKey) < 0) periodKey = ps[0] || null;
      renderBar();
      showWeekly(false);
      renderPeriod();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ---------- period render ---------- */
  function weeksIn(key, m){
    return weeksIndex.filter(function (w) { return keyOf(w.monday, m) === key; })
      .sort(function (a, b) { return a.monday < b.monday ? -1 : 1; }); // oldest first
  }
  var RENDER_TOKEN = 0;
  function renderPeriod(){
    if (!periodKey){ view.innerHTML = '<div class="pv-card pv-empty">No weeks available yet.</div>'; return; }
    var cur = weeksIn(periodKey, mode);
    var prevK = prevKey(periodKey, mode);
    var prev = weeksIn(prevK, mode).slice(0, cur.length);   // like for like
    var need = {};
    cur.concat(prev).forEach(function (w) { need[w.monday] = 1; });
    // weeks before each, for the first row's WoW / MoM
    cur.concat(prev).forEach(function (w) { var k = prevMondayOf(w.monday); if (weeksIndex.some(function (x) { return x.monday === k; })) need[k] = 1; });
    if (mode === 'year'){ var pm = prevKey(monthKey(cur[0] ? cur[0].monday : periodKey + '-01'), 'month'); weeksIn(pm, 'month').forEach(function (w) { need[w.monday] = 1; }); }
    var token = ++RENDER_TOKEN;
    var keep = view.querySelector('.pv-card') ? null : '<div class="pv-card pv-empty">Loading ' + Object.keys(need).length + ' weeks…</div>';
    if (keep) view.innerHTML = keep;
    Promise.all(Object.keys(need).map(fetchWeek)).then(function () { if (token === RENDER_TOKEN) draw(cur, prev, prevK); });
  }
  function prevMondayOf(iso){ var p = d(iso); p.setUTCDate(p.getUTCDate() - 7); return p.toISOString().slice(0, 10); }

  /* ---------- red light KPI tests (one week, one site), three states ---------- */
  var RL_KPIS = [
    { id: 'sales',  label: 'Sales vs target', band: function (r) { return r.triggers.some(function (t) { return /^sales/.test(t); }) ? 'red' : band('vst', r.varPct); }, rule: 'red at or below -10% vs target, amber below target' },
    { id: 'wage',   label: 'Wage %',          band: function (r) { return r.triggers.some(function (t) { return /^wage/.test(t); }) ? 'red' : band('wage', r.wage); }, rule: 'red above 26% (red light) or 23%, amber above 21%' },
    { id: 'food',   label: 'Food %',          band: function (r) { return r.triggers.some(function (t) { return /^food/.test(t); }) ? 'red' : band('food', r.food); }, rule: 'red above 28% (band) or 25% (red light), amber above 25%' },
    { id: 'rating', label: 'Google rating',   band: function (r) { if (r.nReviews === 0) return 'red'; return band('rating', r.rating); }, rule: 'red below 4.5 or no reviews, amber below 4.7' },
    { id: 'deliveroo', label: 'Deliveroo', band: function (r) { return delivBand(r.dv); }, rule: 'five-metric rollup, same as the Deliveroo RAG tab: any metric red = red, all green = green, otherwise amber' },
    { id: 'score',  label: 'Efficiency score', band: function (r) { return r.rag || band('score', r.score); }, rule: 'red below 80, amber below 95' }
  ];
  function rlState(kpi, r){ if (!r) return 'na'; var b = kpi.band(r); return b || 'na'; }

  /* ---------- complaint themes (Google reviews, from reviews_intel.json) ---------- */
  var THEME_LABEL = { food: 'Quality', service: 'Service', speed: 'Speed', value: 'Value', cleanliness_ambience: 'Cleanliness', accuracy: 'Accuracy', hours_access: 'Hours', availability: 'Availability', digital_payment: 'Payment' };
  var THEMES = null;        // site -> week monday -> { n, cats:{cat:n}, hyg }
  var THEMES_P = null;
  function loadThemes(){
    if (THEMES_P) return THEMES_P;
    THEMES_P = fetch(DATA + 'reviews_intel.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var t = {};
        ((j && j.reviews) || []).forEach(function (r) {
          if (!r.issues || !r.issues.length) return;
          var w = r.week; if (!w) return;
          var site = t[r.site] || (t[r.site] = {}); var x = site[w] || (site[w] = { n: 0, cats: {}, hyg: 0 });
          x.n++;
          var seen = {}, hyg = false;
          r.issues.forEach(function (i) { var c = i && i.cat; if (!c || seen[c]) return; seen[c] = 1; x.cats[c] = (x.cats[c] || 0) + 1; });
          r.issues.forEach(function (i) { if (i && ((i.cat === 'food' && i.sub === 'hygiene_foreign') || (i.cat === 'cleanliness_ambience' && i.sub === 'dirty'))) hyg = true; });
          if (hyg) x.hyg++;
        });
        THEMES = t; return t;
      })
      .catch(function () { THEMES = {}; return THEMES; });
    return THEMES_P;
  }
  // Sum complaint themes for a list of json site codes over a list of week mondays.
  function themesFor(codes, mondays){
    if (!THEMES) return null;
    var out = { n: 0, cats: {}, hyg: 0 };
    codes.forEach(function (c) { mondays.forEach(function (monday) {
      var x = THEMES[c] && THEMES[c][monday]; if (!x) return;
      out.n += x.n; out.hyg += x.hyg;
      Object.keys(x.cats).forEach(function (k) { out.cats[k] = (out.cats[k] || 0) + x.cats[k]; });
    }); });
    return out;
  }
  function complaintsCell(t, nReviews){
    if (t == null) return '<td class="txt"><span class="pv-wow na">loading</span></td>';
    var b = complaintBand(t, nReviews), cls = b ? ' pv-tint-' + b : '';
    if (!t.n) return '<td class="txt' + cls + '"><span class="pv-sum" style="font-weight:800">0</span><span class="pv-wow na">' + (nReviews != null ? 'of ' + int(nReviews) + ' reviews' : 'none') + '</span></td>';
    var lines = Object.keys(t.cats).sort(function (a, b2) { return t.cats[b2] - t.cats[a]; })
      .map(function (k) { return '<div><span>' + esc(THEME_LABEL[k] || k) + '</span><b>' + t.cats[k] + '</b></div>'; }).join('');
    if (t.hyg) lines += '<div><span class="pv-r">Hygiene</span><b class="pv-r">' + t.hyg + '</b></div>';
    var topK = Object.keys(t.cats).sort(function (a, b2) { return t.cats[b2] - t.cats[a]; })[0];
    var topTxt = topK ? esc(THEME_LABEL[topK] || topK) + ' ' + t.cats[topK] : '';
    return '<td class="txt' + cls + ' pv-x"><span class="pv-sum">' + t.n + '</span><span class="pv-wow ' + (b === 'red' || t.hyg ? 'down' : 'na') + '">' + (nReviews ? 'of ' + int(nReviews) + ' · ' : '') + topTxt + (t.hyg ? ' · ' + t.hyg + ' hygiene' : '') + '</span><div class="pv-detail">' + lines + '</div></td>';
  }

  var ALL_LOADED = false, DRAW_TOKEN = 0;
  function loadAllWeeks(){ if (ALL_LOADED) return Promise.resolve(); return Promise.all(weeksIndex.map(function (w) { return fetchWeek(w.monday); })).then(function () { ALL_LOADED = true; }); }

  function weekData(monday){
    var j = cache[monday]; if (!j || !j.sites) return null;
    var recs = [], bySite = {};
    Object.keys(j.sites).forEach(function (code) {
      var r = siteRec(j.sites[code], code); var nm = siteName(code, j.sites[code].name);
      r.label = nm.code; r.name = nm.name; r.jsonCode = code; r.cluster = j.sites[code].cluster || '';
      recs.push(r); bySite[code] = r;
    });
    return { monday: monday, recs: recs, bySite: bySite };
  }
  // Group closed weeks into table rows: one per week (month, quarter) or one per month (year).
  function bucketsOf(weeks){
    var out = [], byKey = {};
    weeks.forEach(function (w) {
      var wd = weekData(w.monday); if (!wd) return;
      var key = mode === 'year' ? monthKey(w.monday) : w.monday;
      var b = byKey[key];
      if (!b){ b = byKey[key] = { key: key, weeks: [], mondays: [] }; out.push(b); }
      b.weeks.push(wd); b.mondays.push(w.monday);
    });
    out.forEach(function (b) {
      if (mode === 'year'){ b.label = MONTHS[+b.key.slice(5, 7) - 1]; b.sub = b.weeks.length + ' week' + (b.weeks.length > 1 ? 's' : '') + ' · ' + wcLabel(b.mondays[0]).replace('w/c ', '') + ' to ' + wcLabel(b.mondays[b.mondays.length - 1]).replace('w/c ', ''); b.short = MON3[+b.key.slice(5, 7) - 1]; }
      else { b.label = wcLabel(b.key); b.sub = rangeLabel(b.key); b.short = b.label; }
      b.recs = [].concat.apply([], b.weeks.map(function (w) { return w.recs; }));
      b.bySite = {}; b.recs.forEach(function (r) { (b.bySite[r.jsonCode] = b.bySite[r.jsonCode] || []).push(r); });
    });
    return out;
  }

  function draw(cur, prev, prevK){
    var label = labelOf(periodKey, mode), prevLabel = labelOf(prevK, mode);
    var rowWord = mode === 'year' ? 'MoM' : 'WoW';
    if (!cur.length){ view.innerHTML = '<div class="pv-card pv-empty">No weeks closed yet in ' + esc(label) + '.</div>'; return; }

    var curB = bucketsOf(cur), prevB = bucketsOf(prev);
    if (!curB.length){ view.innerHTML = '<div class="pv-card pv-empty">Week files for ' + esc(label) + ' could not be loaded.</div>'; return; }
    // the bucket before the first one (last week of the prior period, or the prior month for the year view)
    var before0 = null;
    if (mode === 'year'){ var pmW = weeksIn(prevKey(curB[0].key, 'month'), 'month'); var pb = bucketsOf(pmW); before0 = pb.length ? pb[pb.length - 1] : null; }
    else { var bm = prevMondayOf(curB[0].key); if (cache[bm]){ var bb = bucketsOf([{ monday: bm }]); before0 = bb[0] || null; } }

    // Site directory (newest week first so new sites appear), cluster order.
    var order = [], seen = {}, clusterOf = {};
    curB.slice().reverse().forEach(function (b) { b.weeks.slice().reverse().forEach(function (w) { w.recs.forEach(function (r) { if (!seen[r.jsonCode]){ seen[r.jsonCode] = r; order.push(r.jsonCode); clusterOf[r.jsonCode] = r.cluster; } }); }); });
    var clusters = []; order.forEach(function (c) { if (clusters.indexOf(clusterOf[c]) < 0) clusters.push(clusterOf[c]); });
    if (scope !== 'all' && scope.indexOf('site:') !== 0 && clusters.indexOf(scope) < 0) scope = 'all';
    if (scope.indexOf('site:') === 0 && !seen[scope.slice(5)]) scope = 'all';
    var siteOnly = scope.indexOf('site:') === 0 ? scope.slice(5) : null;
    function inScope(r){ if (siteOnly) return r.jsonCode === siteOnly; if (scope === 'all') return true; return r.cluster === scope; }
    var scopeCodes = order.filter(function (c) { return inScope(seen[c]); });
    var scopeLabel = siteOnly ? seen[siteOnly].label + ' ' + seen[siteOnly].name : scope === 'all' ? 'All sites' : scope;

    // Scope aggregates per bucket.
    curB.forEach(function (b) { b.est = aggregate(b.recs.filter(inScope)); });
    prevB.forEach(function (b) { b.est = aggregate(b.recs.filter(inScope)); });
    if (before0) before0.est = aggregate(before0.recs.filter(inScope));
    var allCur = [].concat.apply([], curB.map(function (b) { return b.recs.filter(inScope); }));
    var allPrev = [].concat.apply([], prevB.map(function (b) { return b.recs.filter(inScope); }));
    var totCur = aggregate(allCur), totPrev = prevB.length ? aggregate(allPrev) : null;
    // Prior period shorter than this one (data starts part way through it): compare per week, scaled up.
    var nPrevW = prev.length, prevScale = (totPrev && nPrevW && nPrevW < cur.length) ? cur.length / nPrevW : 1;
    function scaled(ag, f){ f = f == null ? prevScale : f; if (!ag || f === 1) return ag; var o = {}; Object.keys(ag).forEach(function (k) { o[k] = ag[k]; }); if (o.sales != null) o.sales *= f; if (o.covers != null) o.covers *= f; if (o.target != null) o.target *= f; return o; }
    if (siteOnly && totPrev && totPrev.nWk && totCur.nWk && totPrev.nWk !== totCur.nWk){ prevScale = totCur.nWk / totPrev.nWk; nPrevW = totPrev.nWk; }
    totPrev = scaled(totPrev);
    var latestWeek = curB[curB.length - 1].weeks.slice(-1)[0];
    var latestScope = aggregate(latestWeek.recs.filter(inScope));
    var expected = mode === 'month' ? null : mode === 'quarter' ? 13 : 52;
    var nWeeks = cur.length;
    var isOpen = (weeksIndex[0] && keyOf(weeksIndex[0].monday, mode) === periodKey);
    var lfl = totPrev ? (prevScale === 1 ? ' vs first ' + nWeeks + ' week' + (nWeeks > 1 ? 's' : '') + ' of ' + prevLabel : ' vs ' + prevLabel + ' (' + nPrevW + ' week' + (nPrevW > 1 ? 's' : '') + ' on file, £ and covers scaled to ' + nWeeks + ' weeks)') : '';
    var vsT = totCur.target ? pctChange(totCur.sales, totCur.target) : null;
    var allMondays = cur.map(function (w) { return w.monday; });

    /* ----- hero ----- */
    function delta(c, prv, metricKey){
      var m = METRICS[metricKey]; if (prv == null || c == null) return '';
      var dl = m.wowAbs ? c - prv : pctChange(c, prv); if (dl == null) return '';
      var up = dl > 0, good = m.upGood ? up : !up;
      return '<div class="stat-label" style="margin-top:4px;opacity:1;color:' + (Math.abs(dl) < 0.05 ? '#fff' : good ? '#c9f7e2' : '#ffd9d2') + '">' + (up ? '▲ ' : '▼ ') + (up ? '+' : '') + dl.toFixed(1) + (m.wowAbs ? (metricKey === 'score' ? ' pts' : ' pp') : '%') + '</div>';
    }
    function stat(n, l, cls, dd){ return '<div class="stat' + (cls ? ' ' + cls : '') + '"><div class="stat-num">' + n + '</div><div class="stat-label">' + l + '</div>' + (dd || '') + '</div>'; }
    var h = '<div class="hero" style="flex-direction:column;align-items:stretch;gap:12px"><div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">' +
      '<div class="hero-inner"><div class="eyebrow">AM ' + (mode === 'month' ? 'Monthly' : mode === 'quarter' ? 'Quarterly' : 'Year to date') + ' Control Centre' + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</div>' +
      '<h1>' + esc(label) + (siteOnly ? ' · ' + esc(scopeLabel) : '') + '</h1>' +
      '<div class="hero-sub">' + nWeeks + (expected ? ' of ' + expected : '') + ' week' + ((nWeeks > 1 || expected) ? 's' : '') + ' closed' + (isOpen ? ' so far, period still open' : '') +
      ' · ' + wcLabel(cur[0].monday) + ' to ' + wcLabel(cur[cur.length - 1].monday) + ' · ' + (totPrev ? 'deltas like for like' + lfl : 'no prior period to compare') + '</div></div>' +
      '<div class="hero-stats">' + stat(latestScope.n, 'Sites') + stat(latestScope.red, 'Red', 'red') + stat(latestScope.amber, 'Amber', 'amber') + stat(latestScope.green, 'Green', 'green') + stat(latestScope.redSites.length, 'Red lights', 'red') + '</div></div>' +
      '<div class="hero-stats" style="margin:0;justify-content:flex-start">' +
      stat(gbp(totCur.sales), 'Sales' + (vsT != null ? ' · ' + (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '% vs target' : ''), '', delta(totCur.sales, totPrev && totPrev.sales, 'sales')) +
      stat(int(totCur.covers), 'Covers', '', delta(totCur.covers, totPrev && totPrev.covers, 'covers')) +
      stat(gbp2(totCur.sph), 'SPH', '', delta(totCur.sph, totPrev && totPrev.sph, 'sph')) +
      stat(pct1(totCur.wage), 'Wage %', '', delta(totCur.wage, totPrev && totPrev.wage, 'wage')) +
      stat(pct1(totCur.food), 'Food %', '', delta(totCur.food, totPrev && totPrev.food, 'food')) +
      stat(totCur.score == null ? 'n/a' : totCur.score.toFixed(0), 'Avg score', '', delta(totCur.score, totPrev && totPrev.score, 'score')) +
      '</div></div>';

    /* ----- Week on week (month on month for the year) ----- */
    var rowName = mode === 'year' ? 'Month' : 'Week';
    h += '<div class="pv-card"><h2>' + (mode === 'year' ? 'Month on month' : 'Week on week') + ': ' + esc(label) + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">' + (siteOnly ? 'This site, one row per closed ' + rowName.toLowerCase() + '.' : 'Totals per closed ' + rowName.toLowerCase() + ' for ' + esc(scopeLabel).toLowerCase() + '.') + ' ' + rowWord + ' compares each row with the one before it (the first row with the last ' + rowName.toLowerCase() + ' of the prior period).' + (mode === 'year' ? ' Where two months hold a different number of closed weeks, the £ and covers move is per week.' : '') + '</div><table class="pv' + (mode === 'month' ? '' : ' dense') + '"><thead><tr>' +
      '<th style="width:11%">' + rowName + '</th><th>Sales</th><th style="width:7%">vs target</th><th>Covers</th><th>SPH</th><th>Wage %</th><th>Food %</th><th>' + (siteOnly ? 'Score' : 'Avg score') + '</th>' + (siteOnly ? '<th>Rating</th><th style="width:10%">Red light</th>' : '<th>Sites<br>R / A / G</th><th>Red lights</th>') + '<th style="width:14%">Complaints</th><th style="width:14%">Deliveroo</th></tr></thead><tbody>';
    curB.forEach(function (b, i) {
      var e = b.est, pb = i > 0 ? curB[i - 1] : before0;
      var pe = pb ? pb.est : null;
      var vt = e.target ? pctChange(e.sales, e.target) : null;
      var sr = siteOnly ? aggregate(b.bySite[siteOnly] || []) : null;
      var psr = siteOnly && pb ? aggregate(pb.bySite[siteOnly] || []) : null;
      var src = siteOnly ? sr : e, prc = siteOnly ? psr : pe;   // the record this row reads from
      if (prc && pb && pb.weeks.length !== b.weeks.length) prc = scaled(prc, b.weeks.length / pb.weeks.length);   // uneven months: £ and covers per week
      h += '<tr><td class="name">' + esc(b.label) + '<span>' + esc(b.sub) + '</span></td>' +
        '<td class="' + tint('sales', src.sales, { target: src.target }) + '">' + gbp(src.sales) + wow(src.sales, prc && prc.sales, 'sales', rowWord) + '</td>' +
        '<td class="' + tint('vst', src.varPct) + '">' + (src.varPct == null ? 'n/a' : '<strong>' + sgn(src.varPct, 1, '%') + '</strong>') + '</td>' +
        '<td class="' + tint('covers', src.covers, { prev: prc && prc.covers }) + '">' + int(src.covers) + wow(src.covers, prc && prc.covers, 'covers', rowWord) + '</td>' +
        '<td class="' + tint('sph', src.sph, { sphT: src.sphT }) + '">' + gbp2(src.sph) + wow(src.sph, prc && prc.sph, 'sph', rowWord) + '</td>' +
        '<td class="' + tint('wage', src.wage) + '">' + pct1(src.wage) + wow(src.wage, prc && prc.wage, 'wage', rowWord) + '</td>' +
        '<td class="' + tint('food', src.food) + '">' + pct1(src.food) + wow(src.food, prc && prc.food, 'food', rowWord) + '</td>' +
        '<td class="' + tint('score', src.score) + '">' + (src.score == null ? 'n/a' : src.score.toFixed(0)) + wow(src.score, prc && prc.score, 'score', rowWord) + '</td>';
      if (siteOnly){
        var nw = b.weeks.length;
        h += '<td class="' + tint('rating', sr.rating) + '">' + (sr.rating != null ? sr.rating.toFixed(2) + '★' + (sr.nReviews != null ? '<span class="pv-wow na">' + sr.nReviews + ' reviews</span>' : '') : 'n/a') + '</td>' +
          '<td class="txt ' + (sr.nRed ? (nw > 1 && sr.nRed < nw ? 'pv-tint-amber' : 'pv-tint-red') : 'pv-tint-green') + '">' + (sr.nRed ? (nw > 1 ? '<b>' + sr.nRed + ' of ' + nw + ' wks</b>' : '') + esc(sr.triggers.map(function (t) { return t.split(' ')[0]; }).join(', ')) : 'clear') + '</td>';
      } else {
        h += '<td class="' + (e.red ? 'pv-tint-red' : e.amber ? 'pv-tint-amber' : 'pv-tint-green') + '"><span class="pv-r">' + e.red + '</span> / <span class="pv-a">' + e.amber + '</span> / <span class="pv-g">' + e.green + '</span>' + (mode === 'year' ? '<span class="pv-wow na">site weeks</span>' : '') + '</td>' +
          '<td class="' + (e.redSites.length ? 'pv-tint-red' : 'pv-tint-green') + '"><strong>' + (mode === 'year' ? e.nRed : e.redSites.length) + '</strong>' + (mode === 'year' ? '<span class="pv-wow na">site weeks · ' + e.redSites.length + ' sites</span>' : '') + '</td>';
      }
      h += complaintsCell(themesFor(siteOnly ? [siteOnly] : scopeCodes, b.mondays), src.nReviews);
      h += delivCell(src.dv) + '</tr>';
    });
    h += '<tr class="total"><td class="name">' + esc(label) + ' total</td><td>' + gbp(totCur.sales) + (totPrev ? wow(totCur.sales, totPrev.sales, 'sales', 'prior') : '') + '</td>' +
      '<td>' + (vsT == null ? 'n/a' : sgn(vsT, 1, '%')) + '</td>' +
      '<td>' + int(totCur.covers) + (totPrev ? wow(totCur.covers, totPrev.covers, 'covers', 'prior') : '') + '</td>' +
      '<td>' + gbp2(totCur.sph) + (totPrev ? wow(totCur.sph, totPrev.sph, 'sph', 'prior') : '') + '</td>' +
      '<td>' + pct1(totCur.wage) + (totPrev ? wow(totCur.wage, totPrev.wage, 'wage', 'prior') : '') + '</td>' +
      '<td>' + pct1(totCur.food) + (totPrev ? wow(totCur.food, totPrev.food, 'food', 'prior') : '') + '</td>' +
      '<td>' + (totCur.score == null ? 'n/a' : totCur.score.toFixed(0)) + (totPrev ? wow(totCur.score, totPrev.score, 'score', 'prior') : '') + '</td>' +
      (siteOnly ? '<td>' + (totCur.rating != null ? totCur.rating.toFixed(2) + '★' : 'n/a') + '</td><td class="txt">' + totCur.nRed + ' of ' + nWeeks + ' wks</td>'
                : '<td>' + totCur.red + ' / ' + totCur.amber + ' / ' + totCur.green + '<span class="pv-wow na">site weeks</span></td><td>' + totCur.nRed + '<span class="pv-wow na">site weeks</span></td>') +
      complaintsCell(themesFor(siteOnly ? [siteOnly] : scopeCodes, allMondays), totCur.nReviews) +
      delivCell(totCur.dv) + '</tr>';
    h += '</tbody></table>' + (totPrev ? '<div class="pv-foot">Moves on the total row are' + lfl + '.</div>' : '') + '</div>';

    /* ----- Red light persistence ----- */
    h += '<div class="pv-card" id="pv-rl"><h2>Red lights, week after week' + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">One square per closed week in ' + esc(label) + ' (oldest left, newest right): red, amber or green on the same bands as every other cell, grey = no data. "Streak" counts consecutive red weeks up to the newest week, across the full history, not just this period. Sites red on every week of the period are listed first.</div><div id="pv-rl-body" class="pv-empty">Loading history…</div></div>';

    /* ----- Site by site grid (or single site, all measures) ----- */
    var m = METRICS[metric];
    var colsN = curB.length;
    var dense = colsN > 5 ? ' dense' : '';
    function periodAgg(recs){ return aggregate(recs); }
    function periodVal(recs){ return periodAgg(recs)[metric]; }
    var colW = Math.max(5.5, Math.min(9, 78 / (colsN + 1 + (totPrev ? 1 : 0))));
    var thW = ' style="width:' + colW + '%"';
    if (siteOnly){
      var sc = siteOnly;
      h += '<div class="pv-card"><h2>' + esc(scopeLabel) + ', every measure ' + (mode === 'year' ? 'month by month' : 'week by week') + '</h2><div class="hint">Period column: sales and covers summed, SPH from the totals, wage % and food % sales-weighted, score averaged' + (totPrev ? '; compared like for like with ' + prevLabel : '') + '.</div><table class="pv' + dense + '"><thead><tr><th>Measure</th>' + curB.map(function (b) { return '<th' + thW + '>' + esc(b.short) + '</th>'; }).join('') + '<th' + thW + '>' + esc(mode === 'year' ? periodKey + ' YTD' : label) + '</th>' + (totPrev ? '<th' + thW + '>vs prior</th>' : '') + '</tr></thead><tbody>';
      function cellsFor(mk){
        var cells = '';
        curB.forEach(function (b, i) {
          var ag = aggregate(b.bySite[sc] || []), v = ag.n ? ag[mk] : null;
          var pb = i > 0 ? curB[i - 1] : before0; var bg = pb ? aggregate(pb.bySite[sc] || []) : null;
          cells += '<td class="' + tint(mk, v, { target: ag.target, prev: bg && bg.n ? bg[mk] : null, sphT: ag.sphT }) + '">' + METRICS[mk].fmt(v) + wow(v, bg && bg.n ? bg[mk] : null, mk, rowWord) + '</td>';
        });
        return cells;
      }
      Object.keys(METRICS).forEach(function (mk) {
        var mm = METRICS[mk];
        var pv = totCur[mk], ppv = totPrev ? totPrev[mk] : null;   // totPrev already scaled
        h += '<tr><td class="name">' + mm.label + '</td>' + cellsFor(mk) + '<td class="' + tint(mk, pv, { target: totCur.target, prev: ppv, sphT: totCur.sphT }) + '"><strong>' + mm.fmt(pv) + '</strong></td>' + (totPrev ? '<td class="' + tintDelta(pv, ppv, mk) + '">' + mm.fmt(ppv) + wow(pv, ppv, mk, 'prior') + '</td>' : '') + '</tr>';
      });
      h += '<tr><td class="name">vs target</td>' + curB.map(function (b) { var v = aggregate(b.bySite[sc] || []).varPct; return '<td class="' + tint('vst', v) + '">' + (v == null ? 'n/a' : '<strong>' + sgn(v, 1, '%') + '</strong>') + '</td>'; }).join('') + '<td class="' + tint('vst', vsT) + '">' + (vsT == null ? 'n/a' : '<strong>' + sgn(vsT, 1, '%') + '</strong>') + '</td>' + (totPrev ? '<td class="' + tint('vst', totPrev.varPct) + '">' + (totPrev.varPct == null ? '' : sgn(totPrev.varPct, 1, '%')) + '</td>' : '') + '</tr>';
      h += '<tr><td class="name">Google rating</td>' + curB.map(function (b) { var r = aggregate(b.bySite[sc] || []); return '<td class="' + tint('rating', r.rating) + '">' + (r.rating != null ? r.rating.toFixed(2) + '★' : 'n/a') + (r.nReviews != null ? '<span class="pv-wow na">' + r.nReviews + ' reviews</span>' : '') + '</td>'; }).join('') + '<td class="' + tint('rating', totCur.rating) + '">' + (totCur.rating != null ? '<strong>' + totCur.rating.toFixed(2) + '★</strong><span class="pv-wow na">' + totCur.nReviews + ' reviews</span>' : 'n/a') + '</td>' + (totPrev ? '<td class="' + (totCur.rating != null && totPrev.rating != null ? (totCur.rating > totPrev.rating + 0.005 ? 'pv-tint-green' : totCur.rating < totPrev.rating - 0.005 ? 'pv-tint-red' : 'pv-tint-amber') : '') + '">' + (totPrev.rating != null ? totPrev.rating.toFixed(2) + '★' : '') + '</td>' : '') + '</tr>';
      h += '<tr><td class="name">Deliveroo</td>' + curB.map(function (b) { return delivCell(aggregate(b.bySite[sc] || []).dv); }).join('') + delivCell(totCur.dv) + (totPrev ? delivCell(totPrev.dv) : '') + '</tr>';
      h += '<tr><td class="name">Complaints</td>' + curB.map(function (b) { var r = aggregate(b.bySite[sc] || []); return complaintsCell(themesFor([sc], b.mondays), r.nReviews); }).join('') + complaintsCell(themesFor([sc], allMondays), totCur.nReviews) + (totPrev ? '<td></td>' : '') + '</tr>';
      h += '<tr><td class="name">Red light</td>' + curB.map(function (b) { var r = aggregate(b.bySite[sc] || []); var nw = b.weeks.length; return '<td class="txt ' + (r.nRed ? (nw > 1 && r.nRed < nw ? 'pv-tint-amber' : 'pv-tint-red') : 'pv-tint-green') + '">' + (r.nRed ? (nw > 1 ? '<b>' + r.nRed + ' of ' + nw + '</b>' : '') + esc(r.triggers.map(function (t) { return t.split(' ')[0]; }).join(', ')) : 'clear') + '</td>'; }).join('') + '<td class="txt ' + (totCur.nRed ? 'pv-tint-red' : 'pv-tint-green') + '"><b>' + totCur.nRed + ' of ' + nWeeks + '</b>weeks red</td>' + (totPrev ? '<td class="txt">' + totPrev.nRed + ' of ' + prev.length + ' weeks red</td>' : '') + '</tr>';
      h += '</tbody></table></div>';
    } else {
      h += '<div class="pv-card"><h2>Site by site, ' + (mode === 'year' ? 'month by month' : 'week by week') + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">Pick a measure. Each cell shows the value with its ' + rowWord + ' move underneath. Click a site to open it on its own. The period column is the ' +
        (m.how === 'sum' ? 'sum' : m.how === 'avg' ? 'average' : 'sales-weighted figure') + ' across the ' + (mode === 'year' ? 'months' : 'weeks') + ' shown' + (totPrev ? ', compared like for like with ' + prevLabel : '') + '.</div>' +
        '<div class="pv-metrics">' + Object.keys(METRICS).map(function (k) { return '<button class="pv-pill' + (k === metric ? ' active' : '') + '" data-metric="' + k + '">' + METRICS[k].label + '</button>'; }).join('') + '</div>' +
        '<table class="pv' + dense + '"><thead><tr><th>Site</th>' + curB.map(function (b) { return '<th' + thW + '>' + esc(b.short) + '</th>'; }).join('') + '<th' + thW + '>' + esc(mode === 'year' ? periodKey + ' YTD' : label) + '</th>' + (totPrev ? '<th' + thW + '>vs prior</th>' : '') + '</tr></thead><tbody>';
      function rowFor(nameHtml, recsPer, prevRecsAll, cls, attr){
        var cells = '', valsAll = [];
        curB.forEach(function (b, i) {
          var recs = recsPer[i]; var ag = recs.length ? periodAgg(recs) : null; var v = ag ? ag[metric] : null;
          var bprev = i > 0 ? recsPer[i - 1] : recsPer.before;
          var pv = bprev && bprev.length ? periodVal(bprev) : null;
          valsAll = valsAll.concat(recs);
          cells += '<td class="' + (cls === 'total' ? '' : tint(metric, v, { target: ag && ag.target, prev: pv, sphT: ag && ag.sphT })) + '">' + m.fmt(v) + wow(v, pv, metric, rowWord) + '</td>';
        });
        var pag = valsAll.length ? periodAgg(valsAll) : null, pval = pag ? pag[metric] : null;
        var pprev = prevRecsAll && prevRecsAll.length ? periodAgg(prevRecsAll) : null;
        var ppval = pprev ? scaled(pprev, (!cls && pag && pprev.nWk && pag.nWk !== pprev.nWk) ? pag.nWk / pprev.nWk : prevScale)[metric] : null;
        return '<tr' + (cls ? ' class="' + cls + '"' : '') + (attr || '') + '><td class="name">' + nameHtml + '</td>' + cells + '<td class="' + (cls === 'total' ? '' : tint(metric, pval, { target: pag && pag.target, prev: ppval, sphT: pag && pag.sphT })) + '"><strong>' + m.fmt(pval) + '</strong></td>' + (totPrev ? '<td class="' + (cls === 'total' ? '' : tintDelta(pval, ppval, metric)) + '">' + m.fmt(ppval) + wow(pval, ppval, metric, 'prior') + '</td>' : '') + '</tr>';
      }
      var colsAll = curB.length + 2 + (totPrev ? 1 : 0);
      clusters.filter(function (cl) { return scope === 'all' || scope === cl; }).forEach(function (cl) {
        h += '<tr class="cluster"><td colspan="' + colsAll + '">' + esc(cl || 'Unassigned') + '</td></tr>';
        order.filter(function (c) { return clusterOf[c] === cl; }).forEach(function (code) {
          var per = curB.map(function (b) { return b.bySite[code] || []; });
          per.before = before0 && before0.bySite[code] ? before0.bySite[code] : [];
          var pr = [].concat.apply([], prevB.map(function (b) { return b.bySite[code] || []; }));
          var nm = seen[code];
          h += rowFor(esc(nm.label) + '<span>' + esc(nm.name) + '</span>', per, pr, '', ' class="pv-site-row" data-site="' + code + '" title="Open ' + esc(nm.label) + ' on its own"');
        });
        var perC = curB.map(function (b) { return b.recs.filter(function (r) { return r.cluster === cl; }); });
        perC.before = before0 ? before0.recs.filter(function (r) { return r.cluster === cl; }) : [];
        h += rowFor(esc(cl || 'Unassigned') + ' subtotal', perC, allPrev.filter(function (r) { return r.cluster === cl; }), 'sub');
      });
      var perE = curB.map(function (b) { return b.recs.filter(inScope); }); perE.before = before0 ? before0.recs.filter(inScope) : [];
      h += rowFor(scope === 'all' ? 'Estate' : esc(scope) + ' total', perE, allPrev, 'total');
      h += '</tbody></table></div>';
    }
    h += '<div class="pv-foot">Every cell is banded red, amber or green on the same bands as the weekly view. Sales vs target: green at or above target, amber to -10%, red below -10%. Covers: ' + rowWord + ', green up, amber to -5%, red below -5%. SPH vs the site target (£22; Maki Nori £35; Ikigai £21): green at target, amber within £2, red below. Wage %: green 21% and under, amber to 23%, red above 23%. Food %: green 25% and under, amber to 28%, red above 28%. Score: green 95 and above, amber 80 to 94, red below 80. Rating: green 4.7 and above, amber 4.5 to 4.69, red below 4.5. Deliveroo: the five-metric rollup the Deliveroo RAG tab uses (rating 4.7 / 4.0, open hours 98% / 95%, prep 15 / 18 min, inaccuracy 2% / 3%, rider wait 2% / 4% green / amber thresholds): any metric red = red, all five green = green, otherwise amber; figures are plain averages of the storefronts in scope. Complaints: Google reviews of any star rating carrying at least one classified issue (Reviews intelligence file), green at 2% of reviews or under, amber to 6%, red above; hygiene = dirty premises or a foreign body / food safety mention. "vs prior" cells: green if the move is good, red if bad. A week sits in the month, quarter or year its Monday falls in' + (mode === 'year' ? '; the year view rolls weeks up into calendar months' : '') + '. Sales and covers are summed; SPH is period sales over period covers; wage % and food % are sales-weighted; score is the average of the site scores. Red light board per KPI: ' + RL_KPIS.map(function (k) { return k.label + ' (' + k.rule + ')'; }).join('; ') + '. Sources: the same weekly site JSON files the This Week view reads.</div>';

    view.innerHTML = h;
    view.querySelectorAll('td.pv-x').forEach(function (td) { td.addEventListener('click', function (ev) { ev.stopPropagation(); td.classList.toggle('open'); }); });
    view.querySelectorAll('[data-metric]').forEach(function (b) { b.addEventListener('click', function () { metric = b.getAttribute('data-metric'); draw(cur, prev, prevK); }); });
    view.querySelectorAll('.pv-site-row').forEach(function (tr) { tr.addEventListener('click', function () { scope = 'site:' + tr.getAttribute('data-site'); renderBar(); draw(cur, prev, prevK); }); });

    // Red light board needs the full history for streaks.
    loadAllWeeks().then(function () { drawRedLights(cur, scopeCodes, seen); });
    // Complaint themes land once, then the tables are redrawn.
    if (!THEMES){ var token = ++DRAW_TOKEN; loadThemes().then(function () { if (token === DRAW_TOKEN) draw(cur, prev, prevK); }); }
  }

  function drawRedLights(cur, codes, seen){
    var host = document.getElementById('pv-rl-body'); if (!host) return;
    var hist = weeksIndex.slice().sort(function (a, b) { return a.monday < b.monday ? -1 : 1; }).map(function (w) { var j = cache[w.monday]; return { monday: w.monday, sites: (j && j.sites) || {} }; });
    var curSet = {}; cur.forEach(function (w) { curSet[w.monday] = 1; });
    var rows = codes.map(function (code) {
      var kp = {};
      RL_KPIS.forEach(function (k) {
        var dots = [], streak = 0, redInPeriod = 0, amberInPeriod = 0, nInPeriod = 0;
        hist.forEach(function (w) {
          var s = w.sites[code]; var st = s ? rlState(k, siteRec(s, code)) : 'na';
          if (curSet[w.monday]){ dots.push({ m: w.monday, st: st }); if (st !== 'na') nInPeriod++; if (st === 'red') redInPeriod++; if (st === 'amber') amberInPeriod++; }
        });
        for (var i = hist.length - 1; i >= 0; i--){ var s2 = hist[i].sites[code]; var st2 = s2 ? rlState(k, siteRec(s2, code)) : 'na'; if (st2 === 'red') streak++; else if (st2 !== 'na') break; }
        kp[k.id] = { dots: dots, streak: streak, red: redInPeriod, amber: amberInPeriod, n: nInPeriod };
      });
      var totalRed = 0, totalN = 0, everyWeek = 0;
      RL_KPIS.forEach(function (k) { totalRed += kp[k.id].red; totalN += kp[k.id].n; if (kp[k.id].n && kp[k.id].red === kp[k.id].n) everyWeek++; });
      var ov = 0; for (var i2 = hist.length - 1; i2 >= 0; i2--){ var s3 = hist[i2].sites[code]; if (!s3) continue; if (s3.red_light && s3.red_light.status === 'red') ov++; else break; }
      var redWeeks = 0, nW = 0; hist.forEach(function (w) { if (!curSet[w.monday]) return; var s4 = w.sites[code]; if (!s4) return; nW++; if (s4.red_light && s4.red_light.status === 'red') redWeeks++; });
      return { code: code, kp: kp, totalRed: totalRed, totalN: totalN, everyWeek: everyWeek, ovStreak: ov, redWeeks: redWeeks, nW: nW };
    });
    rows.sort(function (a, b) { return (b.everyWeek - a.everyWeek) || (b.ovStreak - a.ovStreak) || (b.totalRed - a.totalRed); });
    var year = mode === 'year';
    var h = '<table class="pv dense"><thead><tr><th style="width:12%">Site</th><th style="width:11%">Red light<br>streak</th>' + RL_KPIS.map(function (k) { return '<th>' + k.label + '</th>'; }).join('') + (year ? '<th style="width:9%">Red KPI weeks</th>' : '') + '</tr></thead><tbody>';
    rows.forEach(function (r) {
      var nm = seen[r.code];
      var flag = r.everyWeek ? '<span class="pv-wow down">' + r.everyWeek + ' KPI' + (r.everyWeek > 1 ? 's' : '') + ' red all period</span>' : '';
      var ovCls = r.ovStreak >= 3 ? 'pv-tint-red' : r.ovStreak ? 'pv-tint-amber' : 'pv-tint-green';
      h += '<tr class="pv-site-row" data-site="' + r.code + '"><td class="name">' + esc(nm.label) + '<span>' + esc(nm.name) + '</span>' + flag + '</td>' +
        '<td class="txt ' + ovCls + '"><b>' + (r.ovStreak ? r.ovStreak + ' wk' + (r.ovStreak > 1 ? 's' : '') : 'clear') + '</b>' + (r.ovStreak ? 'in a row' : '') + '<span class="pv-wow na">' + r.redWeeks + ' of ' + r.nW + ' red this period</span></td>';
      RL_KPIS.forEach(function (k) {
        var x = r.kp[k.id];
        var dots = x.dots.map(function (dd) { return '<span class="pv-rld ' + dd.st + '" title="' + wcLabel(dd.m) + ': ' + dd.st + '"></span>'; }).join('');
        var cls = !x.n ? '' : x.red === x.n ? 'pv-tint-red' : x.red || x.amber ? 'pv-tint-amber' : 'pv-tint-green';
        h += '<td class="' + cls + '"><div class="pv-rl-dots">' + dots + '</div><span class="pv-wow ' + (x.streak ? 'down' : 'na') + '">' + (x.streak ? x.streak + ' in a row' : (x.n ? 'clear' : 'no data')) + (x.n ? ' · ' + x.red + '/' + x.n : '') + '</span></td>';
      });
      if (year) h += '<td><strong>' + r.totalRed + '</strong><span class="pv-wow na">of ' + r.totalN + ' KPI weeks</span></td>';
      h += '</tr>';
    });
    h += '</tbody></table>';
    host.className = ''; host.innerHTML = h;
    host.querySelectorAll('.pv-site-row').forEach(function (tr) { tr.addEventListener('click', function () { scope = 'site:' + tr.getAttribute('data-site'); renderBar(); renderPeriod(); }); });
  }

  /* ---------- boot ---------- */
  fetch(DATA + 'weeks_index.json', { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (idx) {
      weeksIndex = ((idx && idx.weeks) || []).slice().sort(function (a, b) { return a.monday > b.monday ? -1 : 1; });
      renderBar();
      // Site / region directory from the newest week, for the bar.
      if (weeksIndex[0]) fetchWeek(weeksIndex[0].monday).then(function (j) {
        if (!j || !j.sites) return;
        Object.keys(j.sites).forEach(function (code) { var nm = siteName(code, j.sites[code].name); DIR.order.push(code); DIR.seen[code] = { label: nm.code, name: nm.name }; DIR.clusterOf[code] = j.sites[code].cluster || ''; if (DIR.clusters.indexOf(DIR.clusterOf[code]) < 0) DIR.clusters.push(DIR.clusterOf[code]); });
        if (isPeriod(mode)) renderBar();
      });
      // Keep the pills honest whenever the header week selector (or the
      // default-week picker on load) moves the weekly view.
      var lastSeen = null;
      setInterval(function () {
        if (isPeriod(mode)) return;
        var k = window.currentWeekKey; if (k === lastSeen) return; lastSeen = k;
        var nm = (weeksIndex[0] && k === weeksIndex[0].monday) ? 'this' : (weeksIndex[1] && k === weeksIndex[1].monday) ? 'last' : 'other';
        if (nm !== mode){ mode = nm; renderBar(); }
      }, 400);
      // Deep link: ?view=month / quarter / year (optionally &period=2026-10 / 2026-Q4 / 2026, &region=..., &site=M19)
      var q = new URLSearchParams(location.search), v = q.get('view');
      if (q.get('site')) scope = 'site:' + q.get('site'); else if (q.get('region')) scope = q.get('region');
      if (isPeriod(v)){ periodKey = q.get('period') || null; setMode(v, { silent: true }); }
    })
    .catch(function () { renderBar(); });
})();
