#!/usr/bin/env python3
"""patch_v67_monthly_story_roi.py  --  Marketing Hub v6.7 (13 Oct 2026)

  1. MONTHLY tab: covers + sales by calendar month vs previous month, estate + per site, MTD like-for-like
     (same days last month) and a month-end projection. Source: data/marketing_monthly.json (built daily
     by builders/build_marketing_monthly.py from the Kobas cash-up daily files + AM weekly files).
  2. SUMMARY: "Footfall story" (weekly covers with marketing actions overlaid + a what-moved-covers readout)
     and "Marketing return" (Loyalty and Slerp revenue vs tagged ad spend + offer cost).
  3. Brand refresh: Maki orange tokens, logo in the header, orange active tab.

Usage: python3 patch_v67_monthly_story_roi.py <in index.html> <out index.html>
"""
import re, sys

src = open(sys.argv[1], encoding='utf-8').read()
out = src

def sub1(old, new, label):
    global out
    n = out.count(old)
    assert n == 1, '%s: expected 1 match, got %d' % (label, n)
    out = out.replace(old, new)

# ------------------------------------------------------------------ 1. CSS + brand
sub1('<style>\n:root { color-scheme: light; }',
'''<style>
:root { color-scheme: light; --maki: #E94E1B; --maki-soft: #F47C24; --maki-bg: #FFF1EA; --maki-ink: #1A1410; --maki-cream: #FFF8F0; }''', 'root')

sub1("header { background: linear-gradient(120deg, #0F172A 0%, #1E293B 70%, #8A3A0E 100%);",
     "header { background: linear-gradient(120deg, #1A1410 0%, #2A1A12 55%, #E94E1B 100%);", 'header bg')
sub1("nav.tabs button.active { background: #FF8B3D; color: #2A1206; }",
     "nav.tabs button.active { background: var(--maki); color: #fff; }", 'tab active')
sub1("\n.card.hero { background: linear-gradient(135deg, #111827 0%, #7A2E0B 100%); border: 0; color: #fff; }",
     "\n.card.hero { background: linear-gradient(135deg, #1A1410 0%, #B8390F 100%); border: 0; color: #fff; }", 'hero bg')

CSS_ADD = '''
/* ---- v6.7: brand header, footfall story, marketing return, monthly tab ---- */
header .brand { display: flex; align-items: center; gap: 14px; }
header .brand img { height: 46px; width: 46px; border-radius: 50%; background: #fff; box-shadow: 0 2px 10px rgba(0,0,0,.25); flex: none; }
header .brand h1 { font-family: 'Zilla Slab', Georgia, serif; font-size: 22px; letter-spacing: 0; }
header .brand h1 .accent { color: #FFB38A; }
header .brand .kicker { font-size: 10px; text-transform: uppercase; letter-spacing: .14em; color: #FFB38A; font-weight: 600; }
.storywrap { position: relative; height: 300px; }
.storylegend { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 2px; }
.storylegend button { border: 1px solid #E5E7EB; background: #fff; color: #334155; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 999px; cursor: pointer; font-family: inherit; display: inline-flex; align-items: center; gap: 6px; }
.storylegend button .sw { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.storylegend button.off { opacity: .4; }
.evchips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.evchip { font-size: 11px; padding: 4px 10px; border-radius: 999px; background: var(--maki-bg); color: #7A2E0B; border: 1px solid #F8C9B3; display: inline-flex; gap: 6px; align-items: center; }
.evchip b { color: var(--maki); }
.evchip.ops { background: #F1F5F9; color: #334155; border-color: #CBD5E1; } .evchip.ops b { color: #475569; }
.evchip.planned { background: #fff; border-style: dashed; color: #6B7280; } .evchip.planned b { color: #6B7280; }
.movedgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; margin-top: 12px; }
.moved { border: 1px solid #EBE4DC; border-radius: 12px; padding: 10px 12px; background: #FFFCFA; }
.moved .when { font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: #9CA3AF; }
.moved .what { font-weight: 700; font-size: 12px; margin: 2px 0 6px; color: #1A1410; }
.moved .delta { font-size: 22px; font-weight: 700; letter-spacing: -.01em; }
.moved .basis { font-size: 10px; color: #6B7280; margin-top: 2px; }
.roigrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.roi { border-radius: 14px; padding: 14px 16px; border: 1px solid #EBE4DC; background: #fff; position: relative; overflow: hidden; }
.roi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--maki); }
.roi.slerp::before { background: #1A1410; }
.roi h3 { font-size: 13px; margin: 0 0 2px; font-family: 'Zilla Slab', Georgia, serif; font-size: 16px; }
.roi .win { font-size: 10px; color: #9CA3AF; text-transform: uppercase; letter-spacing: .05em; }
.roi .big { font-size: 32px; font-weight: 700; letter-spacing: -.02em; margin: 6px 0 0; color: var(--maki-ink); }
.roi .big small { font-size: 13px; font-weight: 600; color: #6B7280; }
.roi .ledger { width: 100%; margin-top: 8px; font-size: 12px; }
.roi .ledger td { padding: 3px 0; border-bottom: 1px dashed #F1EBE4; }
.roi .ledger td.num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.roi .ledger tr.sum td { border-bottom: 0; border-top: 2px solid #1A1410; font-weight: 700; padding-top: 5px; }
.roi .foot { font-size: 11px; color: #6B7280; margin-top: 8px; }
.roi input.assume { width: 56px; font-size: 11px; padding: 1px 4px; border: 1px solid #D1D5DB; border-radius: 4px; font-family: inherit; text-align: right; }
.mo-hero { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-bottom: 14px; }
.mo-hero .card .value { font-size: 26px; }
.mo-hero .card .cmp { font-size: 11px; color: #6B7280; margin-top: 4px; line-height: 1.5; }
.mo-hero .card .cmp .pos, .mo-hero .card .cmp .neg { font-weight: 700; }
.mo-chartwrap { position: relative; height: 220px; }
.mo-basis { font-size: 10px; color: #9CA3AF; margin-top: 6px; }
td.sitecell { white-space: nowrap; }
.proj { color: #9CA3AF; font-weight: normal; }
.monthsel { font-size: 12px; padding: 5px 10px; border-radius: 8px; border: 1px solid #D1D5DB; font-family: inherit; font-weight: 600; }
@media (max-width: 640px) { .storywrap { height: 240px; } header .brand h1 { font-size: 18px; } }
'''
sub1('</style>\n<link rel="stylesheet" href="https://fonts.googleapis.com', CSS_ADD + '</style>\n<link rel="stylesheet" href="https://fonts.googleapis.com', 'css add')

# ------------------------------------------------------------------ 2. header + nav + panes
sub1('''<header>
  <h1>Maki &amp; Ramen — Marketing Hub</h1>
  <div class="sub" id="asof">Loading…</div>
</header>''',
'''<header>
  <div class="brand">
    <img src="../maki-logo1.png" alt="" onerror="this.style.display='none'">
    <div>
      <div class="kicker">Maki &amp; Ramen</div>
      <h1>Marketing <span class="accent">Hub</span></h1>
    </div>
  </div>
  <div class="sub" id="asof">Loading…</div>
</header>''', 'header')

sub1('''  <button data-tab="summary" class="active">Summary</button>
  <button data-tab="instagram">Instagram</button>''',
'''  <button data-tab="summary" class="active">Summary</button>
  <button data-tab="monthly">Monthly</button>
  <button data-tab="instagram">Instagram</button>''', 'nav')

sub1('''<div id="tab-summary" class="tabpane active">
  <div class="cards" id="cards"><div class="loading">Pulling live data…</div></div>
''',
'''<div id="tab-summary" class="tabpane active">
  <div class="cards" id="cards"><div class="loading">Pulling live data…</div></div>

  <div class="section" id="story-sec">
    <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
      <h2 style="margin:0">Footfall story <span class="subtle" style="font-weight:normal">· estate covers by week, with what marketing did that week</span></h2>
      <span class="subtle" id="story-asof"></span>
    </div>
    <div class="storylegend" id="story-legend"></div>
    <div class="storywrap"><canvas id="story-chart"></canvas></div>
    <div class="evchips" id="story-events"></div>
    <h2 style="margin:16px 0 0">What moved covers <span class="subtle" style="font-weight:normal">· like-for-like sites, 2 weeks after vs 2 weeks before each action</span></h2>
    <div class="movedgrid" id="story-moved"><div class="loading">Loading…</div></div>
    <div class="mo-basis" id="story-note"></div>
  </div>

  <div class="section" id="roi-sec">
    <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
      <h2 style="margin:0">Marketing return <span class="subtle" style="font-weight:normal">· Loyalty and Slerp: revenue earned per £1 of ads + offer cost</span></h2>
      <span class="subtle" id="roi-asof"></span>
    </div>
    <div class="roigrid" id="roi-grid" style="margin-top:10px"><div class="loading">Loading…</div></div>
    <div class="mo-basis" id="roi-note"></div>
  </div>
''', 'summary pane')

sub1('''<!-- ================================================================ -->
<!-- INSTAGRAM TAB                                                     -->
<!-- ================================================================ -->
<div id="tab-instagram" class="tabpane">''',
'''<!-- ================================================================ -->
<!-- MONTHLY TAB (v6.7)                                                -->
<!-- ================================================================ -->
<div id="tab-monthly" class="tabpane">
  <div class="section">
    <div class="controls" style="justify-content:space-between">
      <div>
        <h2 style="margin:0">Monthly <span class="subtle" style="font-weight:normal">· covers and sales vs previous month</span></h2>
        <div class="sub" id="mo-sub">Loading…</div>
      </div>
      <div><label for="mo-sel" style="margin-right:6px">Month</label><select id="mo-sel" class="monthsel"></select></div>
    </div>
    <div class="mo-hero" id="mo-hero"></div>
    <div class="mo-chartwrap"><canvas id="mo-chart"></canvas></div>
    <div class="mo-basis" id="mo-basis"></div>
  </div>
  <div class="section">
    <h2>By site <span class="subtle" style="font-weight:normal" id="mo-table-sub"></span></h2>
    <table>
      <thead><tr><th>Site</th><th class="num">Covers</th><th class="num">Prev month</th><th class="num">Δ covers</th><th class="num">Sales</th><th class="num">Prev month</th><th class="num">Δ sales</th><th class="num">SPH</th><th>Trend · by month</th></tr></thead>
      <tbody id="mo-table"><tr><td colspan="9" class="loading">Loading…</td></tr></tbody>
    </table>
  </div>
</div>

<!-- ================================================================ -->
<!-- INSTAGRAM TAB                                                     -->
<!-- ================================================================ -->
<div id="tab-instagram" class="tabpane">''', 'monthly pane')

# ------------------------------------------------------------------ 3. JS wiring
sub1("    if (name === 'summary') return await loadSummary();\n",
     "    if (name === 'summary') return await loadSummary();\n    if (name === 'monthly') return await loadMonthly();\n", 'loadTab route')

sub1('''  renderCards(d, bbCsv, glCsv);
  renderHealth(d);
  renderGreenLight(glCsv);
''', '''  renderCards(d, bbCsv, glCsv);
  renderHealth(d);
  renderGreenLight(glCsv);
  try { renderRoi(d); } catch (e) { console.warn('roi', e); }
  loadMonthlyData().then(function(m) { try { renderStory(d, m); } catch (e) { console.warn('story', e); } })
    .catch(function(e) { var el = document.getElementById('story-moved'); if (el) el.innerHTML = '<div class="err">Monthly feed unavailable: ' + (e.message || e) + '</div>'; });
''', 'loadSummary hook')

JS_ADD = r'''
// =====================================================================
// v6.7 — MONTHLY FEED (data/marketing_monthly.json, built daily by the cash-up pipe)
// =====================================================================
var MONTHLY_URL = 'https://makiramen.github.io/ops/data/marketing_monthly.json';
var MONTHLY = null, _monthlyPromise = null;
function loadMonthlyData() {
  if (_monthlyPromise) return _monthlyPromise;
  _monthlyPromise = fetch(MONTHLY_URL + '?t=' + Math.floor(Date.now() / 6e5), {cache: 'no-cache'})
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(m) { MONTHLY = m; return m; });
  return _monthlyPromise;
}
function moSiteName(code) {
  var meta = MONTHLY && MONTHLY.sites && MONTHLY.sites[code];
  if (meta && meta.name) return meta.name;
  var alias = {MakiNori: 'NORI', IKI2: 'IKIGAI'}[code] || code;
  return SITE_NAMES[String(alias).toUpperCase()] || code;
}
function moSiteCluster(code) {
  var meta = MONTHLY && MONTHLY.sites && MONTHLY.sites[code];
  if (meta && meta.cluster) return meta.cluster;
  return clusterOf({MakiNori: 'NORI', IKI2: 'IKIGAI'}[code] || code);
}
function isoAdd(iso, n) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function mondayOf(iso) { var s = String(iso || ''); var mm = /^(\d{4})-(\d\d)-(\d\d)/.exec(s) || (function() { var x = /^(\d\d)\/(\d\d)\/(\d{4})/.exec(s); return x ? [0, x[3], x[2], x[1]] : null; })(); if (!mm) return null; var d = new Date(mm[1] + '-' + mm[2] + '-' + mm[3] + 'T00:00:00Z'); if (isNaN(d)) return null; var wd = (d.getUTCDay() + 6) % 7; d.setUTCDate(d.getUTCDate() - wd); return d.toISOString().slice(0, 10); }
function fmtMonth(m) { var d = new Date(m + '-01T00:00:00Z'); return d.toLocaleDateString('en-GB', {month: 'short', year: 'numeric', timeZone: 'UTC'}); }
function fmtDay(iso) { var d = new Date(String(iso).slice(0, 10) + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'}); }

// =====================================================================
// v6.7 — MONTHLY TAB
// =====================================================================
var moSelected = null;
async function loadMonthly() {
  var m = await loadMonthlyData();
  var sel = document.getElementById('mo-sel');
  var months = (m.months || []).filter(function(x) { return x.days_data > 0; });
  if (!months.length) { document.getElementById('mo-sub').textContent = 'No monthly data yet'; return; }
  if (!sel._bound) {
    sel._bound = true;
    sel.addEventListener('change', function() { moSelected = sel.value; renderMonthly(); });
  }
  sel.innerHTML = months.slice().reverse().map(function(x) {
    return '<option value="' + x.m + '">' + x.label + (x.complete ? '' : ' · to ' + fmtDay(x.through)) + '</option>';
  }).join('');
  moSelected = moSelected || months[months.length - 1].m;
  sel.value = moSelected;
  renderMonthly();
}

// same-days view of a month: covers/sales for days 1..N from the daily rows (daily-sourced months only)
function moSameDays(m, monthKey, nDays) {
  var rows = (m.daily || []).filter(function(r) { return r.d.slice(0, 7) === monthKey && Number(r.d.slice(8, 10)) <= nDays; });
  if (!rows.length) return null;
  var out = {covers: 0, sales: 0, days: rows.length, sites: {}};
  rows.forEach(function(r) {
    out.covers += r.covers; out.sales += r.sales;
    Object.keys(r.sites || {}).forEach(function(c) { var s = out.sites[c] = out.sites[c] || {covers: 0, sales: 0, days: 0}; s.covers += r.sites[c][0]; s.sales += r.sites[c][1]; s.days++; });
  });
  return out;
}
// month-end projection: MTD + for each remaining date the average of the last 4 same weekdays
function moProject(m, month) {
  if (month.complete || month.m !== m.months[m.months.length - 1].m) return null;
  var daily = m.daily || [], byDate = {}; daily.forEach(function(r) { byDate[r.d] = r; });
  var through = month.through, dim = month.days_in_month, y = month.m.slice(0, 4), mo = month.m.slice(5, 7);
  var covers = month.covers, sales = month.sales || 0, used = 0;
  for (var d = Number(through.slice(8, 10)) + 1; d <= dim; d++) {
    var iso = y + '-' + mo + '-' + (d < 10 ? '0' : '') + d, wd = new Date(iso + 'T00:00:00Z').getUTCDay();
    var hits = [];
    for (var back = 1; back <= 10 && hits.length < 4; back++) { var p = isoAdd(iso, -7 * back); if (byDate[p]) hits.push(byDate[p]); }
    if (!hits.length) continue;
    covers += hits.reduce(function(s, r) { return s + r.covers; }, 0) / hits.length;
    sales += hits.reduce(function(s, r) { return s + r.sales; }, 0) / hits.length;
    used++;
  }
  return {covers: Math.round(covers), sales: Math.round(sales), days_projected: used};
}
function deltaCell(cur, prev) {
  if (prev == null || cur == null || !(prev > 0)) return '<td class="num subtle">—</td>';
  var x = cur / prev - 1;
  return '<td class="num">' + signedPct(x) + '</td>';
}
function renderMonthly() {
  var m = MONTHLY; if (!m) return;
  var months = m.months || [];
  var idx = -1; months.forEach(function(x, i) { if (x.m === moSelected) idx = i; });
  if (idx < 0) return;
  var cur = months[idx], prev = idx > 0 ? months[idx - 1] : null;
  var hero = document.getElementById('mo-hero'), sub = document.getElementById('mo-sub'), basisEl = document.getElementById('mo-basis');
  var partial = !cur.complete, nDays = Number(cur.through.slice(8, 10));
  // like-for-like comparator: same first N days of the previous month when this month is partial (daily data only)
  var cmp = null, cmpLabel = '';
  if (prev) {
    if (partial) {
      cmp = moSameDays(m, prev.m, nDays);
      if (cmp) cmpLabel = 'first ' + nDays + ' days of ' + prev.label;
      else { cmp = {covers: prev.covers * nDays / prev.days_in_month, sales: prev.sales != null ? prev.sales * nDays / prev.days_in_month : null, sites: null, pro: true}; cmpLabel = prev.label + ' pro-rata to ' + nDays + ' days'; }
    } else { cmp = {covers: prev.covers, sales: prev.sales, sites: prev.sites}; cmpLabel = prev.label + (prev.complete ? '' : ' (partial)'); }
  }
  var proj = moProject(m, cur);
  var wk4 = null;
  if (partial && (m.daily || []).length) {
    var byD = {}; m.daily.forEach(function(r) { byD[r.d] = r; });
    var c4 = 0, s4 = 0, hit = 0;
    for (var dd = 1; dd <= nDays; dd++) { var iso = cur.m + '-' + (dd < 10 ? '0' : '') + dd, pr = byD[isoAdd(iso, -28)]; if (byD[iso] && pr) { c4 += pr.covers; s4 += pr.sales; hit++; } }
    if (hit === nDays) wk4 = {covers: c4, sales: s4};
  }
  var sph = cur.sales != null && cur.covers ? cur.sales / cur.covers : null;
  var sphPrev = cmp && cmp.sales != null && cmp.covers ? cmp.sales / cmp.covers : null;
  var dlvShare = cur.delivery != null && cur.sales ? cur.delivery / cur.sales : null;
  sub.textContent = cur.label + (partial ? ' · month to date, through ' + fmtDay(cur.through) + ' (' + nDays + ' of ' + cur.days_in_month + ' days)' : ' · complete month') + (cmp ? ' · compared with ' + cmpLabel : '');
  function cmpLine(c, p, isMoney) {
    if (!cmp || p == null) return '<span class="subtle">no comparator</span>';
    var x = p > 0 ? c / p - 1 : null;
    return (isMoney ? fmtGbp(p) : fmtN(p)) + ' ' + cmpLabel + ' · ' + signedPct(x);
  }
  hero.innerHTML =
    '<div class="card hero"><div class="label">Covers · ' + cur.label + (partial ? ' MTD' : '') + '</div><div class="value" data-count="' + cur.covers + '">' + fmtN(cur.covers) + '</div>' +
      '<div class="delta">' + cmpLine(cur.covers, cmp && cmp.covers) + '</div>' +
      (wk4 ? '<div class="delta">same weekdays 4 wks earlier ' + fmtN(wk4.covers) + ' · ' + signedPct(cur.covers / wk4.covers - 1) + '</div>' : '') +
      (proj ? '<div class="delta">projected month end <b>' + fmtN(proj.covers) + '</b>' + (prev && prev.complete ? ' · ' + signedPct(proj.covers / prev.covers - 1) + ' vs ' + prev.label + ' full month' : '') + '</div>' : '') + '</div>' +
    '<div class="card"><div class="label">Sales · ' + cur.label + (partial ? ' MTD' : '') + '</div><div class="value">' + (cur.sales != null ? '<span data-count="' + Math.round(cur.sales) + '" data-fmt="gbp">' + fmtGbp(cur.sales) + '</span>' : '—') + '</div>' +
      '<div class="cmp">' + (cur.sales != null ? cmpLine(cur.sales, cmp && cmp.sales, true) : 'sales not in the weekly feed before June') + (wk4 && cur.sales != null ? '<br>same weekdays 4 wks earlier ' + fmtGbp(wk4.sales) + ' · ' + signedPct(cur.sales / wk4.sales - 1) : '') +
      (proj && cur.sales != null ? '<br>projected month end <b>' + fmtGbp(proj.sales) + '</b>' + (prev && prev.complete && prev.sales ? ' · ' + signedPct(proj.sales / prev.sales - 1) + ' vs ' + prev.label : '') : '') + '</div></div>' +
    '<div class="card"><div class="label">Spend per head</div><div class="value">' + (sph != null ? '£' + sph.toFixed(2) : '—') + '</div>' +
      '<div class="cmp">' + (sphPrev != null ? '£' + sphPrev.toFixed(2) + ' ' + cmpLabel + ' · ' + signedPct(sph / sphPrev - 1) : '<span class="subtle">no comparator</span>') + '</div></div>' +
    '<div class="card"><div class="label">Delivery share of sales</div><div class="value">' + (dlvShare != null ? (dlvShare * 100).toFixed(1) + '<small>%</small>' : '—') + '</div>' +
      '<div class="cmp">' + (cur.delivery != null ? fmtGbp(cur.delivery) + ' delivery · ' + fmtGbp(cur.sit_in) + ' sit-in' + (prev && prev.delivery != null && prev.sales ? '<br>' + prev.label + ' ' + (prev.delivery / prev.sales * 100).toFixed(1) + '%' : '') : 'split only on cash-up days (from 27 Jul)') + '</div></div>' +
    '<div class="card"><div class="label">Sites trading</div><div class="value">' + cur.sites_with_data + '</div><div class="cmp">' + (prev ? prev.sites_with_data + ' in ' + prev.label : '') + '<br>' + (cur.sites_with_data !== (prev && prev.sites_with_data) ? '<span class="note">site count changed · per-site rows below are like-for-like</span>' : 'same estate as last month') + '</div></div>';
  animateCounts(hero);

  // chart: covers by month (bars), sales line, projection as a hollow bar
  var el = document.getElementById('mo-chart');
  if (el && typeof Chart !== 'undefined') {
    if (el._chart) el._chart.destroy();
    var labels = months.map(function(x) { return x.label + (!x.complete && x.m !== months[months.length - 1].m ? ' · ' + x.days_data + ' days' : ''); });
    var lastM = months[months.length - 1].m;
    var covers = months.map(function(x) { return (x.complete || x.m !== lastM) ? x.covers : null; });
    var mtd = months.map(function(x) { return (x.complete || x.m !== lastM) ? null : x.covers; });
    var projS = months.map(function(x) { if (x.complete || x.m !== lastM) return null; var p = moProject(m, x); return p ? p.covers - x.covers : null; });
    var sales = months.map(function(x) { return x.sales != null && x.complete ? x.sales : null; });
    el._chart = new Chart(el, {
      data: {labels: labels, datasets: [
        {type: 'bar', label: 'Covers', data: covers, backgroundColor: months.map(function(x) { return x.m === cur.m ? '#E94E1B' : (x.complete ? '#F8B08A' : '#FBD3BE'); }), borderRadius: 6, stack: 'c', order: 2},
        {type: 'bar', label: 'Covers · month to date', data: mtd, backgroundColor: '#E94E1B', borderRadius: 6, stack: 'c', order: 2},
        {type: 'bar', label: 'Projected to month end', data: projS, backgroundColor: 'rgba(233,78,27,.18)', borderColor: '#E94E1B', borderWidth: 1.5, borderDash: [4, 3], borderRadius: 6, stack: 'c', order: 2},
        {type: 'line', label: 'Sales £', data: sales, yAxisID: 'y2', borderColor: '#1A1410', backgroundColor: '#1A1410', borderWidth: 2, pointRadius: 3, tension: .3, spanGaps: true, order: 1}
      ]},
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false},
        plugins: {legend: {position: 'bottom', labels: {boxWidth: 10, font: {size: 11}}}, tooltip: {callbacks: {label: function(c) { var v = c.parsed.y; if (v == null) return null; return c.dataset.label + ': ' + (c.dataset.yAxisID === 'y2' ? fmtGbp(v) : fmtN(v)); }}}},
        scales: {x: {stacked: true, grid: {display: false}}, y: {stacked: true, beginAtZero: true, ticks: {callback: function(v) { return fmtN(v); }}, grid: {color: '#F1EBE4'}}, y2: {position: 'right', beginAtZero: true, grid: {display: false}, ticks: {callback: function(v) { return v >= 1e6 ? '£' + (v / 1e6).toFixed(1) + 'm' : '£' + Math.round(v / 1000) + 'k'; }}}}}
    });
  }
  var basisBits = months.filter(function(x) { return x.basis !== 'daily'; }).map(function(x) { return x.label + ' ' + (x.basis === 'weekly-prorata' ? 'estimated from weekly totals (week ÷ 7 per day)' : x.days_prorata + ' of ' + x.days_data + ' days estimated from weekly totals'); });
  basisEl.textContent = 'Source: Kobas cash-up daily files (from 27 Jul) and the AM weekly files (from w/c 4 May). ' + (basisBits.length ? basisBits.join(' · ') + '. ' : '') + 'Sales before June not available. Projection = MTD plus the average of the last four same weekdays for each remaining day (a site that has just closed still counts in those averages). Calendar MTD vs the same dates last month shifts with the weekday mix; the weekday-aligned line (same dates 4 weeks earlier) is the fairer like-for-like.';

  // per-site table, grouped by cluster, like-for-like against the comparator
  var tbody = document.getElementById('mo-table'), tsub = document.getElementById('mo-table-sub');
  tsub.textContent = '· ' + cur.label + (partial ? ' MTD' : '') + (cmp ? ' vs ' + cmpLabel : '');
  var codes = Object.keys(cur.sites || {});
  var groups = {};
  codes.forEach(function(c) { var k = moSiteCluster(c); (groups[k] = groups[k] || []).push(c); });
  var order = GL_CLUSTER_ORDER.filter(function(k) { return groups[k]; }).concat(Object.keys(groups).filter(function(k) { return GL_CLUSTER_ORDER.indexOf(k) === -1; }));
  var maxCov = Math.max.apply(null, codes.map(function(c) { return cur.sites[c].covers; }));
  var html = '';
  order.forEach(function(k) {
    var list = groups[k].slice().sort(function(a, b) {
      var pa = cmp && cmp.sites && cmp.sites[a] ? cur.sites[a].covers / cmp.sites[a].covers : -1, pb = cmp && cmp.sites && cmp.sites[b] ? cur.sites[b].covers / cmp.sites[b].covers : -1; return pb - pa; });
    var gc = list.reduce(function(s, c) { return s + cur.sites[c].covers; }, 0), gp = cmp && cmp.sites ? list.reduce(function(s, c) { return s + (cmp.sites[c] ? cmp.sites[c].covers : 0); }, 0) : null;
    html += '<tr class="clusterrow"><td colspan="3">' + k + ' · ' + list.length + ' sites</td><td class="num">' + (gp ? signedPct(gc / gp - 1) : '') + '</td><td colspan="5"></td></tr>';
    list.forEach(function(c) {
      var s = cur.sites[c], p = cmp && cmp.sites ? cmp.sites[c] : null;
      var pc = p ? p.covers : (cmp && cmp.pro && prev.sites[c] ? prev.sites[c].covers * nDays / prev.days_in_month : null);
      var ps = p ? p.sales : (cmp && cmp.pro && prev.sites[c] && prev.sites[c].sales != null ? prev.sites[c].sales * nDays / prev.days_in_month : null);
      var newSite = p ? p.days < (cmp.days || prev.days_data) * 0.9 : false;
      var trend = months.map(function(x) { return x.sites[c] ? x.sites[c].covers * (x.complete ? 1 : x.days_in_month / x.days_data) : null; });
      html += '<tr><td class="sitecell"><strong>' + moSiteName(c) + '</strong> <span class="subtle">' + c + '</span>' + (newSite ? ' <span class="note">partial last month</span>' : '') + '</td>' +
        barCell(s.covers, maxCov, fmtN(s.covers), 'rgba(233,78,27,.16)') +
        '<td class="num subtle">' + (pc != null ? fmtN(pc) : '—') + '</td>' + deltaCell(s.covers, pc) +
        '<td class="num">' + (s.sales != null ? fmtGbp(s.sales) : '—') + '</td><td class="num subtle">' + (ps != null ? fmtGbp(ps) : '—') + '</td>' + deltaCell(s.sales, ps) +
        '<td class="num">' + (s.sales != null && s.covers ? '£' + (s.sales / s.covers).toFixed(2) : '—') + '</td>' +
        '<td>' + sparkSvg(trend, 90, 22, '#E94E1B') + '</td></tr>';
    });
  });
  var totPrev = cmp ? cmp.covers : null, totPrevS = cmp ? cmp.sales : null;
  html += '<tr style="font-weight:700;background:#FFF8F0"><td>Estate</td><td class="num">' + fmtN(cur.covers) + '</td><td class="num subtle">' + (totPrev != null ? fmtN(totPrev) : '—') + '</td>' + deltaCell(cur.covers, totPrev) +
    '<td class="num">' + (cur.sales != null ? fmtGbp(cur.sales) : '—') + '</td><td class="num subtle">' + (totPrevS != null ? fmtGbp(totPrevS) : '—') + '</td>' + deltaCell(cur.sales, totPrevS) + '<td class="num">' + (sph != null ? '£' + sph.toFixed(2) : '—') + '</td><td></td></tr>';
  tbody.innerHTML = html;
}

// =====================================================================
// v6.7 — FOOTFALL STORY (Summary)
// =====================================================================
// Marketing actions. Seed list here; rows in DATA.marketing_actions (a future sheet feed: date, label,
// type, note) are merged in, so the list can move to a Google Sheet without a page deploy.
var STORY_EVENTS = [
  {d: '2026-07-01', t: 'paid', l: 'TikTok ads live'},
  {d: '2026-07-07', t: 'paid', l: 'Meta / Google budgets confirmed'},
  {d: '2026-08-18', t: 'loyalty', l: 'Ramen Royalty go-live · £5 welcome ramen', note: 'full estate, 18 Aug'},
  {d: '2026-08-21', t: 'ops', l: 'Birmingham M21 opens'},
  {d: '2026-09-01', t: 'loyalty', l: '£5 welcome batch expiry'},
  {d: '2026-09-14', t: 'influencer', l: 'Joli creator visits ramp up'},
  {d: '2026-09-15', t: 'content', l: 'Steak Tataki hero content'},
  {d: '2026-09-21', t: 'paid', l: 'Student night campaigns (Freshers)'},
  {d: '2026-10-11', t: 'ops', l: 'Birmingham M21 closed (fire)'},
  {d: '2026-10-16', t: 'slerp', l: 'Slerp launch wave 1', planned: true, note: 'go / no-go Wed 14 Oct'}
];
var STORY_SERIES = {
  covers: {label: 'Estate covers', color: '#E94E1B'},
  paid: {label: 'Paid spend £', color: '#1A1410'},
  signups: {label: 'Loyalty sign-ups', color: '#2563EB'},
  visits: {label: 'Influencer visits', color: '#7C3AED'},
  posts: {label: 'Organic posts', color: '#0F766E'},
  slerp: {label: 'Slerp orders', color: '#D97706'}
};
var storyHidden = {signups: true, visits: true, posts: true, slerp: true};
try { var sh = JSON.parse(localStorage.getItem('mrhub-story-hidden') || 'null'); if (sh) storyHidden = sh; } catch (e) {}

function storyWeeks(d, m) {
  var weeks = (m.weekly || []).filter(function(w) { return !w.partial; });
  var byWc = {}; weeks.forEach(function(w) { byWc[w.wc] = {wc: w.wc, covers: w.covers, sales: w.sales, sites: w.sites, per_site: w.per_site || null, paid: 0, signups: 0, visits: 0, posts: 0, slerp: 0}; });
  function bump(iso, f, v) { var k = mondayOf(iso); if (k && byWc[k]) byWc[k][f] += v; }
  (d.paid_daily || []).forEach(function(r) { bump(r.date, 'paid', (Number(r.meta_spend) || 0) + (Number(r.google_spend) || 0) + (Number(r.tiktok_spend) || 0)); });
  var rr = d.rr || {}; (rr.days || []).forEach(function(iso, i) { bump(iso, 'signups', Number(rr.signups[i]) || 0); });
  var seen = {};
  (d.joli_bookings || []).forEach(function(r) { if (r.visit_date && /completed|visited/i.test(r.joli_status || '')) { bump(r.visit_date, 'visits', 1); seen[String(r.handle).toLowerCase()] = true; } });
  (d.dyi_master || []).forEach(function(r) { if (r.visit_date && !seen[String(r.handle).toLowerCase()]) bump(r.visit_date, 'visits', 1); });
  (d.content_library || []).forEach(function(r) { if (r.posted_at) bump(r.posted_at, 'posts', 1); });
  ((d.slerp && d.slerp.days) || []).forEach(function(r) { bump(r[0], 'slerp', Number(r[1]) || 0); });
  return weeks.map(function(w) { return byWc[w.wc]; });
}
function storyEvents(d) {
  var list = STORY_EVENTS.slice();
  (d.marketing_actions || []).forEach(function(r) { if (r.date) list.push({d: String(r.date).slice(0, 10), t: r.type || 'other', l: r.label || r.action || '', note: r.note || '', planned: /plan/i.test(r.status || '')}); });
  return list.sort(function(a, b) { return a.d < b.d ? -1 : 1; });
}
// like-for-like covers change around an event: 2 weeks after (event week + next) vs 2 weeks before
function storyMoved(weeks, ev) {
  var wc = mondayOf(ev.d), idx = -1; weeks.forEach(function(w, i) { if (w.wc === wc) idx = i; });
  if (idx < 2 || idx + 1 >= weeks.length) return null;
  var before = [weeks[idx - 2], weeks[idx - 1]], after = [weeks[idx], weeks[idx + 1]];
  var all = before.concat(after);
  if (!all.every(function(w) { return w.per_site; })) return null;
  var codes = Object.keys(weeks[idx].per_site).filter(function(c) { return all.every(function(w) { return w.per_site[c] && w.per_site[c][0] > 0; }); });
  var b = 0, a = 0; codes.forEach(function(c) { b += before[0].per_site[c][0] + before[1].per_site[c][0]; a += after[0].per_site[c][0] + after[1].per_site[c][0]; });
  var bTot = before[0].covers + before[1].covers, aTot = after[0].covers + after[1].covers;
  return {lfl: b > 0 ? a / b - 1 : null, lflAbs: a - b, sites: codes.length, estate: bTot > 0 ? aTot / bTot - 1 : null, from: before[0].wc, to: isoAdd(after[1].wc, 6)};
}
function renderStory(d, m) {
  var weeks = storyWeeks(d, m), events = storyEvents(d);
  var asof = document.getElementById('story-asof'); if (asof) asof.textContent = 'covers to ' + fmtDay(m.through) + ' · ' + weeks.length + ' complete weeks';
  // legend toggles
  var leg = document.getElementById('story-legend');
  leg.innerHTML = Object.keys(STORY_SERIES).map(function(k) { return '<button data-k="' + k + '" class="' + (storyHidden[k] ? 'off' : '') + '"><span class="sw" style="background:' + STORY_SERIES[k].color + '"></span>' + STORY_SERIES[k].label + '</button>'; }).join('');
  if (!leg._bound) { leg._bound = true; leg.addEventListener('click', function(ev) { var b = ev.target.closest('button[data-k]'); if (!b) return; var k = b.dataset.k; if (k === 'covers') return; storyHidden[k] = !storyHidden[k]; try { localStorage.setItem('mrhub-story-hidden', JSON.stringify(storyHidden)); } catch (e) {} renderStory(d, m); }); }
  // events plugin: vertical markers with short labels
  var labels = weeks.map(function(w) { return w.wc; });
  var evIdx = events.map(function(ev) { var wc = mondayOf(ev.d), i = labels.indexOf(wc); if (i === -1 && ev.planned && weeks.length) i = weeks.length - 1 + Math.max(1, Math.round((Date.parse(ev.d) - Date.parse(weeks[weeks.length - 1].wc)) / 6048e5)); return {ev: ev, i: i}; });
  var markerPlugin = {id: 'storyMarkers', afterDatasetsDraw: function(chart) {
    var ctx = chart.ctx, x = chart.scales.x, area = chart.chartArea, n = 0;
    ctx.save();
    var byWeek = {};
    evIdx.forEach(function(e, n) { if (e.i < 0 || e.i >= labels.length) return; (byWeek[e.i] = byWeek[e.i] || []).push({n: n + 1, ev: e.ev}); });
    Object.keys(byWeek).forEach(function(i) {
      var list = byWeek[i], px = x.getPixelForValue(Number(i)), ops = list.every(function(z) { return z.ev.t === 'ops'; });
      ctx.strokeStyle = ops ? '#64748B' : '#E94E1B'; ctx.lineWidth = 1; ctx.setLineDash(list[0].ev.planned ? [2, 3] : [4, 3]);
      ctx.beginPath(); ctx.moveTo(px, area.top + 14); ctx.lineTo(px, area.bottom); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = ops ? '#64748B' : '#E94E1B'; ctx.beginPath(); ctx.arc(px, area.top + 8, 4, 0, 6.3); ctx.fill();
      ctx.fillStyle = '#1A1410'; ctx.font = '600 10px -apple-system, Segoe UI, sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(list.map(function(z) { return z.n; }).join('·'), px + 6, area.top + 11);
    });
    ctx.restore();
  }};
  var el = document.getElementById('story-chart');
  if (el && typeof Chart !== 'undefined') {
    if (el._chart) el._chart.destroy();
    var ds = [{type: 'bar', label: STORY_SERIES.covers.label, data: weeks.map(function(w) { return w.covers; }), backgroundColor: 'rgba(233,78,27,.55)', hoverBackgroundColor: '#E94E1B', borderRadius: 5, yAxisID: 'y', order: 3}];
    ['paid', 'signups', 'visits', 'posts', 'slerp'].forEach(function(k) {
      if (storyHidden[k]) return;
      ds.push({type: 'line', label: STORY_SERIES[k].label, data: weeks.map(function(w) { return w[k] || 0; }), borderColor: STORY_SERIES[k].color, backgroundColor: STORY_SERIES[k].color, borderWidth: 2, pointRadius: 2.5, tension: .3, yAxisID: 'y' + k, order: 1});
    });
    var scales = {x: {grid: {display: false}, ticks: {callback: function(v, i) { return fmtWc(labels[i]); }, maxRotation: 0, autoSkip: true, font: {size: 10}}}, y: {beginAtZero: true, position: 'left', grid: {color: '#F1EBE4'}, ticks: {callback: function(v) { return fmtN(v); }}, title: {display: true, text: 'covers / week', font: {size: 10}}}};
    ['paid', 'signups', 'visits', 'posts', 'slerp'].forEach(function(k) { scales['y' + k] = {display: false, beginAtZero: true, position: 'right', grid: {display: false}}; });
    el._chart = new Chart(el, {data: {labels: labels, datasets: ds}, plugins: [markerPlugin],
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false}, layout: {padding: {top: 10}},
        plugins: {legend: {display: false}, tooltip: {callbacks: {title: function(items) { return 'w/c ' + fmtWc(labels[items[0].dataIndex]); }, label: function(c) { var v = c.parsed.y; return c.dataset.label + ': ' + (/£/.test(c.dataset.label) ? fmtGbp(v) : fmtN(v)); }, afterBody: function(items) { var i = items[0].dataIndex, w = weeks[i], prev = weeks[i - 1]; var lines = []; if (prev && prev.covers) lines.push('WoW ' + ((w.covers / prev.covers - 1) * 100).toFixed(1) + '% · ' + w.sites + ' sites'); evIdx.forEach(function(e, n) { if (e.i === i) lines.push('● ' + (n + 1) + ' ' + e.ev.l); }); return lines; }}}},
        scales: scales}});
  }
  // event chips (numbered to match the markers)
  var chips = document.getElementById('story-events');
  chips.innerHTML = evIdx.map(function(e, n) { return '<span class="evchip ' + e.ev.t + (e.ev.planned ? ' planned' : '') + '" title="' + escAttr(e.ev.note || '') + '"><b>' + (n + 1) + '</b> ' + fmtDay(e.ev.d) + ' · ' + e.ev.l + (e.ev.planned ? ' (planned)' : '') + '</span>'; }).join('');
  // what moved covers
  var moved = document.getElementById('story-moved'), cards = [];
  events.forEach(function(ev) {
    if (ev.planned) return;
    var r = storyMoved(weeks, ev); if (!r || r.lfl == null) return;
    var cls = r.lfl > 0.02 ? 'pos' : r.lfl < -0.02 ? 'neg' : '';
    cards.push('<div class="moved"><div class="when">' + fmtDay(ev.d) + ' · ' + ev.t + '</div><div class="what">' + ev.l + '</div>' +
      '<div class="delta ' + cls + '">' + (r.lfl > 0 ? '+' : '') + (r.lfl * 100).toFixed(1) + '%</div>' +
      '<div class="basis">' + (r.lflAbs > 0 ? '+' : '') + fmtN(r.lflAbs) + ' covers · ' + r.sites + ' like-for-like sites<br>' + fmtWc(r.from) + ' – ' + fmtWc(r.to) + (r.estate != null && Math.abs(r.estate - r.lfl) > 0.01 ? ' · estate incl. openings ' + (r.estate > 0 ? '+' : '') + (r.estate * 100).toFixed(1) + '%' : '') + '</div></div>');
  });
  moved.innerHTML = cards.length ? cards.join('') : '<div class="subtle">Not enough complete weeks around any action yet.</div>';
  var note = document.getElementById('story-note');
  note.textContent = 'Content and paid action dates are approximate (week they started). Like-for-like = sites trading with covers in all four weeks (so an opening or closure does not move the number). This shows what happened alongside each action, not proof that the action caused it: seasonality (freshers, half term, weather) sits in the same weeks. Add actions in STORY_EVENTS or a marketing_actions feed.';
}

// =====================================================================
// v6.7 — MARKETING RETURN (Summary)
// =====================================================================
// Campaigns are tagged by name. Anything matching the loyalty pattern counts as loyalty ad spend,
// the Slerp pattern as Slerp ad spend. Rename campaigns to carry these tokens and the block picks them up.
var ROI_TAGS = {
  loyalty: /TTJ|TRIP.?TO.?JAPAN|ROYALTY|LOYALTY|\bRR\b|SIGN.?UP|WELCOME|REWARDS/i,
  slerp: /SLERP|ORDER.?DIRECT|MAKI.?DELIVERY|CLICK.?(AND|&|N).?COLLECT|PICK.?UP|\bAPP\b/i
};
function roiAssume(key, dflt) { try { var v = Number(localStorage.getItem('mrhub-roi-' + key)); return v > 0 ? v : dflt; } catch (e) { return dflt; } }
function roiTaggedSpend(d, re) {
  var rows = [];
  (d.meta30 || []).forEach(function(r) { if (re.test(r.campaign || '')) rows.push({ch: 'Meta', name: r.campaign, spend: Number(r.spend) || 0}); });
  (d.gads30 || []).forEach(function(r) { if (re.test(r.campaign || '')) rows.push({ch: 'Google', name: r.campaign, spend: Number(r.spend) || 0}); });
  return rows;
}
function renderRoi(d) {
  var grid = document.getElementById('roi-grid'); if (!grid) return;
  var rr = d.rr || {}, sl = d.slerp || {}, k = sl.kpi || {};
  var cards = [];
  // ---- Loyalty: last 30 settled days of member sales vs tagged ad spend (30d windows) + welcome offer cost
  try {
    var sp = rr.spend || [], bl = rr.bills || [], days = rr.days || [];
    var lastIdx = sp.length - 1; while (lastIdx >= 0 && sp[lastIdx] == null) lastIdx--;
    var from = Math.max(0, lastIdx - 29);
    var rev30 = sumSeries(sp, from, lastIdx + 1), bills30 = sumSeries(bl, from, lastIdx + 1);
    var wv = (rr.vouchers || [])[0], ra = wv && wv.ra ? wv.ra : [];
    var red30 = sumSeries(ra, from, lastIdx + 1);   // welcome ramen redemptions, same window as the sales (ra aligns to rr.days)
    var redAll = wv ? Number(wv.rp) || 0 : 0;
    var oth30 = 0; (rr.vouchers || []).slice(1).forEach(function(v) { oth30 += sumSeries(v.ra || [], from, lastIdx + 1); });
    var disc = roiAssume('welcome', 10), othVal = roiAssume('other', 8);
    var ads = roiTaggedSpend(d, ROI_TAGS.loyalty), adSpend = ads.reduce(function(s, r) { return s + r.spend; }, 0);
    var cost = adSpend + red30 * disc + oth30 * othVal, roas = cost > 0 ? rev30 / cost : null;
    var t = rr.trading || {};
    cards.push('<div class="roi loyalty"><h3>Ramen Royalty · loyalty</h3><div class="win">Last 30 settled days · to ' + fmtDay(days[lastIdx] || '') + '</div>' +
      '<div class="big">' + (roas != null ? '£' + roas.toFixed(1) + ' <small>member sales per £1 of ads + offer</small>' : '—') + '</div>' +
      '<table class="ledger"><tr><td>Member sales (Kobas bills with a member attached)</td><td class="num">' + fmtGbp(rev30) + '</td></tr>' +
      '<tr><td>Member bills · ' + fmtN(bills30) + ' · ATV £' + (bills30 ? (rev30 / bills30).toFixed(2) : '—') + '</td><td class="num"></td></tr>' +
      '<tr><td>Loyalty-tagged ads (' + ads.length + ' campaign' + (ads.length === 1 ? '' : 's') + ', 30d)' + (ads.length ? ' <span class="subtle" title="' + escAttr(ads.map(function(r) { return r.ch + ' · ' + r.name + ' £' + r.spend.toFixed(0); }).join('\n')) + '">ⓘ</span>' : '') + '</td><td class="num">' + fmtGbp(adSpend) + '</td></tr>' +
      '<tr><td>£5 welcome ramen redeemed · ' + fmtN(red30) + ' × £<input class="assume" data-key="welcome" value="' + disc + '" title="assumed discount per redemption (ramen list price less the £5 paid)"> discount</td><td class="num">' + fmtGbp(red30 * disc) + '</td></tr>' +
      '<tr><td>Other rewards redeemed (free ramen, drink, side, birthday) · ' + fmtN(oth30) + ' × £<input class="assume" data-key="other" value="' + othVal + '" title="assumed average value of a reward redeemed"> avg</td><td class="num">' + fmtGbp(oth30 * othVal) + '</td></tr>' +
      '<tr class="sum"><td>Cost of the channel</td><td class="num">' + fmtGbp(cost) + '</td></tr></table>' +
      '<div class="foot">Since go-live: ' + fmtGbp(t.spend) + ' member sales · ' + fmtN(t.bills) + ' bills · ' + fmtN(redAll) + ' welcome ramen spent · members ' + fmtN(rr.members && rr.members.total) + ' · member share of sales ' + (rr.share ? rr.share.sales + '%' : '—') + ' · 2nd visit in 7d ' + (rr.second_visit ? rr.second_visit.rate + '%' : '—') + '</div></div>');
  } catch (e) { console.warn('roi loyalty', e); }
  // ---- Slerp: last 30 days revenue vs tagged ad spend + discounts given
  try {
    var dd = (sl.days || []).slice().sort(function(a, b) { return a[0] < b[0] ? -1 : 1; }), last30 = lastN(dd, 30);
    var sRev = last30.reduce(function(s, r) { return s + (Number(r[2]) || 0); }, 0), sOrd = last30.reduce(function(s, r) { return s + (Number(r[1]) || 0); }, 0);
    var totRev = Number(String(k['Revenue (paid)'] || '').replace(/[£,]/g, '')) || 0, totDisc = Number(String(k['Discounts given'] || '').replace(/[£,]/g, '')) || 0;
    var discShare = totRev + totDisc > 0 ? totDisc / (totRev + totDisc) : 0, sDisc = sRev * discShare / (1 - discShare || 1);
    var sAds = roiTaggedSpend(d, ROI_TAGS.slerp), sAdSpend = sAds.reduce(function(s, r) { return s + r.spend; }, 0);
    var inserts = (d.non_ad_log || []).filter(function(r) { return /slerp|insert|bag/i.test((r.channel || '') + ' ' + (r.description || '')) && !/example/i.test(r.channel || ''); }).reduce(function(s, r) { return s + (Number(r.amount_gbp) || 0); }, 0);
    var sCost = sAdSpend + sDisc + inserts, sRoas = sCost > 0 ? sRev / sCost : null;
    cards.push('<div class="roi slerp"><h3>Slerp · order direct</h3><div class="win">Last 30 days · to ' + fmtDay(sl.asof || '') + '</div>' +
      '<div class="big">' + (sRoas != null ? '£' + sRoas.toFixed(1) + ' <small>revenue per £1 of ads + offer</small>' : '—') + '</div>' +
      '<table class="ledger"><tr><td>Slerp revenue (paid) · ' + fmtN(sOrd) + ' orders · AOV ' + (sOrd ? fmtGbp2(sRev / sOrd) : '—') + '</td><td class="num">' + fmtGbp(sRev) + '</td></tr>' +
      '<tr><td>Slerp-tagged ads (' + sAds.length + ' campaign' + (sAds.length === 1 ? '' : 's') + ', 30d)' + (sAds.length ? '' : ' <span class="bad">none tagged yet</span>') + '</td><td class="num">' + fmtGbp(sAdSpend) + '</td></tr>' +
      '<tr><td>Discounts given (50% opening offer etc, pro-rated from since-launch ' + (discShare * 100).toFixed(1) + '%)</td><td class="num">' + fmtGbp(sDisc) + '</td></tr>' +
      '<tr><td>Bag inserts / non-ad spend logged</td><td class="num">' + fmtGbp(inserts) + '</td></tr>' +
      '<tr class="sum"><td>Cost of the channel</td><td class="num">' + fmtGbp(sCost) + '</td></tr></table>' +
      '<div class="foot">Since launch: ' + (k['Orders'] || '—') + ' orders · ' + (k['Revenue (paid)'] || '—') + ' · ' + (k['Unique customers'] || '—') + ' customers · repeat ' + (k['Repeat rate'] || '—') + ' · pickup ' + (k['Pickup orders'] || '—') + ' / delivery ' + (k['Delivery orders'] || '—') + '</div></div>');
  } catch (e) { console.warn('roi slerp', e); }
  grid.innerHTML = cards.join('');
  grid.querySelectorAll('input.assume').forEach(function(inp) { inp.addEventListener('change', function() { try { localStorage.setItem('mrhub-roi-' + inp.dataset.key, String(Number(inp.value) || 0)); } catch (e) {} renderRoi(d); }); });
  var note = document.getElementById('roi-note');
  note.textContent = 'Ad spend is matched by campaign name. Loyalty: TTJ, Trip to Japan, Royalty, Loyalty, RR, Sign-up, Welcome, Rewards. Slerp: Slerp, Order direct, Maki Delivery, Click & collect, Pickup, App. Name campaigns with those words and they count automatically. Member sales are all sales on bills with a member attached, not incremental sales. The discount and reward values are assumptions you can edit (saved in this browser).';
  var asof = document.getElementById('roi-asof'); if (asof) asof.textContent = 'ads = 30d Windsor windows · loyalty hourly · Slerp daily';
}
'''
sub1("// Feeds strip: one line per source, judged against its own cadence.\n", JS_ADD + "\n// Feeds strip: one line per source, judged against its own cadence.\n", 'js add')

# version stamp in the title
sub1('<title>M&amp;R Marketing Hub</title>', '<title>Maki &amp; Ramen · Marketing Hub</title>', 'title')

open(sys.argv[2], 'w', encoding='utf-8').write(out)
print('ok', len(src), '->', len(out))
