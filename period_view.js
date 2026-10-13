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
  function tint(metric, v){
    if (v == null) return '';
    if (metric === 'wage')  return v <= 22 ? 'pv-tint-green' : v <= 24 ? 'pv-tint-amber' : 'pv-tint-red';
    if (metric === 'food')  return v <= 25 ? 'pv-tint-green' : 'pv-tint-red';
    if (metric === 'score') return v >= 95 ? 'pv-tint-green' : v >= 80 ? 'pv-tint-amber' : 'pv-tint-red';
    return '';
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
    return { code: disp, name: (hit && hit.name) || EXTRA_NAMES[code] || jsonName || code };
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
  function siteRec(s){
    var k = s.kpis || {};
    var sales = k.sales && k.sales.actual, covers = k.covers && k.covers.actual;
    var sph = (k.sph && k.sph.actual != null) ? k.sph.actual : (sales != null && covers ? sales / covers : null);
    return {
      sales: sales, target: k.sales && k.sales.target, covers: covers, sph: sph,
      wage: k.wage_pct && k.wage_pct.actual, food: k.food_pct && k.food_pct.actual,
      score: s.efficiency_score && s.efficiency_score.score,
      rag: (s.efficiency_score && s.efficiency_score.rag) || null,
      red: s.red_light && s.red_light.status === 'red',
      triggers: (s.red_light && s.red_light.triggers) || []
    };
  }
  // Aggregate a list of site records.
  function aggregate(recs){
    var a = { sales: 0, target: 0, nTarget: 0, covers: 0, wageNum: 0, wageDen: 0, foodNum: 0, foodDen: 0, scoreSum: 0, scoreN: 0, red: 0, amber: 0, green: 0, n: 0, redSites: [] };
    recs.forEach(function (r) {
      a.n++;
      if (r.sales != null){ a.sales += r.sales; if (r.target != null){ a.target += r.target; a.nTarget++; } }
      if (r.covers != null) a.covers += r.covers;
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
      red: a.red, amber: a.amber, green: a.green, redSites: a.redSites, n: a.n
    };
  }

  /* ---------- state ---------- */
  var mode = 'this';        // this | last | month | quarter
  var periodKey = null;     // e.g. 2026-10 or 2026-Q4
  var metric = 'sales';
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

  function draw(cur, prev, prevK){
    var label = mode === 'month' ? monthLabel(periodKey) : quarterLabel(periodKey);
    var prevLabel = mode === 'month' ? monthLabel(prevK) : quarterLabel(prevK);
    if (!cur.length){ view.innerHTML = '<div class="pv-card pv-empty">No weeks closed yet in ' + esc(label) + '.</div>'; return; }

    // Build per-week structures.
    function weekData(w){
      var j = cache[w.monday]; if (!j || !j.sites) return null;
      var recs = [], bySite = {};
      Object.keys(j.sites).forEach(function (code) {
        var r = siteRec(j.sites[code]); var nm = siteName(code, j.sites[code].name);
        r.label = nm.code; r.name = nm.name; r.jsonCode = code; r.cluster = j.sites[code].cluster || '';
        recs.push(r); bySite[code] = r;
      });
      return { monday: w.monday, recs: recs, bySite: bySite, est: aggregate(recs) };
    }
    function prevMondayOf(iso){ var p = d(iso); p.setUTCDate(p.getUTCDate() - 7); return p.toISOString().slice(0, 10); }
    var curW = cur.map(weekData).filter(Boolean);
    var prevW = prev.map(weekData).filter(Boolean);
    var wkBefore = {};
    curW.forEach(function (w) { var pm = prevMondayOf(w.monday); var pj = cache[pm]; wkBefore[w.monday] = pj ? weekData({ monday: pm }) : null; });
    if (!curW.length){ view.innerHTML = '<div class="pv-card pv-empty">Week files for ' + esc(label) + ' could not be loaded.</div>'; return; }

    // Period totals (estate) = aggregate over every site-week.
    var allCur = [].concat.apply([], curW.map(function (w) { return w.recs; }));
    var allPrev = [].concat.apply([], prevW.map(function (w) { return w.recs; }));
    var totCur = aggregate(allCur), totPrev = prevW.length ? aggregate(allPrev) : null;
    var expected = mode === 'month' ? null : 13;
    var nWeeks = curW.length;
    var isOpen = (weeksIndex[0] && (mode === 'month' ? monthKey(weeksIndex[0].monday) : quarterKey(weeksIndex[0].monday)) === periodKey);
    var lfl = totPrev ? ' vs first ' + nWeeks + ' week' + (nWeeks > 1 ? 's' : '') + ' of ' + prevLabel : '';

    function heroStat(n, l, cur, prv, metricKey){
      var m = METRICS[metricKey];
      var dl = '';
      if (prv != null && cur != null){
        var delta = m.wowAbs ? cur - prv : pctChange(cur, prv);
        if (delta != null){
          var up = delta > 0, good = m.upGood ? up : !up;
          dl = '<div class="d" style="color:' + (Math.abs(delta) < 0.05 ? 'rgba(255,255,255,.6)' : good ? '#6ee7b7' : '#fca5a5') + '">' + (up ? '▲ ' : '▼ ') + (up ? '+' : '') + delta.toFixed(1) + (m.wowAbs ? (metricKey === 'score' ? ' pts' : ' pp') : '%') + ' vs prior</div>';
        }
      }
      return '<div class="pv-stat"><div class="n">' + n + '</div><div class="l">' + l + '</div>' + dl + '</div>';
    }
    var vsT = totCur.target ? pctChange(totCur.sales, totCur.target) : null;
    var h = '<div class="pv-hero"><div><div class="eyebrow">AM ' + (mode === 'month' ? 'Monthly' : 'Quarterly') + ' view</div>' +
      '<h1>' + esc(label) + '</h1><div class="sub">' + nWeeks + (expected ? ' of ' + expected : '') + ' week' + ((nWeeks > 1 || expected) ? 's' : '') + ' closed' + (isOpen ? ' so far (period still open)' : '') +
      ' · ' + wcLabel(curW[0].monday) + ' to ' + wcLabel(curW[curW.length - 1].monday) + ' · ' + totCur.n / nWeeks + ' sites' +
      (totPrev ? ' · deltas are like for like' + lfl : ' · no prior period to compare') + '</div></div>' +
      '<div class="pv-stats">' +
      heroStat(gbp(totCur.sales), 'Sales' + (vsT != null ? ' · ' + (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '% vs target' : ''), totCur.sales, totPrev && totPrev.sales, 'sales') +
      heroStat(int(totCur.covers), 'Covers', totCur.covers, totPrev && totPrev.covers, 'covers') +
      heroStat(gbp2(totCur.sph), 'SPH', totCur.sph, totPrev && totPrev.sph, 'sph') +
      heroStat(pct1(totCur.wage), 'Wage %', totCur.wage, totPrev && totPrev.wage, 'wage') +
      heroStat(pct1(totCur.food), 'Food %', totCur.food, totPrev && totPrev.food, 'food') +
      heroStat(totCur.score == null ? 'n/a' : totCur.score.toFixed(0), 'Avg score', totCur.score, totPrev && totPrev.score, 'score') +
      '</div></div>';

    /* ----- Week on week (estate) with annotations ----- */
    h += '<div class="pv-card"><h2>Week on week: ' + esc(label) + '</h2><div class="hint">Estate totals per closed week. WoW compares each week with the week before it (the first row compares with the last week of the prior period). The annotation names what moved.</div><div class="pv-scroll"><table class="pv"><thead><tr>' +
      '<th>Week</th><th>Sales</th><th>vs target</th><th>Covers</th><th>SPH</th><th>Wage %</th><th>Food %</th><th>Avg score</th><th>Sites R / A / G</th><th>Red lights</th><th style="text-align:left">Annotation</th></tr></thead><tbody>';
    curW.forEach(function (w, i) {
      var e = w.est, b = i > 0 ? curW[i - 1] : wkBefore[w.monday];
      var pe = b ? b.est : null;
      var vt = e.target ? pctChange(e.sales, e.target) : null;
      h += '<tr><td class="name">' + wcLabel(w.monday) + '<span>' + rangeLabel(w.monday) + '</span></td>' +
        '<td>' + gbp(e.sales) + wow(e.sales, pe && pe.sales, 'sales') + '</td>' +
        '<td>' + (vt == null ? 'n/a' : '<span class="pv-chip ' + (vt >= 0 ? 'green' : vt >= -10 ? 'amber' : 'red') + '">' + (vt > 0 ? '+' : '') + vt.toFixed(1) + '%</span>') + '</td>' +
        '<td>' + int(e.covers) + wow(e.covers, pe && pe.covers, 'covers') + '</td>' +
        '<td>' + gbp2(e.sph) + wow(e.sph, pe && pe.sph, 'sph') + '</td>' +
        '<td class="' + tint('wage', e.wage) + '">' + pct1(e.wage) + wow(e.wage, pe && pe.wage, 'wage') + '</td>' +
        '<td class="' + tint('food', e.food) + '">' + pct1(e.food) + wow(e.food, pe && pe.food, 'food') + '</td>' +
        '<td class="' + tint('score', e.score) + '">' + (e.score == null ? 'n/a' : e.score.toFixed(0)) + wow(e.score, pe && pe.score, 'score') + '</td>' +
        '<td><span class="pv-dot red"></span>' + e.red + ' <span class="pv-dot amber"></span>' + e.amber + ' <span class="pv-dot green"></span>' + e.green + '</td>' +
        '<td>' + (e.redSites.length ? '<span class="pv-chip red">' + e.redSites.length + '</span>' : '<span class="pv-chip green">0</span>') + '</td>' +
        '<td class="ann">' + annotate(w, b) + '</td></tr>';
    });
    // Period total row
    h += '<tr class="total"><td class="name">' + esc(label) + ' total</td><td>' + gbp(totCur.sales) + (totPrev ? wow(totCur.sales, totPrev.sales, 'sales') : '') + '</td>' +
      '<td>' + (vsT == null ? 'n/a' : (vsT > 0 ? '+' : '') + vsT.toFixed(1) + '%') + '</td>' +
      '<td>' + int(totCur.covers) + (totPrev ? wow(totCur.covers, totPrev.covers, 'covers') : '') + '</td>' +
      '<td>' + gbp2(totCur.sph) + (totPrev ? wow(totCur.sph, totPrev.sph, 'sph') : '') + '</td>' +
      '<td>' + pct1(totCur.wage) + (totPrev ? wow(totCur.wage, totPrev.wage, 'wage') : '') + '</td>' +
      '<td>' + pct1(totCur.food) + (totPrev ? wow(totCur.food, totPrev.food, 'food') : '') + '</td>' +
      '<td>' + (totCur.score == null ? 'n/a' : totCur.score.toFixed(0)) + (totPrev ? wow(totCur.score, totPrev.score, 'score') : '') + '</td>' +
      '<td colspan="3" style="text-align:left;white-space:normal;font-weight:500;font-size:11.5px;opacity:.9">' + (totPrev ? 'Chips on this row are' + lfl + '.' : 'No prior period in the data set.') + '</td></tr>';
    h += '</tbody></table></div></div>';

    /* ----- Site by site, week by week ----- */
    h += '<div class="pv-card"><h2>Site by site, week by week</h2><div class="hint">Pick a measure. Each cell shows the week’s value with its WoW move underneath. The period column is the ' +
      (METRICS[metric].how === 'sum' ? 'sum' : METRICS[metric].how === 'avg' ? 'average' : 'sales-weighted figure') + ' across the weeks shown' + (totPrev ? ', compared like for like with ' + prevLabel : '') + '.</div>' +
      '<div class="pv-metrics">' + Object.keys(METRICS).map(function (k) { return '<button class="pv-pill' + (k === metric ? ' active' : '') + '" data-metric="' + k + '">' + METRICS[k].label + '</button>'; }).join('') + '</div>' +
      '<div class="pv-scroll"><table class="pv"><thead><tr><th>Site</th>' + curW.map(function (w) { return '<th>' + wcLabel(w.monday) + '</th>'; }).join('') + '<th>' + esc(label) + '</th>' + (totPrev ? '<th>vs prior</th>' : '') + '</tr></thead><tbody>';

    // Site order: from the newest week file (cluster grouped), add any site seen only in older weeks.
    var order = [], seen = {}, clusterOf = {};
    curW.slice().reverse().forEach(function (w) { w.recs.forEach(function (r) { if (!seen[r.jsonCode]){ seen[r.jsonCode] = r; order.push(r.jsonCode); clusterOf[r.jsonCode] = r.cluster; } }); });
    var clusters = []; order.forEach(function (c) { if (clusters.indexOf(clusterOf[c]) < 0) clusters.push(clusterOf[c]); });
    var m = METRICS[metric];
    function periodVal(recs){ var a = aggregate(recs); return a[metric]; }
    function rowFor(nameHtml, recsPerWeek, prevRecsAll, cls){
      var cells = '', valsAll = [];
      curW.forEach(function (w, i) {
        var recs = recsPerWeek[i]; var v = recs.length ? periodVal(recs) : null;
        var b = i > 0 ? recsPerWeek[i - 1] : null;
        if (i === 0 && wkBefore[w.monday]) b = recsPerWeek.before;
        var pv = b && b.length ? periodVal(b) : null;
        valsAll = valsAll.concat(recs);
        cells += '<td class="' + (cls ? '' : tint(metric, v)) + '">' + m.fmt(v) + wow(v, pv, metric) + '</td>';
      });
      var pval = valsAll.length ? periodVal(valsAll) : null;
      var ppval = prevRecsAll && prevRecsAll.length ? periodVal(prevRecsAll) : null;
      return '<tr' + (cls ? ' class="' + cls + '"' : '') + '><td class="name">' + nameHtml + '</td>' + cells + '<td class="' + (cls ? '' : tint(metric, pval)) + '"><strong>' + m.fmt(pval) + '</strong></td>' + (totPrev ? '<td>' + m.fmt(ppval) + wow(pval, ppval, metric) + '</td>' : '') + '</tr>';
    }
    clusters.forEach(function (cl) {
      h += '<tr class="cluster"><td colspan="' + (curW.length + 2 + (totPrev ? 1 : 0)) + '">' + esc(cl || 'Unassigned') + '</td></tr>';
      var codes = order.filter(function (c) { return clusterOf[c] === cl; });
      codes.forEach(function (code) {
        var per = curW.map(function (w) { return w.bySite[code] ? [w.bySite[code]] : []; });
        var bw = wkBefore[curW[0].monday]; per.before = bw && bw.bySite[code] ? [bw.bySite[code]] : [];
        var pr = [].concat.apply([], prevW.map(function (w) { return w.bySite[code] ? [w.bySite[code]] : []; }));
        var nm = seen[code];
        h += rowFor(esc(nm.label) + '<span>' + esc(nm.name) + '</span>', per, pr, '');
      });
      var perC = curW.map(function (w) { return w.recs.filter(function (r) { return r.cluster === cl; }); });
      var bwc = wkBefore[curW[0].monday]; perC.before = bwc ? bwc.recs.filter(function (r) { return r.cluster === cl; }) : [];
      var prC = allPrev.filter(function (r) { return r.cluster === cl; });
      h += rowFor(esc(cl || 'Unassigned') + ' subtotal', perC, prC, 'sub');
    });
    var perE = curW.map(function (w) { return w.recs; }); var bwe = wkBefore[curW[0].monday]; perE.before = bwe ? bwe.recs : [];
    h += rowFor('Estate', perE, allPrev, 'total');
    h += '</tbody></table></div>' +
      '<div class="pv-foot">Wage % bands: green 22.0% and under, amber 22.01 to 24%, red above 24%. Food % red above 25%. Score: green 95 and above, amber 80 to 94, red below 80. A week sits in the month or quarter its Monday falls in. Sales and covers are summed; SPH is period sales over period covers; wage % and food % are sales-weighted; score is the average of the site scores. Sources: the same weekly site JSON files the This Week view reads.</div></div>';

    view.innerHTML = h;
    view.querySelectorAll('[data-metric]').forEach(function (b) { b.addEventListener('click', function () { metric = b.getAttribute('data-metric'); draw(cur, prev, prevK); }); });
  }

  // Plain English note for one estate week.
  function annotate(w, before){
    var e = w.est;
    if (!before) return 'First week in the data set, so no WoW comparison.';
    var pe = before.est, parts = [];
    var sw = pctChange(e.sales, pe.sales);
    if (sw != null) parts.push('Sales ' + (sw > 0 ? 'up ' : sw < 0 ? 'down ' : 'flat ') + (sw ? Math.abs(sw).toFixed(1) + '%' : '') + ' WoW (' + gbp(e.sales - pe.sales) + ')');
    var cw = pctChange(e.covers, pe.covers);
    if (cw != null) parts.push('covers ' + (cw > 0 ? '+' : '') + cw.toFixed(1) + '%');
    if (e.sph != null && pe.sph != null) parts.push('SPH ' + (e.sph - pe.sph >= 0 ? '+' : '-') + '£' + Math.abs(e.sph - pe.sph).toFixed(2));
    var s1 = parts.join(', ') + '.';
    // movers
    var moves = [];
    w.recs.forEach(function (r) { var b = before.bySite[r.jsonCode]; if (!b) return; var p = pctChange(r.sales, b.sales); if (p != null) moves.push({ l: r.label, p: p }); });
    moves.sort(function (a, b) { return b.p - a.p; });
    var ups = moves.filter(function (x) { return x.p >= 5; }).slice(0, 3), downs = moves.filter(function (x) { return x.p <= -5; }).slice(-3).reverse();
    var s2 = '';
    if (ups.length) s2 += ' Up most: ' + ups.map(function (x) { return x.l + ' +' + x.p.toFixed(1) + '%'; }).join(', ') + '.';
    if (downs.length) s2 += ' Down most: ' + downs.map(function (x) { return x.l + ' ' + x.p.toFixed(1) + '%'; }).join(', ') + '.';
    // cost lines
    var s3 = '';
    if (e.wage != null && pe.wage != null && Math.abs(e.wage - pe.wage) >= 0.5) s3 += ' Wage ' + (e.wage > pe.wage ? 'worse' : 'better') + ' by ' + Math.abs(e.wage - pe.wage).toFixed(1) + ' pp.';
    if (e.food != null && pe.food != null && Math.abs(e.food - pe.food) >= 0.5) s3 += ' Food ' + (e.food > pe.food ? 'worse' : 'better') + ' by ' + Math.abs(e.food - pe.food).toFixed(1) + ' pp.';
    var newRed = e.redSites.filter(function (x) { return pe.redSites.indexOf(x) < 0; });
    var cleared = pe.redSites.filter(function (x) { return e.redSites.indexOf(x) < 0; });
    var s4 = e.redSites.length ? ' Red lights (' + e.redSites.length + '): ' + e.redSites.join(', ') + '.' : ' No red lights.';
    if (newRed.length) s4 += ' New: ' + newRed.join(', ') + '.';
    if (cleared.length) s4 += ' Cleared: ' + cleared.join(', ') + '.';
    return esc(s1 + s2 + s3 + s4);
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
