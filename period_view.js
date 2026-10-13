/* ============================================================
   PERIOD VIEW  (This week / Last week / Month / Quarter)
   AM Control Centre, This Week tab.
   Added 13/10/2026. Reads the same all_sites_wc_<monday>.json
   files the weekly view uses, so there is no new data pipe.
   Rules:
     - a week belongs to the month / quarter its Monday falls in
     - Sales, covers are summed; SPH = sales / covers
     - wage % and food % are sales-weighted (= total £ / total sales)
     - score is the plain average of site efficiency scores
     - "vs prior period" is like for like: the same number of
       weeks from the start of the previous month / quarter
   ============================================================ */
(function () {
  'use strict';
  var DATA = (typeof DATA_DIR === 'string' ? DATA_DIR : './data/');
  var tab = document.getElementById('tab-week');
  if (!tab) return;

  /* ---------- styles ---------- */
  var css = '\
  #period-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 14px;padding:10px 12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}\
  #period-bar .pv-lab{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);margin-right:2px}\
  .pv-pill{background:var(--surface);border:1px solid var(--line);color:var(--ink-2);padding:7px 14px;border-radius:999px;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;font-family:inherit}\
  .pv-pill:hover{border-color:var(--maki-orange);color:var(--ink)}\
  .pv-pill.active{background:var(--maki-orange);border-color:var(--maki-orange);color:#fff}\
  .pv-pill small{font-weight:500;opacity:.8;margin-left:4px}\
  .pv-sel{font:inherit;font-size:13px;font-weight:600;padding:7px 10px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);cursor:pointer}\
  .pv-sel:focus{outline:none;border-color:var(--maki-orange);box-shadow:0 0 0 3px var(--maki-orange-ring)}\
  #period-view{display:none}\
  .pv-hero{background:linear-gradient(135deg,var(--maki-ink) 0%,#2a1d14 60%,#4a2a14 100%);color:#fff;border-radius:16px;padding:22px 24px;margin-bottom:18px;display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;align-items:flex-end}\
  .pv-hero .eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--maki-orange-soft);font-weight:700;margin-bottom:6px}\
  .pv-hero h1{margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:-.02em}\
  .pv-hero .sub{font-size:13px;color:rgba(255,255,255,.72)}\
  .pv-stats{display:flex;gap:10px;flex-wrap:wrap}\
  .pv-stat{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 14px;min-width:118px}\
  .pv-stat .n{font-size:20px;font-weight:800;letter-spacing:-.02em}\
  .pv-stat .l{font-size:11px;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.06em;margin-top:2px}\
  .pv-stat .d{font-size:11px;margin-top:4px;font-weight:700}\
  .pv-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:16px 18px;margin-bottom:18px;overflow:hidden}\
  .pv-card h2{margin:0 0 4px;font-size:17px;font-weight:700;letter-spacing:-.01em}\
  .pv-card .hint{color:var(--ink-3);font-size:12px;margin-bottom:12px}\
  .pv-scroll{overflow-x:auto}\
  table.pv{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px}\
  table.pv th{position:sticky;top:0;background:var(--surface-2);color:var(--ink-2);font-weight:700;font-size:11px;letter-spacing:.04em;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;z-index:1}\
  table.pv th:first-child,table.pv td:first-child{text-align:left;position:sticky;left:0;background:var(--surface);z-index:2}\
  table.pv th:first-child{background:var(--surface-2);z-index:3}\
  table.pv td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;vertical-align:top}\
  table.pv tr:last-child td{border-bottom:0}\
  table.pv td.name{font-weight:700;color:var(--ink)}\
  table.pv td.name span{font-weight:500;color:var(--ink-3);margin-left:4px}\
  table.pv td.ann{white-space:normal;text-align:left;min-width:280px;color:var(--ink-2);line-height:1.45;font-size:12px}\
  table.pv tr.cluster td{background:var(--maki-orange-bg);color:var(--maki-ink);font-weight:800;font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:7px 10px}\
  table.pv tr.sub td{background:var(--surface-2);font-weight:700}\
  table.pv td.pv-tint-green{background:var(--green-bg)} table.pv td.pv-tint-amber{background:var(--amber-bg)} table.pv td.pv-tint-red{background:var(--red-bg)}\
  table.pv tr.total td{background:var(--maki-ink);color:#fff;font-weight:800;border-bottom:0}\
  table.pv tr.total td:first-child{background:var(--maki-ink)}\
  table.pv tr.total .pv-wow{color:#fff;opacity:.9}\
  .pv-wow{display:block;font-size:10.5px;font-weight:700;margin-top:2px}\
  .pv-wow.up{color:var(--green)} .pv-wow.down{color:var(--red)} .pv-wow.flat,.pv-wow.na{color:var(--ink-3);font-weight:500}\
  .pv-tint-green{background:var(--green-bg)} .pv-tint-amber{background:var(--amber-bg)} .pv-tint-red{background:var(--red-bg)}\
  .pv-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px;vertical-align:middle}\
  .pv-dot.red{background:var(--red)} .pv-dot.amber{background:var(--amber)} .pv-dot.green{background:var(--green)}\
  .pv-chip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;margin:1px 2px}\
  .pv-chip.red{background:var(--red-bg);color:var(--red);border:1px solid var(--red-ring)}\
  .pv-chip.amber{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-ring)}\
  .pv-chip.green{background:var(--green-bg);color:var(--green);border:1px solid var(--green-ring)}\
  .pv-chip.grey{background:var(--surface-2);color:var(--ink-2);border:1px solid var(--line)}\
  .pv-metrics{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}\
  .pv-rl-dots{display:flex;gap:3px;margin-bottom:3px}\
  .pv-rld{display:inline-block;width:11px;height:11px;border-radius:3px;background:var(--line)}\
  .pv-rld.red{background:var(--red)} .pv-rld.ok{background:var(--green)} .pv-rld.na{background:var(--line)}\
  #pv-cluster-nav{position:static}\
  .pv-empty{padding:30px;text-align:center;color:var(--ink-3)}\
  .pv-foot{font-size:11.5px;color:var(--ink-3);margin-top:10px;line-height:1.5}\
  @media (max-width:720px){.pv-hero h1{font-size:20px}.pv-stat{min-width:96px}}';
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
  function monthLabel(k){ return MONTHS[+k.slice(5, 7) - 1] + ' ' + k.slice(0, 4); }
  function quarterLabel(k){ var q = +k.slice(6); var m = (q - 1) * 3; return 'Q' + q + ' ' + k.slice(0, 4) + ' (' + MON3[m] + ' to ' + MON3[m + 2] + ')'; }
  function prevKey(k, mode){
    if (mode === 'month'){ var y = +k.slice(0, 4), m = +k.slice(5, 7) - 1; if (m === 0){ y--; m = 12; } return y + '-' + (m < 10 ? '0' : '') + m; }
    var yy = +k.slice(0, 4), q = +k.slice(6) - 1; if (q === 0){ yy--; q = 4; } return yy + '-Q' + q;
  }
  function gbp(n){ if (n == null || isNaN(n)) return 'n/a'; return '£' + Math.round(n).toLocaleString('en-GB'); }
  function gbp2(n){ if (n == null || isNaN(n)) return 'n/a'; return '£' + n.toFixed(2); }
  function int(n){ if (n == null || isNaN(n)) return 'n/a'; return Math.round(n).toLocaleString('en-GB'); }
  function pct1(n){ if (n == null || isNaN(n)) return 'n/a'; return n.toFixed(1) + '%'; }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pctChange(cur, prev){ if (cur == null || prev == null || !prev) return null; return (cur - prev) / Math.abs(prev) * 100; }

  var METRICS = {
    sales:  { label: 'Sales',   fmt: gbp,  upGood: true,  how: 'sum',  wowAbs: false },
    covers: { label: 'Covers',  fmt: int,  upGood: true,  how: 'sum',  wowAbs: false },
    sph:    { label: 'SPH',     fmt: gbp2, upGood: true,  how: 'calc', wowAbs: false },
    wage:   { label: 'Wage %',  fmt: pct1, upGood: false, how: 'wavg', wowAbs: true },
    food:   { label: 'Food %',  fmt: pct1, upGood: false, how: 'wavg', wowAbs: true },
    score:  { label: 'Score',   fmt: int,  upGood: true,  how: 'avg',  wowAbs: true }
  };
  // One RAG band set for every cell, the same bands the weekly view uses
  // (wageRag / foodRag / sphRag / efficiencyRag / weeklyRatingRag in index.html).
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
    return '';
  }
  function tint(metric, v, ctx){ var b = band(metric, v, ctx); return b ? 'pv-tint-' + b : ''; }
  // Tint for a "vs prior" cell: by whether the move is good or bad.
  function tintDelta(cur, prv, metric){
    var m = METRICS[metric]; if (cur == null || prv == null) return '';
    var dl = m.wowAbs ? cur - prv : pctChange(cur, prv); if (dl == null) return '';
    if (Math.abs(dl) < 0.05) return 'pv-tint-amber';
    var up = dl > 0, good = m.upGood ? up : !up; return good ? 'pv-tint-green' : 'pv-tint-red';
  }
  // WoW chip. Percent change for £ / counts, absolute points for % and score.
  function wow(cur, prev, metric){
    var m = METRICS[metric];
    if (cur == null || prev == null) return '<span class="pv-wow na">no WoW</span>';
    var delta = m.wowAbs ? (cur - prev) : pctChange(cur, prev);
    if (delta == null) return '<span class="pv-wow na">no WoW</span>';
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
    var k = s.kpis || {};
    var sales = k.sales && k.sales.actual, covers = k.covers && k.covers.actual;
    var sph = (k.sph && k.sph.actual != null) ? k.sph.actual : (sales != null && covers ? sales / covers : null);
    return {
      sales: sales, target: k.sales && k.sales.target, covers: covers, sph: sph,
      wage: k.wage_pct && k.wage_pct.actual, food: k.food_pct && k.food_pct.actual,
      score: s.efficiency_score && s.efficiency_score.score,
      rag: (s.efficiency_score && s.efficiency_score.rag) || null,
      red: s.red_light && s.red_light.status === 'red',
      triggers: (s.red_light && s.red_light.triggers) || [],
      varPct: k.sales && k.sales.var_pct,
      rating: s.reviews && s.reviews.week_avg_rating, nReviews: s.reviews && s.reviews.new_reviews,
      prep: s.deliveroo && s.deliveroo.avg_prep_min,
      sphT: sphTargetFor(code != null ? ((typeof jsonToDisplay === 'function') ? jsonToDisplay(code) : code) : null)
    };
  }
  // Aggregate a list of site records.
  function aggregate(recs){
    var a = { sales: 0, target: 0, nTarget: 0, covers: 0, wageNum: 0, wageDen: 0, foodNum: 0, foodDen: 0, scoreSum: 0, scoreN: 0, red: 0, amber: 0, green: 0, n: 0, redSites: [], sphTNum: 0, sphTDen: 0, ratNum: 0, ratDen: 0 };
    recs.forEach(function (r) {
      a.n++;
      if (r.sales != null){ a.sales += r.sales; if (r.target != null){ a.target += r.target; a.nTarget++; } }
      if (r.covers != null){ a.covers += r.covers; if (r.sphT != null){ a.sphTNum += r.sphT * r.covers; a.sphTDen += r.covers; } }
      if (r.rating != null && r.nReviews){ a.ratNum += r.rating * r.nReviews; a.ratDen += r.nReviews; }
      if (r.wage != null && r.sales != null){ a.wageNum += r.wage * r.sales; a.wageDen += r.sales; }
      if (r.food != null && r.sales != null){ a.foodNum += r.food * r.sales; a.foodDen += r.sales; }
      if (r.score != null){ a.scoreSum += r.score; a.scoreN++; }
      if (r.rag === 'red') a.red++; else if (r.rag === 'amber') a.amber++; else if (r.rag === 'green') a.green++;
      if (r.red) a.redSites.push(r.label);
    });
    return {
      sales: a.n ? a.sales : null, target: a.nTarget ? a.target : null,
      covers: a.n ? a.covers : null, sph: a.covers ? a.sales / a.covers : null,
      wage: a.wageDen ? a.wageNum / a.wageDen : null, food: a.foodDen ? a.foodNum / a.foodDen : null,
      score: a.scoreN ? a.scoreSum / a.scoreN : null,
      red: a.red, amber: a.amber, green: a.green, redSites: a.redSites, n: a.n,
      sphT: a.sphTDen ? a.sphTNum / a.sphTDen : 22, rating: a.ratDen ? a.ratNum / a.ratDen : null, nReviews: a.ratDen
    };
  }

  /* ---------- state ---------- */
  var mode = 'this';        // this | last | month | quarter
  var periodKey = null;     // e.g. 2026-10 or 2026-Q4
  var metric = 'sales';
  var scope = 'all';        // all | <cluster name> | site:<jsonCode>
  var hidden = [];          // weekly children we hid

  /* ---------- bar ---------- */
  var bar = document.createElement('div'); bar.id = 'period-bar';
  var view = document.createElement('div'); view.id = 'period-view';
  tab.insertBefore(view, tab.firstChild);
  tab.insertBefore(bar, tab.firstChild);

  function periodsFor(m){
    var seen = {}, out = [];
    weeksIndex.forEach(function (w) { var k = m === 'month' ? monthKey(w.monday) : quarterKey(w.monday); if (!seen[k]){ seen[k] = 1; out.push(k); } });
    return out; // newest first
  }
  function renderBar(){
    var thisW = weeksIndex[0], lastW = weeksIndex[1];
    var h = '<span class="pv-lab">View</span>';
    h += '<button class="pv-pill' + (mode === 'this' ? ' active' : '') + '" data-mode="this">This week' + (thisW ? '<small>' + wcLabel(thisW.monday) + '</small>' : '') + '</button>';
    h += '<button class="pv-pill' + (mode === 'last' ? ' active' : '') + '" data-mode="last">Last week' + (lastW ? '<small>' + wcLabel(lastW.monday) + '</small>' : '') + '</button>';
    h += '<button class="pv-pill' + (mode === 'month' ? ' active' : '') + '" data-mode="month">Month</button>';
    h += '<button class="pv-pill' + (mode === 'quarter' ? ' active' : '') + '" data-mode="quarter">Quarter</button>';
    if (mode === 'month' || mode === 'quarter'){
      var ps = periodsFor(mode);
      h += '<select class="pv-sel" id="pv-period">' + ps.map(function (k) {
        return '<option value="' + k + '"' + (k === periodKey ? ' selected' : '') + '>' + (mode === 'month' ? monthLabel(k) : quarterLabel(k)) + '</option>';
      }).join('') + '</select>';
    }
    bar.innerHTML = h;
    bar.querySelectorAll('.pv-pill').forEach(function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-mode')); }); });
    var sel = bar.querySelector('#pv-period');
    if (sel) sel.addEventListener('change', function () { periodKey = sel.value; renderPeriod(); });
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
    return weeksIndex.filter(function (w) { return (m === 'month' ? monthKey(w.monday) : quarterKey(w.monday)) === key; })
      .sort(function (a, b) { return a.monday < b.monday ? -1 : 1; }); // oldest first
  }
  function renderPeriod(){
    if (!periodKey){ view.innerHTML = '<div class="pv-card pv-empty">No weeks available yet.</div>'; return; }
    var cur = weeksIn(periodKey, mode);
    var prevK = prevKey(periodKey, mode);
    var prev = weeksIn(prevK, mode).slice(0, cur.length);   // like for like
    var need = {};
    cur.concat(prev).forEach(function (w) { need[w.monday] = 1; });
    // one week before each, for the first week's WoW
    cur.concat(prev).forEach(function (w) { var p = d(w.monday); p.setUTCDate(p.getUTCDate() - 7); var k = p.toISOString().slice(0, 10); if (weeksIndex.some(function (x) { return x.monday === k; })) need[k] = 1; });
    view.innerHTML = '<div class="pv-card pv-empty">Loading ' + Object.keys(need).length + ' weeks…</div>';
    Promise.all(Object.keys(need).map(fetchWeek)).then(function () { draw(cur, prev, prevK); });
  }

  /* ---------- red light KPI tests (one week, one site) ---------- */
  // Mirrors the dashboard's own red light basis for sales / wage / food (read
  // straight off red_light.triggers), plus rating, score and Deliveroo prep.
  var RL_KPIS = [
    { id: 'sales',  label: 'Sales vs target', test: function (r) { return r.triggers.some(function (t) { return /^sales/.test(t); }); }, rule: 'at or below -10% vs target' },
    { id: 'wage',   label: 'Wage %',          test: function (r) { return r.triggers.some(function (t) { return /^wage/.test(t); }); },  rule: 'wage above 26%' },
    { id: 'food',   label: 'Food %',          test: function (r) { return r.triggers.some(function (t) { return /^food/.test(t); }); },  rule: 'food above 25%' },
    { id: 'rating', label: 'Google rating',   test: function (r) { if (r.nReviews === 0) return true; return r.rating != null && r.rating < 4.7; }, rule: 'week average below 4.7, or no reviews', na: function (r) { return r.rating == null && r.nReviews !== 0; } },
    { id: 'prep',   label: 'Deliveroo prep',  test: function (r) { return r.prep != null && r.prep > 15; }, rule: 'avg prep above 15 min', na: function (r) { return r.prep == null; } },
    { id: 'score',  label: 'Efficiency score', test: function (r) { return r.rag === 'red'; }, rule: 'score below 80', na: function (r) { return r.score == null; } }
  ];
  function rlState(kpi, r){ if (!r) return 'na'; if (kpi.na && kpi.na(r)) return 'na'; return kpi.test(r) ? 'red' : 'ok'; }

  /* ---------- complaint themes (Google reviews, from reviews_intel.json) ---------- */
  var THEME_LABEL = { food: 'food quality', service: 'service', speed: 'speed', value: 'value', cleanliness_ambience: 'cleanliness', accuracy: 'order accuracy', hours_access: 'hours', availability: 'availability', digital_payment: 'payment tech' };
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
  // Sum complaint themes for a list of json site codes in one week.
  function themesFor(codes, monday){
    if (!THEMES) return null;
    var out = { n: 0, cats: {}, hyg: 0, bySite: [] };
    codes.forEach(function (c) {
      var x = THEMES[c] && THEMES[c][monday]; if (!x) return;
      out.n += x.n; out.hyg += x.hyg; out.bySite.push({ code: c, n: x.n });
      Object.keys(x.cats).forEach(function (k) { out.cats[k] = (out.cats[k] || 0) + x.cats[k]; });
    });
    return out;
  }
  function complaintsText(t, siteLabels){
    if (t == null) return 'Complaints: loading.';
    if (!t.n) return 'No complaints.';
    var top = Object.keys(t.cats).sort(function (a, b) { return t.cats[b] - t.cats[a]; }).slice(0, 3)
      .map(function (k) { return (THEME_LABEL[k] || k) + ' ' + t.cats[k]; }).join(', ');
    var s = 'Complaints ' + t.n + ': ' + top;
    if (t.hyg) s += ' (' + t.hyg + ' hygiene)';
    if (siteLabels && t.bySite.length > 1){ var m = t.bySite.slice().sort(function (a, b) { return b.n - a.n; })[0]; s += '; most at ' + (siteLabels[m.code] || m.code) + ' (' + m.n + ')'; }
    return s + '.';
  }

  var ALL_LOADED = false, DRAW_TOKEN = 0;
  function loadAllWeeks(){ if (ALL_LOADED) return Promise.resolve(); return Promise.all(weeksIndex.map(function (w) { return fetchWeek(w.monday); })).then(function () { ALL_LOADED = true; }); }

  function draw(cur, prev, prevK){
    var label = mode === 'month' ? monthLabel(periodKey) : quarterLabel(periodKey);
    var prevLabel = mode === 'month' ? monthLabel(prevK) : quarterLabel(prevK);
    if (!cur.length){ view.innerHTML = '<div class="pv-card pv-empty">No weeks closed yet in ' + esc(label) + '.</div>'; return; }

    function weekData(w){
      var j = cache[w.monday]; if (!j || !j.sites) return null;
      var recs = [], bySite = {};
      Object.keys(j.sites).forEach(function (code) {
        var r = siteRec(j.sites[code], code); var nm = siteName(code, j.sites[code].name);
        r.label = nm.code; r.name = nm.name; r.jsonCode = code; r.cluster = j.sites[code].cluster || '';
        recs.push(r); bySite[code] = r;
      });
      return { monday: w.monday, recs: recs, bySite: bySite };
    }
    function prevMondayOf(iso){ var p = d(iso); p.setUTCDate(p.getUTCDate() - 7); return p.toISOString().slice(0, 10); }
    var curW = cur.map(weekData).filter(Boolean);
    var prevW = prev.map(weekData).filter(Boolean);
    if (!curW.length){ view.innerHTML = '<div class="pv-card pv-empty">Week files for ' + esc(label) + ' could not be loaded.</div>'; return; }
    var before0 = cache[prevMondayOf(curW[0].monday)] ? weekData({ monday: prevMondayOf(curW[0].monday) }) : null;

    // Site directory (newest week first so new sites appear), cluster order.
    var order = [], seen = {}, clusterOf = {};
    curW.slice().reverse().forEach(function (w) { w.recs.forEach(function (r) { if (!seen[r.jsonCode]){ seen[r.jsonCode] = r; order.push(r.jsonCode); clusterOf[r.jsonCode] = r.cluster; } }); });
    var clusters = []; order.forEach(function (c) { if (clusters.indexOf(clusterOf[c]) < 0) clusters.push(clusterOf[c]); });
    if (scope !== 'all' && scope.indexOf('site:') !== 0 && clusters.indexOf(scope) < 0) scope = 'all';
    if (scope.indexOf('site:') === 0 && !seen[scope.slice(5)]) scope = 'all';
    var siteOnly = scope.indexOf('site:') === 0 ? scope.slice(5) : null;
    function inScope(r){ if (siteOnly) return r.jsonCode === siteOnly; if (scope === 'all') return true; return r.cluster === scope; }
    var scopeCodes = order.filter(function (c) { return inScope(seen[c]); });
    var scopeLabel = siteOnly ? seen[siteOnly].label + ' ' + seen[siteOnly].name : scope === 'all' ? 'All sites' : scope;

    // Estate / scope aggregates per week.
    curW.forEach(function (w) { w.est = aggregate(w.recs.filter(inScope)); });
    prevW.forEach(function (w) { w.est = aggregate(w.recs.filter(inScope)); });
    if (before0) before0.est = aggregate(before0.recs.filter(inScope));
    var allCur = [].concat.apply([], curW.map(function (w) { return w.recs.filter(inScope); }));
    var allPrev = [].concat.apply([], prevW.map(function (w) { return w.recs.filter(inScope); }));
    var totCur = aggregate(allCur), totPrev = prevW.length ? aggregate(allPrev) : null;
    var latest = curW[curW.length - 1];
    var latestScope = aggregate(latest.recs.filter(inScope));
    var expected = mode === 'month' ? null : 13;
    var nWeeks = curW.length;
    var isOpen = (weeksIndex[0] && (mode === 'month' ? monthKey(weeksIndex[0].monday) : quarterKey(weeksIndex[0].monday)) === periodKey);
    var lfl = totPrev ? ' vs first ' + nWeeks + ' week' + (nWeeks > 1 ? 's' : '') + ' of ' + prevLabel : '';
    var vsT = totCur.target ? pctChange(totCur.sales, totCur.target) : null;

    /* ----- cluster nav (same look as the weekly view) ----- */
    function ragCounts(recs){ var a = aggregate(recs); return '<span class="cn-rag"><b class="r">' + a.red + '</b><b class="a">' + a.amber + '</b><b class="g">' + a.green + '</b></span>'; }
    var h = '<div class="cluster-nav" id="pv-cluster-nav"><span class="cn-label">Clusters</span>';
    h += '<div class="cn-pill' + (scope === 'all' ? ' active' : '') + '" data-scope="all"><span class="cn-name">All sites</span><span class="cn-count">' + order.length + '</span>' + (scope === 'all' ? '' : ragCounts(latest.recs)) + '</div>';
    clusters.forEach(function (cl) {
      var recs = latest.recs.filter(function (r) { return r.cluster === cl; });
      h += '<div class="cn-pill' + (scope === cl ? ' active' : '') + '" data-scope="' + esc(cl) + '"><span class="cn-name">' + esc(cl) + '</span><span class="cn-count">' + order.filter(function (c) { return clusterOf[c] === cl; }).length + '</span>' + (scope === cl ? '' : ragCounts(recs)) + '</div>';
    });
    h += '<span class="cn-label" style="margin-left:auto">Site</span><select class="pv-sel" id="pv-site"><option value="">All</option>' + order.map(function (c) { return '<option value="site:' + c + '"' + (scope === 'site:' + c ? ' selected' : '') + '>' + esc(seen[c].label + ' ' + seen[c].name) + '</option>'; }).join('') + '</select></div>';

    /* ----- hero (orange, like the weekly view) ----- */
    function delta(cur, prv, metricKey){
      var m = METRICS[metricKey]; if (prv == null || cur == null) return '';
      var dl = m.wowAbs ? cur - prv : pctChange(cur, prv); if (dl == null) return '';
      var up = dl > 0, good = m.upGood ? up : !up;
      return '<div class="stat-label" style="margin-top:4px;opacity:1;color:' + (Math.abs(dl) < 0.05 ? '#fff' : good ? '#c9f7e2' : '#ffd9d2') + '">' + (up ? '▲ ' : '▼ ') + (up ? '+' : '') + dl.toFixed(1) + (m.wowAbs ? (metricKey === 'score' ? ' pts' : ' pp') : '%') + '</div>';
    }
    function stat(n, l, cls, d){ return '<div class="stat' + (cls ? ' ' + cls : '') + '"><div class="stat-num">' + n + '</div><div class="stat-label">' + l + '</div>' + (d || '') + '</div>'; }
    h += '<div class="hero" style="flex-direction:column;align-items:stretch;gap:12px"><div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">' +
      '<div class="hero-inner"><div class="eyebrow">AM ' + (mode === 'month' ? 'Monthly' : 'Quarterly') + ' Control Centre' + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</div>' +
      '<h1>' + esc(label) + (siteOnly ? ' · ' + esc(scopeLabel) : '') + '</h1>' +
      '<div class="hero-sub">' + nWeeks + (expected ? ' of ' + expected : '') + ' week' + ((nWeeks > 1 || expected) ? 's' : '') + ' closed' + (isOpen ? ' so far, period still open' : '') +
      ' · ' + wcLabel(curW[0].monday) + ' to ' + wcLabel(latest.monday) + ' · ' + (totPrev ? 'deltas like for like' + lfl : 'no prior period to compare') + '</div></div>' +
      '<div class="hero-stats">' + stat(latestScope.n, 'Sites') + stat(latestScope.red, 'Red', 'red') + stat(latestScope.amber, 'Amber', 'amber') + stat(latestScope.green, 'Green', 'green') + stat(latestScope.redSites.length, 'Red lights', 'red') + '</div></div>' +
      '<div class="hero-stats" style="margin:0;justify-content:flex-start">' +
      stat(gbp(totCur.sales), 'Sales' + (vsT != null ? ' · ' + (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '% vs target' : ''), '', delta(totCur.sales, totPrev && totPrev.sales, 'sales')) +
      stat(int(totCur.covers), 'Covers', '', delta(totCur.covers, totPrev && totPrev.covers, 'covers')) +
      stat(gbp2(totCur.sph), 'SPH', '', delta(totCur.sph, totPrev && totPrev.sph, 'sph')) +
      stat(pct1(totCur.wage), 'Wage %', '', delta(totCur.wage, totPrev && totPrev.wage, 'wage')) +
      stat(pct1(totCur.food), 'Food %', '', delta(totCur.food, totPrev && totPrev.food, 'food')) +
      stat(totCur.score == null ? 'n/a' : totCur.score.toFixed(0), 'Avg score', '', delta(totCur.score, totPrev && totPrev.score, 'score')) +
      '</div></div>';

    /* ----- Week on week with annotations ----- */
    h += '<div class="pv-card"><h2>Week on week: ' + esc(label) + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">' + (siteOnly ? 'This site, one row per closed week.' : 'Totals per closed week for ' + esc(scopeLabel).toLowerCase() + '.') + ' WoW compares each week with the week before it (the first row with the last week of the prior period). The annotation names what moved.</div><div class="pv-scroll"><table class="pv"><thead><tr>' +
      '<th>Week</th><th>Sales</th><th>vs target</th><th>Covers</th><th>SPH</th><th>Wage %</th><th>Food %</th><th>' + (siteOnly ? 'Score' : 'Avg score') + '</th>' + (siteOnly ? '<th>Rating</th><th>Red light</th>' : '<th>Sites R / A / G</th><th>Red lights</th>') + '<th style="text-align:left">Annotation</th></tr></thead><tbody>';
    curW.forEach(function (w, i) {
      var e = w.est, b = i > 0 ? curW[i - 1] : before0;
      var pe = b ? b.est : null;
      var vt = e.target ? pctChange(e.sales, e.target) : null;
      var sr = siteOnly ? w.bySite[siteOnly] : null;
      h += '<tr><td class="name">' + wcLabel(w.monday) + '<span>' + rangeLabel(w.monday) + '</span></td>' +
        '<td class="' + tint('sales', e.sales, { target: e.target }) + '">' + gbp(e.sales) + wow(e.sales, pe && pe.sales, 'sales') + '</td>' +
        '<td class="' + tint('vst', vt) + '">' + (vt == null ? 'n/a' : '<span class="pv-chip ' + band('vst', vt) + '">' + (vt > 0 ? '+' : '') + vt.toFixed(1) + '%</span>') + '</td>' +
        '<td class="' + tint('covers', e.covers, { prev: pe && pe.covers }) + '">' + int(e.covers) + wow(e.covers, pe && pe.covers, 'covers') + '</td>' +
        '<td class="' + tint('sph', e.sph, { sphT: e.sphT }) + '">' + gbp2(e.sph) + wow(e.sph, pe && pe.sph, 'sph') + '</td>' +
        '<td class="' + tint('wage', e.wage) + '">' + pct1(e.wage) + wow(e.wage, pe && pe.wage, 'wage') + '</td>' +
        '<td class="' + tint('food', e.food) + '">' + pct1(e.food) + wow(e.food, pe && pe.food, 'food') + '</td>' +
        '<td class="' + tint('score', e.score) + '">' + (e.score == null ? 'n/a' : e.score.toFixed(0)) + wow(e.score, pe && pe.score, 'score') + '</td>';
      if (siteOnly){
        h += '<td class="' + tint('rating', sr && sr.rating) + '">' + (sr && sr.rating != null ? sr.rating.toFixed(2) + '★' + (sr.nReviews != null ? '<span class="pv-wow na">' + sr.nReviews + ' reviews</span>' : '') : 'n/a') + '</td>' +
          '<td class="' + (sr && sr.red ? 'pv-tint-red' : 'pv-tint-green') + '" style="white-space:normal;max-width:170px;text-align:left">' + (sr && sr.red ? sr.triggers.map(function (t) { return '<span class="pv-chip red">' + esc(t) + '</span>'; }).join(' ') : '<span class="pv-chip green">clear</span>') + '</td>';
      } else {
        h += '<td class="' + (e.red ? 'pv-tint-red' : e.amber ? 'pv-tint-amber' : 'pv-tint-green') + '"><span class="pv-dot red"></span>' + e.red + ' <span class="pv-dot amber"></span>' + e.amber + ' <span class="pv-dot green"></span>' + e.green + '</td>' +
          '<td class="' + (e.redSites.length ? 'pv-tint-red' : 'pv-tint-green') + '">' + (e.redSites.length ? '<span class="pv-chip red">' + e.redSites.length + '</span>' : '<span class="pv-chip green">0</span>') + '</td>';
      }
      h += '<td class="ann">' + (siteOnly ? annotateSite(sr, b && b.bySite[siteOnly], themesFor([siteOnly], w.monday)) : annotate(w, b, inScope, themesFor(scopeCodes, w.monday), seen)) + '</td></tr>';
    });
    h += '<tr class="total"><td class="name">' + esc(label) + ' total</td><td>' + gbp(totCur.sales) + (totPrev ? wow(totCur.sales, totPrev.sales, 'sales') : '') + '</td>' +
      '<td>' + (vsT == null ? 'n/a' : (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '%') + '</td>' +
      '<td>' + int(totCur.covers) + (totPrev ? wow(totCur.covers, totPrev.covers, 'covers') : '') + '</td>' +
      '<td>' + gbp2(totCur.sph) + (totPrev ? wow(totCur.sph, totPrev.sph, 'sph') : '') + '</td>' +
      '<td>' + pct1(totCur.wage) + (totPrev ? wow(totCur.wage, totPrev.wage, 'wage') : '') + '</td>' +
      '<td>' + pct1(totCur.food) + (totPrev ? wow(totCur.food, totPrev.food, 'food') : '') + '</td>' +
      '<td>' + (totCur.score == null ? 'n/a' : totCur.score.toFixed(0)) + (totPrev ? wow(totCur.score, totPrev.score, 'score') : '') + '</td>' +
      '<td colspan="3" style="text-align:left;white-space:normal;font-weight:500;font-size:11.5px;opacity:.9">' + (totPrev ? 'Chips on this row are' + lfl + '.' : 'No prior period in the data set.') + '</td></tr>';
    h += '</tbody></table></div></div>';

    /* ----- Red light persistence ----- */
    h += '<div class="pv-card" id="pv-rl"><h2>Red lights, week after week' + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">One dot per closed week in ' + esc(label) + ' (oldest left, newest right): red = tripped, green = clear, grey = no data. "Streak" counts consecutive red weeks up to the newest week, across the full history, not just this period. Sites red on every KPI week are listed first.</div><div id="pv-rl-body" class="pv-empty">Loading history…</div></div>';

    /* ----- Site by site grid (or single site, all measures) ----- */
    var m = METRICS[metric];
    function periodAgg(recs){ return aggregate(recs); }
    function periodVal(recs){ return periodAgg(recs)[metric]; }
    if (siteOnly){
      var sc = siteOnly;
      h += '<div class="pv-card"><h2>' + esc(scopeLabel) + ', every measure week by week</h2><div class="hint">Period column: sales and covers summed, SPH from the totals, wage % and food % sales-weighted, score averaged' + (totPrev ? '; compared like for like with ' + prevLabel : '') + '.</div><div class="pv-scroll"><table class="pv"><thead><tr><th>Measure</th>' + curW.map(function (w) { return '<th>' + wcLabel(w.monday) + '</th>'; }).join('') + '<th>' + esc(label) + '</th>' + (totPrev ? '<th>vs prior</th>' : '') + '</tr></thead><tbody>';
      Object.keys(METRICS).forEach(function (mk) {
        var mm = METRICS[mk], cells = '';
        curW.forEach(function (w, i) {
          var r = w.bySite[sc], v = r ? r[mk] : null;
          var b = i > 0 ? curW[i - 1].bySite[sc] : (before0 && before0.bySite[sc]);
          cells += '<td class="' + tint(mk, v, { target: r && r.target, prev: b && b[mk], sphT: r && r.sphT }) + '">' + mm.fmt(v) + wow(v, b ? b[mk] : null, mk) + '</td>';
        });
        var pv = totCur[mk], pp = totPrev ? totPrev[mk] : null;
        h += '<tr><td class="name">' + mm.label + '</td>' + cells + '<td class="' + tint(mk, pv, { target: totCur.target, prev: pp, sphT: totCur.sphT }) + '"><strong>' + mm.fmt(pv) + '</strong></td>' + (totPrev ? '<td class="' + tintDelta(pv, pp, mk) + '">' + mm.fmt(pp) + wow(pv, pp, mk) + '</td>' : '') + '</tr>';
      });
      // extra rows: vs target, rating, red light
      h += '<tr><td class="name">vs target</td>' + curW.map(function (w) { var r = w.bySite[sc]; var v = r && r.varPct; return '<td class="' + tint('vst', v) + '">' + (v == null ? 'n/a' : '<span class="pv-chip ' + band('vst', v) + '">' + (v > 0 ? '+' : '') + v.toFixed(1) + '%</span>') + '</td>'; }).join('') + '<td class="' + tint('vst', vsT) + '">' + (vsT == null ? 'n/a' : '<strong>' + (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '%</strong>') + '</td>' + (totPrev ? '<td></td>' : '') + '</tr>';
      h += '<tr><td class="name">Google rating</td>' + curW.map(function (w) { var r = w.bySite[sc]; return '<td class="' + tint('rating', r && r.rating) + '">' + (r && r.rating != null ? r.rating.toFixed(2) + '★' : 'n/a') + (r && r.nReviews != null ? '<span class="pv-wow na">' + r.nReviews + ' reviews</span>' : '') + '</td>'; }).join('') + '<td class="' + tint('rating', totCur.rating) + '">' + (totCur.rating != null ? '<strong>' + totCur.rating.toFixed(2) + '★</strong><span class="pv-wow na">' + totCur.nReviews + ' reviews</span>' : '') + '</td>' + (totPrev ? '<td class="' + (totCur.rating != null && totPrev.rating != null ? (totCur.rating > totPrev.rating + 0.005 ? 'pv-tint-green' : totCur.rating < totPrev.rating - 0.005 ? 'pv-tint-red' : 'pv-tint-amber') : '') + '">' + (totPrev.rating != null ? totPrev.rating.toFixed(2) + '★' : '') + '</td>' : '') + '</tr>';
      h += '<tr><td class="name">Red light</td>' + curW.map(function (w) { var r = w.bySite[sc]; return '<td class="' + (r && r.red ? 'pv-tint-red' : 'pv-tint-green') + '" style="white-space:normal;max-width:180px">' + (r && r.red ? r.triggers.map(function (t) { return '<span class="pv-chip red">' + esc(t) + '</span>'; }).join(' ') : '<span class="pv-chip green">clear</span>') + '</td>'; }).join('') + '<td class="' + (curW.some(function (w) { return w.bySite[sc] && w.bySite[sc].red; }) ? 'pv-tint-red' : 'pv-tint-green') + '">' + curW.filter(function (w) { return w.bySite[sc] && w.bySite[sc].red; }).length + ' of ' + nWeeks + ' weeks red</td>' + (totPrev ? '<td></td>' : '') + '</tr>';
      h += '</tbody></table></div></div>';
    } else {
      h += '<div class="pv-card"><h2>Site by site, week by week' + (scope !== 'all' ? ' · ' + esc(scopeLabel) : '') + '</h2><div class="hint">Pick a measure. Each cell shows the week’s value with its WoW move underneath. Click a site to open it on its own. The period column is the ' +
        (m.how === 'sum' ? 'sum' : m.how === 'avg' ? 'average' : 'sales-weighted figure') + ' across the weeks shown' + (totPrev ? ', compared like for like with ' + prevLabel : '') + '.</div>' +
        '<div class="pv-metrics">' + Object.keys(METRICS).map(function (k) { return '<button class="pv-pill' + (k === metric ? ' active' : '') + '" data-metric="' + k + '">' + METRICS[k].label + '</button>'; }).join('') + '</div>' +
        '<div class="pv-scroll"><table class="pv"><thead><tr><th>Site</th>' + curW.map(function (w) { return '<th>' + wcLabel(w.monday) + '</th>'; }).join('') + '<th>' + esc(label) + '</th>' + (totPrev ? '<th>vs prior</th>' : '') + '</tr></thead><tbody>';
      function rowFor(nameHtml, recsPerWeek, prevRecsAll, cls, attr){
        var cells = '', valsAll = [];
        curW.forEach(function (w, i) {
          var recs = recsPerWeek[i]; var ag = recs.length ? periodAgg(recs) : null; var v = ag ? ag[metric] : null;
          var b = i > 0 ? recsPerWeek[i - 1] : recsPerWeek.before;
          var pv = b && b.length ? periodVal(b) : null;
          valsAll = valsAll.concat(recs);
          cells += '<td class="' + (cls === 'total' ? '' : tint(metric, v, { target: ag && ag.target, prev: pv, sphT: ag && ag.sphT })) + '">' + m.fmt(v) + wow(v, pv, metric) + '</td>';
        });
        var pag = valsAll.length ? periodAgg(valsAll) : null, pval = pag ? pag[metric] : null;
        var ppval = prevRecsAll && prevRecsAll.length ? periodVal(prevRecsAll) : null;
        return '<tr' + (cls ? ' class="' + cls + '"' : '') + (attr || '') + '><td class="name">' + nameHtml + '</td>' + cells + '<td class="' + (cls === 'total' ? '' : tint(metric, pval, { target: pag && pag.target, prev: ppval, sphT: pag && pag.sphT })) + '"><strong>' + m.fmt(pval) + '</strong></td>' + (totPrev ? '<td class="' + (cls === 'total' ? '' : tintDelta(pval, ppval, metric)) + '">' + m.fmt(ppval) + wow(pval, ppval, metric) + '</td>' : '') + '</tr>';
      }
      var cols = curW.length + 2 + (totPrev ? 1 : 0);
      clusters.filter(function (cl) { return scope === 'all' || scope === cl; }).forEach(function (cl) {
        h += '<tr class="cluster"><td colspan="' + cols + '">' + esc(cl || 'Unassigned') + '</td></tr>';
        order.filter(function (c) { return clusterOf[c] === cl; }).forEach(function (code) {
          var per = curW.map(function (w) { return w.bySite[code] ? [w.bySite[code]] : []; });
          per.before = before0 && before0.bySite[code] ? [before0.bySite[code]] : [];
          var pr = [].concat.apply([], prevW.map(function (w) { return w.bySite[code] ? [w.bySite[code]] : []; }));
          var nm = seen[code];
          h += rowFor(esc(nm.label) + '<span>' + esc(nm.name) + '</span>', per, pr, '', ' class="pv-site-row" data-site="' + code + '" style="cursor:pointer" title="Open ' + esc(nm.label) + ' on its own"');
        });
        var perC = curW.map(function (w) { return w.recs.filter(function (r) { return r.cluster === cl; }); });
        perC.before = before0 ? before0.recs.filter(function (r) { return r.cluster === cl; }) : [];
        h += rowFor(esc(cl || 'Unassigned') + ' subtotal', perC, allPrev.filter(function (r) { return r.cluster === cl; }), 'sub');
      });
      var perE = curW.map(function (w) { return w.recs.filter(inScope); }); perE.before = before0 ? before0.recs.filter(inScope) : [];
      h += rowFor(scope === 'all' ? 'Estate' : esc(scope) + ' total', perE, allPrev, 'total');
      h += '</tbody></table></div></div>';
    }
    h += '<div class="pv-foot">Every cell is banded red, amber or green on the same bands as the weekly view. Sales vs target: green at or above target, amber to -10%, red below -10%. Covers: WoW, green up, amber to -5%, red below -5%. SPH vs the site target (£22; Maki Nori £35; Ikigai £21): green at target, amber within £2, red below. Wage %: green 21% and under, amber to 23%, red above 23%. Food %: green 25% and under, amber to 28%, red above 28%. Score: green 95 and above, amber 80 to 94, red below 80. Rating: green 4.7 and above, amber 4.5 to 4.69, red below 4.5. "vs prior" cells: green if the move is good, red if bad. Complaints in the annotation are Google reviews of any star rating carrying at least one classified issue (from the Reviews intelligence file), counted once per theme; hygiene = dirty premises or a foreign body / food safety mention. A week sits in the month or quarter its Monday falls in. Sales and covers are summed; SPH is period sales over period covers; wage % and food % are sales-weighted; score is the average of the site scores. Red light basis per KPI: ' + RL_KPIS.map(function (k) { return k.label + ' (' + k.rule + ')'; }).join('; ') + '. Sources: the same weekly site JSON files the This Week view reads.</div>';

    view.innerHTML = h;
    view.querySelectorAll('[data-metric]').forEach(function (b) { b.addEventListener('click', function () { metric = b.getAttribute('data-metric'); draw(cur, prev, prevK); }); });
    view.querySelectorAll('.cn-pill[data-scope]').forEach(function (b) { b.addEventListener('click', function () { scope = b.getAttribute('data-scope'); draw(cur, prev, prevK); }); });
    view.querySelectorAll('.pv-site-row').forEach(function (tr) { tr.addEventListener('click', function () { scope = 'site:' + tr.getAttribute('data-site'); draw(cur, prev, prevK); window.scrollTo({ top: 0, behavior: 'smooth' }); }); });
    var ss = view.querySelector('#pv-site'); if (ss) ss.addEventListener('change', function () { scope = ss.value || 'all'; draw(cur, prev, prevK); });

    // Red light board needs the full history for streaks.
    loadAllWeeks().then(function () { drawRedLights(curW, scopeCodes, seen, clusterOf); });
    // Complaint themes land once, then the annotations are redrawn.
    if (!THEMES){ var token = ++DRAW_TOKEN; loadThemes().then(function () { if (token === DRAW_TOKEN) draw(cur, prev, prevK); }); }
  }

  function drawRedLights(curW, codes, seen, clusterOf){
    var host = document.getElementById('pv-rl-body'); if (!host) return;
    // full history, oldest first
    var hist = weeksIndex.slice().sort(function (a, b) { return a.monday < b.monday ? -1 : 1; }).map(function (w) { var j = cache[w.monday]; return { monday: w.monday, sites: (j && j.sites) || {} }; });
    var curSet = {}; curW.forEach(function (w) { curSet[w.monday] = 1; });
    var rows = codes.map(function (code) {
      var kp = {};
      RL_KPIS.forEach(function (k) {
        var dots = [], streak = 0, redInPeriod = 0, nInPeriod = 0, broken = false;
        hist.forEach(function (w) {
          var s = w.sites[code]; var st = s ? rlState(k, siteRec(s)) : 'na';
          if (curSet[w.monday]){ dots.push({ m: w.monday, st: st }); if (st !== 'na') nInPeriod++; if (st === 'red') redInPeriod++; }
        });
        for (var i = hist.length - 1; i >= 0; i--){ var s2 = hist[i].sites[code]; var st2 = s2 ? rlState(k, siteRec(s2)) : 'na'; if (st2 === 'red') streak++; else if (st2 === 'ok') break; /* na: skip without breaking */ }
        kp[k.id] = { dots: dots, streak: streak, red: redInPeriod, n: nInPeriod };
      });
      var totalRed = 0, totalN = 0, everyWeek = 0;
      RL_KPIS.forEach(function (k) { totalRed += kp[k.id].red; totalN += kp[k.id].n; if (kp[k.id].n && kp[k.id].red === kp[k.id].n) everyWeek++; });
      // overall red light streak
      var ov = 0; for (var i2 = hist.length - 1; i2 >= 0; i2--){ var s3 = hist[i2].sites[code]; if (!s3) continue; if (s3.red_light && s3.red_light.status === 'red') ov++; else break; }
      return { code: code, kp: kp, totalRed: totalRed, totalN: totalN, everyWeek: everyWeek, ovStreak: ov };
    });
    rows.sort(function (a, b) { return (b.everyWeek - a.everyWeek) || (b.ovStreak - a.ovStreak) || (b.totalRed - a.totalRed); });
    var nW = curW.length;
    var h = '<div class="pv-scroll"><table class="pv"><thead><tr><th>Site</th><th>Red light streak</th>' + RL_KPIS.map(function (k) { return '<th>' + k.label + '</th>'; }).join('') + '<th>Red weeks</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      var nm = seen[r.code];
      var flag = r.everyWeek ? '<span class="pv-chip red" title="red every week of the period on ' + r.everyWeek + ' KPI' + (r.everyWeek > 1 ? 's' : '') + '">' + r.everyWeek + ' KPI' + (r.everyWeek > 1 ? 's' : '') + ' red all period</span>' : '';
      h += '<tr class="pv-site-row" data-site="' + r.code + '" style="cursor:pointer"><td class="name">' + esc(nm.label) + '<span>' + esc(nm.name) + '</span><div style="margin-top:3px">' + flag + '</div></td>' +
        '<td>' + (r.ovStreak ? '<span class="pv-chip ' + (r.ovStreak >= 3 ? 'red' : 'amber') + '">' + r.ovStreak + ' wk' + (r.ovStreak > 1 ? 's' : '') + ' in a row</span>' : '<span class="pv-chip green">clear</span>') + '</td>';
      RL_KPIS.forEach(function (k) {
        var x = r.kp[k.id];
        var dots = x.dots.map(function (dd) { return '<span class="pv-rld ' + dd.st + '" title="' + wcLabel(dd.m) + ': ' + dd.st + '"></span>'; }).join('');
        var cls = x.n && x.red === x.n ? 'pv-tint-red' : '';
        h += '<td class="' + cls + '" style="text-align:left"><div class="pv-rl-dots">' + dots + '</div><span class="pv-wow ' + (x.streak ? 'down' : 'na') + '">' + (x.streak ? x.streak + ' in a row' : (x.n ? 'clear' : 'no data')) + (x.n ? ' · ' + x.red + '/' + x.n : '') + '</span></td>';
      });
      h += '<td><strong>' + r.totalRed + '</strong><span class="pv-wow na">of ' + r.totalN + ' KPI weeks</span></td></tr>';
    });
    h += '</tbody></table></div>';
    host.className = ''; host.innerHTML = h;
    host.querySelectorAll('.pv-site-row').forEach(function (tr) { tr.addEventListener('click', function () { var sel = document.getElementById('pv-site'); scope = 'site:' + tr.getAttribute('data-site'); if (sel){ sel.value = scope; sel.dispatchEvent(new Event('change')); } window.scrollTo({ top: 0, behavior: 'smooth' }); }); });
  }

  function pp(v){ return (v > 0 ? '+' : '') + v.toFixed(1) + 'pp'; }
  function pc(v){ return (v > 0 ? '+' : '') + v.toFixed(1) + '%'; }
  function trig(t){ return t.split(' ')[0]; }

  // Short note for one site week.
  function annotateSite(r, b, th){
    if (!r) return 'No file for this site this week.';
    var p = [];
    if (r.varPct != null) p.push('Sales ' + pc(r.varPct) + ' vs target');
    var sw = b && b.sales != null && r.sales != null ? pctChange(r.sales, b.sales) : null;
    if (sw != null) p.push(pc(sw) + ' WoW (' + (r.sales - b.sales < 0 ? '-' : '+') + gbp(Math.abs(r.sales - b.sales)) + ')');
    var s = p.length ? p.join(', ') + '.' : '';
    var c = [];
    if (b && r.wage != null && b.wage != null && Math.abs(r.wage - b.wage) >= 0.5) c.push('wage ' + pp(r.wage - b.wage));
    if (b && r.food != null && b.food != null && Math.abs(r.food - b.food) >= 0.5) c.push('food ' + pp(r.food - b.food));
    if (c.length) s += ' ' + c.join(', ').replace(/^./, function (x) { return x.toUpperCase(); }) + '.';
    if (r.rating != null) s += ' Rating ' + r.rating.toFixed(2) + (r.nReviews != null ? ' on ' + r.nReviews : '') + (r.rating < 4.7 ? ' (under 4.7).' : '.');
    s += ' ' + complaintsText(th);
    if (r.prep != null && r.prep > 15) s += ' Deliveroo prep ' + r.prep.toFixed(1) + ' min.';
    var rl = r.red ? 'Red light: ' + r.triggers.map(trig).join(', ') : 'No red light';
    if (b){
      var nw = r.triggers.filter(function (t) { return !b.triggers.some(function (u) { return trig(u) === trig(t); }); }).map(trig);
      var cl = b.triggers.filter(function (t) { return !r.triggers.some(function (u) { return trig(u) === trig(t); }); }).map(trig);
      var x = []; if (nw.length) x.push('new ' + nw.join(', ')); if (cl.length) x.push('cleared ' + cl.join(', '));
      if (x.length) rl += ' (' + x.join('; ') + ')';
    }
    return esc(s.trim() + ' ' + rl + '.');
  }

  // Short note for one estate / cluster week.
  function annotate(w, before, inScope, th, seen){
    inScope = inScope || function(){ return true; };
    var e = w.est;
    var labels = {}; Object.keys(seen || {}).forEach(function (c) { labels[c] = seen[c].label; });
    if (!before) return esc('First week in the data set, no WoW. ' + complaintsText(th, labels));
    var pe = before.est, parts = [];
    var sw = pctChange(e.sales, pe.sales);
    if (sw != null) parts.push('Sales ' + pc(sw) + ' WoW (' + (e.sales - pe.sales < 0 ? '-' : '+') + gbp(Math.abs(e.sales - pe.sales)) + ')');
    var cw = pctChange(e.covers, pe.covers);
    if (cw != null) parts.push('covers ' + pc(cw));
    var s = parts.join(', ') + '.';
    var moves = [];
    w.recs.filter(inScope).forEach(function (r) { var b = before.bySite[r.jsonCode]; if (!b) return; var p = pctChange(r.sales, b.sales); if (p != null) moves.push({ l: r.label, p: p }); });
    moves.sort(function (a, b) { return b.p - a.p; });
    var ups = moves.filter(function (x) { return x.p >= 5; }).slice(0, 2), downs = moves.filter(function (x) { return x.p <= -5; }).slice(-2).reverse();
    if (ups.length) s += ' Up: ' + ups.map(function (x) { return x.l + ' ' + pc(x.p); }).join(', ') + '.';
    if (downs.length) s += ' Down: ' + downs.map(function (x) { return x.l + ' ' + pc(x.p); }).join(', ') + '.';
    var c = [];
    if (e.wage != null && pe.wage != null && Math.abs(e.wage - pe.wage) >= 0.5) c.push('wage ' + pp(e.wage - pe.wage));
    if (e.food != null && pe.food != null && Math.abs(e.food - pe.food) >= 0.5) c.push('food ' + pp(e.food - pe.food));
    if (c.length) s += ' ' + c.join(', ').replace(/^./, function (x) { return x.toUpperCase(); }) + '.';
    s += ' ' + complaintsText(th, labels);
    var newRed = e.redSites.filter(function (x) { return pe.redSites.indexOf(x) < 0; });
    var cleared = pe.redSites.filter(function (x) { return e.redSites.indexOf(x) < 0; });
    var rl = e.redSites.length ? 'Red lights ' + e.redSites.length : 'No red lights';
    function few(a){ return a.length > 4 ? a.slice(0, 4).join(', ') + ' +' + (a.length - 4) + ' more' : a.join(', '); }
    var x = []; if (newRed.length) x.push('new ' + few(newRed)); if (cleared.length) x.push('cleared ' + few(cleared));
    if (x.length) rl += ' (' + x.join('; ') + ')';
    return esc(s + ' ' + rl + '.');
  }

  /* ---------- boot ---------- */
  fetch(DATA + 'weeks_index.json', { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (idx) {
      weeksIndex = ((idx && idx.weeks) || []).slice().sort(function (a, b) { return a.monday > b.monday ? -1 : 1; });
      renderBar();
      // Keep the pills honest whenever the header week selector (or the
      // default-week picker on load) moves the weekly view.
      var lastSeen = null;
      setInterval(function () {
        if (mode === 'month' || mode === 'quarter') return;
        var k = window.currentWeekKey; if (k === lastSeen) return; lastSeen = k;
        var nm = (weeksIndex[0] && k === weeksIndex[0].monday) ? 'this' : (weeksIndex[1] && k === weeksIndex[1].monday) ? 'last' : 'other';
        if (nm !== mode){ mode = nm; renderBar(); }
      }, 400);
      // Deep link: ?view=month or ?view=quarter (optionally &period=2026-10 / 2026-Q4)
      var q = new URLSearchParams(location.search), v = q.get('view');
      if (v === 'month' || v === 'quarter'){ periodKey = q.get('period') || null; setMode(v, { silent: true }); }
    })
    .catch(function () { renderBar(); });
})();
