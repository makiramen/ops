#!/usr/bin/env python3
"""patch_v69_slerp_views.py  --  Marketing Hub v6.9 (19 Oct 2026)

Slerp tab rebuilt in the Loyalty tab's shape: four views
  Summary · Daily · Weekly · Monthly
All numbers still come from DATA.slerp (HubPublish v4, Slerp Orders SoT
sheet) with the 5 Oct snapshot as the fallback. Daily / Weekly / Monthly are
aggregated in the page from DATA.slerp.days (date, orders, revenue), so no
HubPublish change is needed. A feed-stale banner shows when the last day with
orders is two or more days behind the payload date.

Usage: python3 patch_v69_slerp_views.py index.html
"""
import re, sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()
orig_len = len(s)

# ---------------------------------------------------------------- 1. CSS
# Reuse the Loyalty tab's design system under #tab-slerp so the two tabs look
# identical. The old sl-* rules go.
css_start = s.index('/* ═══════════════ LOYALTY TAB (Ramen Royalty Control) ═══════════════')
css_end = s.index('/* ═══════════════ END LOYALTY TAB CSS ═══════════════════════════════ */')
loy_css = s[css_start:css_end]
loy_css = loy_css[loy_css.index('#tab-loyalty {'):]  # drop the header comment
sl_css = loy_css.replace('#tab-loyalty', '#tab-slerp')

old_style_start = s.index('<!-- SLERP TAB  (v6.5.1, 6 Oct 2026) · source: Slerp Orders SoT sheet    -->')
old_style_end = s.index('<div id="tab-slerp" class="tabpane">')
new_head = '''<!-- SLERP TAB  (v6.9, 19 Oct 2026) · source: Slerp Orders SoT sheet      -->
<!-- Reads DATA.slerp when HubPublish carries it, else the snapshot.   -->
<!-- Four views, same shape as Loyalty: Summary · Daily · Weekly · Monthly -->
<!-- ================================================================ -->
<style>
/* ═══════════════ SLERP TAB CSS (v6.9) · Loyalty design system, rescoped ═══════════════ */
''' + sl_css + '''
#tab-slerp .rrview[hidden] { display: none; }
#tab-slerp .sl-pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;background:var(--rr-soft);color:#8F3C05}
#tab-slerp .sl-pill.live{background:#DCFCE7;color:#166534}#tab-slerp .sl-pill.done{background:#E5E7EB;color:#374151}
#tab-slerp .good{color:var(--rr-good);font-weight:700}#tab-slerp .bad{color:var(--rr-crit);font-weight:700}#tab-slerp .watch{color:#B45309;font-weight:700}
#tab-slerp .ctl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
#tab-slerp .ctl label{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#64748B;font-weight:700}
#tab-slerp .ctl select{font:inherit;font-size:12px;padding:6px 8px;border:1px solid var(--rr-line);border-radius:8px;background:#fff}
#tab-slerp .ctl .nav button{font:inherit;font-size:12px;padding:6px 10px;border:1px solid var(--rr-line);border-radius:8px;background:#fff;cursor:pointer;margin-right:4px}
#tab-slerp .ctl .spacer{flex:1}
#tab-slerp .ctl .st{font-size:11px;color:#94A3B8}
#tab-slerp svg.rrchart{width:100%;height:auto;display:block}
#tab-slerp svg.rrchart text{font-size:10px;fill:#94A3B8}
</style>
'''
s = s[:old_style_start] + new_head + s[old_style_end:]

# ---------------------------------------------------------------- 2. MARKUP
mk_start = s.index('<div id="tab-slerp" class="tabpane">')
mk_end = s.index('<div id="tab-loyalty" class="tabpane">')
markup = '''<div id="tab-slerp" class="tabpane">

  <div class="rrsub" role="tablist">
    <button role="tab" data-sl="sum"   aria-selected="true">Summary</button>
    <button role="tab" data-sl="day"   aria-selected="false">Daily</button>
    <button role="tab" data-sl="week"  aria-selected="false">Weekly</button>
    <button role="tab" data-sl="month" aria-selected="false">Monthly</button>
    <span class="rrstamp" id="sl-stamp">Loading…</span>
  </div>

  <div id="sl-feedbar" hidden></div>

  <!-- ---------------- SUMMARY ---------------- -->
  <section class="rrview" id="slv-sum" role="tabpanel">
    <div class="shead"><span class="n">S1</span><h2>The launch, all time</h2><span class="r" id="sl-since">Since first order</span></div>
    <div class="kpis" id="sl-kpis-all"></div>
    <p class="caveat">Counts exclude refunded, rejected and test-store orders. Revenue is what the customer paid after the 50% offer. Customers are unique by email, else phone.</p>

    <div class="shead"><span class="n">S2</span><h2>Last 7 days against target</h2><span class="r">150 orders · £4,000 a week by w/c 16 Nov</span></div>
    <div class="kpis" id="sl-kpis-7d"></div>
    <div class="grid2" style="margin-top:14px">
      <div class="card">
        <h3>Orders per day <span>last 28 days · dashed line = 21 a day (150 a week)</span></h3>
        <div id="sl-chart"></div>
      </div>
      <div class="card">
        <h3>Targets <span>now vs plan</span></h3>
        <div class="tw"><table id="sl-targets"><thead><tr><th>Metric</th><th class="num">Now</th><th class="num">Target</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
      </div>
    </div>

    <div class="shead"><span class="n">S3</span><h2>Rollout waves</h2><span class="r">Fri to Sun · 50% off · £20 min · app weblink only</span></div>
    <div class="card"><div class="tw"><table id="sl-waves"><thead><tr><th>Wave</th><th>Dates</th><th>Sites</th><th>Status</th></tr></thead><tbody></tbody></table></div></div>

    <div class="shead"><span class="n">S4</span><h2>Where the orders come from</h2><span class="r">All time</span></div>
    <div class="grid2">
      <div class="card">
        <h3>By store <span>orders · revenue · AOV</span></h3>
        <div class="tw" style="max-height:420px;overflow-y:auto"><table id="sl-stores"><thead><tr><th>Store</th><th>Wave</th><th class="num">Orders</th><th class="num">Revenue</th><th class="num">AOV</th><th style="width:90px"></th></tr></thead><tbody></tbody></table></div>
      </div>
      <div class="card">
        <h3>Top products <span>by quantity</span></h3>
        <div class="tw"><table id="sl-prods"><thead><tr><th>Product</th><th class="num">Qty</th><th class="num">Sales</th></tr></thead><tbody></tbody></table></div>
        <h3 style="margin-top:16px">Order status <span>all events to date</span></h3>
        <div class="tw"><table id="sl-status"><thead><tr><th>Status</th><th class="num">Orders</th><th class="num">Share</th></tr></thead><tbody></tbody></table></div>
      </div>
    </div>
    <p class="caveat" style="margin-top:12px">Source: <a class="sheetlink" target="_blank" href="https://docs.google.com/spreadsheets/d/1gtuuycsV9Ai5YkbGAFajqLplyw1UWPt9gmienpyTYLM/edit">Slerp Orders SoT ↗</a> (Slerp webhook, published 4-hourly by HubPublish) · plan: <a class="sheetlink" target="_blank" href="https://claude.ai/code/artifact/ceaa1e49-1f4d-478e-baa1-b7553d871d42">launch strategy ↗</a></p>
  </section>

  <!-- ---------------- DAILY ---------------- -->
  <section class="rrview" id="slv-day" role="tabpanel" hidden>
    <div class="ctl">
      <label for="sl-daysel">Day</label>
      <select id="sl-daysel"></select>
      <div class="nav"><button id="sl-dprev">Previous</button><button id="sl-dnext">Next</button></div>
      <div class="spacer"></div>
      <span class="st" id="sl-dstatus"></span>
    </div>
    <div class="kpis" id="sl-d-kpis"></div>
    <div class="grid2" style="margin-top:14px">
      <div class="card">
        <h3>Last 28 days <span>orders and revenue by day</span></h3>
        <div class="tw" style="max-height:520px;overflow-y:auto"><table id="sl-d-table"><thead><tr><th>Day</th><th class="num">Orders</th><th class="num">Revenue</th><th class="num">AOV</th><th class="num">vs 7-day avg</th><th style="width:90px"></th></tr></thead><tbody></tbody></table></div>
      </div>
      <div class="card">
        <h3>Revenue per day <span>last 28 days</span></h3>
        <div id="sl-d-chart"></div>
        <h3 style="margin-top:16px">Day of week <span>average orders, last 8 weeks</span></h3>
        <div class="tw"><table id="sl-d-dow"><thead><tr><th>Day</th><th class="num">Avg orders</th><th class="num">Avg revenue</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
      </div>
    </div>
    <p class="caveat">Per-store and per-product splits by day are not in the payload yet; HubPublish carries totals per day only. Add them when the daily cut is needed.</p>
  </section>

  <!-- ---------------- WEEKLY ---------------- -->
  <section class="rrview" id="slv-week" role="tabpanel" hidden>
    <div class="shead"><span class="n">W1</span><h2>Week by week</h2><span class="r">Mon to Sun · current week so far marked</span></div>
    <div class="kpis" id="sl-w-kpis"></div>
    <div class="card" style="margin-top:14px">
      <h3>Orders per week <span>bars · dashed line = 150 target</span></h3>
      <div id="sl-w-chart"></div>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>All weeks <span>since first order</span></h3>
      <div class="tw"><table id="sl-w-table"><thead><tr><th>Week</th><th class="num">Orders</th><th class="num">WoW</th><th class="num">Revenue</th><th class="num">WoW</th><th class="num">AOV</th><th class="num">Orders / day</th><th class="num">vs 150</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
    </div>
  </section>

  <!-- ---------------- MONTHLY ---------------- -->
  <section class="rrview" id="slv-month" role="tabpanel" hidden>
    <div class="shead"><span class="n">M1</span><h2>Month by month</h2><span class="r">Calendar months · current month so far marked</span></div>
    <div class="kpis" id="sl-m-kpis"></div>
    <div class="card" style="margin-top:14px">
      <h3>All months <span>since first order</span></h3>
      <div class="tw"><table id="sl-m-table"><thead><tr><th>Month</th><th class="num">Orders</th><th class="num">MoM</th><th class="num">Revenue</th><th class="num">MoM</th><th class="num">AOV</th><th class="num">Trading days</th><th class="num">Orders / day</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
    </div>
    <p class="caveat">A month is counted on the orders received that month. Trading days are days with at least one order. The current month is partial until the last day has passed.</p>
  </section>
</div>

'''
s = s[:mk_start] + markup + s[mk_end:]

# ---------------------------------------------------------------- 3. SCRIPT
js_start = s.index('function slerpRender() {')
js_end = s.index('<!-- maki usage beacon -->')
# keep SLERP_SNAP / SLERP_WAVES / SLERP_WAVE_OF above js_start untouched
js = r'''var SL_VIEW = 'sum', SL_DAY = null, SL_DAY_ASOF = null;
function slerpData_() { return (typeof DATA !== 'undefined' && DATA && DATA.slerp) ? DATA.slerp : SLERP_SNAP; }
function slNum_(x) { return Number(String(x == null ? 0 : x).replace(/[£,%\s]/g, '')) || 0; }
function slGbp_(n, dp) { return '£' + Number(n || 0).toLocaleString('en-GB', {minimumFractionDigits: dp == null ? 0 : dp, maximumFractionDigits: dp == null ? 0 : dp}); }
function slPct_(a, b) { return b ? (a / b * 100) : 0; }
function slDelta_(now, prev, money) {
  if (prev == null || !prev) return '<span class="caveat">—</span>';
  var d = (now - prev) / prev * 100, c = d > 0.5 ? 'good' : (d < -0.5 ? 'bad' : '');
  return '<span class="' + c + '">' + (d > 0 ? '+' : '') + d.toFixed(0) + '%</span>';
}
function slBar_(v, max) { return '<span class="bar"><i style="width:' + (max ? Math.min(100, v / max * 100) : 0).toFixed(1) + '%"></i></span>'; }
function slDayLabel_(iso, long) {
  var d = new Date(iso + 'T00:00:00Z'), dn = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], mn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return dn[d.getUTCDay()] + ' ' + d.getUTCDate() + ' ' + mn[d.getUTCMonth()] + (long ? ' ' + d.getUTCFullYear() : '');
}
function slMondayOf_(iso) { var d = new Date(iso + 'T00:00:00Z'), k = (d.getUTCDay() + 6) % 7; d.setUTCDate(d.getUTCDate() - k); return d.toISOString().slice(0, 10); }
function slAddDays_(iso, n) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function slDayMap_(S) { var m = {}; (S.days || []).forEach(function(r) { m[r[0]] = {o: Number(r[1]) || 0, r: Number(r[2]) || 0}; }); return m; }
function slSortedDays_(S) { return (S.days || []).map(function(r) { return r[0]; }).sort(); }

// Bar chart: pts = [[label, value, isPartial]], target line optional
function slChart_(pts, opts) {
  opts = opts || {};
  var W = Math.max(600, (opts.el && opts.el.clientWidth) || 760), H = 190, P = 30, B = 22, max = Math.max(opts.min || 1, Math.max.apply(null, pts.map(function(p) { return p[1]; })) , opts.target || 0);
  var bw = (W - P) / Math.max(1, pts.length), y = function(v) { return H - B - v / max * (H - B - 12); };
  var svg = '<svg class="rrchart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + (opts.label || '') + '">';
  var step = max > 400 ? 100 : (max > 160 ? 50 : (max > 60 ? 20 : (max > 24 ? 10 : 5)));
  for (var g = 0; g <= max; g += step) svg += '<line x1="' + P + '" x2="' + W + '" y1="' + y(g) + '" y2="' + y(g) + '" stroke="#EEE"/><text x="0" y="' + (y(g) + 3) + '">' + (opts.money ? '£' + (g >= 1000 ? (g / 1000) + 'k' : g) : g) + '</text>';
  pts.forEach(function(p, i) {
    var x = P + i * bw, fill = p[2] ? '#EF9B3C' : '#D9540E';
    svg += '<rect x="' + (x + 2) + '" y="' + y(p[1]) + '" width="' + Math.max(1, bw - 4) + '" height="' + Math.max(0, H - B - y(p[1])) + '" rx="2" fill="' + fill + '"' + (p[2] ? ' opacity=".7"' : '') + '><title>' + escAttr(p[0]) + ': ' + (opts.money ? slGbp_(p[1]) : p[1]) + (p[2] ? ' (so far)' : '') + '</title></rect>';
    if (p[3]) svg += '<text x="' + (x + bw / 2) + '" y="' + (H - 6) + '" text-anchor="middle">' + escAttr(p[3]) + '</text>';
  });
  if (opts.target) svg += '<line x1="' + P + '" x2="' + W + '" y1="' + y(opts.target) + '" y2="' + y(opts.target) + '" stroke="#8F3C05" stroke-dasharray="4 3"/>';
  return svg + '</svg>';
}

function slKpi_(v, k, d, hot) { return '<div class="kpi' + (hot ? ' hot' : '') + '"><div class="v">' + v + '</div><div class="k">' + k + '</div><div class="d">' + (d || '') + '</div></div>'; }

function slerpRender() {
  var S = slerpData_(), live = S !== SLERP_SNAP, k = S.kpi || {};
  var days = slSortedDays_(S), map = slDayMap_(S), asof = S.asof || (days.length ? days[days.length - 1] : '2026-10-05');
  var lastOrderDay = days.length ? days[days.length - 1] : null;
  // stamp + feed banner
  document.getElementById('sl-stamp').innerHTML = (live ? '<b>LIVE</b>' : 'SNAPSHOT') + ' · PAYLOAD.SLERP ' + escAttr(asof) + (lastOrderDay ? ' · LAST ORDER ' + escAttr(slDayLabel_(lastOrderDay)).toUpperCase() : '');
  var fb = document.getElementById('sl-feedbar');
  var gap = lastOrderDay ? Math.round((new Date(asof + 'T00:00:00Z') - new Date(lastOrderDay + 'T00:00:00Z')) / 864e5) : 0;
  if (lastOrderDay && gap >= 2) {
    fb.hidden = false;
    fb.innerHTML = '<div class="alertbar"><div><h3>No orders have reached the sheet since ' + escAttr(slDayLabel_(lastOrderDay, true)) + '.</h3><p>The payload is dated ' + escAttr(slDayLabel_(asof, true)) + '. Either Slerp has taken nothing for ' + gap + ' days or the webhook (controls.slerp.com → Integrations → Connect Webhooks → Slerp Orders SoT) has stopped delivering. Check the Raw Events tab of the SoT sheet first.</p></div><div><div class="amt">' + gap + 'd</div><div class="amtk">silent</div></div></div>';
  } else { fb.hidden = true; fb.innerHTML = ''; }
  try { slSummary_(S, k, days, map, asof, live); } catch (e) { console.error('slerp summary', e); }
  try { slDaily_(S, days, map, asof); } catch (e) { console.error('slerp daily', e); }
  try { slWeekly_(S, days, map, asof); } catch (e) { console.error('slerp weekly', e); }
  try { slMonthly_(S, days, map, asof); } catch (e) { console.error('slerp monthly', e); }
}

function slSummary_(S, k, days, map, asof, live) {
  var st = {}; (S.status || []).forEach(function(r) { st[r[0]] = Number(r[1]) || 0; });
  var all = 0; Object.keys(st).forEach(function(x) { all += st[x]; });
  var refPct = slPct_(st.REFUNDED || 0, all);
  var orders = slNum_(k['Orders']), rev = slNum_(k['Revenue (paid)']), cust = slNum_(k['Unique customers']);
  var firstDay = days.length ? days[0] : null;
  document.getElementById('sl-since').textContent = firstDay ? 'Since ' + slDayLabel_(firstDay, true) : 'Since first order';
  var pick = slNum_(k['Pickup orders']), del = slNum_(k['Delivery orders']);
  document.getElementById('sl-kpis-all').innerHTML = [
    slKpi_(fmtN(orders), 'Orders', (days.length ? (orders / days.length).toFixed(1) + ' a trading day' : ''), true),
    slKpi_(slGbp_(rev), 'Revenue (paid)', (k['Discounts given'] ? slGbp_(slNum_(k['Discounts given'])) + ' given away in offers' : ''), true),
    slKpi_(slGbp_(slNum_(k['Avg order value']), 2), 'Average order', 'target £32+'),
    slKpi_(fmtN(cust), 'Customers', (k['Repeat customers (2+ orders)'] ? fmtN(slNum_(k['Repeat customers (2+ orders)'])) + ' ordered twice · ' : '') + (k['Repeat rate'] || '—') + ' repeat'),
    slKpi_(pick + ' <small>/ ' + del + '</small>', 'Pickup / delivery', (pick + del) ? Math.round(slPct_(pick, pick + del)) + '% pickup' : ''),
    slKpi_('<span class="' + (refPct < 2 ? 'good' : (refPct < 4 ? 'watch' : 'bad')) + '">' + refPct.toFixed(1) + '%</span>', 'Refund rate', (st.REFUNDED || 0) + ' of ' + all + ' · target under 2%'),
    slKpi_('<span class="' + (!st.ACCEPTED ? 'good' : (st.ACCEPTED < 5 ? 'watch' : 'bad')) + '">' + (st.ACCEPTED || 0) + '</span>', 'Stuck on Accepted', 'never closed in Slerp · target 0')
  ].join('');
  // last 7 days (from days, so it matches the chart) with the 7 before
  var l7 = 0, l7r = 0, p7 = 0, p7r = 0;
  for (var i = 0; i < 7; i++) { var d1 = map[slAddDays_(asof, -i)], d2 = map[slAddDays_(asof, -7 - i)]; if (d1) { l7 += d1.o; l7r += d1.r; } if (d2) { p7 += d2.o; p7r += d2.r; } }
  var o7 = slNum_(k['Orders last 7 days']) || l7, r7 = slNum_(k['Revenue last 7 days']) || l7r;
  document.getElementById('sl-kpis-7d').innerHTML = [
    slKpi_('<span class="' + (o7 >= 150 ? 'good' : (o7 >= 75 ? 'watch' : 'bad')) + '">' + fmtN(o7) + '</span>', 'Orders, last 7 days', 'previous 7: ' + fmtN(p7) + ' · ' + slDelta_(o7, p7), true),
    slKpi_('<span class="' + (r7 >= 4000 ? 'good' : (r7 >= 2000 ? 'watch' : 'bad')) + '">' + slGbp_(r7) + '</span>', 'Revenue, last 7 days', 'previous 7: ' + slGbp_(p7r) + ' · ' + slDelta_(r7, p7r), true),
    slKpi_(slGbp_(o7 ? r7 / o7 : 0, 2), 'Average order, 7 days', 'all time ' + slGbp_(slNum_(k['Avg order value']), 2)),
    slKpi_(Math.round(slPct_(o7, 150)) + '%', 'Of weekly target', '150 orders a week'),
    slKpi_((o7 / 7).toFixed(1), 'Orders a day', 'target 21.4 a day')
  ].join('');
  // 28-day chart
  var pts = [];
  for (var j = 27; j >= 0; j--) { var key = slAddDays_(asof, -j), d = new Date(key + 'T00:00:00Z'); pts.push([slDayLabel_(key), map[key] ? map[key].o : 0, false, d.getUTCDay() === 5 ? d.getUTCDate() + '/' + (d.getUTCMonth() + 1) : '']); }
  document.getElementById('sl-chart').innerHTML = slChart_(pts, {target: 21.4, min: 24, label: 'Slerp orders per day', el: document.getElementById('sl-chart')});
  // targets
  var tg = [['Orders a week', o7, 150, '150 (300 by Dec)'], ['Sales a week', r7, 4000, '£4,000', true], ['Average order', slNum_(k['Avg order value']), 32, '£32+', true],
    ['30-day repeat', slNum_(k['Repeat rate']), 25, '25%'], ['Refund rate', refPct, 2, 'under 2%', false, true], ['Stuck on Accepted', st.ACCEPTED || 0, 0, '0', false, true]];
  document.querySelector('#sl-targets tbody').innerHTML = tg.map(function(r) {
    var inv = r[5], ok = inv ? r[1] <= r[2] : r[1] >= r[2];
    var now = r[4] ? slGbp_(r[1], r[0] === 'Average order' ? 2 : 0) : (r[0] === '30-day repeat' || r[0] === 'Refund rate' ? r[1].toFixed(r[0] === 'Refund rate' ? 1 : 0) + '%' : fmtN(r[1]));
    return '<tr><td>' + r[0] + '</td><td class="num ' + (ok ? 'good' : '') + '">' + now + '</td><td class="num">' + r[3] + '</td><td>' + (inv ? '' : slBar_(r[1], r[2])) + '</td></tr>'; }).join('');
  // waves
  var today = new Date().toISOString().slice(0, 10), f = function(x) { var p = x.split('-'); return +p[2] + '/' + +p[1]; };
  document.querySelector('#sl-waves tbody').innerHTML = SLERP_WAVES.map(function(w) {
    var s = today > w[2] ? '<span class="sl-pill done">Done</span>' : (today >= w[1] ? '<span class="sl-pill live">Live</span>' : '<span class="sl-pill">Upcoming</span>');
    return '<tr' + (today >= w[1] && today <= w[2] ? ' class="hl"' : '') + '><td>' + w[0] + '</td><td>' + f(w[1]) + ' to ' + f(w[2]) + '</td><td>' + w[3] + '</td><td>' + s + '</td></tr>'; }).join('');
  // stores
  var stores = (S.stores || []).slice().sort(function(a, b) { return b[1] - a[1]; }), smax = stores.length ? stores[0][1] : 0;
  document.querySelector('#sl-stores tbody').innerHTML = stores.map(function(r) {
    return '<tr><td>' + escAttr(r[0]) + '</td><td>' + (SLERP_WAVE_OF[r[0]] || '') + '</td><td class="num">' + r[1] + '</td><td class="num">' + slGbp_(r[2]) + '</td><td class="num">' + slGbp_(r[1] ? r[2] / r[1] : 0, 2) + '</td><td>' + slBar_(r[1], smax) + '</td></tr>'; }).join('');
  document.querySelector('#sl-prods tbody').innerHTML = (S.products || []).slice(0, 8).map(function(r) {
    return '<tr><td>' + escAttr(r[0]) + '</td><td class="num">' + r[1] + '</td><td class="num">' + slGbp_(r[2]) + '</td></tr>'; }).join('');
  document.querySelector('#sl-status tbody').innerHTML = (S.status || []).slice().sort(function(a, b) { return b[1] - a[1]; }).map(function(r) {
    return '<tr><td>' + escAttr(r[0]) + '</td><td class="num">' + r[1] + '</td><td class="num">' + slPct_(r[1], all).toFixed(0) + '%</td></tr>'; }).join('');
}

function slDaily_(S, days, map, asof) {
  var sel = document.getElementById('sl-daysel'), list = [];
  for (var i = 0; i < 28; i++) list.push(slAddDays_(asof, -i));
  if (SL_DAY_ASOF !== asof) { SL_DAY_ASOF = asof; SL_DAY = null; }
  if (!SL_DAY || list.indexOf(SL_DAY) < 0) { var lastWith = days.length ? days[days.length - 1] : null; SL_DAY = (lastWith && list.indexOf(lastWith) >= 0) ? lastWith : list[0]; }
  sel.innerHTML = list.map(function(d) { return '<option value="' + d + '"' + (d === SL_DAY ? ' selected' : '') + '>' + slDayLabel_(d, true) + '</option>'; }).join('');
  var d = map[SL_DAY] || {o: 0, r: 0};
  var avg7o = 0, avg7r = 0; for (var j = 1; j <= 7; j++) { var x = map[slAddDays_(SL_DAY, -j)]; if (x) { avg7o += x.o; avg7r += x.r; } } avg7o /= 7; avg7r /= 7;
  var lw = map[slAddDays_(SL_DAY, -7)] || {o: 0, r: 0};
  document.getElementById('sl-dstatus').textContent = d.o ? '' : 'No orders recorded for this day';
  document.getElementById('sl-d-kpis').innerHTML = [
    slKpi_(fmtN(d.o), 'Orders', 'same day last week ' + lw.o + ' · ' + slDelta_(d.o, lw.o), true),
    slKpi_(slGbp_(d.r), 'Revenue', 'same day last week ' + slGbp_(lw.r) + ' · ' + slDelta_(d.r, lw.r), true),
    slKpi_(slGbp_(d.o ? d.r / d.o : 0, 2), 'Average order', ''),
    slKpi_(avg7o.toFixed(1), 'Prior 7-day avg orders', 'this day ' + slDelta_(d.o, avg7o)),
    slKpi_(slGbp_(avg7r), 'Prior 7-day avg revenue', 'this day ' + slDelta_(d.r, avg7r)),
    slKpi_(Math.round(slPct_(d.o, 21.4)) + '%', 'Of daily target', '21.4 orders a day')
  ].join('');
  var rows = list.map(function(k) { var v = map[k] || {o: 0, r: 0}; var a = 0; for (var q = 1; q <= 7; q++) { var z = map[slAddDays_(k, -q)]; if (z) a += z.o; } a /= 7; return [k, v.o, v.r, a]; });
  var dmax = Math.max.apply(null, rows.map(function(r) { return r[1]; }));
  document.querySelector('#sl-d-table tbody').innerHTML = rows.map(function(r) {
    return '<tr class="' + (r[0] === SL_DAY ? 'hl' : (!r[1] ? 'dim' : '')) + '"><td>' + slDayLabel_(r[0]) + '</td><td class="num">' + r[1] + '</td><td class="num">' + slGbp_(r[2]) + '</td><td class="num">' + slGbp_(r[1] ? r[2] / r[1] : 0, 2) + '</td><td class="num">' + slDelta_(r[1], r[3]) + '</td><td>' + slBar_(r[1], dmax) + '</td></tr>'; }).join('');
  var pts = rows.slice().reverse().map(function(r) { var dt = new Date(r[0] + 'T00:00:00Z'); return [slDayLabel_(r[0]), Math.round(r[2]), false, dt.getUTCDay() === 5 ? dt.getUTCDate() + '/' + (dt.getUTCMonth() + 1) : '']; });
  document.getElementById('sl-d-chart').innerHTML = slChart_(pts, {money: true, min: 100, label: 'Slerp revenue per day', el: document.getElementById('sl-d-chart')});
  // day of week, last 8 weeks
  var dow = [0, 0, 0, 0, 0, 0, 0].map(function() { return {o: 0, r: 0, n: 0}; });
  for (var w = 0; w < 56; w++) { var kk = slAddDays_(asof, -w), dd = new Date(kk + 'T00:00:00Z').getUTCDay(), vv = map[kk]; dow[dd].n++; if (vv) { dow[dd].o += vv.o; dow[dd].r += vv.r; } }
  var names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], order = [1, 2, 3, 4, 5, 6, 0];
  var dmx = Math.max.apply(null, order.map(function(i) { return dow[i].n ? dow[i].o / dow[i].n : 0; }));
  document.querySelector('#sl-d-dow tbody').innerHTML = order.map(function(i, idx) { var ao = dow[i].n ? dow[i].o / dow[i].n : 0, ar = dow[i].n ? dow[i].r / dow[i].n : 0;
    return '<tr><td>' + names[idx] + '</td><td class="num">' + ao.toFixed(1) + '</td><td class="num">' + slGbp_(ar) + '</td><td>' + slBar_(ao, dmx) + '</td></tr>'; }).join('');
}

function slWeeks_(days, map, asof) {
  if (!days.length) return [];
  var start = slMondayOf_(days[0]), thisMon = slMondayOf_(asof), weeks = [];
  for (var wc = start; wc <= thisMon; wc = slAddDays_(wc, 7)) {
    var o = 0, r = 0, td = 0;
    for (var i = 0; i < 7; i++) { var v = map[slAddDays_(wc, i)]; if (v) { o += v.o; r += v.r; if (v.o) td++; } }
    weeks.push({wc: wc, o: o, r: r, td: td, partial: wc === thisMon && slAddDays_(wc, 6) > asof, daysIn: wc === thisMon ? Math.min(7, Math.round((new Date(asof + 'T00:00:00Z') - new Date(wc + 'T00:00:00Z')) / 864e5) + 1) : 7});
  }
  return weeks;
}
function slWeekly_(S, days, map, asof) {
  var weeks = slWeeks_(days, map, asof);
  if (!weeks.length) return;
  var cur = weeks[weeks.length - 1], full = weeks.filter(function(w) { return !w.partial; }), last = full[full.length - 1], prev = full[full.length - 2];
  var best = full.slice().sort(function(a, b) { return b.o - a.o; })[0];
  document.getElementById('sl-w-kpis').innerHTML = [
    slKpi_(fmtN(last ? last.o : 0), 'Last full week orders', (last ? 'w/c ' + slDayLabel_(last.wc) : '') + (prev ? ' · ' + slDelta_(last.o, prev.o) + ' WoW' : ''), true),
    slKpi_(slGbp_(last ? last.r : 0), 'Last full week revenue', prev ? slDelta_(last.r, prev.r) + ' WoW' : '', true),
    slKpi_(fmtN(cur.o), 'This week so far', cur.daysIn + ' of 7 days · w/c ' + slDayLabel_(cur.wc)),
    slKpi_(Math.round(slPct_(last ? last.o : 0, 150)) + '%', 'Of 150 target', 'last full week'),
    slKpi_(best ? fmtN(best.o) : '—', 'Best week', best ? 'w/c ' + slDayLabel_(best.wc) : ''),
    slKpi_(full.length ? (full.reduce(function(s, w) { return s + w.o; }, 0) / full.length).toFixed(0) : '—', 'Average full week', full.length + ' full weeks')
  ].join('');
  var show = weeks.slice(-16);
  document.getElementById('sl-w-chart').innerHTML = slChart_(show.map(function(w) { var p = w.wc.split('-'); return ['w/c ' + slDayLabel_(w.wc), w.o, w.partial, +p[2] + '/' + +p[1]]; }), {target: 150, min: 40, label: 'Slerp orders per week', el: document.getElementById('sl-w-chart')});
  var wmax = Math.max.apply(null, weeks.map(function(w) { return w.o; }));
  document.querySelector('#sl-w-table tbody').innerHTML = weeks.slice().reverse().map(function(w, i, arr) {
    var p = arr[i + 1];
    return '<tr' + (w.partial ? ' class="hl"' : '') + '><td>w/c ' + slDayLabel_(w.wc, true) + (w.partial ? ' <span class="sl-pill live">so far</span>' : '') + '</td><td class="num">' + w.o + '</td><td class="num">' + (p && !w.partial ? slDelta_(w.o, p.o) : '—') + '</td><td class="num">' + slGbp_(w.r) + '</td><td class="num">' + (p && !w.partial ? slDelta_(w.r, p.r) : '—') + '</td><td class="num">' + slGbp_(w.o ? w.r / w.o : 0, 2) + '</td><td class="num">' + (w.o / w.daysIn).toFixed(1) + '</td><td class="num ' + (w.o >= 150 ? 'good' : '') + '">' + Math.round(slPct_(w.o, 150)) + '%</td><td>' + slBar_(w.o, wmax) + '</td></tr>'; }).join('');
}

function slMonthly_(S, days, map, asof) {
  if (!days.length) return;
  var months = {}, order = [];
  days.forEach(function(d) { var m = d.slice(0, 7); if (!months[m]) { months[m] = {m: m, o: 0, r: 0, td: 0}; order.push(m); } var v = map[d]; months[m].o += v.o; months[m].r += v.r; if (v.o) months[m].td++; });
  var curM = asof.slice(0, 7); if (!months[curM]) { months[curM] = {m: curM, o: 0, r: 0, td: 0}; order.push(curM); }
  order.sort();
  var mn = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var lab = function(m) { var p = m.split('-'); return mn[+p[1] - 1] + ' ' + p[0]; };
  var daysInMonth = function(m) { var p = m.split('-'); return new Date(Date.UTC(+p[0], +p[1], 0)).getUTCDate(); };
  var list = order.map(function(m) { var x = months[m]; x.partial = m === curM && +asof.slice(8, 10) < daysInMonth(m); x.daysIn = m === curM ? +asof.slice(8, 10) : daysInMonth(m); return x; });
  var cur = list[list.length - 1], full = list.filter(function(x) { return !x.partial; }), last = full[full.length - 1], prev = full[full.length - 2];
  var run = cur.daysIn ? cur.o / cur.daysIn * daysInMonth(cur.m) : 0;
  document.getElementById('sl-m-kpis').innerHTML = [
    slKpi_(fmtN(cur.o), lab(cur.m) + (cur.partial ? ' so far' : ''), cur.daysIn + ' of ' + daysInMonth(cur.m) + ' days' + (cur.partial ? ' · on track for ' + fmtN(Math.round(run)) : ''), true),
    slKpi_(slGbp_(cur.r), 'Revenue ' + (cur.partial ? 'so far' : ''), cur.partial ? 'on track for ' + slGbp_(cur.daysIn ? cur.r / cur.daysIn * daysInMonth(cur.m) : 0) : '', true),
    slKpi_(last ? fmtN(last.o) : '—', last ? lab(last.m) : 'Last full month', last && prev ? slDelta_(last.o, prev.o) + ' MoM' : ''),
    slKpi_(last ? slGbp_(last.r) : '—', 'Revenue, last full month', last && prev ? slDelta_(last.r, prev.r) + ' MoM' : ''),
    slKpi_(slGbp_(cur.o ? cur.r / cur.o : 0, 2), 'Average order this month', last ? 'last month ' + slGbp_(last.o ? last.r / last.o : 0, 2) : '')
  ].join('');
  var mmax = Math.max.apply(null, list.map(function(x) { return x.o; }));
  document.querySelector('#sl-m-table tbody').innerHTML = list.slice().reverse().map(function(x, i, arr) {
    var p = arr[i + 1];
    return '<tr' + (x.partial ? ' class="hl"' : '') + '><td>' + lab(x.m) + (x.partial ? ' <span class="sl-pill live">so far</span>' : '') + '</td><td class="num">' + x.o + '</td><td class="num">' + (p && !x.partial ? slDelta_(x.o, p.o) : '—') + '</td><td class="num">' + slGbp_(x.r) + '</td><td class="num">' + (p && !x.partial ? slDelta_(x.r, p.r) : '—') + '</td><td class="num">' + slGbp_(x.o ? x.r / x.o : 0, 2) + '</td><td class="num">' + x.td + '</td><td class="num">' + (x.daysIn ? (x.o / x.daysIn).toFixed(1) : '—') + '</td><td>' + slBar_(x.o, mmax) + '</td></tr>'; }).join('');
}

(function() {
  var b = document.querySelector('#tabs button[data-tab="slerp"]');
  var go = function() {
    try { slerpRender(); } catch (e) { console.error('slerp', e); }
    if (typeof loadData === 'function') loadData().then(function() { try { slerpRender(); } catch (e) {} }).catch(function() {});
  };
  if (b) b.addEventListener('click', go);
  if (location.hash === '#slerp') setTimeout(go, 0);
  // sub-views
  var btns = document.querySelectorAll('#tab-slerp .rrsub button');
  Array.prototype.forEach.call(btns, function(bt) {
    bt.addEventListener('click', function() {
      SL_VIEW = bt.dataset.sl;
      Array.prototype.forEach.call(btns, function(b2) { b2.setAttribute('aria-selected', b2 === bt ? 'true' : 'false'); });
      document.querySelectorAll('#tab-slerp .rrview').forEach(function(v) { v.hidden = (v.id !== 'slv-' + SL_VIEW); });
      window.scrollTo({top: 0, behavior: 'instant'});
      try { slerpRender(); } catch (e) {}
    });
  });
  var sel = document.getElementById('sl-daysel');
  if (sel) {
    sel.addEventListener('change', function() { SL_DAY = sel.value; try { var S = slerpData_(); slDaily_(S, slSortedDays_(S), slDayMap_(S), S.asof); } catch (e) {} });
    var step = function(n) { var i = sel.selectedIndex + n; if (i < 0 || i >= sel.options.length) return; sel.selectedIndex = i; sel.dispatchEvent(new Event('change')); };
    document.getElementById('sl-dprev').addEventListener('click', function() { step(1); });
    document.getElementById('sl-dnext').addEventListener('click', function() { step(-1); });
  }
})();
</script>

'''
s = s[:js_start] + js + s[js_end:]

# version comment
s = s.replace('<!-- v6.8.1 (13 Oct 2026): hero covers from the weekly cash-up feed; Monthly compares the same weekdays 4 weeks earlier -->',
              '<!-- v6.8.1 (13 Oct 2026): hero covers from the weekly cash-up feed; Monthly compares the same weekdays 4 weeks earlier -->\n<!-- v6.9 (19 Oct 2026): Slerp tab rebuilt as Summary / Daily / Weekly / Monthly views in the Loyalty design; feed-stale banner -->', 1)

open(p, 'w', encoding='utf-8').write(s)
print('patched', p, orig_len, '->', len(s))
