"""Write a kpi_auto pull folder to the KPI Auto Google Sheet (22/10/2026, Michael), so the results can be read without
downloading the run artifact. Service account from GOOGLE_SERVICE_ACCOUNT_JSON (GitHub secret SITE_CC_SERVICE_ACCOUNT_JSON);
the sheet must be shared with that account as Editor.
Tabs written (each fully rewritten every run):
  Items_All    date, site, mode, then every column of the Kobas All Item Sales export (all sites, all days, mode 'all' only)
  Cat_Totals   date, site, mode, category, qty, gross, net (item rows only: TOTAL and 'of which' modifier rows excluded)
  Day_Totals   date, site, mode, the report's own TOTAL gross/net, the item-row sums, and the difference (must be 0)
  M14_Items    M14 item list over the whole range, per mode
  Probe        log.json, report keys, labour / cash log routes and any labour export text, one line per row
  Meta         run time, range, headers seen, files that failed to parse"""
import os, sys, csv, io, json, glob, re, datetime
SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
out = sys.argv[1]

from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import gretry  # noqa: retries 429/5xx
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()

def num(s):
    s = re.sub(r'[£,%\s]', '', str(s or ''))
    try: return float(s)
    except ValueError: return None

# ---- read every item export ----
headers, bad, rows = {}, [], []
for f in sorted(glob.glob(os.path.join(out, 'items', '*.csv'))):
    site, day, mode = os.path.basename(f)[:-4].rsplit('_', 2)
    try:
        lines = list(csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())))
    except Exception as e:
        bad.append([os.path.basename(f), str(e)]); continue
    lines = [l for l in lines if any(c.strip() for c in l)]
    if not lines: bad.append([os.path.basename(f), 'empty']); continue
    h = tuple(c.strip() for c in lines[0]); headers.setdefault(h, []).append(os.path.basename(f))
    for l in lines[1:]: rows.append((day, site, mode, h, l))
main_h = max(headers, key=lambda k: len(headers[k])) if headers else ()

def col(h, *pats, avoid=()):
    for p in pats:
        for i, c in enumerate(h):
            lc = c.lower()
            if p in lc and not any(a in lc for a in avoid): return i
    return None

items = [['date', 'site', 'mode'] + list(main_h)]
cat = {}
for day, site, mode, h, l in rows:
    if h != main_h:
        l = [l[h.index(c)] if c in h and h.index(c) < len(l) else '' for c in main_h]
    items.append([day, site, mode] + l)
ci = col(main_h, 'category', 'group')
qi = col(main_h, 'items sold', 'qty', 'quantity', 'sold', 'count')
gi = col(main_h, 'gross sales', 'gross')
vi = col(main_h, 'net sales', 'net', 'value', 'sales', 'total', avoid=('%', 'qty', 'quantity', 'potential'))
ni = col(main_h, 'item', 'name', 'product')
# 'of which ...' lines are modifier breakdowns already inside their parent item (Kobas trap 1): never sum them.
def is_item(l):
    nm = l[ni].strip().lower() if ni is not None else ''
    return nm and nm != 'total' and not nm.startswith('of which ')
day = {}
for r in items[1:]:
    l = r[3:]
    if ci is None or vi is None: break
    nm = l[ni].strip().lower() if ni is not None else ''
    dk = (r[0], r[1], r[2]); d = day.setdefault(dk, [0.0, 0.0, 0.0, 0.0])
    if nm == 'total':                       # the report's own per-lead-type TOTAL rows
        d[0] += (num(l[gi]) or 0) if gi is not None else 0; d[1] += num(l[vi]) or 0; continue
    if not is_item(l): continue
    d[2] += (num(l[gi]) or 0) if gi is not None else 0; d[3] += num(l[vi]) or 0
    k = dk + (l[ci].strip(),)
    c = cat.setdefault(k, [0.0, 0.0, 0.0])
    c[0] += (num(l[qi]) or 0) if qi is not None else 0
    c[1] += (num(l[gi]) or 0) if gi is not None else 0
    c[2] += num(l[vi]) or 0
cats = [['date', 'site', 'mode', 'category', 'qty', 'gross', 'net']] + [list(k) + [round(v[0], 2), round(v[1], 2), round(v[2], 2)] for k, v in sorted(cat.items())]
days = [['date', 'site', 'mode', 'total_gross', 'total_net', 'items_gross', 'items_net', 'diff_gross', 'diff_net']] + \
       [list(k) + [round(v[0], 2), round(v[1], 2), round(v[2], 2), round(v[3], 2), round(v[2] - v[0], 2), round(v[3] - v[1], 2)]
        for k, v in sorted(day.items())]

# M14 item list over the range
m14 = {}
for r in items[1:]:
    if r[1] != 'M14' or ni is None: continue
    l = r[3:]
    k = (r[2], l[ci].strip() if ci is not None else '', l[ni].strip())
    c = m14.setdefault(k, [0.0, 0.0])
    c[0] += (num(l[qi]) or 0) if qi is not None else 0
    c[1] += (num(l[vi]) or 0) if vi is not None else 0
m14r = [['mode', 'category', 'item', 'qty', 'value']] + [list(k) + [round(v[0], 2), round(v[1], 2)] for k, v in sorted(m14.items())]

# probe dump
probe = [['file', 'line']]
for f in sorted(glob.glob(os.path.join(out, '*.json')) + glob.glob(os.path.join(out, '*.txt')) + glob.glob(os.path.join(out, 'labour', '*'))):
    txt = open(f, encoding='utf-8', errors='replace').read()
    name = os.path.relpath(f, out)
    if name.startswith('page_'): txt = txt.split('\n--html\n')[0]   # routes only, not the page html
    for line in txt.splitlines()[:3000]: probe.append([name, line[:45000]])

meta = [['key', 'value'], ['written', datetime.datetime.now(datetime.timezone.utc).isoformat()],
        ['range', f"{os.environ.get('DATE_FROM')} to {os.environ.get('DATE_TO')}"],
        ['item files', sum(len(v) for v in headers.values())], ['item rows', len(items) - 1],
        ['category col', main_h[ci] if ci is not None else 'NOT FOUND'], ['qty col', main_h[qi] if qi is not None else 'NOT FOUND'],
        ['net col', main_h[vi] if vi is not None else 'NOT FOUND'], ['gross col', main_h[gi] if gi is not None else 'NOT FOUND'], ['item col', main_h[ni] if ni is not None else 'NOT FOUND']]
for h, fs in headers.items(): meta.append(['header (%d files)' % len(fs), ' | '.join(h)])
for b in bad: meta.append(['bad file'] + b)

# ---- write ----
have = {s['properties']['title'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties.title').execute()['sheets']}
def put(tab, data):
    w = max(len(r) for r in data)
    data = [[('' if c is None else c) for c in r] + [''] * (w - len(r)) for r in data]
    if tab not in have:
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': tab,
            'gridProperties': {'rowCount': len(data) + 10, 'columnCount': max(w, 5)}}}}]}).execute()
    else:
        sid = [s['properties'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets'] if s['properties']['title'] == tab][0]
        g = sid['gridProperties']
        if g['rowCount'] < len(data) + 10 or g['columnCount'] < w:
            svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': sid['sheetId'],
                'gridProperties': {'rowCount': max(g['rowCount'], len(data) + 10), 'columnCount': max(g['columnCount'], w)}},
                'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
        svc.values().clear(spreadsheetId=SHEET, range=f"'{tab}'").execute()
    for i in range(0, len(data), 8000):
        svc.values().update(spreadsheetId=SHEET, range=f"'{tab}'!A{i + 1}", valueInputOption='RAW',
                            body={'values': data[i:i + 8000]}).execute()
    print('wrote', tab, len(data), 'rows', flush=True)

# Items_All (70k+ rows) made the workbook too big to read back through Drive; drop it and keep the compact tabs.
if 'Items_All' in have:
    sid = [s['properties']['sheetId'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets'] if s['properties']['title'] == 'Items_All'][0]
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'deleteSheet': {'sheetId': sid}}]}).execute(); have.discard('Items_All')
put('Meta', meta); put('Probe', probe); put('Cat_Totals', cats); put('Day_Totals', days); put('M14_Items', m14r)
