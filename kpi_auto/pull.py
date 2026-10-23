"""KPI sheet automation, October test pull. Kobas direct via the keyline bot user (no email skim, no Mac).
Writes: items/<site>_<date>_<mode>.csv (All Item Sales per venue per day, all / eat-in / delivery / takeaway),
labour/* (any already-generated Labour Costs reports in the range, exported), and the route probe dumps."""
import os, re, sys, json, datetime, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
from concurrent.futures import ThreadPoolExecutor
out = sys.argv[1]; os.makedirs(out + '/items', exist_ok=True); os.makedirs(out + '/labour', exist_ok=True)
V = {'M1': 3, 'M3': 5, 'M6': 43, 'M7': 9, 'M8': 47, 'M9': 2, 'M10': 13, 'M11': 24, 'M12': 27, 'M13': 28, 'M14': 37,
     'M15': 41, 'M16': 42, 'M17': 49, 'M18': 51, 'M19': 58, 'M20': 60, 'M21': 61, 'NORI': 57, 'IKI2': 7}
d0 = datetime.date.fromisoformat(os.environ.get('DATE_FROM', '2026-09-28'))
d1 = datetime.date.fromisoformat(os.environ.get('DATE_TO', '2026-10-21'))
k = Kobas(); assert k.login(), 'login failed'
def save(name, txt): open(os.path.join(out, name), 'w').write(txt)
log = []
# ---- route probe (labour + cash log) ----
r = k.s.get(BASE + '/data/report-queue', timeout=60); save('report_queue.json', r.text)
for name, url in [('labour', '/reports/labour-costs/'), ('reports_list', '/reports/list/'),
                  ('cashlog', '/daily/cashlog/edit/18833'), ('cashlog_list', '/daily/cashlog/')]:
    try:
        p = k.s.get(BASE + url, timeout=60)
        urls = sorted(set(re.findall(r"""['"](/(?:data|api|reports|daily|reporting)/[^'"\s<>]{2,160})['"]""", p.text)))
        save(f'page_{name}.txt', f'{p.status_code} {p.url}\n' + '\n'.join(urls) + '\n--html\n' + p.text[:80000])
    except Exception as e: save(f'page_{name}.txt', 'ERR ' + str(e))
try:
    q = r.json(); q = q if isinstance(q, list) else q.get('data', [])
    keys = sorted({str(x.get('report_key')) for x in q})
    log.append({'report_keys': keys})
    for x in q:
        if 'labour' in str(x.get('report_key', '')).lower() and x.get('generated'):
            rid = x['id']
            for path in [f'/data/reports/labour-costs/{rid}/export', f'/data/reports/labour-costs/{rid}']:
                p = k.s.get(BASE + path, timeout=120)
                save(f'labour/{rid}_{path.rsplit("/",1)[-1]}.txt', f'{p.status_code}\n{json.dumps(x)}\n' + p.text)
except Exception as e: log.append({'queue_err': str(e)})
# ---- KPI sources beyond items (23/10): cash log report, labour costs report, deliveries ----
def chunk(t, n=400): return '\n'.join(t[i:i + n] for i in range(0, len(t), n))
def getj(path, params=None, tries=4):
    last = None
    for i in range(tries):
        try:
            r = k.s.get(BASE + path, params=params, timeout=180)
            if r.status_code in (200, 201): return r
            last = r
        except Exception as e: last = e
        time.sleep(3 * (i + 1))
    return last
VIDS = sorted(V.values())
# 1) cash log report, one call per venue (the payload is keyed by date; venue id is not guaranteed inside it)
os.makedirs(out + '/cashlog', exist_ok=True)
for fmt in ('%Y-%m-%d',):
    for site, vid in V.items():
        r = getj('/data/reports/cash-log', [('venueIds[]', str(vid)), ('fromDate', d0.strftime(fmt)), ('toDate', d1.strftime(fmt))])
        txt = getattr(r, 'text', str(r))
        open(f'{out}/cashlog/{site}.json', 'w').write(txt)
        if site == 'M1': save('probe_cashlog_report_M1.txt', f'{getattr(r, "status_code", "ERR")}\n' + chunk(txt[:30000]))
# 2) labour costs report: queue a fresh one per Monday in range, wait, export; fall back to the newest existing
mondays = sorted({(d0 + datetime.timedelta(i) - datetime.timedelta((d0 + datetime.timedelta(i)).weekday())).isoformat() for i in range((d1 - d0).days + 1)})
queued = {}
for m in mondays:
    data = [('reportQueue[report_key]', 'labour_costs_report'), ('reportQueue[filters][date]', m)] + [('reportQueue[filters][venue_ids][]', str(v)) for v in VIDS]
    try:
        r = k.s.post(BASE + '/data/report-queue', data=data, timeout=60)
        save(f'probe_labour_queue_{m}.txt', f'{r.status_code}\n{r.text[:2000]}')
        if r.status_code == 201: queued[m] = r.json()['id']
    except Exception as e: save(f'probe_labour_queue_{m}.txt', 'ERR ' + str(e))
t0 = time.time(); done = {}
while queued and time.time() - t0 < 15 * 60 and len(done) < len(queued):
    time.sleep(30)
    try: q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'labour_costs_report'}, timeout=60).json()
    except Exception: continue
    for x in q:
        for m, rid in queued.items():
            if x.get('id') == rid and x.get('generated'): done[m] = rid
if len(done) < len(mondays):
    q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'labour_costs_report'}, timeout=60).json()
    for m in mondays:
        if m in done: continue
        c = [x for x in q if x.get('generated') and (x.get('filters') or {}).get('date') == m]
        if c: done[m] = max(c, key=lambda x: x.get('generation_end') or '')['id']
os.makedirs(out + '/labour', exist_ok=True)
for m, rid in done.items():
    r = getj(f'/data/reports/labour-costs/{rid}/export')
    open(f'{out}/labour/{m}_{rid}.csv', 'w').write(getattr(r, 'text', ''))
log.append({'labour_reports': done, 'labour_fresh': sorted(set(done) & set(queued))})
# 3) deliveries received (food cost), venue from the parent stock order
since = (d0 - datetime.timedelta(60)).isoformat()
omap = {}; off = 0
while True:
    r = getj('/data/v2/stock/order', {'limit': 100, 'offset': off, 'orderBy[log_date]': 'DESC', 'filterBy[log_date][gte]': since})
    j = r.json() if hasattr(r, 'json') else []
    for o in j: omap[o['id']] = (o.get('to_venue_id'), o.get('from_supplier_name'), o.get('type'))
    if len(j) < 100: break
    off += 100
dels = []; off = 0
while True:
    r = getj('/data/v2/stock/order/delivery', {'limit': 100, 'offset': off, 'orderBy[log_date]': 'ASC',
             'filterBy[log_date][gte]': d0.isoformat(), 'filterBy[log_date][lte]': d1.isoformat()})
    j = r.json() if hasattr(r, 'json') else []
    dels += j
    if len(j) < 100: break
    off += 100
miss = [d['stock_order_id'] for d in dels if d['stock_order_id'] not in omap]
for oid in sorted(set(miss)):
    try:
        o = k.gj(f'/data/v2/stock/order/{oid}'); omap[oid] = (o.get('to_venue_id'), o.get('from_supplier_name'), o.get('type'))
    except Exception: pass
with open(f'{out}/deliveries.json', 'w') as f:
    json.dump([dict(d, to_venue_id=omap.get(d['stock_order_id'], (None,))[0], supplier=omap.get(d['stock_order_id'], (None, None))[1]) for d in dels], f)
log.append({'deliveries': len(dels), 'orders_mapped': len(omap)})
# 4) probe the eat-in consumption mode spelling (eat-in returned header-only)
for mode in ('eatin', 'eat_in', 'dine-in', 'dine_in', 'sit-in', 'Eat In', 'eat in', 'EAT_IN', 'dinein', 'table'):
    try:
        p = k.s.post(BASE + '/data/reports/item-by-sales/export', data=[('venueIds[]', '3'), ('from', '2026-10-01'), ('to', '2026-10-01'), ('piscMode', ''),
                     ('filterByTill', 'false'), ('seatingArea', ''), ('consumptionMode', mode)], timeout=120,
                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        tot = [l for l in p.text.splitlines() if l.lower().startswith('total') or l.lower().startswith('"total')]
        save(f'probe_mode_{re.sub(chr(32), "_", mode)}.txt', f'{p.status_code} lines={len(p.text.splitlines())}\n' + '\n'.join(tot))
    except Exception as e: save(f'probe_mode_{mode}.txt', 'ERR ' + str(e))
# ---- item sales per venue per day per consumption mode ----
jobs = []
d = d0
while d <= d1:
    for site, vid in V.items():
        for mode in ['', 'eat-in', 'delivery', 'takeaway']:
            jobs.append((site, vid, d.isoformat(), mode))
    d += datetime.timedelta(days=1)
def one(j):
    site, vid, day, mode = j
    data = [('venueIds[]', str(vid)), ('from', day), ('to', day), ('piscMode', ''), ('filterByTill', 'false'),
            ('seatingArea', ''), ('consumptionMode', mode)]
    for i in range(4):
        try:
            p = k.s.post(BASE + '/data/reports/item-by-sales/export', data=data, timeout=120,
                         headers={'Content-Type': 'application/x-www-form-urlencoded'})
            if p.status_code == 200:
                open(f'{out}/items/{site}_{day}_{mode or "all"}.csv', 'w').write(p.text); return 0
        except Exception: pass
        time.sleep(2 * (i + 1))
    return 1
with ThreadPoolExecutor(5) as ex: errs = sum(ex.map(one, jobs))
log.append({'item_calls': len(jobs), 'errors': errs})
save('log.json', json.dumps(log, indent=1)); print(json.dumps(log))
