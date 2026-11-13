"""Kobas nightly pull (11/11/2026, Michael: "everything from Kobas, can we not just log in").

Logs into Kobas with the keyline bot user (no Mac, no browser) and pulls, per site, for each week asked:
  sales + covers   Cash Log report            /data/reports/cash-log                     (one call per venue)
  labour           Labour Costs report        report-queue labour_costs_report -> /data/reports/labour-costs/<id>/export
  item mix         All Item Sales             /data/reports/item-by-sales/export         (one call per venue per week)
  waste/comp/dir   Stock Usage History        report-queue stock_usage_report (csv)
  purchases        Orders & Deliveries        /data/v2/stock/order (type delivery, delivered in the week) + delivery entries
  stock checks     Stock Checks               /data/v2/stock/check (dates, closing counts by category)
  food cost +      Stock Usage Comparison     POST /reports/index.php m=CORE_Reports_UsageComparison, opening/closing stock check
  stock variance                              dates as YYYY-MM-DD (the report Matt keys into Mona Lisa / the variance sheet)
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

# ---- 2b) hours worked by department (13/11/2026, Michael x Remy: FOH and BOH cost per labour hour) ----------------
# Rotas > Hours Worked (index.php?m=fullhours), the department filter is a POST. Only the totals per department per day are
# kept: no staff names, no shift rows.
DEPTS = {'foh': 'FrontofHouse', 'boh': 'BackofHouse', 'management': 'Management', 'norole': 'norole'}
try: rotas = {(x['venueid'], str(x['rotadate'])[:10]): x['id'] for x in get('/data/rota/past', {'include-current-week': 1}).json()}
except Exception as e: rotas = {}; err('rota list', e)
# 13/11/2026: the page lists the venue's staff, so it also carries their shifts worked at OTHER venues (each shift names the
# venue it was worked at). Only shifts worked at this venue count, which is what the Labour Costs report hours are.
try:
    _vj = get('/data/venue').json(); _vj = _vj.get('data', _vj) if isinstance(_vj, dict) else _vj
    VNAMES = {int(x['id']): str(x.get('name', '')).strip() for x in _vj if isinstance(x, dict) and x.get('id') is not None}
except Exception as e: VNAMES = {}; err('venue names', e)
_txt = lambda h: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()
def dept_hours(job):
    site, vid, w = job; rid = rotas.get((vid, w.isoformat()))
    if not rid: return {'site': site, 'week': w.isoformat(), 'error': 'no rota'}
    o = {'site': site, 'week': w.isoformat(), 'rota_id': rid}; pages = {}
    for key, dep in DEPTS.items():
        try:
            t = post_form(f'/rotas/index.php?m=fullhours&iRotaID={rid}&venueid={vid}', {'department': dep}).text
            if not re.search(r'<option[^>]*value="%s"[^>]*selected' % dep, t): raise RuntimeError('department filter not applied')
            sh_ = []
            for m in re.finditer(r'<td[^>]*class="staff_\d+_day_(\d)"[^>]*>(.*?)(?=<td|</tr>)', t, re.S):
                for sh in re.findall(r'<div[^>]*>(.*?)</div>', m.group(2), re.S):
                    h = re.search(r'</a>\s*<br\s*/?>\s*(\d+)h(?:&nbsp;|\s)*(\d+)m', sh); lm = re.search(r'<strong[^>]*>(.*?)</strong>', sh, re.S)
                    if h: sh_.append((int(m.group(1)) - 1, _txt(lm.group(1)) if lm else '', int(h.group(1)) + int(h.group(2)) / 60.0))
            pages[key] = sh_
        except Exception as e: pages[key] = None; err(f'dept hours {site} {w} {key}', e)
    by = {}
    for sh_ in pages.values():
        for _, lab, hh in sh_ or []: by[lab] = by.get(lab, 0) + hh
    own = VNAMES.get(vid) if VNAMES.get(vid) in by else (max(by, key=by.get) if by else None)   # this venue's label; fallback: the label with most hours
    for key, sh_ in pages.items():
        if sh_ is None: o[key] = None; continue
        hrs = [0.0] * 7; away = 0.0
        for d_, lab, hh in sh_:
            if lab == own: hrs[d_] += hh
            else: away += hh
        o[key] = [round(x, 2) for x in hrs]; o[key + '_other_venue_hours'] = round(away, 2)
    return o
with ThreadPoolExecutor(4) as ex: save('dept_hours.json', list(ex.map(dept_hours, [(s_, v_, w) for w in weeks for s_, v_ in V.items()])))

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
        rows.append([cat, e.get('total_value') or 0, None if (theo is None or uvp is None) else round(theo * uv * uvp, 4), si.get('stock_ingredient_category_id')])
    return dict({kk: c.get(kk) for kk in ('id', 'venue_id', 'venue_name', 'name', 'log_date', 'type', 'status', 'total_value', 'c_date')}, entries=rows)
stock = [c for c in checks if c.get('type') == 'stock' and c.get('status') == 'completed' and c.get('venue_id') in VID2S]
save('stock_check_list.json', [{kk: c.get(kk) for kk in ('id', 'venue_id', 'log_date', 'c_date', 'total_value')} for c in stock])
def uc_pairs(vid, w):
    """The stock period that closes a week: the LAST completed stock check date logged Fri..Tue after the week start, paired with
    the last check 5..9 days before it. Sites that split the take over two days (M6: food Sunday, drinks Monday) must use the later
    day at both ends: Kobas carries the other category's position forward, and pairing the earlier days gives nonsense (proved
    11/11/2026, M6 w/c 02/11: 02/11 -> 08/11 read food variance -79%, 02/11 -> 09/11 reads +0.3%)."""
    ds = sorted({c['log_date'][:10] for c in stock if c['venue_id'] == vid})
    out = []
    for cd in [d for d in ds if (w + datetime.timedelta(4)).isoformat() <= d <= (w + datetime.timedelta(8)).isoformat()][-1:]:
        lo, hi = (datetime.date.fromisoformat(cd) - datetime.timedelta(9)).isoformat(), (datetime.date.fromisoformat(cd) - datetime.timedelta(5)).isoformat()
        op = [d for d in ds if lo <= d <= hi]
        out.append((op[-1] if op else None, cd))
    return out
closing_days = {(c['venue_id'], cd) for w in weeks for c in stock for _, cd in uc_pairs(c['venue_id'], w)}
closing = [c for c in stock if (c['venue_id'], c['log_date'][:10]) in closing_days]
with ThreadPoolExecutor(5) as ex: save('stock_checks.json', [x for x in ex.map(check_full, closing) if x])
log['stock_checks'] = len(stock); log['closing_checks_pulled'] = len(closing)

# 4b2) Stock Usage Comparison per site per week (opening -> closing stock check). Parsed here, raw html not kept.
def uc_const(t, name):
    i = t.find(f"'{name}',")
    if i < 0: return None
    j = t.find(');</script>', i)
    return json.loads(t[i + len(name) + 3:j].strip())
def usage_comparison(job):
    site, vid, a, b = job
    if not (a and b): return {'site': site, 'opening': a, 'closing': b, 'error': 'no opening stock check 5..9 days before the closing one'}
    data = {'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venueid': str(vid), 'opening_years': a[:4], 'opening_days': a,
            'closing_years': b[:4], 'closing_days': b}
    for i in range(3):
        try:
            r = k.s.post(BASE + '/reports/index.php', data=data, timeout=300)
            td = uc_const(r.text, 'table_data')
            if r.status_code == 200 and td:
                hd = re.search(r'Viewing report for ([^<]*)', r.text)
                cats = {cid: {kk: v['total'].get(kk) for kk in ('net_rev', 'usage_value', 'theory_value', 'variance_value', 'cos_value', 'cow_value', 'coc_value', 'cod_value', 'actual_gp_perc', 'theory_gp_perc')}
                        for cid, v in td.items()}
                return {'site': site, 'opening': a, 'closing': b, 'heading': hd.group(1).strip() if hd else None,
                        'total_net_revenue': uc_const(r.text, 'total_net_revenue'), 'categories': cats}
        except Exception as e: last = repr(e)
        time.sleep(5)
    return {'site': site, 'opening': a, 'closing': b, 'error': 'usage comparison returned no table'}
uc_jobs = sorted({(s, v, a, b) for w in weeks for s, v in V.items() for a, b in uc_pairs(v, w)}, key=lambda x: (x[0], x[3]))
with ThreadPoolExecutor(4) as ex: save('usage_comparison.json', list(ex.map(usage_comparison, uc_jobs)))

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
