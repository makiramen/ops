#!/usr/bin/env python3
"""Turn the compact Kobas aggregate lines (from the in-browser __agg helper)
into part_data.html. Input file: pull.txt, one line per report:
  <reportId>=<checkDate>|key:qty:days[:mN] key:qty:days ...
Venue -> site mapping is by report id order given in REPORTS below."""
import json, re, sys, datetime
from zoneinfo import ZoneInfo
UK = ZoneInfo('Europe/London')
VERSION = sys.argv[1] if len(sys.argv) > 1 else '1.1.0'   # keyline_cloud_run.py passes the page version

REPORTS = {}   # reportId -> site code, filled from pull.txt header line "MAP 26079=M9 ..."
SITE_ORDER = ['M9','M10','M11','M14','M16','M17','M18','M19','M20']
KEYS = ['tonkotsu','chkbroth','karaage','katsu','pbsliced','noodle','rump',
        'chkfillet','soba','teriyaki','tataki','hell','gyoza']

txt = open('pull.txt').read().strip().splitlines()
lines, siteMeta = [], {}
today = datetime.datetime.now(UK).date()
checkDates = []
for ln in txt:
    ln = ln.strip()
    if not ln: continue
    if ln.startswith('MAP'):
        for tok in ln.split()[1:]:
            rid, site = tok.split('='); REPORTS[rid] = site
        continue
    rid, rest = ln.split('=', 1)
    site = REPORTS[rid]
    date, body = rest.split('|', 1)
    d = datetime.date.fromisoformat(date); checkDates.append(d)
    siteMeta[site] = {'checkDate': d.strftime('%m/%d'), 'stale': (today - d).days > 8}
    vals = {}
    for tok in body.split():
        parts = tok.split(':')
        vals[parts[0]] = parts
    for k in KEYS:
        v = vals.get(k)
        if not v or v[1] == 'MISSING':
            lines.append({'site': site, 'item': k, 'stock': None, 'cover': None, 'missing': True}); continue
        qty = round(float(v[1]), 2)
        cover = 0.0 if v[2] == 'x' else float(v[2])
        row = {'site': site, 'item': k, 'stock': qty, 'cover': cover}
        if qty < 0: row['negative'] = True
        lines.append(row)

lines.sort(key=lambda r: (SITE_ORDER.index(r['site']), KEYS.index(r['item'])))
now = datetime.datetime.now(datetime.timezone.utc)
cd = sorted(set(checkDates))
reportDate = (cd[0].strftime('%d %b %Y') if len(cd) == 1 else
              (f"{cd[0].strftime('%d')} to {cd[-1].strftime('%d %b %Y')}" if cd[0].month == cd[-1].month else f"{cd[0].strftime('%d %b')} to {cd[-1].strftime('%d %b %Y')}")) if cd else today.strftime('%d %b %Y')
data = {
  'meta': {'reportDate': reportDate, 'importedAt': now.isoformat(timespec='minutes'),
           'importedLabel': 'pulled from Kobas ' + now.astimezone(UK).strftime('%d %b %H:%M') + ' UK',
           'source': 'kobas-live', 'version': VERSION},
  'siteMeta': {s: siteMeta[s] for s in SITE_ORDER if s in siteMeta},
  'lines': lines}
open('part_data.html', 'w').write('<script>\nwindow.KEYLINE_DATA = ' + json.dumps(data, separators=(', ', ': ')) + ';\n</script>\n')
print(len(lines), 'lines,', sum(1 for l in lines if l.get('negative')), 'negative,', sum(1 for l in lines if l.get('missing')), 'missing')
