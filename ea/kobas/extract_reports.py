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
    runs = []; off = 0
    while True:
        try:
            r = k.s.get(BASE + '/data/report-queue', params={'limit': 200, 'offset': off}, timeout=90)
            page = r.json()
        except Exception as e: log('report-queue', off, e); break
        if isinstance(page, dict): page = page.get('data') or page.get('results') or []
        if not isinstance(page, list): log('report-queue shape', type(page).__name__, str(page)[:200]); break
        runs += page
        if len(page) < 200 or off > 20000: break
        off += 200
    if not runs:
        try:
            r = k.s.get(BASE + '/data/report-queue', timeout=90); j = r.json()
            runs = j if isinstance(j, list) else (j.get('data') or [])
            log('report-queue unpaged', r.status_code, len(runs))
        except Exception as e: log('report-queue unpaged', e)
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
           'keys': {kk: {'runs': v['runs'], 'filters': sorted(v['filters']), 'latest': v['latest']} for kk, v in sorted(keys.items())},
           'catalogue': catalogue}
    os.makedirs(a.out, exist_ok=True); os.makedirs(a.raw, exist_ok=True)
    json.dump(inv, open(os.path.join(a.out, 'reports_inventory.json'), 'w'), indent=1)
    log('report keys', len(keys), 'catalogue', len(catalogue))
    # 2. export the latest run of each key
    entities = {}
    for key, K in sorted(keys.items()):
        if only and not any(o in key for o in only): continue
        if not K['latest']: continue
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
