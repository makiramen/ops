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
cats = [['date', 'site', 'mode', 'category', 'qty', 'gross', 'net']] + [list(k) + [round(v[0], 2), round(v[1], 2), round(v[2], 2)] for k, v in sorted(cat.items()) if k[2] == 'all']
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

# ---- report TOTAL rows per lead type (food / wet / controllables), every numeric column ----
li = col(main_h, 'lead type')
numcols = [i for i, c in enumerate(main_h) if c not in ('Item', 'Lead Type', 'Category')]
lead = [['date', 'site', 'mode', 'lead'] + [main_h[i] for i in numcols]]
for r in items[1:]:
    l = r[3:]
    if ni is not None and l[ni].strip().lower() == 'total':
        lead.append(r[:3] + [l[li] if li is not None else ''] + [num(l[i]) if i < len(l) else None for i in numcols])

# ---- item rows carrying waste / comp / director units (to rebuild the Headline Revenue cost columns) ----
wi = [main_h.index(c) if c in main_h else None for c in ('Waste', 'Comp', 'Director')]
wcd = [['date', 'site', 'mode'] + list(main_h)]
for r in items[1:]:
    l = r[3:]
    if r[2] == 'all' and is_item(l) and any(i is not None and i < len(l) and (num(l[i]) or 0) != 0 for i in wi):
        wcd.append(r[:3] + [num(x) if num(x) is not None else x for x in l])

# ---- cash log report per site: flatten every numeric leaf to (site, date, key, value) ----
from zoneinfo import ZoneInfo
UK = ZoneInfo('Europe/London')
def flat(o, pre=''):
    if isinstance(o, dict):
        for kk, v in o.items(): yield from flat(v, f'{pre}.{kk}' if pre else str(kk))
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from flat(v, f'{pre}[{i}]')
    else:
        v = num(o) if not isinstance(o, bool) else None
        if v is not None: yield pre, v
        elif isinstance(o, str) and o and len(o) < 200: yield pre, o
def keydate(kk):
    kk = str(kk)
    if kk.isdigit() and len(kk) >= 9: return datetime.datetime.fromtimestamp(int(kk), UK).date().isoformat()
    m = re.match(r'(\d{4}-\d{2}-\d{2})', kk)
    return m.group(1) if m else None
cash = [['site', 'date', 'key', 'value']]
for f in sorted(glob.glob(os.path.join(out, 'cashlog', '*.json'))):
    site = os.path.basename(f)[:-5]
    try: j = json.load(open(f))
    except Exception as e: cash.append([site, '', 'PARSE ERROR', str(e)[:200]]); continue
    body = j.get('data', j) if isinstance(j, dict) else j
    if isinstance(body, dict) and any(keydate(x) for x in body):
        for kk, v in body.items():
            d = keydate(kk)
            for path, val in flat(v): cash.append([site, d or kk, path, val])
    else:
        for path, val in flat(body):
            if re.search(r'(venues\[0\]\.name$|data\.\w+\[\d+\]\.(name|\d{4}-\d{2}-\d{2})$)', path) and 'otherPaymentTypes' not in path:
                cash.append([site, '', path, val])

# ---- labour costs report CSVs ----
lab = [['week', 'venue', 'information', 'date', 'value']]
for f in sorted(glob.glob(os.path.join(out, 'labour', '*.csv'))):
    wk = os.path.basename(f)[:10]
    ls = list(csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())))
    if not ls: continue
    h = ls[0]
    for l in ls[1:]:
        for i in range(2, min(len(h), len(l))):
            lab.append([wk, l[0], l[1], h[i], num(l[i])])

# ---- labour snapshots (report generated the morning after each day), only the snapshot day's column ----
snap = [['day', 'report_id', 'generated', 'venue', 'information', 'value']]
for f in sorted(glob.glob(os.path.join(out, 'labour_snap', '*.csv'))):
    day, rid, gen = os.path.basename(f)[:-4].split('_', 2)
    ls = list(csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())))
    if not ls or day not in ls[0]: continue
    i = ls[0].index(day)
    for l in ls[1:]:
        if len(l) > i: snap.append([day, rid, gen, l[0], l[1], num(l[i])])
# ---- deliveries ----
delv = [['id', 'to_venue_id', 'supplier', 'log_date', 'net', 'gross', 'total', 'note_number', 'staff']]
try:
    for d in json.load(open(os.path.join(out, 'deliveries.json'))):
        delv.append([d.get('id'), d.get('to_venue_id'), d.get('supplier'), d.get('log_date'), d.get('delivery_note_net_total'),
                     d.get('delivery_note_gross_total'), d.get('total'), d.get('delivery_note_number'), d.get('staff_name')])
except Exception as e: delv.append(['ERR', str(e)])

# ---- delivery entries joined to deliveries ----
dentr = [['id', 'to_venue_id', 'supplier', 'log_date', 'header_total', 'entries_ex', 'entries_inc_tax', 'entries_complementary', 'n_entries', 'categories', 'c_date']]
try:
    hdr = {d['id']: d for d in json.load(open(os.path.join(out, 'deliveries.json')))}
    for e in json.load(open(os.path.join(out, 'delivery_entries.json'))):
        d = hdr.get(e[0], {})
        dentr.append([e[0], d.get('to_venue_id'), d.get('supplier'), d.get('log_date'), d.get('total')] + list(e[1:]))
except Exception as ex: dentr.append(['ERR', str(ex)])
# ---- item reference (unit cost / price) over the long range per site ----
iref = [['site'] + list(main_h)]
for f in sorted(glob.glob(os.path.join(out, 'items_range', '*.csv'))):
    site = os.path.basename(f)[:-4]
    ls = [l for l in csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())) if any(c.strip() for c in l)]
    if not ls: continue
    h = tuple(c.strip() for c in ls[0])
    for l in ls[1:]:
        l2 = [l[h.index(c)] if c in h and h.index(c) < len(l) else '' for c in main_h]
        nm = l2[ni].strip().lower() if ni is not None else ''
        if nm and nm != 'total' and not nm.startswith('of which '): iref.append([site] + [num(x) if num(x) is not None else x for x in l2])

# ---- orders (stock_order headers) and the stock usage report export ----
ords = [['id', 'to_venue_id', 'from_supplier_name', 'type', 'status', 'log_date', 'c_date', 'total', 'delivered_date', 'm_date']]
try:
    for o in json.load(open(os.path.join(out, 'orders.json'))):
        ords.append([o.get('id'), o.get('to_venue_id'), o.get('from_supplier_name'), o.get('type'), o.get('status'), o.get('log_date'),
                     o.get('c_date'), o.get('total'), o.get('delivered_date'), o.get('m_date')])
except Exception as ex: ords.append(['ERR', str(ex)])
susage = [['line']]
try:
    for l in csv.reader(io.StringIO(open(os.path.join(out, 'stock_usage_export.txt'), encoding='utf-8-sig', errors='replace').read())):
        if len(susage) < 20000: susage.append(l)
except Exception as ex: susage.append(['ERR', str(ex)])

# probe dump
probe = [['file', 'line']]
for f in sorted([x for x in glob.glob(os.path.join(out, '*.json')) if os.path.basename(x) not in ('deliveries.json', 'delivery_entries.json', 'orders.json')] + [x for x in glob.glob(os.path.join(out, '*.txt')) if not os.path.basename(x).startswith('stock_usage_export')]):
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
    """Rewrite a tab at exactly the size of its data (shrinks too, so the workbook stays under the 10M cell limit)."""
    w = max(len(r) for r in data)
    data = [[('' if c is None else c) for c in r] + [''] * (w - len(r)) for r in data]
    props = {s['properties']['title']: s['properties'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets']}
    reqs = []
    if tab in props:
        reqs.append({'updateSheetProperties': {'properties': {'sheetId': props[tab]['sheetId'], 'gridProperties': {'rowCount': len(data) + 5, 'columnCount': max(w, 2)}},
                     'fields': 'gridProperties(rowCount,columnCount)'}})
        svc.values().clear(spreadsheetId=SHEET, range=f"'{tab}'").execute()
    else:
        reqs.append({'addSheet': {'properties': {'title': tab, 'gridProperties': {'rowCount': len(data) + 5, 'columnCount': max(w, 2)}}}})
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': reqs}).execute()
    for i in range(0, len(data), 8000):
        svc.values().update(spreadsheetId=SHEET, range=f"'{tab}'!A{i + 1}", valueInputOption='RAW',
                            body={'values': data[i:i + 8000]}).execute()
    print('wrote', tab, len(data), 'rows', flush=True)

for gone in ('M14_Items', 'Deliv_Entries', 'Item_Ref', 'Deliveries', 'Stock_Usage', 'Sheet1', 'Labour', 'Orders', 'Cash_Log', 'Probe'):
    if gone in have:
        gid = [x['properties']['sheetId'] for x in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets'] if x['properties']['title'] == gone][0]
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'deleteSheet': {'sheetId': gid}}]}).execute(); have.discard(gone)
# Items_All (70k+ rows) made the workbook too big to read back through Drive; drop it and keep the compact tabs.
if 'Items_All' in have:
    sid = [s['properties']['sheetId'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets'] if s['properties']['title'] == 'Items_All'][0]
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'deleteSheet': {'sheetId': sid}}]}).execute(); have.discard('Items_All')
put('Meta', meta); put('Probe', probe); put('Cat_Totals', cats); put('Day_Totals', days)
put('Lead_Totals', lead); put('Cash_Log', cash); put('Labour_Snap', snap); put('Items_WCD', wcd); put('Orders', ords); put('Stock_Usage', susage)
