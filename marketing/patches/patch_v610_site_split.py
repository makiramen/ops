#!/usr/bin/env python3
"""patch_v610_site_split.py  --  Marketing Hub v6.10 (20 Oct 2026)

Slerp tab: which sites had orders, per day / week / month.
  Daily   - "Sites with orders" card for the selected day (+ KPI count).
  Weekly  - click a week row; "Sites with orders" card for that week.
  Monthly - click a month row; same card for that month.
Data: DATA.slerp.dayStores = [[date, store, orders, revenue], ...] (HubPublish
v5). Until that ships the cards say so instead of showing nothing.

Usage: python3 patch_v610_site_split.py index.html
"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()
orig = len(s)

def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:80])
    s = s.replace(old, new)

# ---------------------------------------------------------------- CSS
rep('#tab-slerp tr.hl { background: var(--rr-soft); }',
    '#tab-slerp tr.hl { background: var(--rr-soft); }\n'
    '#tab-slerp tr.pick { cursor: pointer; }\n'
    '#tab-slerp tr.pick:hover { background: #FFF4EA; }\n'
    '#tab-slerp tr.tot td { font-weight: 700; border-top: 2px solid var(--rr-line); }')

# ---------------------------------------------------------------- MARKUP
SITES = lambda id_, sub: (
    '<div class="card" style="margin-top:12px">\n'
    '      <h3>Sites with orders <span id="' + id_ + '-sub">' + sub + '</span></h3>\n'
    '      <div class="tw" style="max-height:480px;overflow-y:auto"><table id="' + id_ + '"><thead><tr><th>Site</th><th>Wave</th><th class="num">Orders</th><th class="num">Share</th><th class="num">Revenue</th><th class="num">AOV</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>\n'
    '      <p class="caveat" id="' + id_ + '-note" hidden></p>\n'
    '    </div>')

rep('    <p class="caveat">Per-store and per-product splits by day are not in the payload yet; HubPublish carries totals per day only. Add them when the daily cut is needed.</p>\n',
    '    ' + SITES('sl-d-sites', '') + '\n'
    '    <p class="caveat">Sites are the Slerp store names. Counts exclude refunded, rejected and test-store orders. Pick a day above or click a day in the table.</p>\n')

rep('''      <div class="tw"><table id="sl-w-table"><thead><tr><th>Week</th><th class="num">Orders</th><th class="num">WoW</th><th class="num">Revenue</th><th class="num">WoW</th><th class="num">AOV</th><th class="num">Orders / day</th><th class="num">vs 150</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
    </div>
  </section>''',
'''      <div class="tw"><table id="sl-w-table"><thead><tr><th>Week</th><th class="num">Orders</th><th class="num">WoW</th><th class="num">Revenue</th><th class="num">WoW</th><th class="num">AOV</th><th class="num">Orders / day</th><th class="num">vs 150</th><th style="width:110px"></th></tr></thead><tbody></tbody></table></div>
      <p class="caveat">Click a week to see which sites had orders.</p>
    </div>
    ''' + SITES('sl-w-sites', '') + '''
  </section>''')

rep('''    <p class="caveat">A month is counted on the orders received that month. Trading days are days with at least one order. The current month is partial until the last day has passed.</p>
  </section>''',
'''    <p class="caveat">A month is counted on the orders received that month. Trading days are days with at least one order. The current month is partial until the last day has passed. Click a month to see which sites had orders.</p>
    ''' + SITES('sl-m-sites', '') + '''
  </section>''')

# ---------------------------------------------------------------- SCRIPT
rep("function slSortedDays_(S) { return (S.days || []).map(function(r) { return r[0]; }).sort(); }",
r"""function slSortedDays_(S) { return (S.days || []).map(function(r) { return r[0]; }).sort(); }

// v6.10: per-site split. S.dayStores = [[date, store, orders, revenue], ...] (HubPublish v5)
var SL_WEEK = null, SL_MONTH = null, SL_WEEK_ASOF = null, SL_MONTH_ASOF = null;
function slSites_(S, from, to) {
  var agg = {};
  (S.dayStores || []).forEach(function(r) {
    var d = String(r[0]).slice(0, 10); if (d < from || d > to) return;
    var st = String(r[1] || '?'); var a = (agg[st] = agg[st] || {o: 0, r: 0}); a.o += Number(r[2]) || 0; a.r += Number(r[3]) || 0;
  });
  return Object.keys(agg).map(function(st) { return [st, agg[st].o, agg[st].r]; }).sort(function(a, b) { return b[1] - a[1] || b[2] - a[2]; });
}
function slSitesTable_(S, id, from, to, subText) {
  var tb = document.querySelector('#' + id + ' tbody'), note = document.getElementById(id + '-note'), sub = document.getElementById(id + '-sub');
  if (!tb) return 0;
  if (sub) sub.textContent = subText || '';
  if (!S.dayStores) {
    tb.innerHTML = ''; note.hidden = false;
    note.textContent = 'The per-site split is not in the published data yet. It arrives with HubPublish v5 on the next 4-hourly publish after it is pasted in.';
    return 0;
  }
  var rows = slSites_(S, from, to), tot = {o: 0, r: 0};
  rows.forEach(function(r) { tot.o += r[1]; tot.r += r[2]; });
  var max = rows.length ? rows[0][1] : 0;
  var minD = null; (S.dayStores || []).forEach(function(r) { var d = String(r[0]).slice(0, 10); if (!minD || d < minD) minD = d; });
  if (minD && from < minD) { note.hidden = false; note.textContent = 'Site split covers ' + slDayLabel_(minD, true) + ' onwards (latest 60 days in the payload); earlier days in this range are not split.'; }
  else { note.hidden = true; note.textContent = ''; }
  if (!rows.length) { tb.innerHTML = '<tr class="dim"><td colspan="7">No orders in this period.</td></tr>'; return 0; }
  tb.innerHTML = rows.map(function(r) {
    return '<tr><td>' + escAttr(r[0]) + '</td><td>' + (SLERP_WAVE_OF[r[0]] || '') + '</td><td class="num">' + r[1] + '</td><td class="num">' + Math.round(slPct_(r[1], tot.o)) + '%</td><td class="num">' + slGbp_(r[2]) + '</td><td class="num">' + slGbp_(r[1] ? r[2] / r[1] : 0, 2) + '</td><td>' + slBar_(r[1], max) + '</td></tr>';
  }).join('') + '<tr class="tot"><td>' + rows.length + ' site' + (rows.length === 1 ? '' : 's') + '</td><td></td><td class="num">' + tot.o + '</td><td class="num">100%</td><td class="num">' + slGbp_(tot.r) + '</td><td class="num">' + slGbp_(tot.o ? tot.r / tot.o : 0, 2) + '</td><td></td></tr>';
  return rows.length;
}""")

# Daily: KPI + sites card + clickable day rows
rep("""    slKpi_(Math.round(slPct_(d.o, 21.4)) + '%', 'Of daily target', '21.4 orders a day')
  ].join('');""",
"""    slKpi_(Math.round(slPct_(d.o, 21.4)) + '%', 'Of daily target', '21.4 orders a day'),
    slKpi_(S.dayStores ? String(slSites_(S, SL_DAY, SL_DAY).length) : '—', 'Sites with orders', S.dayStores ? 'of ' + (S.stores || []).length + ' live on Slerp' : 'needs HubPublish v5')
  ].join('');
  slSitesTable_(S, 'sl-d-sites', SL_DAY, SL_DAY, slDayLabel_(SL_DAY, true));""")

rep("""    return '<tr class="' + (r[0] === SL_DAY ? 'hl' : (!r[1] ? 'dim' : '')) + '"><td>' + slDayLabel_(r[0]) + '</td>""",
    """    return '<tr class="pick ' + (r[0] === SL_DAY ? 'hl' : (!r[1] ? 'dim' : '')) + '" data-day="' + r[0] + '"><td>' + slDayLabel_(r[0]) + '</td>""")

# Weekly: selected week drives the sites card
rep("""  var wmax = Math.max.apply(null, weeks.map(function(w) { return w.o; }));
  document.querySelector('#sl-w-table tbody').innerHTML = weeks.slice().reverse().map(function(w, i, arr) {
    var p = arr[i + 1];
    return '<tr' + (w.partial ? ' class="hl"' : '') + '><td>w/c '""",
"""  var wmax = Math.max.apply(null, weeks.map(function(w) { return w.o; }));
  if (SL_WEEK_ASOF !== asof) { SL_WEEK_ASOF = asof; SL_WEEK = null; }
  if (!SL_WEEK || !weeks.some(function(w) { return w.wc === SL_WEEK; })) SL_WEEK = cur.wc;
  document.querySelector('#sl-w-table tbody').innerHTML = weeks.slice().reverse().map(function(w, i, arr) {
    var p = arr[i + 1];
    return '<tr class="pick' + (w.wc === SL_WEEK ? ' hl' : '') + '" data-wc="' + w.wc + '"><td>w/c '""")
rep("""Math.round(slPct_(w.o, 150)) + '%</td><td>' + slBar_(w.o, wmax) + '</td></tr>'; }).join('');
}""",
"""Math.round(slPct_(w.o, 150)) + '%</td><td>' + slBar_(w.o, wmax) + '</td></tr>'; }).join('');
  var sw = weeks.filter(function(w) { return w.wc === SL_WEEK; })[0] || cur;
  slSitesTable_(S, 'sl-w-sites', sw.wc, slAddDays_(sw.wc, 6), 'w/c ' + slDayLabel_(sw.wc, true) + (sw.partial ? ' (so far)' : ''));
}""")

# Monthly
rep("""  var mmax = Math.max.apply(null, list.map(function(x) { return x.o; }));
  document.querySelector('#sl-m-table tbody').innerHTML = list.slice().reverse().map(function(x, i, arr) {
    var p = arr[i + 1];
    return '<tr' + (x.partial ? ' class="hl"' : '') + '><td>' + lab(x.m)""",
"""  var mmax = Math.max.apply(null, list.map(function(x) { return x.o; }));
  if (SL_MONTH_ASOF !== asof) { SL_MONTH_ASOF = asof; SL_MONTH = null; }
  if (!SL_MONTH || !months[SL_MONTH]) SL_MONTH = cur.m;
  document.querySelector('#sl-m-table tbody').innerHTML = list.slice().reverse().map(function(x, i, arr) {
    var p = arr[i + 1];
    return '<tr class="pick' + (x.m === SL_MONTH ? ' hl' : '') + '" data-m="' + x.m + '"><td>' + lab(x.m)""")
rep("""(x.daysIn ? (x.o / x.daysIn).toFixed(1) : '—') + '</td><td>' + slBar_(x.o, mmax) + '</td></tr>'; }).join('');
}""",
"""(x.daysIn ? (x.o / x.daysIn).toFixed(1) : '—') + '</td><td>' + slBar_(x.o, mmax) + '</td></tr>'; }).join('');
  var sm = months[SL_MONTH] || cur;
  slSitesTable_(S, 'sl-m-sites', sm.m + '-01', sm.m + '-31', lab(sm.m) + (sm.partial ? ' (so far)' : ''));
}""")

# Click wiring (event delegation on the three tables)
rep("""    document.getElementById('sl-dprev').addEventListener('click', function() { step(1); });
    document.getElementById('sl-dnext').addEventListener('click', function() { step(-1); });
  }""",
"""    document.getElementById('sl-dprev').addEventListener('click', function() { step(1); });
    document.getElementById('sl-dnext').addEventListener('click', function() { step(-1); });
    document.querySelector('#sl-d-table tbody').addEventListener('click', function(e) {
      var tr = e.target.closest('tr[data-day]'); if (!tr) return; sel.value = tr.dataset.day; sel.dispatchEvent(new Event('change'));
    });
  }
  var wt = document.querySelector('#sl-w-table tbody');
  if (wt) wt.addEventListener('click', function(e) {
    var tr = e.target.closest('tr[data-wc]'); if (!tr) return; SL_WEEK = tr.dataset.wc;
    try { var S = slerpData_(); slWeekly_(S, slSortedDays_(S), slDayMap_(S), S.asof); } catch (err) { console.error('slerp week pick', err); }
  });
  var mt = document.querySelector('#sl-m-table tbody');
  if (mt) mt.addEventListener('click', function(e) {
    var tr = e.target.closest('tr[data-m]'); if (!tr) return; SL_MONTH = tr.dataset.m;
    try { var S = slerpData_(); slMonthly_(S, slSortedDays_(S), slDayMap_(S), S.asof); } catch (err) { console.error('slerp month pick', err); }
  });""")

rep('<!-- v6.9.2 (19 Oct 2026): Slerp tab fetches the published data.json itself so a stale browser cache can\'t pin it to the 5 Oct snapshot -->',
    '<!-- v6.9.2 (19 Oct 2026): Slerp tab fetches the published data.json itself so a stale browser cache can\'t pin it to the 5 Oct snapshot -->\n'
    '<!-- v6.10 (20 Oct 2026): Slerp Daily / Weekly / Monthly show which sites had orders (click a day, week or month); needs HubPublish v5 dayStores -->')

open(p, 'w', encoding='utf-8').write(s)
print('patched', orig, '->', len(s))
