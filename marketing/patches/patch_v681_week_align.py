#!/usr/bin/env python3
"""patch_v681_week_align.py  --  Marketing Hub v6.8.1 (13 Oct 2026)

  1. SUMMARY hero "Covers" card now reads the same feed as the footfall story (data/marketing_monthly.json):
     last complete week (Mon to Sun), WoW, this week so far, 12-week sparkline. The Green Light board lags a day
     (Sunday lands on the board the next night), so it showed the week before.
  2. MONTHLY tab: for a month in progress the comparator is now the same weekdays 4 weeks earlier
     (hero, cluster rows, site rows, estate row). Calendar "first N days of last month" stays as a second line
     on the hero only. Oct 1 to 11 had two full weekends, Sep 1 to 11 had one: the calendar comparison overstated
     every site by 20 to 60 points.

Usage: python3 patch_v681_week_align.py <in index.html> <out index.html>
"""
import sys

src = open(sys.argv[1], encoding='utf-8').read()
out = src

def sub1(old, new, label):
    global out
    n = out.count(old)
    assert n == 1, '%s: expected 1 match, got %d' % (label, n)
    out = out.replace(old, new)

# ---------------------------------------------------------------- 1. hero covers card from the weekly feed
sub1("  loadMonthlyData().then(function(m) { try { renderStory(d, m); } catch (e) { console.warn('story', e); } })",
     "  loadMonthlyData().then(function(m) { try { renderCoversHero(d, m); } catch (e) { console.warn('hero', e); } try { renderStory(d, m); } catch (e) { console.warn('story', e); } })", 'hero hook')

sub1("      cards.push('<div class=\"card hero\"><div class=\"label\">Covers · wk of ' + fmtWc(g.report) + '</div>",
     "      cards.push('<div class=\"card hero\" id=\"covers-hero\"><div class=\"label\">Covers · wk of ' + fmtWc(g.report) + '</div>", 'hero id')

HERO_JS = r'''
// v6.8.1 — hero covers card from the cash-up weekly feed (same numbers as the footfall story)
function renderCoversHero(d, m) {
  var weeks = ((m && m.weekly) || []).filter(function(w) { return !w.partial && w.covers; });
  if (!weeks.length) return;
  var card = document.getElementById('covers-hero'); if (!card) return;
  var last = weeks[weeks.length - 1], prev = weeks[weeks.length - 2], partial = storyPartial(m);
  var wow = prev && prev.covers ? last.covers / prev.covers - 1 : null;
  var series = weeks.slice(-12).map(function(w) { return w.covers; });
  var g = null; try { g = glParse(d[SHEETS.GREEN_LIGHT_BOARD] || []); } catch (e) {}
  var target = null;
  if (g && g.weeks && g.weeks[last.wc] && g.weeks[last.wc].length === last.sites) target = g.weeks[last.wc].reduce(function(s, r) { return s + (Number(r.covers_target_week) || 0); }, 0);   // only when the board covers the same sites
  card.innerHTML = '<div class="label">Covers · w/c ' + fmtWc(last.wc) + ' · Mon to Sun</div><div class="value">' + fmtN(last.covers) + '</div>' +
    '<div class="delta">' + (wow != null ? signedPct(wow) + ' WoW (' + fmtN(prev.covers) + ')' : '') + (target ? ' · target ' + fmtN(target) + ' · <span class="' + (last.covers >= target ? 'pos' : 'neg') + '">' + Math.round(last.covers / target * 100) + '%</span>' : '') + '</div>' +
    '<div class="delta">' + (partial ? 'this wk so far ' + fmtN(partial.covers) + ' · ' + partial.days + ' day' + (partial.days === 1 ? '' : 's') : 'this wk: Monday lands at the 09:30 UK build') + ' · ' + last.sites + ' sites</div>' +
    (series.length > 1 ? '<div class="sparkwrap"><canvas id="covers-spark"></canvas></div>' : '');
  if (series.length > 1) { try { drawSpark('covers-spark', series, '#FFC078', 'rgba(255,192,120,.18)'); } catch (e) {} }
}
'''
sub1("// =====================================================================\n// v6.7 — MONTHLY TAB\n", HERO_JS + "\n// =====================================================================\n// v6.7 — MONTHLY TAB\n", 'hero js')

# ---------------------------------------------------------------- 2. weekday-aligned comparator on the Monthly tab
sub1("""  var cmp = null, cmpLabel = '';
  if (prev) {
    if (partial) {
      cmp = moSameDays(m, prev.m, nDays);
      if (cmp) cmpLabel = 'first ' + nDays + ' days of ' + prev.label;
      else { cmp = {covers: prev.covers * nDays / prev.days_in_month, sales: prev.sales != null ? prev.sales * nDays / prev.days_in_month : null, sites: null, pro: true}; cmpLabel = prev.label + ' pro-rata to ' + nDays + ' days'; }
    } else { cmp = {covers: prev.covers, sales: prev.sales, sites: prev.sites}; cmpLabel = prev.label + (prev.complete ? '' : ' (partial)'); }
  }""",
"""  var cmp = null, cmpLabel = '', cal = null, calLabel = '';
  if (prev) {
    if (partial) {
      // v6.8.1: primary comparator = the same weekdays 4 weeks earlier (fair on weekends); calendar is the second line
      cmp = moSameWeekdays(m, cur.m, nDays);
      if (cmp) cmpLabel = 'same weekdays 4 wks earlier (' + fmtDay(cmp.from) + ' to ' + fmtDay(cmp.to) + ')';
      cal = moSameDays(m, prev.m, nDays);
      if (cal) calLabel = 'first ' + nDays + ' days of ' + prev.label;
      else { cal = {covers: prev.covers * nDays / prev.days_in_month, sales: prev.sales != null ? prev.sales * nDays / prev.days_in_month : null, sites: null, pro: true}; calLabel = prev.label + ' pro-rata to ' + nDays + ' days'; }
      if (!cmp) { cmp = cal; cmpLabel = calLabel; cal = null; }
    } else { cmp = {covers: prev.covers, sales: prev.sales, sites: prev.sites}; cmpLabel = prev.label + (prev.complete ? '' : ' (partial)'); }
  }""", 'comparator')

sub1("""      (wk4 ? '<div class="delta">same weekdays 4 wks earlier ' + fmtN(wk4.covers) + ' · ' + signedPct(cur.covers / wk4.covers - 1) + '</div>' : '') +""",
     """      (cal ? '<div class="delta">calendar: ' + fmtN(cal.covers) + ' ' + calLabel + ' · ' + signedPct(cur.covers / cal.covers - 1) + '</div>' : '') +""", 'hero covers cal line')
sub1("""(wk4 && cur.sales != null ? '<br>same weekdays 4 wks earlier ' + fmtGbp(wk4.sales) + ' · ' + signedPct(cur.sales / wk4.sales - 1) : '') +""",
     """(cal && cur.sales != null && cal.sales != null ? '<br>calendar: ' + fmtGbp(cal.sales) + ' ' + calLabel + ' · ' + signedPct(cur.sales / cal.sales - 1) : '') +""", 'hero sales cal line')

sub1("""      var pc = p ? p.covers : (cmp && cmp.pro && prev.sites[c] ? prev.sites[c].covers * nDays / prev.days_in_month : null);""",
     """      var pc = p ? p.covers : (cmp && cmp.pro && prev.sites[c] ? prev.sites[c].covers * nDays / prev.days_in_month : null);
      if (p && cmp.aligned && p.days < nDays) p = null, pc = null;   // site missing days in the comparator window: no delta rather than a wrong one""", 'site missing days')

SAMEWK_JS = r'''function moSameWeekdays(m, monthKey, nDays) {
  // the nDays dates of this month, each matched to the same weekday 4 weeks earlier; null unless every day matches
  var byD = {}; (m.daily || []).forEach(function(r) { byD[r.d] = r; });
  var out = {covers: 0, sales: 0, days: 0, sites: {}, aligned: true, from: null, to: null};
  for (var dd = 1; dd <= nDays; dd++) {
    var iso = monthKey + '-' + (dd < 10 ? '0' : '') + dd, pr = byD[isoAdd(iso, -28)];
    if (!byD[iso] || !pr) return null;
    if (!out.from) out.from = isoAdd(iso, -28); out.to = isoAdd(iso, -28);
    out.covers += pr.covers; out.sales += pr.sales; out.days++;
    Object.keys(pr.sites || {}).forEach(function(c) { var s = out.sites[c] = out.sites[c] || {covers: 0, sales: 0, days: 0}; s.covers += pr.sites[c][0]; s.sales += pr.sites[c][1]; s.days++; });
  }
  return out;
}
'''
sub1("// month-end projection: MTD + for each remaining date the average of the last 4 same weekdays\n", SAMEWK_JS + "// month-end projection: MTD + for each remaining date the average of the last 4 same weekdays\n", 'sameweekdays fn')

sub1("<!-- v6.8 (13 Oct 2026): Summary story and marketing return tightened; assumptions and actions via the manual feeds sheet -->",
     "<!-- v6.8 (13 Oct 2026): Summary story and marketing return tightened; assumptions and actions via the manual feeds sheet -->\n<!-- v6.8.1 (13 Oct 2026): hero covers from the weekly cash-up feed; Monthly compares the same weekdays 4 weeks earlier -->", 'version note')

sub1('<th class="num">Covers</th><th class="num">Prev month</th><th class="num">Δ covers</th><th class="num">Sales</th><th class="num">Prev month</th>',
     '<th class="num">Covers</th><th class="num" id="mo-th-cmp1">Compared with</th><th class="num">Δ covers</th><th class="num">Sales</th><th class="num" id="mo-th-cmp2">Compared with</th>', 'th labels')
sub1("  tsub.textContent = '· ' + cur.label + (partial ? ' MTD' : '') + (cmp ? ' vs ' + cmpLabel : '');",
     "  tsub.textContent = '· ' + cur.label + (partial ? ' MTD' : '') + (cmp ? ' vs ' + cmpLabel : '');\n  var thc = partial && cmp && cmp.aligned ? '4 wks earlier' : 'Prev month'; ['mo-th-cmp1', 'mo-th-cmp2'].forEach(function(id) { var th = document.getElementById(id); if (th) th.textContent = thc; });", 'th text')

open(sys.argv[2], 'w', encoding='utf-8').write(out)
print('ok', len(src), '->', len(out))
