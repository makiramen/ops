"""Kobas nightly pull (11/11/2026, Michael: "everything from Kobas, can we not just log in").

Logs into Kobas with the keyline bot user (no Mac, no browser) and pulls, per site, for each week asked:
  sales + covers   Cash Log report            /data/reports/cash-log                     (one call per venue)
  labour           Labour Costs report        report-queue labour_costs_report -> /data/reports/labour-costs/<id>/export
  item mix         All Item Sales             /data/reports/item-by-sales/export         (one call per venue per week)
  waste/comp/dir   Stock Usage History        report-queue stock_usage_report (csv)
  purchases        Orders & Deliveries        /data/v2/stock/order (type delivery, delivered in the week) + delivery entries
  stock            Stock Checks               /data/v2/stock/check (completed stock checks, entries valued at Kobas FIFO price)
  transfers        Stock Transfers report     /data/reports/stock/transfer/totals
  targets          Rotas > Sales Budgets      /admin/budgets/ (the KPI sheet targets kpi-auto pushes into Kobas daily)

Raw pulls go to <out>/raw/... ; build.py turns them into data/kobas/wc_<monday>.json.
Env: KOBAS_COMPANY_ID / KOBAS_USERNAME / KOBAS_PASSWORD, WEEKS (comma list of Mondays; default = this week and last week, UK).
"""
import os, re, sys, json, time, html, datetime
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kobas_pull import Kobas, BASE
from sitemap import V, VID2S

out = sys.argv[1]; RAW = os.path.join(out, 'raw'); os.makedirs(RAW, exist_ok=True)
UK = ZoneInfo('Europe/London')
today = datetime.datetime.now(UK).date()
this_mon = today - datetime.timedelta(today.weekday())
weeks = [datetime.date.fromisoformat(w.strip()) for w in (os.environ.get('WEEKS') or '').split(',') if w.strip()] \
        or [this_mon - datetime.timedelta(7), this_mon]
weeks = sorted({w - datetime.timedelta(w.weekday()) for w in weeks})
VIDS = sorted(V.values())
log = {'weeks': [w.isoformat() for w in weeks], 'started': datetime.datetime.now(UK).isoformat(timespec='seconds'), 'errors': []}


def err(what, e):
    log['errors'].append(f'{what}: {e}'[:400]); print('ERR', what, e, file=sys.stderr, flush=True)


def save(rel, txt):
    p = os.path.join(RAW, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(txt if isinstance(txt, str) else json.dumps(txt))


k = Kobas()
if not k.login():
    log['errors'].append('LOGIN FAILED'); save('log.json', log); sys.exit(30)


def get(path, params=None, tries=4, timeout=180):
    last = None
    for i in range(tries):
        try:
            r = k.s.get(BASE + path, params=params, timeout=timeout)
            if r.status_code == 200: return r
            last = f'{r.status_code} {r.text[:150]}'
        except Exception as e: last = repr(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f'GET {path}: {last}')


def post_form(path, data, tries=4, timeout=180):
    last = None
    for i in range(tries):
        try:
            r = k.s.post(BASE + path, data=data, timeout=timeout, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            if r.status_code in (200, 201): return r
            last = f'{r.status_code} {r.text[:150]}'
        except Exception as e: last = repr(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f'POST {path}: {last}')


d_first = weeks[0]
d_last = min(weeks[-1] + datetime.timedelta(6), today - datetime.timedelta(1))
log['days'] = [d_first.isoformat(), d_last.isoformat()]

# ---- 1) cash log (sales, covers, tips), one call per venue for the whole span --------------------------
def cashlog(item):
    site, vid = item
    try:
        r = get('/data/reports/cash-log', [('venueIds[]', str(vid)), ('fromDate', d_first.isoformat()), ('toDate', d_last.isoformat())])
        save(f'cashlog/{site}.json', r.text); return 0
    except Exception as e: err(f'cashlog {site}', e); return 1
with ThreadPoolExecutor(5) as ex: log['cashlog_fail'] = sum(ex.map(cashlog, V.items()))

# ---- 2) item mix: one All Item Sales export per venue per week (CSV has no venue column: never batch venues) ------
def items(job):
    site, vid, w = job
    to = min(w + datetime.timedelta(6), d_last)
    if to < w: return 0
    data = [('venueIds[]', str(vid)), ('from', w.isoformat()), ('to', to.isoformat()), ('piscMode', ''), ('filterByTill', 'false'),
            ('seatingArea', ''), ('consumptionMode', '')]
    try:
        r = post_form('/data/reports/item-by-sales/export', data); save(f'items/{w}/{site}.csv', r.text); return 0
    except Exception as e: err(f'items {site} {w}', e); return 1
with ThreadPoolExecutor(5) as ex: log['items_fail'] = sum(ex.map(items, [(s, v, w) for w in weeks for s, v in V.items()]))

# ---- 3) queued reports: labour costs (one per Monday) + stock usage (whole span), queued together then waited on ------
def queue(key, filters):
    data = [('reportQueue[report_key]', key)]
    for kk, vv in filters:
        data.append((f'reportQueue[{kk}]' if kk == 'storage_format' else f'reportQueue[filters][{kk}]', vv))
    r = k.s.post(BASE + '/data/report-queue', data=data, timeout=60)
    if r.status_code != 201: raise RuntimeError(f'queue {key}: {r.status_code} {r.text[:200]}')
    return r.json()['id']

queued = {}
for w in weeks:
    try: queued[('labour', w.isoformat())] = queue('labour_costs_report', [('date', w.isoformat())] + [('venue_ids][', str(v)) for v in VIDS])
    except Exception as e: err(f'queue labour {w}', e)
try:
    queued[('usage', 'span')] = queue('stock_usage_report', [('storage_format', 'csv'), ('from', d_first.isoformat()), ('to', d_last.isoformat()),
                                                          ('usage_type', '')] + [('venue_ids][', str(v)) for v in VIDS])
except Exception as e: err('queue stock usage', e)

# ---- 4) while those generate: purchases, stock checks, transfers, budgets -------------------------------
# 4a) supplier deliveries: orders delivered in the span (stable id ordering per venue, see kpi_auto/pull.py)
orders = {}
for vid in VIDS:
    off = 0
    while True:
        try:
            j = get('/data/v2/stock/order', {'limit': 100, 'offset': off, 'orderBy[id]': 'ASC', 'filterBy[to_venue_id][eq]': vid,
                                             'filterBy[log_date][gte]': (d_first - datetime.timedelta(30)).isoformat(),
                                             'filterBy[log_date][lte]': (d_last + datetime.timedelta(10)).isoformat()}).json()
        except Exception as e: err(f'orders {vid}', e); break
        for o in j: orders[o['id']] = o
        if len(j) < 100: break
        off += 100
inweek = [o for o in orders.values() if o.get('type') == 'delivery' and d_first.isoformat() <= str(o.get('delivered_date') or '')[:10] <= d_last.isoformat()]
save('orders.json', list(orders.values()))
# delivery lines, valued and split by ingredient category (food / wet / controllables)
dels = []; off = 0
while True:
    try:
        j = get('/data/v2/stock/order/delivery', {'limit': 100, 'offset': off, 'orderBy[log_date]': 'ASC',
                                                  'filterBy[log_date][gte]': d_first.isoformat(), 'filterBy[log_date][lte]': d_last.isoformat()}).json()
    except Exception as e: err('deliveries list', e); break
    dels += j
    if len(j) < 100: break
    off += 100

def dent(dv):
    try: j = get(f'/data/v2/stock/order/delivery/{dv["id"]}').json()
    except Exception as e: err(f'delivery {dv["id"]}', e); return None
    cats = {}
    for e in j.get('stock_order_delivery_entries') or []:
        ci = ((e.get('stock_ingredient') or {}).get('custom_stock_ingredient_interval') or {})
        v = (e.get('pack_price') or 0) * (e.get('units') or 0) / (ci.get('pack_size') or 1)
        c = (((e.get('stock_ingredient') or {}).get('parent') or {}).get('stock_ingredient_category_name')
             or (e.get('stock_ingredient') or {}).get('stock_ingredient_category_name') or '?')
        cats[c] = cats.get(c, 0.0) + v
    o = orders.get(dv['stock_order_id']) or {}
    return {'id': dv['id'], 'order_id': dv['stock_order_id'], 'log_date': dv.get('log_date'), 'to_venue_id': o.get('to_venue_id'),
            'supplier': o.get('from_supplier_name'), 'order_total': o.get('total'), 'cats': cats}
with ThreadPoolExecutor(6) as ex: save('delivery_lines.json', [x for x in ex.map(dent, dels) if x])

# 4b) stock checks: every completed stock check from 10 days before the span to the end, full entries
checks = []; off = 0
while True:
    try:
        r = get('/data/v2/stock/check', {'limit': 100, 'offset': off, 'orderBy[log_date]': 'DESC',
                                         'filterBy[log_date][gte]': (d_first - datetime.timedelta(10)).isoformat(),
                                         'filterBy[log_date][lte]': (d_last + datetime.timedelta(2)).isoformat() + ' 23:59:59'})
    except Exception as e: err('stock check list', e); break
    j = r.json(); checks += j
    if len(j) < 100: break
    off += 100

def check_full(c):
    ents, off = [], 0
    try:
        while True:
            r = get(f'/data/v2/stock/check/{c["id"]}', {'limit': 500, 'offset': off})
            ents += r.json().get('stock_check_entries') or []
            off += 500
            if off >= int(r.headers.get('x-total-count') or 0): break
    except Exception as e: err(f'stock check {c["id"]}', e); return None
    rows = []
    for e in ents:
        si = e.get('stock_ingredient') or e.get('stock_product') or {}
        cat = si.get('stock_ingredient_category_name') or si.get('stock_product_category_name') or '?'
        uvp = si.get('lilo_unit_volume_price'); uv = e.get('unit_volume') or 0
        theo = e.get('theoretical_holding_units')
        rows.append([cat, e.get('total_value') or 0, None if (theo is None or uvp is None) else round(theo * uv * uvp, 4)])
    return dict({kk: c.get(kk) for kk in ('id', 'venue_id', 'venue_name', 'name', 'log_date', 'type', 'status', 'total_value', 'c_date')}, entries=rows)
stock = [c for c in checks if c.get('type') == 'stock' and c.get('status') == 'completed' and c.get('venue_id') in VID2S]
with ThreadPoolExecutor(5) as ex: save('stock_checks.json', [x for x in ex.map(check_full, stock) if x])
log['stock_checks'] = len(stock)

# 4c) transfers, per week, all venues
for w in weeks:
    to = min(w + datetime.timedelta(6), d_last)
    try:
        r = get('/data/reports/stock/transfer/totals', [('venueIds[]', str(v)) for v in VIDS + [11]] + [('from', w.isoformat()), ('to', to.isoformat())])
        save(f'transfers/{w}.json', r.text)
    except Exception as e: err(f'transfers {w}', e)

# 4d) sales budgets (targets)
try:
    p = get('/admin/budgets/')
    vname = {v['name'].strip(): v['id'] for v in k.gj('/data/venue', params={'fields': 'id,name'})}
    MON = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}
    bud = []
    for tr in re.findall(r'<tr[^>]*class="tabledata"[^>]*>(.*?)</tr>', p.text, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
        if len(tds) < 9: continue
        name = html.unescape(re.sub(r'<[^>]+>', '', tds[0])).strip()
        m = re.match(r'(\d+)\w*\s+(\w{3})\s+(\d{4})', re.sub(r'<[^>]+>', '', tds[1]).strip())
        raw = {d.lower(): float(v) for v, d in re.findall(r'data-raw="([\d.\-]+)" id="(Mon|Tue|Wed|Thu|Fri|Sat|Sun)_\d+"', tr)}
        if m and name in vname:
            bud.append({'venue_id': vname[name], 'week': datetime.date(int(m.group(3)), MON[m.group(2)], int(m.group(1))).isoformat(), **raw})
    save('budgets.json', bud)
except Exception as e: err('budgets', e)

# ---- 5) wait for the queued reports, export them ---------------------------------------------------
t0 = time.time(); done = {}
while queued and len(done) < len(queued) and time.time() - t0 < 25 * 60:
    time.sleep(20)
    for key in ('labour_costs_report', 'stock_usage_report'):
        try: q = get('/data/report-queue', {'filterBy[report_key][eq]': key, 'limit': 50}).json()
        except Exception: continue
        for x in q:
            for kk, rid in queued.items():
                if x.get('id') == rid and x.get('generated'): done[kk] = rid
for (kind, w), rid in queued.items():
    if (kind, w) not in done: err(f'{kind} {w}', f'report {rid} not generated after {int(time.time() - t0)}s'); continue
    try:
        if kind == 'labour': save(f'labour/{w}.csv', get(f'/data/reports/labour-costs/{rid}/export').text)
        else: save('stock_usage.csv', get(f'/data/reports/stock-usage/{rid}/export').text)
    except Exception as e: err(f'export {kind} {w}', e)

log['finished'] = datetime.datetime.now(UK).isoformat(timespec='seconds')
save('log.json', log); print(json.dumps(log))
