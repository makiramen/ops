#!/usr/bin/env python3
"""kobas_pull.py: the Keyline Kobas pull, offline (no Chrome, no Mac).

Logs into Kobas with a bot user held in the environment, queues the nine Stock Current Position
reports, waits for them, exports and aggregates them into pull.txt (the exact compact shape
build_data.py has always read), then pulls six weeks of stock orders and deliveries for the nine
venues and writes part_orders.html (window.KEYLINE_ORDERS, the shape part_e reads).

  KOBAS_COMPANY_ID  KOBAS_USERNAME  KOBAS_PASSWORD   (GitHub Actions secrets)

  python3 kobas_pull.py --out . [--skip-orders] [--since YYYY-MM-DD] [--report /tmp/pull_report.json]

Exit codes: 0 ok · 30 login failed · 31 reports never generated · 32 export failed · 33 orders pull failed
(33 still leaves pull.txt in place, so the stock side of the run can carry on degraded).

This is a straight port of pull-helpers.js (__parse/__ex/__agg) and pull-orders.js, kept line for
line where it matters so the numbers match the browser pull to the penny.
"""
import argparse, csv, datetime, io, json, os, re, sys, time
from zoneinfo import ZoneInfo
import requests

BASE = 'https://login.kobas.co.uk'
UK = ZoneInfo('Europe/London')
VENUES = {2: 'M9', 13: 'M10', 24: 'M11', 37: 'M14', 42: 'M16', 49: 'M17', 51: 'M18', 58: 'M19', 60: 'M20'}
SITE_ORDER = ['M9', 'M10', 'M11', 'M14', 'M16', 'M17', 'M18', 'M19', 'M20']
CATS = [24, 23]
REPORT_KEY = 'stock_current_position_report'
# Item ID -> keyline key (13 keylines, v1.8.0 onward)
KEY = {2173: 'tonkotsu', 12077: 'chkbroth', 1965: 'karaage', 2751: 'katsu', 1971: 'pbsliced', 2143: 'noodle',
       1975: 'rump', 11408: 'chkfillet', 2184: 'soba', 2192: 'teriyaki', 2188: 'tataki', 2196: 'hell', 2883: 'gyoza'}
KEYS = ['tonkotsu', 'chkbroth', 'karaage', 'katsu', 'pbsliced', 'noodle', 'rump', 'chkfillet', 'soba', 'teriyaki', 'tataki', 'hell', 'gyoza']
# default pack in grams (noodle in items) for the orders conversion, same as the stock pull's default row
G = {'tonkotsu': 14400, 'chkbroth': 14400, 'karaage': 10000, 'katsu': 10000, 'pbsliced': 10000, 'noodle': 50,
     'chkfillet': 5000, 'soba': 2000, 'teriyaki': 2000, 'tataki': 2000, 'hell': 2000, 'gyoza': 6000}

def log(*a): print(*a, file=sys.stderr, flush=True)

def supmap(n):
    n = (n or '').upper()
    if n.startswith('JFC'): return 'JFC'
    if 'HARRO' in n: return 'Harro'
    if n.startswith('JFE'): return 'JFE'
    if 'DUNSTER' in n: return 'Dunster Farm'
    if 'BRAKES' in n: return 'Brakes'
    return None

class Kobas:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh) KeylineControl/1.0',
                               'X-Requested-With': 'XMLHttpRequest'})

    def gj(self, url, tries=4, **kw):
        """GET json with backoff, the gj() helper from the 12 Sep fix."""
        last = None
        for i in range(tries):
            try:
                r = self.s.get(BASE + url, timeout=60, **kw)
                if r.status_code == 200:
                    return r.json()
                last = f'{r.status_code} {r.text[:120]}'
            except Exception as e:
                last = str(e)
            time.sleep(1.5 * (i + 1))
        raise RuntimeError(f'GET {url} failed after {tries}: {last}')

    def signed_in(self):
        r = self.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': REPORT_KEY}, timeout=60)
        return r.status_code == 200

    def login(self):
        cid, user, pw = os.environ.get('KOBAS_COMPANY_ID'), os.environ.get('KOBAS_USERNAME'), os.environ.get('KOBAS_PASSWORD')
        if not (cid and user and pw):
            log('KOBAS_COMPANY_ID / KOBAS_USERNAME / KOBAS_PASSWORD missing from the environment'); return False
        self.s.get(BASE + '/', timeout=60)  # cookie jar
        r = self.s.post(BASE + '/', data={'user_sign_in': '1', 'company_id': cid, 'username': user, 'password': pw},
                        headers={'X-Requested-With': None, 'Referer': BASE + '/'}, timeout=60, allow_redirects=True)
        ok = self.signed_in()
        log('login', 'ok' if ok else f'FAILED (http {r.status_code}, landed {r.url})')
        return ok

    # ---- stock position -------------------------------------------------------------------
    def queue_reports(self):
        ids = {}
        for vid in VENUES:
            data = [('reportQueue[filters][stock_ingredient_category_ids][]', str(c)) for c in CATS]
            data += [('reportQueue[filters][venue_id]', str(vid)), ('reportQueue[report_key]', REPORT_KEY)]
            r = self.s.post(BASE + '/data/report-queue', data=data, timeout=60)
            if r.status_code != 201:
                raise RuntimeError(f'queue venue {vid}: {r.status_code} {r.text[:200]}')
            ids[vid] = r.json()['id']
        log('queued', ids)
        return ids

    def wait_generated(self, ids, timeout_s=25 * 60):
        want = set(ids.values()); done = set(); t0 = time.time()
        while time.time() - t0 < timeout_s:
            lst = self.gj('/data/report-queue?filterBy[report_key][eq]=' + REPORT_KEY)
            for it in lst:
                if it['id'] in want and it.get('generated'): done.add(it['id'])
            log(f'generated {len(done)}/{len(want)} after {int(time.time()-t0)}s')
            if done == want: return True
            time.sleep(45)
        return False

    def export_rows(self, rid):
        r = self.s.get(BASE + f'/data/reports/stock-current-position/{rid}/export', timeout=120)
        if r.status_code != 200: raise RuntimeError(f'export {rid}: {r.status_code}')
        rows = list(csv.reader(io.StringIO(r.text)))
        h = rows[0]; ix = {n: h.index(n) for n in ('Stock Check Date', 'Venue ID', 'Item ID', 'Item Name', 'Each Pack',
                                                   'Current Estimated Stock', 'Estimated Days Remaining')}
        out = []
        for x in rows[1:]:
            if len(x) < len(h): continue
            try: iid = int(x[ix['Item ID']])
            except ValueError: continue
            if iid not in KEY: continue
            out.append({'date': x[ix['Stock Check Date']], 'venue': x[ix['Venue ID']], 'id': iid,
                        'name': x[ix['Item Name']].replace('&', '+')[:60], 'each': x[ix['Each Pack']],
                        'stock': x[ix['Current Estimated Stock']], 'days': x[ix['Estimated Days Remaining']]})
        return out

    @staticmethod
    def agg(rows):
        """Port of __agg: unit trap, stock is in eaches of THAT row's each size; convert to grams, sum across
        rows of the Item ID, divide by the default row's pack. Days from the default row."""
        by = {}; date = ''
        for r in rows:
            date = r['date']; by.setdefault(r['id'], []).append(r)
        def ep(s):
            m = re.search(r'([\d.]+)\s*x\s*([\d.]+)', s or '')
            return (float(m.group(1)), float(m.group(2))) if m else (1.0, 1.0)
        out = []
        for iid, key in KEY.items():
            rs = by.get(iid)
            if not rs: out.append(key + ':MISSING'); continue
            d = next((r for r in rs if '(Default Supply)' in r['name']), rs[0])
            base = 0.0
            for r in rs:
                n, g = ep(r['each'])
                try: base += float(r['stock'] or 0) * g
                except ValueError: pass
            dn, dg = ep(d['each'])
            qty = base / 3000 if key == 'rump' else base / (dn * dg)
            try: days = float(d['days']); days_s = ('%g' % days)
            except ValueError: days_s = 'x'
            out.append(f'{key}:{qty:.2f}:{days_s}' + (f':m{len(rs)}' if len(rs) > 1 else ''))
        return date + '|' + ' '.join(out)

    def pull_stock(self, outdir):
        ids = self.queue_reports()
        if not self.wait_generated(ids):
            log('reports never generated'); return 31, None
        lines = ['MAP ' + ' '.join(f'{ids[v]}={VENUES[v]}' for v in VENUES)]
        for v in VENUES:
            rows = self.export_rows(ids[v])
            lines.append(f'{ids[v]}=' + self.agg(rows))
        txt = '\n'.join(lines) + '\n'
        open(os.path.join(outdir, 'pull.txt'), 'w').write(txt)
        log(txt)
        return 0, ids

    # ---- orders and deliveries ------------------------------------------------------------
    def child_map(self):
        ch = {}; off = 0
        while True:
            page = self.gj(f'/data/v2/stock/ingredient?limit=500&offset={off}')
            for p in page:
                for c in (p.get('children') or []):
                    iv = c.get('current_stock_ingredient_interval') or {}
                    ch[c['id']] = {'p': p['id'], 'sup': c.get('supplier_name'), 'uv': iv.get('unit_volume') or 0}
            if len(page) < 500: break
            off += 500
        log('ingredient children', len(ch))
        return ch

    def pull_orders(self, outdir, since):
        ch = self.child_map()
        def conv(child_id, units):
            c = ch.get(child_id)
            if not c: return None
            key = KEY.get(c['p'])
            if not key: return None
            grams = units * (c['uv'] or 0)
            q = grams / 3000 if key == 'rump' else grams / G[key]
            return key, round(q * 100) / 100
        orders = []
        for vid in VENUES:
            off = 0
            while True:
                j = self.gj(f'/data/v2/stock/order?limit=100&offset={off}&orderBy[log_date]=DESC'
                            f'&filterBy[log_date][gte]={since}&filterBy[to_venue_id][eq]={vid}')
                orders += [o for o in j if o.get('type') == 'delivery']
                if len(j) < 100: break
                off += 100
        log('orders listed', len(orders))
        out = []; sups = {}
        for n, o in enumerate(orders, 1):
            sup = supmap(o.get('from_supplier_name')); sups[o.get('from_supplier_name')] = sups.get(o.get('from_supplier_name'), 0) + 1
            d = self.gj(f'/data/v2/stock/order/{o["id"]}')
            lines = {}; other = 0
            for e in d.get('stock_order_entries') or []:
                c = conv(e['stock_ingredient_id'], e['units'])
                if not c: other += 1; continue
                L = lines.setdefault(c[0], {'ord': 0, 'del': None}); L['ord'] = round((L['ord'] + c[1]) * 100) / 100
            if not sup and not lines: continue
            delivered_at = None
            if o.get('status') == 'delivered':
                dl = self.gj(f'/data/v2/stock/order/delivery?limit=10&filterBy[stock_order_id][eq]={o["id"]}')
                for dv in dl:
                    if not delivered_at or dv['log_date'] > delivered_at: delivered_at = dv['log_date']
                    dd = self.gj(f'/data/v2/stock/order/delivery/{dv["id"]}')
                    for e in dd.get('stock_order_delivery_entries') or []:
                        c = conv(e['stock_ingredient_id'], e['units'])
                        if not c: continue
                        L = lines.setdefault(c[0], {'ord': 0, 'del': 0}); L['del'] = round(((L['del'] or 0) + c[1]) * 100) / 100
                for L in lines.values():
                    if L['del'] is None: L['del'] = 0
            out.append({'id': o['id'], 'site': VENUES[o['to_venue_id']], 'sup': sup or o.get('from_supplier_name'),
                        'by': o.get('staff_name'), 'created': (o.get('c_date') or '')[:16], 'reqDel': o.get('log_date'),
                        'status': o.get('status'), 'deliveredAt': delivered_at, 'lines': lines})
            if n % 100 == 0: log(f'orders detail {n}/{len(orders)}')
        now = datetime.datetime.now(UK)
        meta = {'source': 'kobas-live', 'pulledAt': now.strftime('%Y-%m-%dT%H:%M'), 'since': since, 'nListed': len(orders),
                'venues': {str(k): v for k, v in VENUES.items()}, 'suppliersSeen': sups,
                'units': 'keyline units (cases, packs, kg) converted from Kobas inner units via the default supply pack',
                'pulledLabel': now.strftime('%d %b %H:%M') + ' UK'}
        body = json.dumps({'meta': meta, 'orders': out}, separators=(',', ':'))
        open(os.path.join(outdir, 'part_orders.html'), 'w').write('<script>\nwindow.KEYLINE_ORDERS = ' + body + ';\n</script>\n')
        log('orders kept', len(out), 'pulledLabel', meta['pulledLabel'])
        return len(orders), len(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='.'); ap.add_argument('--skip-orders', action='store_true')
    ap.add_argument('--since'); ap.add_argument('--report')
    a = ap.parse_args()
    R = {'run_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'login': False,
         'stock': None, 'orders': None, 'warnings': []}
    def finish(code):
        R['exit'] = code
        if a.report: json.dump(R, open(a.report, 'w'), indent=1)
        print(json.dumps(R)); sys.exit(code)
    k = Kobas()
    if not k.login(): finish(30)
    R['login'] = True
    try:
        code, ids = k.pull_stock(a.out)
    except Exception as e:
        log('stock pull failed:', e); R['warnings'].append(f'stock: {e}'); finish(32)
    if code: finish(code)
    R['stock'] = {'reports': ids}
    if a.skip_orders: finish(0)
    since = a.since or (datetime.date.today() - datetime.timedelta(weeks=6)).isoformat()
    try:
        listed, kept = k.pull_orders(a.out, since)
        R['orders'] = {'since': since, 'listed': listed, 'kept': kept}
    except Exception as e:
        log('orders pull failed:', e); R['warnings'].append(f'orders: {e}'); finish(33)
    finish(0)

if __name__ == '__main__':
    main()
