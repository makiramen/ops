#!/usr/bin/env python3
"""patch_v68_story_tight.py  --  Marketing Hub v6.8 (13 Oct 2026)

Summary tab, tightened for a non-technical marketing team:
  1. FOOTFALL STORY: one plain-English headline, four tiles (last week, vs 4 weeks ago, best week,
     this week so far), covers-only chart by default with a single "Show marketing activity" toggle,
     actions in three colours (marketing / offers / ops), a hatched "this week so far" bar, and
     "What moved covers" as a ranked list. Stamp: week commencing · covers to · refreshed.
  2. MARKETING RETURN: £ back per £1 with a traffic light, then Sales / Cost / ROI (profit after cost
     at the gross margin), full working behind "How this is worked out". No editable inputs: the
     assumptions live in code defaults, overridable from the manual feeds sheet (feed = Assumption).
  3. Marketing actions can come from the manual feeds sheet too (feed = Action), no page deploy.

Usage: python3 patch_v68_story_tight.py <in index.html> <out index.html>
"""
import re, sys

src = open(sys.argv[1], encoding='utf-8').read()
out = src

def sub1(old, new, label):
    global out
    n = out.count(old)
    assert n == 1, '%s: expected 1 match, got %d' % (label, n)
    out = out.replace(old, new)

# ------------------------------------------------------------------ 1. CSS
CSS_ADD = '''
/* ---- v6.8: story tightened, ROI verdicts ---- */
.st-head { font-family: 'Zilla Slab', Georgia, serif; font-size: 18px; line-height: 1.35; color: var(--maki-ink); margin: 10px 0 12px; max-width: 980px; }
.st-head b { color: var(--maki); }
.st-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 12px; }
.st-tiles .card .value { font-size: 24px; }
.st-tiles .card .delta { font-size: 11px; color: #6B7280; margin-top: 3px; line-height: 1.45; }
.pos { color: #15803D; } .neg { color: #B91C1C; } .flat { color: #6B7280; }
.st-bar { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin: 4px 0 2px; }
.st-toggle { border: 1px solid #E5E7EB; background: #fff; color: #334155; font-size: 11px; font-weight: 600; padding: 5px 12px; border-radius: 999px; cursor: pointer; font-family: inherit; }
.st-toggle.on { background: var(--maki-bg); border-color: #F8C9B3; color: #7A2E0B; }
.st-key { display: inline-flex; gap: 12px; font-size: 11px; color: #6B7280; flex-wrap: wrap; }
.st-key i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
.evchip.mkt { background: var(--maki-bg); color: #7A2E0B; border-color: #F8C9B3; } .evchip.mkt b { color: var(--maki); }
.evchip.offer { background: #1A1410; color: #fff; border-color: #1A1410; } .evchip.offer b { color: #FFB38A; }
.mvlist { margin-top: 10px; border: 1px solid #EBE4DC; border-radius: 12px; background: #FFFCFA; overflow: hidden; }
.mv { display: grid; grid-template-columns: 28px 1fr auto; gap: 10px; align-items: center; padding: 8px 12px; border-bottom: 1px solid #F1EBE4; font-size: 12px; }
.mv:last-child { border-bottom: 0; }
.mv .n { width: 22px; height: 22px; border-radius: 50%; background: var(--maki); color: #fff; font-weight: 700; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; }
.mv.offer .n { background: #1A1410; } .mv.ops .n { background: #64748B; }
.mv .what b { color: var(--maki-ink); } .mv .what span { color: #6B7280; }
.mv .d { font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.mv .d small { display: block; font-size: 10px; font-weight: 500; color: #9CA3AF; }
.roihead { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.verdict { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; }
.verdict.g { background: #DCFCE7; color: #15803D; } .verdict.a { background: #FEF3C7; color: #B45309; } .verdict.r { background: #FEE2E2; color: #B91C1C; } .verdict.n { background: #F1F5F9; color: #64748B; }
.roi3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
.roi3 div { background: #FFFCFA; border: 1px solid #F1EBE4; border-radius: 10px; padding: 8px 10px; }
.roi3 span { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: #9CA3AF; }
.roi3 b { font-size: 17px; font-variant-numeric: tabular-nums; }
.roi details { margin-top: 10px; }
.roi summary { font-size: 11px; font-weight: 600; color: #6B7280; cursor: pointer; }
.roi .ledger { margin-top: 6px; }
'''
sub1("@media (max-width: 640px) { .storywrap { height: 240px; } header .brand h1 { font-size: 18px; } }\n",
     "@media (max-width: 640px) { .storywrap { height: 240px; } header .brand h1 { font-size: 18px; } }\n" + CSS_ADD, 'css add')

# ------------------------------------------------------------------ 2. Summary markup
sub1('''      <h2 style="margin:0">Footfall story <span class="subtle" style="font-weight:normal">· estate covers by week, with what marketing did that week</span></h2>
      <span class="subtle" id="story-asof"></span>
    </div>
    <div class="storylegend" id="story-legend"></div>
    <div class="storywrap"><canvas id="story-chart"></canvas></div>
    <div class="evchips" id="story-events"></div>
    <h2 style="margin:16px 0 0">What moved covers <span class="subtle" style="font-weight:normal">· like-for-like sites, 2 weeks after vs 2 weeks before each action</span></h2>
    <div class="movedgrid" id="story-moved"><div class="loading">Loading…</div></div>
    <div class="mo-basis" id="story-note"></div>''',
'''      <h2 style="margin:0">Footfall story <span class="subtle" style="font-weight:normal">· covers each week and what marketing did</span></h2>
      <span class="subtle" id="story-asof"></span>
    </div>
    <div class="st-head" id="story-head"></div>
    <div class="st-tiles" id="story-tiles"></div>
    <div class="st-bar">
      <span class="st-key"><span><i style="background:#E94E1B"></i>Marketing</span><span><i style="background:#1A1410"></i>Offers and loyalty</span><span><i style="background:#64748B"></i>Operations</span><span><i style="background:repeating-linear-gradient(135deg,#E94E1B 0 2px,#fff 2px 5px)"></i>This week so far</span></span>
      <button class="st-toggle" id="story-toggle" type="button">Show marketing activity</button>
    </div>
    <div class="storylegend" id="story-legend" style="display:none"></div>
    <div class="storywrap"><canvas id="story-chart"></canvas></div>
    <div class="evchips" id="story-events"></div>
    <h2 style="margin:16px 0 0">What moved covers <span class="subtle" style="font-weight:normal">· same sites, 2 weeks after vs 2 weeks before</span></h2>
    <div class="mvlist" id="story-moved"><div class="loading">Loading…</div></div>
    <div class="mo-basis" id="story-note"></div>''', 'story markup')

sub1('''      <h2 style="margin:0">Marketing return <span class="subtle" style="font-weight:normal">· Loyalty and Slerp: revenue earned per £1 of ads + offer cost</span></h2>''',
     '''      <h2 style="margin:0">Marketing return <span class="subtle" style="font-weight:normal">· what Loyalty and Slerp give back for every £1 spent</span></h2>''', 'roi h2')

# ------------------------------------------------------------------ 3. JS: replace renderStory + the ROI block
start = out.index("function renderStory(d, m) {")
end_marker = "var asof = document.getElementById('roi-asof'); if (asof) asof.textContent = 'ads = 30d Windsor windows · loyalty hourly · Slerp daily';\n}\n"
end = out.index(end_marker) + len(end_marker)

JS_NEW = r'''// v6.8 — story: categories, assumptions, partial week, headline
var STORY_GROUP = {paid: 'mkt', content: 'mkt', influencer: 'mkt', other: 'mkt', loyalty: 'offer', slerp: 'offer', ops: 'ops'};
var STORY_GROUP_COLOR = {mkt: '#E94E1B', offer: '#1A1410', ops: '#64748B'};
function storyGroup(ev) { return STORY_GROUP[ev.t] || 'mkt'; }
var storyActivity = false;
try { storyActivity = localStorage.getItem('mrhub-story-activity') === '1'; } catch (e) {}
function storyPartial(m) { var p = (m.weekly || []).filter(function(w) { return w.partial; }); return p.length ? p[p.length - 1] : null; }
function fmtStamp(iso) { if (!iso) return ''; var d = new Date(iso); if (isNaN(d)) return String(iso); return d.toLocaleString('en-GB', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London'}) + ' UK'; }
function fmtK(n) { return n >= 10000 ? (n / 1000).toFixed(1) + 'k' : fmtN(n); }
function pctStr(p, dp) { if (p == null || !isFinite(p)) return '—'; return (p > 0 ? '+' : '') + (p * 100).toFixed(dp == null ? 1 : dp) + '%'; }
function pctCls(p, band) { band = band || 0.02; return p > band ? 'pos' : p < -band ? 'neg' : 'flat'; }
function hatchPattern(color) { var c = document.createElement('canvas'); c.width = c.height = 8; var x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 8, 8); x.strokeStyle = color; x.lineWidth = 2; x.beginPath(); x.moveTo(-2, 10); x.lineTo(10, -2); x.moveTo(-2, 2); x.lineTo(2, -2); x.moveTo(6, 10); x.lineTo(10, 6); x.stroke(); return x.createPattern(c, 'repeat'); }

function renderStory(d, m) {
  var weeks = storyWeeks(d, m), events = storyEvents(d), partial = storyPartial(m);
  var n = weeks.length, last = weeks[n - 1], prev = weeks[n - 2], w4 = weeks[n - 5];
  var thisMon = partial ? partial.wc : (last ? isoAdd(last.wc, 7) : null);
  var asof = document.getElementById('story-asof');
  if (asof) asof.textContent = (thisMon ? 'Week commencing ' + fmtDay(thisMon) + ' · ' : '') + 'covers to ' + fmtDay(m.through) + ' · refreshed ' + fmtStamp(m.generated_at);
  // ---- what moved, ranked (used by the headline and the list)
  var moved = [];
  events.forEach(function(ev, i) { if (ev.planned) return; var r = storyMoved(weeks, ev); if (r && r.lfl != null) moved.push({ev: ev, n: i + 1, r: r}); });
  moved.sort(function(a, b) { return Math.abs(b.r.lfl) - Math.abs(a.r.lfl); });
  var best = null; weeks.forEach(function(w) { if (!best || w.covers > best.covers) best = w; });
  // ---- headline
  var head = document.getElementById('story-head');
  if (head && last) {
    var wow = prev && prev.covers ? last.covers / prev.covers - 1 : null, v4 = w4 && w4.covers ? last.covers / w4.covers - 1 : null;
    var s = '<b>' + fmtK(last.covers) + ' covers</b> last week (w/c ' + fmtDay(last.wc) + '), ';
    s += wow == null ? '' : '<span class="' + pctCls(wow) + '">' + pctStr(wow) + '</span> on the week before';
    s += v4 == null ? '.' : ' and <span class="' + pctCls(v4) + '">' + pctStr(v4) + '</span> on four weeks ago.';
    var top = moved.filter(function(x) { return storyGroup(x.ev) !== 'ops'; })[0];
    if (top) s += ' Biggest marketing mover so far: <b>' + top.ev.l + '</b>, <span class="' + pctCls(top.r.lfl) + '">' + pctStr(top.r.lfl) + '</span> covers on the same sites.';
    if (partial && partial.covers) s += ' This week: ' + fmtK(partial.covers) + ' covers after ' + partial.days + ' day' + (partial.days === 1 ? '' : 's') + '.';
    head.innerHTML = s;
  }
  // ---- tiles
  var tiles = document.getElementById('story-tiles');
  if (tiles && last) {
    var t = [];
    var wowT = prev && prev.covers ? last.covers / prev.covers - 1 : null;
    t.push('<div class="card"><div class="label">Last week · w/c ' + fmtDay(last.wc) + '</div><div class="value">' + fmtN(last.covers) + '</div><div class="delta"><span class="' + pctCls(wowT) + '">' + pctStr(wowT) + '</span> vs week before' + (prev ? ' (' + fmtN(prev.covers) + ')' : '') + '</div></div>');
    var v4T = w4 && w4.covers ? last.covers / w4.covers - 1 : null;
    t.push('<div class="card"><div class="label">vs 4 weeks ago</div><div class="value ' + pctCls(v4T) + '">' + pctStr(v4T) + '</div><div class="delta">w/c ' + (w4 ? fmtDay(w4.wc) + ': ' + fmtN(w4.covers) : '—') + '</div></div>');
    t.push('<div class="card"><div class="label">Best week since May</div><div class="value">' + (best ? fmtN(best.covers) : '—') + '</div><div class="delta">' + (best ? 'w/c ' + fmtDay(best.wc) + (last.wc === best.wc ? ' · that is last week' : ' · last week was ' + pctStr(last.covers / best.covers - 1, 0) + ' off it') : '') + '</div></div>');
    t.push('<div class="card"><div class="label">This week so far</div><div class="value">' + (partial ? fmtN(partial.covers) : '—') + '</div><div class="delta">' + (partial ? partial.days + ' day' + (partial.days === 1 ? '' : 's') + ' in · w/c ' + fmtDay(partial.wc) + (prev && last ? '' : '') : 'appears once Monday\'s cash-up lands (about 09:30 UK)') + '</div></div>');
    tiles.innerHTML = t.join('');
  }
  // ---- activity toggle + legend
  var tog = document.getElementById('story-toggle'), leg = document.getElementById('story-legend');
  if (tog) { tog.textContent = storyActivity ? 'Hide marketing activity' : 'Show marketing activity'; tog.className = 'st-toggle' + (storyActivity ? ' on' : ''); if (!tog._bound) { tog._bound = true; tog.addEventListener('click', function() { storyActivity = !storyActivity; try { localStorage.setItem('mrhub-story-activity', storyActivity ? '1' : '0'); } catch (e) {} renderStory(d, m); }); } }
  if (leg) {
    leg.style.display = storyActivity ? '' : 'none';
    leg.innerHTML = Object.keys(STORY_SERIES).filter(function(k) { return k !== 'covers'; }).map(function(k) { return '<button data-k="' + k + '" class="' + (storyHidden[k] ? 'off' : '') + '"><span class="sw" style="background:' + STORY_SERIES[k].color + '"></span>' + STORY_SERIES[k].label + '</button>'; }).join('');
    if (!leg._bound) { leg._bound = true; leg.addEventListener('click', function(ev) { var b = ev.target.closest('button[data-k]'); if (!b) return; var k = b.dataset.k; storyHidden[k] = !storyHidden[k]; try { localStorage.setItem('mrhub-story-hidden', JSON.stringify(storyHidden)); } catch (e) {} renderStory(d, m); }); }
  }
  // ---- chart
  var all = partial ? weeks.concat([partial]) : weeks, labels = all.map(function(w) { return w.wc; });
  var evIdx = events.map(function(ev) { var wc = mondayOf(ev.d), i = labels.indexOf(wc); if (i === -1 && ev.planned && labels.length) i = labels.length - 1 + Math.max(1, Math.round((Date.parse(ev.d) - Date.parse(labels[labels.length - 1])) / 6048e5)); return {ev: ev, i: i}; });
  var markerPlugin = {id: 'storyMarkers', afterDatasetsDraw: function(chart) {
    var ctx = chart.ctx, x = chart.scales.x, area = chart.chartArea;
    ctx.save();
    var byWeek = {};
    evIdx.forEach(function(e, k) { if (e.i < 0 || e.i >= labels.length) return; (byWeek[e.i] = byWeek[e.i] || []).push({n: k + 1, ev: e.ev}); });
    Object.keys(byWeek).forEach(function(i) {
      var list = byWeek[i], px = x.getPixelForValue(Number(i));
      var g = list.map(storyGroupOf).sort(function(a, b) { return ({mkt: 0, offer: 1, ops: 2})[a] - ({mkt: 0, offer: 1, ops: 2})[b]; })[0];
      var col = STORY_GROUP_COLOR[g];
      ctx.strokeStyle = col; ctx.lineWidth = 1; ctx.setLineDash(list.every(function(z) { return z.ev.planned; }) ? [2, 3] : [4, 3]);
      ctx.beginPath(); ctx.moveTo(px, area.top + 14); ctx.lineTo(px, area.bottom); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(px, area.top + 8, 4, 0, 6.3); ctx.fill();
      ctx.fillStyle = '#1A1410'; ctx.font = '600 10px -apple-system, Segoe UI, sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(list.map(function(z) { return z.n; }).join('·'), px + 6, area.top + 11);
    });
    ctx.restore();
  }};
  function storyGroupOf(z) { return storyGroup(z.ev); }
  var el = document.getElementById('story-chart');
  if (el && typeof Chart !== 'undefined') {
    if (el._chart) el._chart.destroy();
    var hatch = hatchPattern('#E94E1B');
    var ds = [{type: 'bar', label: STORY_SERIES.covers.label, data: all.map(function(w) { return w.covers; }),
      backgroundColor: all.map(function(w) { return w.partial ? hatch : 'rgba(233,78,27,.55)'; }), hoverBackgroundColor: all.map(function(w) { return w.partial ? hatch : '#E94E1B'; }),
      borderColor: all.map(function(w) { return w.partial ? '#E94E1B' : 'transparent'; }), borderWidth: all.map(function(w) { return w.partial ? 1 : 0; }), borderRadius: 5, yAxisID: 'y', order: 3}];
    if (storyActivity) ['paid', 'signups', 'visits', 'posts', 'slerp'].forEach(function(k) {
      if (storyHidden[k]) return;
      ds.push({type: 'line', label: STORY_SERIES[k].label, data: weeks.map(function(w) { return w[k] || 0; }), borderColor: STORY_SERIES[k].color, backgroundColor: STORY_SERIES[k].color, borderWidth: 2, pointRadius: 2.5, tension: .3, yAxisID: 'y' + k, order: 1});
    });
    var scales = {x: {grid: {display: false}, ticks: {callback: function(v, i) { return fmtWc(labels[i]) + (all[i] && all[i].partial ? ' (so far)' : ''); }, maxRotation: 0, autoSkip: true, font: {size: 10}}}, y: {beginAtZero: true, position: 'left', grid: {color: '#F1EBE4'}, ticks: {callback: function(v) { return fmtN(v); }}, title: {display: true, text: 'covers / week', font: {size: 10}}}};
    ['paid', 'signups', 'visits', 'posts', 'slerp'].forEach(function(k) { scales['y' + k] = {display: false, beginAtZero: true, position: 'right', grid: {display: false}}; });
    el._chart = new Chart(el, {data: {labels: labels, datasets: ds}, plugins: [markerPlugin],
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false}, layout: {padding: {top: 10}},
        plugins: {legend: {display: false}, tooltip: {callbacks: {title: function(items) { var w = all[items[0].dataIndex]; return 'w/c ' + fmtWc(labels[items[0].dataIndex]) + (w && w.partial ? ' · ' + w.days + ' day' + (w.days === 1 ? '' : 's') + ' so far' : ''); }, label: function(c) { var v = c.parsed.y; return c.dataset.label + ': ' + (/£/.test(c.dataset.label) ? fmtGbp(v) : fmtN(v)); }, afterBody: function(items) { var i = items[0].dataIndex, w = all[i], p = all[i - 1]; var lines = []; if (p && p.covers && !w.partial) lines.push('vs week before ' + pctStr(w.covers / p.covers - 1) + ' · ' + w.sites + ' sites'); evIdx.forEach(function(e, k) { if (e.i === i) lines.push('● ' + (k + 1) + ' ' + e.ev.l); }); return lines; }}}},
        scales: scales}});
  }
  // ---- chips (numbered to match the markers)
  var chips = document.getElementById('story-events');
  chips.innerHTML = evIdx.map(function(e, k) { return '<span class="evchip ' + storyGroup(e.ev) + (e.ev.planned ? ' planned' : '') + '" title="' + escAttr(e.ev.note || '') + '"><b>' + (k + 1) + '</b> ' + fmtDay(e.ev.d) + ' · ' + e.ev.l + (e.ev.planned ? ' (planned)' : '') + '</span>'; }).join('');
  // ---- what moved covers: ranked list
  var mv = document.getElementById('story-moved');
  mv.innerHTML = moved.length ? moved.map(function(x) {
    var r = x.r;
    return '<div class="mv ' + storyGroup(x.ev) + '"><span class="n">' + x.n + '</span><div class="what"><b>' + x.ev.l + '</b> <span>· ' + fmtDay(x.ev.d) + ' · ' + r.sites + ' sites open throughout</span></div>' +
      '<div class="d ' + pctCls(r.lfl) + '">' + pctStr(r.lfl) + '<small>' + (r.lflAbs > 0 ? '+' : '') + fmtN(r.lflAbs) + ' covers over 2 weeks</small></div></div>';
  }).join('') : '<div class="subtle" style="padding:10px 12px">Not enough complete weeks around any action yet.</div>';
  var note = document.getElementById('story-note');
  note.textContent = 'Each action: covers in the 2 weeks after vs the 2 weeks before, same sites only (so an opening or closure does not move it). It shows what happened alongside the action, not proof it caused it: freshers, half term and weather sit in the same weeks. Marketing adds actions in the Hub manual feeds sheet (feed = Action).';
}

// =====================================================================
// v6.7 / v6.8 — MARKETING RETURN (Summary)
// =====================================================================
// Campaigns are tagged by name. Anything matching the loyalty pattern counts as loyalty ad spend,
// the Slerp pattern as Slerp ad spend. Name campaigns with these tokens and the block picks them up.
var ROI_TAGS = {
  loyalty: /TTJ|TRIP.?TO.?JAPAN|ROYALTY|LOYALTY|\bRR\b|SIGN.?UP|WELCOME|REWARDS/i,
  slerp: /SLERP|ORDER.?DIRECT|MAKI.?DELIVERY|CLICK.?(AND|&|N).?COLLECT|PICK.?UP|\bAPP\b/i
};
// Assumptions. Defaults here; a row in the manual feeds sheet with feed = Assumption, key_metric = one of
// these keys and value = a number overrides it for everyone on the next publish. No per-browser inputs.
var ROI_DEFAULTS = {welcome_discount: 10, reward_value: 8, gp_pct: 65, target_green: 3, target_amber: 1.5};
function roiAssumptions(d) {
  var a = {}; Object.keys(ROI_DEFAULTS).forEach(function(k) { a[k] = ROI_DEFAULTS[k]; });
  (d.manual_feeds || []).forEach(function(r) { if (!/^assum/i.test(String(r.feed || ''))) return; var k = String(r.key_metric || '').trim().toLowerCase().replace(/[^a-z]+/g, '_'), v = Number(r.value); if (k in a && v > 0) a[k] = v; });
  if (d.roi_assumptions) Object.keys(d.roi_assumptions).forEach(function(k) { var v = Number(d.roi_assumptions[k]); if (k in a && v > 0) a[k] = v; });
  return a;
}
function roiVerdict(roas, a) {
  if (roas == null) return {c: 'n', t: 'No spend yet'};
  if (roas >= a.target_green) return {c: 'g', t: 'Paying back well'};
  if (roas >= a.target_amber) return {c: 'a', t: 'Paying back, watch it'};
  return {c: 'r', t: 'Not paying back yet'};
}
function roiTaggedSpend(d, re) {
  var rows = [];
  (d.meta30 || []).forEach(function(r) { if (re.test(r.campaign || '')) rows.push({ch: 'Meta', name: r.campaign, spend: Number(r.spend) || 0}); });
  (d.gads30 || []).forEach(function(r) { if (re.test(r.campaign || '')) rows.push({ch: 'Google', name: r.campaign, spend: Number(r.spend) || 0}); });
  return rows;
}
function roiCard(o) {
  // o: {cls, title, win, roas, sales, cost, a, ledger: [[label, value]], foot}
  var v = roiVerdict(o.roas, o.a), gp = o.a.gp_pct / 100, profit = o.sales * gp - o.cost, roi = o.cost > 0 ? profit / o.cost : null;
  return '<div class="roi ' + o.cls + '"><div class="roihead"><h3>' + o.title + '</h3><span class="verdict ' + v.c + '">' + v.t + '</span></div><div class="win">' + o.win + '</div>' +
    '<div class="big">' + (o.roas != null ? '£' + o.roas.toFixed(2) + ' <small>back for every £1 spent</small>' : '<small>nothing spent on this channel in the last 30 days</small>') + '</div>' +
    '<div class="roi3"><div><span>Sales</span><b>' + fmtGbp(o.sales) + '</b></div><div><span>Cost</span><b>' + fmtGbp(o.cost) + '</b></div><div><span>ROI · profit after cost</span><b class="' + (roi == null ? '' : roi >= 0 ? 'pos' : 'neg') + '">' + (roi == null ? '—' : pctStr(roi, 0)) + '</b></div></div>' +
    '<details><summary>How this is worked out</summary><table class="ledger">' + o.ledger.map(function(r) { return '<tr' + (r[2] ? ' class="sum"' : '') + '><td>' + r[0] + '</td><td class="num">' + r[1] + '</td></tr>'; }).join('') +
    '<tr><td>Profit after cost = sales × ' + o.a.gp_pct + '% gross margin − cost</td><td class="num ' + (profit >= 0 ? 'pos' : 'neg') + '">' + (profit >= 0 ? '+' : '−') + fmtGbp(Math.abs(profit)) + '</td></tr></table>' +
    '<div class="foot">' + o.foot + '</div></details></div>';
}
function renderRoi(d) {
  var grid = document.getElementById('roi-grid'); if (!grid) return;
  var rr = d.rr || {}, sl = d.slerp || {}, k = sl.kpi || {}, a = roiAssumptions(d);
  var cards = [];
  // ---- Loyalty: last 30 settled days of member sales vs tagged ad spend (30d windows) + offer cost
  try {
    var sp = rr.spend || [], bl = rr.bills || [], days = rr.days || [];
    var lastIdx = sp.length - 1; while (lastIdx >= 0 && sp[lastIdx] == null) lastIdx--;
    var from = Math.max(0, lastIdx - 29);
    var rev30 = sumSeries(sp, from, lastIdx + 1), bills30 = sumSeries(bl, from, lastIdx + 1);
    var wv = (rr.vouchers || [])[0], ra = wv && wv.ra ? wv.ra : [];
    var red30 = sumSeries(ra, from, lastIdx + 1);
    var redAll = wv ? Number(wv.rp) || 0 : 0;
    var oth30 = 0; (rr.vouchers || []).slice(1).forEach(function(v) { oth30 += sumSeries(v.ra || [], from, lastIdx + 1); });
    var ads = roiTaggedSpend(d, ROI_TAGS.loyalty), adSpend = ads.reduce(function(s, r) { return s + r.spend; }, 0);
    var cost = adSpend + red30 * a.welcome_discount + oth30 * a.reward_value, roas = cost > 0 ? rev30 / cost : null;
    var t = rr.trading || {};
    cards.push(roiCard({cls: 'loyalty', title: 'Ramen Royalty · loyalty', win: 'Last 30 days to ' + fmtDay(days[lastIdx] || ''), roas: roas, sales: rev30, cost: cost, a: a,
      ledger: [
        ['Sales on bills with a member attached · ' + fmtN(bills30) + ' bills · £' + (bills30 ? (rev30 / bills30).toFixed(2) : '—') + ' per bill', fmtGbp(rev30)],
        ['Loyalty ads, 30 days (' + ads.length + ' campaign' + (ads.length === 1 ? '' : 's') + ')' + (ads.length ? ' <span class="subtle" title="' + escAttr(ads.map(function(r) { return r.ch + ' · ' + r.name + ' £' + r.spend.toFixed(0); }).join('\n')) + '">ⓘ</span>' : ''), fmtGbp(adSpend)],
        ['£5 welcome ramen · ' + fmtN(red30) + ' redeemed × £' + a.welcome_discount + ' discount', fmtGbp(red30 * a.welcome_discount)],
        ['Other rewards (free ramen, drink, side, birthday) · ' + fmtN(oth30) + ' × £' + a.reward_value, fmtGbp(oth30 * a.reward_value)],
        ['Cost of the channel', fmtGbp(cost), true]],
      foot: 'Member sales are all sales where a member was on the bill, not extra sales caused by loyalty. Since go-live: ' + fmtGbp(t.spend) + ' member sales · ' + fmtN(t.bills) + ' bills · ' + fmtN(redAll) + ' welcome ramen used · ' + fmtN(rr.members && rr.members.total) + ' members · ' + (rr.share ? rr.share.sales + '%' : '—') + ' of all sales · 2nd visit within 7 days ' + (rr.second_visit ? rr.second_visit.rate + '%' : '—') + '.'}));
  } catch (e) { console.warn('roi loyalty', e); }
  // ---- Slerp: last 30 days revenue vs tagged ad spend + discounts given
  try {
    var dd = (sl.days || []).slice().sort(function(x, y) { return x[0] < y[0] ? -1 : 1; }), last30 = lastN(dd, 30);
    var sRev = last30.reduce(function(s, r) { return s + (Number(r[2]) || 0); }, 0), sOrd = last30.reduce(function(s, r) { return s + (Number(r[1]) || 0); }, 0);
    var totRev = Number(String(k['Revenue (paid)'] || '').replace(/[£,]/g, '')) || 0, totDisc = Number(String(k['Discounts given'] || '').replace(/[£,]/g, '')) || 0;
    var discShare = totRev + totDisc > 0 ? totDisc / (totRev + totDisc) : 0, sDisc = sRev * discShare / (1 - discShare || 1);
    var sAds = roiTaggedSpend(d, ROI_TAGS.slerp), sAdSpend = sAds.reduce(function(s, r) { return s + r.spend; }, 0);
    var inserts = (d.non_ad_log || []).filter(function(r) { return /slerp|insert|bag/i.test((r.channel || '') + ' ' + (r.description || '')) && !/example/i.test(r.channel || ''); }).reduce(function(s, r) { return s + (Number(r.amount_gbp) || 0); }, 0);
    var sCost = sAdSpend + sDisc + inserts, sRoas = sCost > 0 ? sRev / sCost : null;
    cards.push(roiCard({cls: 'slerp', title: 'Slerp · order direct', win: 'Last 30 days to ' + fmtDay(sl.asof || ''), roas: sRoas, sales: sRev, cost: sCost, a: a,
      ledger: [
        ['Slerp sales (paid) · ' + fmtN(sOrd) + ' orders · ' + (sOrd ? fmtGbp2(sRev / sOrd) : '—') + ' per order', fmtGbp(sRev)],
        ['Slerp ads, 30 days (' + sAds.length + ' campaign' + (sAds.length === 1 ? '' : 's') + ')' + (sAds.length ? ' <span class="subtle" title="' + escAttr(sAds.map(function(r) { return r.ch + ' · ' + r.name + ' £' + r.spend.toFixed(0); }).join('\n')) + '">ⓘ</span>' : ' <span class="subtle">· spend shows once Windsor reports it</span>'), fmtGbp(sAdSpend)],
        ['Discounts given (50% opening offer etc, ' + (discShare * 100).toFixed(1) + '% of order value since launch)', fmtGbp(sDisc)],
        ['Bag inserts and other non-ad spend logged', fmtGbp(inserts)],
        ['Cost of the channel', fmtGbp(sCost), true]],
      foot: 'Since launch: ' + (k['Orders'] || '—') + ' orders · ' + (k['Revenue (paid)'] || '—') + ' · ' + (k['Unique customers'] || '—') + ' customers · repeat ' + (k['Repeat rate'] || '—') + ' · pickup ' + (k['Pickup orders'] || '—') + ' / delivery ' + (k['Delivery orders'] || '—') + '.'}));
  } catch (e) { console.warn('roi slerp', e); }
  grid.innerHTML = cards.join('');
  var note = document.getElementById('roi-note');
  note.textContent = 'Green = £' + a.target_green + ' or more back per £1, amber from £' + a.target_amber + '. Ads count when the campaign name says Loyalty, Royalty, TTJ, Welcome or Rewards (loyalty) or Slerp, Order direct, Maki Delivery, Click and collect or Pickup (Slerp). Assumptions: £' + a.welcome_discount + ' welcome discount, £' + a.reward_value + ' per reward, ' + a.gp_pct + '% gross margin. Change them in the Hub manual feeds sheet (feed = Assumption).';
  var asof = document.getElementById('roi-asof'); if (asof) asof.textContent = 'ads 30 days (Windsor) · loyalty hourly · Slerp daily';
}
'''
out = out[:start] + JS_NEW + out[end:]

# marketing actions from the manual feeds sheet (feed = Action; week_commencing = date, key_metric = type, value = label)
sub1("  (d.marketing_actions || []).forEach(function(r) { if (r.date) list.push({d: String(r.date).slice(0, 10), t: r.type || 'other', l: r.label || r.action || '', note: r.note || '', planned: /plan/i.test(r.status || '')}); });",
     "  (d.marketing_actions || []).forEach(function(r) { if (r.date) list.push({d: String(r.date).slice(0, 10), t: r.type || 'other', l: r.label || r.action || '', note: r.note || '', planned: /plan/i.test(r.status || '')}); });\n"
     "  (d.manual_feeds || []).forEach(function(r) { if (!/^action/i.test(String(r.feed || '')) || !r.week_commencing || !r.value) return; var t = String(r.key_metric || 'other').trim().toLowerCase(); list.push({d: String(r.week_commencing).slice(0, 10), t: STORY_GROUP[t] ? t : 'other', l: String(r.value), note: r.note || '', planned: /plan/i.test(String(r.note || ''))}); });",
     'actions from manual feeds')

# drop the unused input css
sub1(".roi input.assume { width: 56px; font-size: 11px; padding: 1px 4px; border: 1px solid #D1D5DB; border-radius: 4px; font-family: inherit; text-align: right; }\n", "", 'assume css')

sub1("<!-- v6.6.2 (9 Oct 2026): STATIC_MAX_AGE_H 6 -> 30 for the once-a-day publish -->",
     "<!-- v6.6.2 (9 Oct 2026): STATIC_MAX_AGE_H 6 -> 30 for the once-a-day publish -->\n<!-- v6.8 (13 Oct 2026): Summary story and marketing return tightened; assumptions and actions via the manual feeds sheet -->", 'version note')

open(sys.argv[2], 'w', encoding='utf-8').write(out)
print('ok', len(src), '->', len(out))
