#!/usr/bin/env python3
"""Kobas business entity extraction for Marcel's enterprise architecture exercise (step 1, 5 Nov 2026).

Runs in GitHub Actions as the keyline bot user (KOBAS_COMPANY_ID / KOBAS_USERNAME / KOBAS_PASSWORD secrets).
No Mac, no Chrome, no Claude session, no password outside the Actions secret store.

What it does
  1. discover   log in, walk the Kobas UI pages and their same-origin JS bundles, harvest every /data/... route
                it can see, add the seed list below (routes the other pipes already use plus likely entity names)
  2. probe      GET each candidate route (limit=25). Keep the ones that answer JSON. Record status for all.
  3. schema     infer a JSON schema per entity from the sample records (types, nullable, nested objects,
                enum-like small value sets). PII fields keep their type only, never a value.
  4. graph      every <thing>_id field becomes a reference edge to the entity <thing> when one was found
                (singular / plural / hyphen / underscore tolerant); nested objects become composition edges;
                unresolved references are listed so the ontology work can name them by hand.
  5. uml        PlantUML and Mermaid class diagrams of the same graph.

Outputs (committed to main under ea/kobas/out/):
  inventory.json       every route probed, http status, content type, record count, sample keys
  schemas/<e>.json     one JSON schema per entity (draft 2020-12 style, plus x-examples for non-PII scalars)
  graph.json           {nodes:[...], edges:[{from,to,field,kind}], unresolved:[...]}
  kobas.puml           PlantUML class diagram
  kobas.mmd            Mermaid classDiagram
  SUMMARY.md           counts and the entity list for reading in chat
Raw samples (PII redacted) go to /tmp only and are kept as a 7-day workflow artifact, never committed.

  python3 extract.py --out out --raw /tmp/kobas_raw [--limit 25] [--only venue,customer]
Exit codes: 0 ok · 30 login failed · 34 nothing probed successfully
"""
import argparse, datetime, json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'keyline'))
from kobas_pull import Kobas, BASE  # noqa: E402

def log(*a): print(*a, file=sys.stderr, flush=True)

# UI pages to walk for route discovery (HTML + same-origin <script src>). Read-only GETs.
PAGES = ['/', '/dashboard/', '/admin/', '/admin/venues/', '/admin/users/', '/admin/budgets/', '/reports/list/',
         '/reports/labour-costs/', '/reporting/sales-breakdown', '/daily/', '/daily/cashlog/', '/epos/', '/epos/items/',
         '/epos/menus/', '/epos/tills/', '/stock/', '/stock/ingredients/', '/stock/orders/', '/stock/suppliers/',
         '/customers/', '/customer/', '/loyalty/', '/bookings/', '/reservations/', '/staff/', '/rota/', '/hr/',
         '/payments/', '/gift-cards/', '/vouchers/', '/discounts/', '/promotions/', '/settings/', '/integrations/']

# Seed routes: what the other pipes already call, plus plausible entity names in both API styles.
SEED = ['/data/venue', '/data/daily', '/data/items', '/data/item/1', '/data/item/category/6', '/data/till/all',
        '/data/till-menu/1', '/data/till-page/1', '/data/price-band', '/data/reports/cash-log', '/data/report-queue',
        '/data/v2/epos/item', '/data/v2/epos/items', '/data/epos/item', '/data/v2/stock/ingredient',
        '/data/v2/stock/order', '/data/v2/stock/order/delivery', '/data/v2/stock/usage', '/data/v2/stock/usage/reasons']
NAMES = ['venue', 'venues', 'company', 'customer', 'customers', 'customer-group', 'loyalty', 'loyalty-scheme',
         'loyalty-card', 'booking', 'bookings', 'reservation', 'reservations', 'table', 'tables', 'seating-area',
         'order', 'orders', 'sale', 'sales', 'transaction', 'transactions', 'receipt', 'receipts', 'tab', 'tabs',
         'payment', 'payments', 'payment-type', 'payment-types', 'payment-method', 'refund', 'refunds', 'tip', 'tips',
         'service-charge', 'gift-card', 'gift-cards', 'voucher', 'vouchers', 'discount', 'discounts', 'promotion',
         'promotions', 'price-band', 'price-bands', 'menu', 'menus', 'till', 'tills', 'till-menu', 'till-page',
         'item', 'items', 'item/category', 'item-category', 'product', 'products', 'modifier', 'modifiers',
         'consumption-mode', 'department', 'departments', 'tax', 'tax-rate', 'vat', 'staff', 'user', 'users',
         'employee', 'employees', 'role', 'roles', 'shift', 'shifts', 'rota', 'rotas', 'clock-in', 'timesheet',
         'supplier', 'suppliers', 'delivery', 'deliveries', 'stock/ingredient', 'stock/order', 'stock/usage',
         'stock/stocktake', 'stock/transfer', 'recipe', 'recipes', 'cash-log', 'cashlog', 'cash-up', 'z-report',
         'review', 'reviews', 'feedback', 'integration', 'integrations', 'webhook', 'webhooks', 'api-key',
         'budget', 'budgets', 'forecast', 'target', 'targets', 'event', 'events', 'session', 'sessions',
         'device', 'devices', 'printer', 'printers', 'card-terminal', 'terminal', 'terminals', 'online-order',
         'online-orders', 'delivery-order', 'deliveroo', 'uber-eats', 'just-eat', 'web-order', 'click-collect']
PREFIXES = ['/data/', '/data/v2/', '/data/v2/epos/', '/data/v2/customer/', '/data/v2/booking/', '/data/v2/payment/',
            '/data/v2/staff/', '/data/epos/', '/data/customer/', '/data/booking/', '/data/payment/']

PII = re.compile(r'(^|_)(first_?name|last_?name|full_?name|surname|forename|email|phone|mobile|telephone|address'
                 r'|address_?line|postcode|post_?code|zip|dob|date_of_birth|birth|password|pin|token|secret|api_?key'
                 r'|card_?number|pan|iban|sort_?code|account_?number|ip|ip_address|notes?|comment)($|_)', re.I)
NAMEY = re.compile(r'(^|_)name$', re.I)  # a venue/item/supplier name is not PII, a customer name is
PEOPLE = re.compile(r'customer|staff|user|employee|member|guest|contact', re.I)


def entity_of(route):
    """'/data/v2/stock/order/delivery' -> 'stock_order_delivery'; strips ids and query strings."""
    p = route.split('?')[0]
    p = re.sub(r'^/data/(v\d+/)?', '', p).strip('/')
    p = re.sub(r'/\d+(/|$)', r'\1', p).strip('/')
    p = re.sub(r'/(all|list|export|history|reasons|breakdown)$', '', p)
    return re.sub(r'[^a-z0-9]+', '_', p.lower()).strip('_') or 'root'


def norm(n):
    n = re.sub(r'[^a-z0-9]+', '', n.lower())
    for suf in ('ies', 'ses', 's'):
        if n.endswith(suf) and len(n) > 3:
            return n[:-len(suf)] + ('y' if suf == 'ies' else ('s' if suf == 'ses' else ''))
    return n


def jtype(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'boolean'
    if isinstance(v, int): return 'integer'
    if isinstance(v, float): return 'number'
    if isinstance(v, str):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v): return 'string:date'
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?.*', v): return 'string:date-time'
        if re.fullmatch(r'-?\d+(\.\d+)?', v): return 'string:numeric'
        return 'string'
    if isinstance(v, list): return 'array'
    if isinstance(v, dict): return 'object'
    return 'unknown'


class Field:
    def __init__(self): self.types = {}; self.n = 0; self.nulls = 0; self.values = {}; self.child = None; self.items = None

def infer(records, person_entity):
    """Merge a list of dicts into {field: Field}, recursing into objects and arrays of objects."""
    fields = {}
    for r in records:
        if not isinstance(r, dict): continue
        for k, v in r.items():
            f = fields.setdefault(k, Field()); f.n += 1
            t = jtype(v); f.types[t] = f.types.get(t, 0) + 1
            if v is None: f.nulls += 1; continue
            if t == 'object':
                f.child = merge_fields(f.child, infer([v], person_entity))
            elif t == 'array':
                objs = [x for x in v if isinstance(x, dict)]
                if objs: f.items = merge_fields(f.items, infer(objs, person_entity))
                else: f.items = f.items or {'_scalar': sorted({jtype(x) for x in v})}
            else:
                sensitive = PII.search(k) or (NAMEY.search(k) and person_entity)
                if not sensitive and len(f.values) < 12:
                    s = str(v)[:40]; f.values[s] = f.values.get(s, 0) + 1
    return fields

def merge_fields(a, b):
    if a is None: return b
    for k, fb in b.items():
        fa = a.get(k)
        if fa is None: a[k] = fb; continue
        fa.n += fb.n; fa.nulls += fb.nulls
        for t, c in fb.types.items(): fa.types[t] = fa.types.get(t, 0) + c
        for s, c in fb.values.items():
            if len(fa.values) < 12: fa.values[s] = fa.values.get(s, 0) + c
        fa.child = merge_fields(fa.child, fb.child) if fb.child else fa.child
        if fb.items and isinstance(fb.items, dict) and '_scalar' not in fb.items:
            fa.items = merge_fields(fa.items if isinstance(fa.items, dict) and '_scalar' not in (fa.items or {}) else None, fb.items)
        elif fb.items and not fa.items: fa.items = fb.items
    return a

def to_schema(fields, total):
    props = {}; required = []
    for k, f in fields.items():
        ts = [t for t in f.types if t != 'null']
        base = sorted({t.split(':')[0] for t in ts}) or ['null']
        p = {'type': base[0] if len(base) == 1 else base}
        fmt = sorted({t.split(':')[1] for t in ts if ':' in t})
        if fmt: p['format'] = fmt[0] if len(fmt) == 1 else fmt
        if f.nulls: p['nullable'] = True
        if f.n == total and not f.nulls: required.append(k)
        if f.child: p['properties'] = to_schema(f.child, f.n - f.nulls)['properties']
        if f.items:
            if isinstance(f.items, dict) and '_scalar' in f.items: p['items'] = {'type': f.items['_scalar']}
            elif f.items: p['items'] = {'type': 'object', 'properties': to_schema(f.items, f.n - f.nulls)['properties']}
        if f.values and len(f.values) <= 8 and sum(f.values.values()) >= 3 and p['type'] in ('string', 'integer'):
            p['x-enum-like'] = sorted(f.values)
        elif f.values: p['x-examples'] = list(f.values)[:3]
        props[k] = p
    return {'type': 'object', 'properties': props, 'required': sorted(required)}


def redact(rec, person_entity):
    if isinstance(rec, dict):
        return {k: ('<redacted>' if (PII.search(k) or (NAMEY.search(k) and person_entity)) and not isinstance(v, (dict, list)) else redact(v, person_entity)) for k, v in rec.items()}
    if isinstance(rec, list): return [redact(x, person_entity) for x in rec]
    return rec


def discover(k):
    found = set(SEED)
    seen_js = set()
    for pg in PAGES:
        try:
            r = k.s.get(BASE + pg, timeout=60, headers={'X-Requested-With': None})
        except Exception as e:
            log('page', pg, 'ERR', e); continue
        if r.status_code != 200 or 'text/html' not in r.headers.get('content-type', ''): continue
        html = r.text
        found |= set(re.findall(r"""["'`](/data/[A-Za-z0-9_\-/]+)""", html))
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', html):
            if src.startswith('//') or ('://' in src and not src.startswith(BASE)): continue
            if src.startswith('/'): src = BASE + src
            if src in seen_js or not src.startswith(BASE): continue
            seen_js.add(src)
            try:
                js = k.s.get(src, timeout=60).text
                found |= set(re.findall(r"""["'`](/data/[A-Za-z0-9_\-/]+)""", js))
            except Exception as e:
                log('js', src, 'ERR', e)
        log('page', pg, 'routes so far', len(found))
    for pre in PREFIXES:
        for n in NAMES: found.add(pre + n)
    # drop obvious non-entity routes and template fragments
    out = set()
    for f in found:
        if re.search(r'/(export|delete|update|create|save|edit|new|print|email|send|queue|login|logout)(/|$)', f): continue
        if '{' in f or '$' in f or f.endswith('/'): f = f.rstrip('/')
        out.add(f)
    return sorted(out)


def probe(k, routes, limit, raw_dir, only):
    inventory = []; entities = {}
    for route in routes:
        ent = entity_of(route)
        if only and ent not in only: continue
        url = route + ('&' if '?' in route else '?') + f'limit={limit}'
        try:
            r = k.s.get(BASE + url, timeout=60)
        except Exception as e:
            inventory.append({'route': route, 'status': 'ERR', 'error': str(e)[:120]}); continue
        ct = r.headers.get('content-type', '')
        row = {'route': route, 'entity': ent, 'status': r.status_code, 'content_type': ct.split(';')[0], 'bytes': len(r.content)}
        recs = None
        if r.status_code == 200 and 'json' in ct:
            try: j = r.json()
            except Exception: j = None
            if isinstance(j, list): recs = j
            elif isinstance(j, dict):
                for key in ('data', 'results', 'items', 'rows'):
                    if isinstance(j.get(key), list): recs = j[key]; row['wrapper'] = key; break
                if recs is None: recs = [j]; row['shape'] = 'object'
        if recs is not None:
            row['records'] = len(recs)
            keys = sorted({kk for x in recs if isinstance(x, dict) for kk in x.keys()})
            row['keys'] = keys[:60]
            if keys:
                e = entities.setdefault(ent, {'routes': [], 'records': []})
                e['routes'].append(route)
                if len(e['records']) < limit: e['records'] += recs[:limit - len(e['records'])]
        inventory.append(row)
        log(f'{r.status_code:>4} {ct.split(";")[0]:<24} {route}' + (f'  recs={row.get("records")}' if recs is not None else ''))
        time.sleep(0.25)
    os.makedirs(raw_dir, exist_ok=True)
    for ent, e in entities.items():
        person = bool(PEOPLE.search(ent))
        json.dump(redact(e['records'], person), open(os.path.join(raw_dir, ent + '.json'), 'w'), indent=1)
    return inventory, entities


def build(entities, out):
    os.makedirs(os.path.join(out, 'schemas'), exist_ok=True)
    names = {norm(e): e for e in entities}
    nodes = []; edges = []; unresolved = {}
    for ent, e in sorted(entities.items()):
        person = bool(PEOPLE.search(ent))
        fields = infer(e['records'], person)
        sch = to_schema(fields, len(e['records']))
        sch.update({'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': ent, 'x-routes': e['routes'],
                    'x-sample-size': len(e['records']), 'x-pii-redacted': person})
        json.dump(sch, open(os.path.join(out, 'schemas', ent + '.json'), 'w'), indent=1)
        nodes.append({'id': ent, 'fields': len(fields), 'routes': e['routes'], 'sample': len(e['records'])})
        def walk(fs, owner, path=''):
            for k, f in fs.items():
                m = re.fullmatch(r'(.+?)_ids?', k)
                if m:
                    tgt = names.get(norm(m.group(1))) or names.get(norm(owner + '_' + m.group(1)))
                    if not tgt:  # try last path segment, e.g. to_venue_id -> venue
                        last = m.group(1).split('_')[-1]; tgt = names.get(norm(last))
                    if tgt and tgt != ent: edges.append({'from': ent, 'to': tgt, 'field': path + k, 'kind': 'reference'})
                    elif not tgt: unresolved.setdefault(m.group(1), set()).add(ent)
                if f.child:
                    tgt = names.get(norm(k))
                    edges.append({'from': ent, 'to': tgt or f'{ent}.{k}', 'field': path + k, 'kind': 'composition' + ('' if tgt else ':inline')})
                    walk(f.child, k, path + k + '.')
                if f.items and isinstance(f.items, dict) and '_scalar' not in f.items:
                    tgt = names.get(norm(k))
                    edges.append({'from': ent, 'to': tgt or f'{ent}.{k}', 'field': path + k + '[]', 'kind': 'composition-many' + ('' if tgt else ':inline')})
                    walk(f.items, k, path + k + '[].')
        walk(fields, ent)
    graph = {'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'source': BASE,
             'nodes': nodes, 'edges': edges, 'unresolved_references': {k: sorted(v) for k, v in sorted(unresolved.items())}}
    json.dump(graph, open(os.path.join(out, 'graph.json'), 'w'), indent=1)
    # PlantUML
    L = ['@startuml', 'title Kobas business entities (PSM, extracted ' + graph['generated'][:10] + ')', 'hide empty members', 'skinparam classAttributeIconSize 0']
    for ent, e in sorted(entities.items()):
        sch = json.load(open(os.path.join(out, 'schemas', ent + '.json')))
        L.append(f'class {ent} {{')
        for k, p in list(sch['properties'].items())[:40]:
            t = p['type'] if isinstance(p['type'], str) else '|'.join(p['type'])
            L.append(f'  {k} : {t}' + ('?' if p.get('nullable') else ''))
        if len(sch['properties']) > 40: L.append(f'  .. {len(sch["properties"]) - 40} more ..')
        L.append('}')
    seen = set()
    for ed in edges:
        if ed['to'].startswith(ed['from'] + '.') or (ed['from'], ed['to']) in seen: continue
        seen.add((ed['from'], ed['to']))
        arrow = '-->' if ed['kind'] == 'reference' else ('*--' if 'many' not in ed['kind'] else '*-- "many"')
        L.append(f'{ed["from"]} {arrow} {ed["to"]} : {ed["field"]}')
    L.append('@enduml')
    open(os.path.join(out, 'kobas.puml'), 'w').write('\n'.join(L) + '\n')
    # Mermaid
    M = ['classDiagram']
    for ent in sorted(entities):
        sch = json.load(open(os.path.join(out, 'schemas', ent + '.json')))
        M.append(f'  class {ent} {{')
        for k, p in list(sch['properties'].items())[:25]:
            t = p['type'] if isinstance(p['type'], str) else 'mixed'
            M.append(f'    {t} {k}')
        M.append('  }')
    seen = set()
    for ed in edges:
        if ed['to'].startswith(ed['from'] + '.') or (ed['from'], ed['to']) in seen: continue
        seen.add((ed['from'], ed['to']))
        M.append(f'  {ed["from"]} {"-->" if ed["kind"] == "reference" else "*--"} {ed["to"]} : {ed["field"]}')
    open(os.path.join(out, 'kobas.mmd'), 'w').write('\n'.join(M) + '\n')
    return graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out'); ap.add_argument('--raw', default='/tmp/kobas_raw')
    ap.add_argument('--limit', type=int, default=25); ap.add_argument('--only', default='')
    a = ap.parse_args()
    only = {s.strip() for s in a.only.split(',') if s.strip()}
    k = Kobas()
    if not k.login(): sys.exit(30)
    routes = discover(k)
    log('candidate routes', len(routes))
    inventory, entities = probe(k, routes, a.limit, a.raw, only)
    os.makedirs(a.out, exist_ok=True)
    json.dump({'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'routes': inventory},
              open(os.path.join(a.out, 'inventory.json'), 'w'), indent=1)
    if not entities:
        log('no JSON entity answered'); sys.exit(34)
    graph = build(entities, a.out)
    ok = [r for r in inventory if r.get('records') is not None]
    S = [f'# Kobas extraction {graph["generated"][:16]}Z', '',
         f'- routes probed: {len(inventory)}; answered JSON: {len(ok)}; entities with fields: {len(entities)}',
         f'- reference edges: {sum(1 for e in graph["edges"] if e["kind"] == "reference")}; compositions: {sum(1 for e in graph["edges"] if e["kind"] != "reference")}',
         f'- unresolved `<x>_id` references: {len(graph["unresolved_references"])} ({", ".join(list(graph["unresolved_references"])[:20])})', '',
         '| entity | routes | fields | sample |', '|---|---|---|---|']
    for n in graph['nodes']: S.append(f'| {n["id"]} | {", ".join(n["routes"])} | {n["fields"]} | {n["sample"]} |')
    S += ['', '## Non-JSON or failed routes (first 80)', '']
    for r in inventory:
        if r.get('records') is None: S.append(f'- {r.get("status")} {r["route"]}')
        if len(S) > 400: break
    open(os.path.join(a.out, 'SUMMARY.md'), 'w').write('\n'.join(S) + '\n')
    print(json.dumps({'routes': len(inventory), 'json': len(ok), 'entities': len(entities), 'edges': len(graph['edges'])}))

if __name__ == '__main__':
    main()
