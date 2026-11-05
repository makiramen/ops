#!/usr/bin/env python3
"""Kobas EA extraction, step 1b: the report-only entities (tabs, sales, payments, receipts, cash, labour ...).

Kobas does not list tabs / sales / payments under /data as JSON. They only come out as report exports from the
report queue. This script:
  1. reads /data/report-queue (everything the company has ever queued) and the /reports/list/ catalogue page,
     and writes reports_inventory.json: every report_key seen, its filter fields, how many runs, latest run id
  2. for every key whose latest run is generated, downloads that export (/data/reports/<slug>/<id>/export, csv)
     and infers a column schema from the header plus 25 rows (PII columns keep type only)
  3. writes schemas/report__<key>.json and appends report nodes and <x>_id edges to graph.json, kobas.puml, kobas.mmd
Nothing is queued fresh (no new Kobas load); it reads what is already there. Raw export samples go to --raw only.

  python3 extract_reports.py --out out --raw /tmp/kobas_raw [--limit 25] [--only tab,payment]
Exit: 0 ok · 30 login failed · 35 report queue unreadable
"""
import argparse, csv, datetime, io, json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'keyline'))
from kobas_pull import Kobas, BASE  # noqa: E402
import extract as X  # noqa: E402

def log(*a): print(*a, file=sys.stderr, flush=True)

def col_key(c):
    return re.sub(r'[^a-z0-9]+', '_', c.strip().lower()).strip('_')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out'); ap.add_argument('--raw', default='/tmp/kobas_raw')
    ap.add_argument('--limit', type=int, default=25); ap.add_argument('--only', default='')
    a = ap.parse_args()
    only = {s.strip() for s in a.only.split(',') if s.strip()}
    k = Kobas()
    if not k.login(): sys.exit(30)
    # 1. queue inventory
    # The queue only answers per report_key (400 otherwise). Build the key list from the catalogue pages, the
    # keys the other pipes use, and a guessed set, then ask the queue for each.
    KNOWN = ['labour_costs_report', 'stock_current_position_report', 'stock_usage_report', 'stock_transfers_report',
             'supplier_stock_deliveries_report', 'operational_profitability_report', 'hours_export', 'item_by_sales_report',
             'all_item_sales_report', 'sales_breakdown_report', 'tabs_report', 'tab_report', 'tab_export', 'payments_report',
             'payment_report', 'payments_export', 'sales_report', 'sales_export', 'z_report', 'z_reports', 'cash_log_report',
             'cash_log_export', 'transactions_report', 'transaction_export', 'receipts_report', 'discounts_report',
             'discount_usage_report', 'vouchers_report', 'voucher_usage_report', 'loyalty_report', 'loyalty_customers_report',
             'customers_report', 'customer_export', 'reservations_report', 'bookings_report', 'covers_report',
             'daily_headline_revenue_report', 'headline_revenue_report', 'daily_sales_report', 'sales_by_payment_type_report',
             'payment_types_report', 'card_payments_report', 'tips_report', 'service_charge_report', 'refunds_report',
             'voids_report', 'comps_report', 'wastage_report', 'staff_sales_report', 'staff_report', 'rota_report',
             'clock_ins_report', 'till_sessions_report', 'epos_sessions_report', 'session_report', 'menu_report',
             'item_sales_report', 'product_mix_report', 'category_sales_report', 'hourly_sales_report', 'delivery_sales_report',
             'deliverect_orders_report', 'online_orders_report', 'xero_export', 'accounting_export', 'gift_cards_report']
    found_keys = set(KNOWN)
    for pg in ('/reports/list/', '/reports/', '/reporting/', '/data/report-queue'):
        try:
            h = k.s.get(BASE + pg, timeout=60, headers={'X-Requested-With': None}).text
            found_keys |= set(re.findall(r'\b([a-z]+(?:_[a-z0-9]+)*_(?:report|export))\b', h))
            found_keys |= {x.replace('-', '_') + '_report' for x in re.findall(r'/reports/([a-z0-9\-]+)/', h)}
            for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', h):
                if src.startswith('/'): src = BASE + src
                if not src.startswith(BASE): continue
                try: found_keys |= set(re.findall(r'\b([a-z]+(?:_[a-z0-9]+)*_(?:report|export))\b', k.s.get(src, timeout=60).text))
                except Exception: pass
        except Exception as e: log('catalogue', pg, e)
    found_keys = {x for x in found_keys if 3 < len(x) < 60}
    log('candidate report keys', len(found_keys))
    runs = []; key_status = {}
    for key in sorted(found_keys):
        try:
            r = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': key}, timeout=90)
            j = r.json() if 'json' in r.headers.get('content-type', '') else None
            lst = j if isinstance(j, list) else (j.get('data') if isinstance(j, dict) and isinstance(j.get('data'), list) else [])
            key_status[key] = {'status': r.status_code, 'runs': len(lst)}
            if r.status_code == 200 and lst: runs += lst
            elif r.status_code == 200: runs.append({'report_key': key, 'id': 0, 'generated': None})
        except Exception as e:
            key_status[key] = {'status': 'ERR', 'error': str(e)[:100]}
        time.sleep(0.2)
    log('valid keys', sum(1 for v in key_status.values() if v.get('status') == 200), 'with runs', sum(1 for v in key_status.values() if v.get('runs')))
    runs = [r for r in runs if r.get('id')] or runs
    if not runs: sys.exit(35)
    keys = {}
    for r in runs:
        key = str(r.get('report_key')); K = keys.setdefault(key, {'runs': 0, 'filters': set(), 'latest': None})
        K['runs'] += 1
        f = r.get('filters') or {}
        if isinstance(f, dict): K['filters'] |= set(f.keys())
        if r.get('generated') and (K['latest'] is None or r['id'] > K['latest']['id']):
            K['latest'] = {'id': r['id'], 'generated': r.get('generated'), 'c_date': r.get('c_date'), 'filters': f}
    # catalogue page: names and keys the company has not necessarily run
    catalogue = []
    try:
        h = k.s.get(BASE + '/reports/list/', timeout=60, headers={'X-Requested-With': None}).text
        catalogue = sorted(set(re.findall(r'report[_-]key["\']?\s*[:=]\s*["\']([a-z0-9_]+)', h)) |
                           set(re.findall(r'/reports/([a-z0-9\-]+)/', h)))
    except Exception as e: log('catalogue', e)
    inv = {'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'queued_runs': len(runs),
           'key_status': key_status,
           'keys': {kk: {'runs': v['runs'], 'filters': sorted(v['filters']), 'latest': v['latest']} for kk, v in sorted(keys.items())},
           'catalogue': catalogue}
    os.makedirs(a.out, exist_ok=True); os.makedirs(a.raw, exist_ok=True)
    json.dump(inv, open(os.path.join(a.out, 'reports_inventory.json'), 'w'), indent=1)
    log('report keys', len(keys), 'catalogue', len(catalogue))
    # 2. export the latest run of each key
    entities = {}
    for key, K in sorted(keys.items()):
        if only and not any(o in key for o in only): continue
        if not K['latest'] or not K['latest'].get('id'): continue
        slug = re.sub(r'_report$', '', key).replace('_', '-')
        rid = K['latest']['id']; rows = None
        for url in (f'/data/reports/{slug}/{rid}/export', f'/data/reports/{slug}/{rid}/export?format=csv', f'/data/report-queue/{rid}/export'):
            try:
                r = k.s.get(BASE + url, timeout=120)
            except Exception as e:
                log(key, url, 'ERR', e); continue
            ct = r.headers.get('content-type', '')
            if r.status_code == 200 and ('csv' in ct or 'text/plain' in ct or 'octet' in ct or (r.text[:1] not in '<{[' and ',' in r.text[:500])):
                rows = list(csv.reader(io.StringIO(r.text))); inv['keys'][key]['export'] = url; break
            if r.status_code == 200 and 'json' in ct:
                try:
                    j = r.json(); recs = j if isinstance(j, list) else (j.get('data') if isinstance(j, dict) else None)
                    if recs: entities['report__' + key] = {'routes': [url], 'records': recs[:a.limit]}; inv['keys'][key]['export'] = url
                except Exception: pass
                break
            log(key, url, r.status_code, ct.split(';')[0])
        if rows and len(rows) > 1:
            hdr = [col_key(c) for c in rows[0]]
            recs = []
            for x in rows[1:1 + a.limit]:
                if len(x) < len(hdr): continue
                d = {}
                for c, v in zip(hdr, x):
                    v = v.strip()
                    if re.fullmatch(r'-?\d+', v): d[c] = int(v)
                    elif re.fullmatch(r'-?\d+\.\d+', v): d[c] = float(v)
                    elif v == '': d[c] = None
                    else: d[c] = v
                recs.append(d)
            entities['report__' + key] = {'routes': [inv['keys'][key]['export']], 'records': recs, 'columns': rows[0], 'row_count_sample': len(rows) - 1}
            log(key, 'csv cols', len(hdr), 'rows', len(rows) - 1)
        time.sleep(0.3)
    # 2b. direct (non-queued) report exports: the reports list page links every report page; each page's
    # /data/reports/<slug>/export answers a POST with venueIds[] / from / to (the item-by-sales pattern the KPI pipe uses).
    pages = set(); nav = {}
    for pg in ('/reports/list/', '/reports/', '/reporting/', '/', '/dashboard/'):
        try:
            rr = k.s.get(BASE + pg, timeout=60, headers={'X-Requested-With': None}); h = rr.text
            hrefs = sorted(set(re.findall(r'href=["\']([^"\'#]+)', h)))
            nav[pg] = {'status': rr.status_code, 'final_url': rr.url, 'bytes': len(h), 'hrefs': [x for x in hrefs if not x.startswith(('http', 'mailto', 'javascript'))][:400],
                       'ext': [x for x in hrefs if x.startswith('http') and 'kobas' in x][:100]}
            log('nav', pg, rr.status_code, rr.url, len(h), 'hrefs', len(hrefs))
            pages |= set(re.findall(r'href=["\'](?:https?://login\.kobas\.co\.uk)?(/report(?:s|ing)/[a-z0-9\-/]+)', h))
        except Exception as e: log('pages', pg, e)
    inv['nav'] = nav
    # the reports list is rendered client side: keep its inline scripts and every url-ish / key-ish string in them
    try:
        h = k.s.get(BASE + '/reports/list/', timeout=60, headers={'X-Requested-With': None}).text
        scripts = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', h, flags=re.S)
        open(os.path.join(a.raw, 'reports_list_inline_scripts.js'), 'w').write('\n\n/* ---- */\n\n'.join(scripts))
        strings = set()
        for sc in scripts:
            strings |= set(re.findall(r'["\'](/[A-Za-z0-9_\-/\.]{3,120})["\']', sc))
            strings |= set(re.findall(r'\b([a-z]+(?:_[a-z0-9]+){1,6})\b', sc))
        inv['reports_list_strings'] = sorted(x for x in strings if 'report' in x or x.startswith('/'))[:600]
        pages |= {x.rstrip('/') for x in strings if x.startswith('/reports/') and x.count('/') >= 2}
        log('reports list inline scripts', len(scripts), 'strings kept', len(inv['reports_list_strings']))
        # the catalogue comes from the external bundles (cloudfront): read those too
        bundles = {}
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', h):
            u = ('https:' + src) if src.startswith('//') else ((BASE + src) if src.startswith('/') else src)
            try:
                js = k.s.get(u, timeout=90).text
            except Exception as e: log('bundle', u, e); continue
            urls = sorted(set(re.findall(r'["\'`](/(?:data|reports?)/[A-Za-z0-9_\-/\.${}]{2,120})["\'`]', js)))
            bkeys = sorted(set(re.findall(r'\b([a-z]+(?:_[a-z0-9]+){1,6}_(?:report|export))\b', js)))
            bundles[u] = {'bytes': len(js), 'urls': urls[:400], 'report_keys': bkeys[:200]}
            log('bundle', u.split('/')[-1][:50], len(js), 'urls', len(urls), 'keys', len(bkeys), urls[:30])
            pages |= {x.rstrip('/') for x in urls if x.startswith('/reports/') and x.count('/') >= 2 and '$' not in x}
        inv['bundles'] = bundles
        for cand in ('/data/report/system', '/data/reports', '/data/report', '/data/report/list', '/data/reports/list', '/data/reports/available', '/data/report-list'):
            try:
                rr = k.s.get(BASE + cand, timeout=60)
                log('catalogue api', cand, rr.status_code, rr.headers.get('content-type', '')[:30], rr.text[:200].replace('\n', ' '))
                if rr.status_code == 200 and 'json' in rr.headers.get('content-type', ''):
                    body = rr.json(); inv['catalogue_api'] = {'route': cand, 'body': body}
                    blob = json.dumps(body)
                    pages |= {x.rstrip('/') for x in re.findall(r'"(/reports?/[a-z0-9\-/]+)"', blob)}
                    found = sorted(set(re.findall(r'"([a-z]+(?:_[a-z0-9]+)*_(?:report|export))"', blob)) | set(re.findall(r'"report_key":\s*"([a-z0-9_]+)"', blob)))
                    inv['catalogue_keys'] = found
                    log('catalogue api keys', len(found), found[:80], 'pages', len(pages))
                    break
            except Exception as e: log('catalogue api', cand, e)
    except Exception as e: log('reports list scripts', e)
    pages = sorted(p.rstrip('/') for p in pages if p.count('/') >= 2 and not p.endswith('/list'))
    inv['report_pages'] = pages; log('report pages', len(pages), pages[:40])
    yday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    direct = {}
    for pg in pages:
        slug = pg.split('/')[-1]
        routes = set()
        try:
            h = k.s.get(BASE + pg + '/', timeout=60, headers={'X-Requested-With': None}).text
            routes |= set(re.findall(r'["\'](/data/reports?/[A-Za-z0-9_\-/]+)', h))
            routes |= set(re.findall(r'["\'](/data/[A-Za-z0-9_\-/]*export[A-Za-z0-9_\-/]*)', h))
        except Exception as e: log('page', pg, e); continue
        routes.add(f'/data/reports/{slug}/export')
        # the report's own JSON (the pattern the KPI pipe uses for cash-log): GET /data/reports/<slug>?venueIds[]=..&fromDate=..&toDate=..
        if not (only and not any(o in slug for o in only)):
            jurl = f'/data/reports/{slug}'
            params = [('venueIds[]', '37'), ('fromDate', yday), ('toDate', yday), ('from', yday), ('to', yday), ('date', yday)]
            try:
                r = k.s.get(BASE + jurl, params=params, timeout=180)
                ct = r.headers.get('content-type', '')
                log('report json', jurl, r.status_code, ct.split(';')[0], len(r.text), r.text[:160].replace('\n', ' '))
                if r.status_code == 200 and 'json' in ct:
                    j = r.json()
                    if isinstance(j, dict) and isinstance(j.get('data'), (list, dict)): j = j['data']
                    recs = None
                    if isinstance(j, list) and j and isinstance(j[0], dict): recs = j
                    elif isinstance(j, dict):
                        vals = list(j.values())
                        if vals and all(isinstance(v, dict) for v in vals) and all(re.fullmatch(r'[\d\-/ :T]+', str(kk)) for kk in j): recs = vals  # keyed by date
                        else: recs = [j]
                    if recs:
                        entities['report__' + slug.replace('-', '_')] = {'routes': [jurl + ' (GET venueIds[], fromDate, toDate)'], 'records': recs[:a.limit]}
                        log(slug, 'json records', len(recs), 'keys', sorted(recs[0].keys())[:30])
            except Exception as e: log('report json', jurl, 'ERR', e)
        direct[pg] = sorted(routes)
        if only and not any(o in slug for o in only): continue
        for url in sorted(routes):
            if not url.endswith('/export'): continue
            form = [('venueIds[]', '37'), ('venue_ids[]', '37'), ('venueId', '37'), ('from', yday), ('to', yday), ('date', yday),
                    ('fromDate', yday), ('toDate', yday), ('piscMode', ''), ('filterByTill', 'false'), ('seatingArea', ''), ('consumptionMode', '')]
            try:
                r = k.s.post(BASE + url, data=form, timeout=120, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            except Exception as e: log(url, 'ERR', e); continue
            ct = r.headers.get('content-type', '')
            log('direct', url, r.status_code, ct.split(';')[0], len(r.text))
            if r.status_code != 200 or r.text[:1] == '<': continue
            if 'json' in ct:
                try:
                    j = r.json(); recs = j if isinstance(j, list) else (j.get('data') if isinstance(j, dict) else None)
                    if recs and isinstance(recs, list) and isinstance(recs[0], dict):
                        entities['report__' + slug.replace('-', '_')] = {'routes': [url + ' (POST)'], 'records': recs[:a.limit]}
                except Exception: pass
                continue
            rows = list(csv.reader(io.StringIO(r.text)))
            if len(rows) > 1 and len(rows[0]) > 1:
                hdr = [col_key(c) for c in rows[0]]; recs = []
                for x in rows[1:1 + a.limit]:
                    if len(x) < len(hdr): continue
                    d = {}
                    for c, v in zip(hdr, x):
                        v = v.strip()
                        if re.fullmatch(r'-?\d+', v): d[c] = int(v)
                        elif re.fullmatch(r'-?\d+\.\d+', v): d[c] = float(v)
                        else: d[c] = v or None
                    recs.append(d)
                entities['report__' + slug.replace('-', '_')] = {'routes': [url + ' (POST)'], 'records': recs, 'columns': rows[0], 'row_count_sample': len(rows) - 1}
                log(slug, 'csv cols', len(hdr), 'rows', len(rows) - 1)
            time.sleep(0.3)
    inv['direct_exports'] = direct
    json.dump(inv, open(os.path.join(a.out, 'reports_inventory.json'), 'w'), indent=1)
    # 3. schemas and graph merge
    os.makedirs(os.path.join(a.out, 'schemas'), exist_ok=True)
    gpath = os.path.join(a.out, 'graph.json')
    graph = json.load(open(gpath)) if os.path.exists(gpath) else {'nodes': [], 'edges': [], 'unresolved_references': {}}
    graph['nodes'] = [n for n in graph['nodes'] if not n['id'].startswith('report__')]
    graph['edges'] = [e for e in graph['edges'] if not e['from'].startswith('report__')]
    names = {X.norm(n['id']): n['id'] for n in graph['nodes']}
    for ent, e in sorted(entities.items()):
        person = bool(re.search(r'customer|staff|loyalty|employee|clock|rota|shift|labour', ent))
        json.dump(X.redact(e['records'], person), open(os.path.join(a.raw, ent + '.json'), 'w'), indent=1)
        fields = X.infer(e['records'], person)
        sch = X.to_schema(fields, len(e['records']))
        sch.update({'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': ent, 'x-routes': e['routes'],
                    'x-sample-size': len(e['records']), 'x-pii-redacted': person, 'x-source': 'report export (csv)',
                    'x-columns': e.get('columns')})
        json.dump(sch, open(os.path.join(a.out, 'schemas', ent + '.json'), 'w'), indent=1)
        graph['nodes'].append({'id': ent, 'fields': len(fields), 'routes': e['routes'], 'sample': len(e['records']), 'kind': 'report'})
        for kf in fields:
            m = re.fullmatch(r'(.+?)_ids?', kf)
            if not m: continue
            tgt = names.get(X.norm(m.group(1))) or names.get(X.norm(m.group(1).split('_')[-1]))
            if tgt: graph['edges'].append({'from': ent, 'to': tgt, 'field': kf, 'kind': 'reference'})
            else: graph['unresolved_references'].setdefault(m.group(1), []); graph['unresolved_references'][m.group(1)] = sorted(set(graph['unresolved_references'][m.group(1)] + [ent]))
    graph['generated'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    json.dump(graph, open(gpath, 'w'), indent=1)
    # UML: append report classes to both diagrams
    for fn, open_tag, close_tag, fmt in (('kobas.puml', 'class {ent} <<report>> {{', '}}', '  {k} : {t}'), ('kobas.mmd', '  class {ent} {{', '  }}', '    {t} {k}')):
        p = os.path.join(a.out, fn)
        txt = open(p).read() if os.path.exists(p) else ('@startuml\n@enduml\n' if fn.endswith('puml') else 'classDiagram\n')
        txt = re.sub(r'\n(?:class report__|  class report__).*?(?:\n\}|\n  \})', '', txt, flags=re.S)
        txt = '\n'.join(l for l in txt.split('\n') if not l.startswith('report__') and not l.startswith('  report__'))
        add = []
        for ent in sorted(entities):
            sch = json.load(open(os.path.join(a.out, 'schemas', ent + '.json')))
            add.append(open_tag.format(ent=ent))
            for kk, pp in list(sch['properties'].items())[:30]:
                t = pp['type'] if isinstance(pp['type'], str) else 'mixed'
                add.append(fmt.format(k=kk, t=t))
            add.append(close_tag)
        for ed in graph['edges']:
            if ed['from'].startswith('report__'):
                add.append(f'{"" if fn.endswith("puml") else "  "}{ed["from"]} --> {ed["to"]} : {ed["field"]}')
        if fn.endswith('puml'): txt = txt.replace('@enduml', '\n'.join(add) + '\n@enduml')
        else: txt = txt.rstrip('\n') + '\n' + '\n'.join(add) + '\n'
        open(p, 'w').write(txt)
    S = [f'\n## Report-only entities (step 1b, {graph["generated"][:16]}Z)', '',
         f'- report keys ever queued: {len(keys)}; exports read: {len(entities)}; catalogue entries on /reports/list/: {len(catalogue)}', '',
         '| report | columns | sample rows | export |', '|---|---|---|---|']
    for ent, e in sorted(entities.items()): S.append(f'| {ent} | {len(e.get("columns") or [])} | {len(e["records"])} | {e["routes"][0]} |')
    S += ['', '### Keys with no readable export', ''] + [f'- {kk} (runs {v["runs"]}, latest {v["latest"] and v["latest"]["id"]})' for kk, v in sorted(keys.items()) if 'report__' + kk not in entities]
    sp = os.path.join(a.out, 'SUMMARY.md')
    base = open(sp).read() if os.path.exists(sp) else ''
    base = base.split('\n## Report-only entities')[0]
    open(sp, 'w').write(base.rstrip('\n') + '\n' + '\n'.join(S) + '\n')
    print(json.dumps({'report_keys': len(keys), 'exports': len(entities), 'catalogue': len(catalogue)}))

if __name__ == '__main__':
    main()
