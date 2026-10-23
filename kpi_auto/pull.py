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
# ---- route discovery v3 (23/10): cash log JSON, labour report export. Text dumps go to the Probe tab ----
def chunk(t, n=400): return '\n'.join(t[i:i + n] for i in range(0, len(t), n))
def grab(name, path, n=60000):
    try:
        p = k.s.get(path if path.startswith('http') else BASE + path, timeout=90)
        save(f'probe_{name}.txt', f'{p.status_code} {p.url} {p.headers.get("content-type","")}\n' + chunk(p.text[:n]))
        return p
    except Exception as e:
        save(f'probe_{name}.txt', 'ERR ' + str(e)); return None
cl = k.s.get(BASE + '/daily/cashlog/edit/18270', timeout=90).text
save('probe_cashlog_fields.txt', '\n'.join(sorted(set(re.findall(r'cashlog\.data\[date\][\w\.\[\]\'+ ]{0,80}', cl)))) + '\n--\n' +
     '\n'.join(sorted(set(re.findall(r'(?:ng-init|data-[\w-]+)="[^"]{0,300}"', cl)))))
for u in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', cl))):
    if re.search(r'cash|report|daily', u):
        grab('js_' + re.sub(r'\W+', '_', u.rsplit('/', 1)[-1])[:40], ('https:' + u) if u.startswith('//') else u, 30000)
for name, path in [('hist1', '/data/cashlog/historical/'), ('hist2', '/data/cashlog/historical/18270'),
                   ('hist3', '/data/cashlog/historical/?venue_id=3&date=2026-09-28'), ('hist4', '/data/cashlog/historical/3/2026-09-28'),
                   ('hist5', '/data/cashlog/historical/?venueId=3&from=2026-09-28&to=2026-09-28'), ('hist6', '/data/cashlog/18270/historical')]:
    grab(name, path, 20000)
# labour costs report: existing generated reports per Monday, export the newest that covers every venue
try:
    q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'labour_costs_report'}, timeout=60).json()
    save('probe_labour_queue.txt', chunk(json.dumps([{kk: x.get(kk) for kk in ('id', 'filters', 'generated', 'generation_end', 'staff_name')} for x in q])[:30000]))
    best = {}
    for x in q:
        dt = (x.get('filters') or {}).get('date')
        if x.get('generated') and dt and (dt not in best or len(x['filters'].get('venue_ids', [])) >= len(best[dt]['filters'].get('venue_ids', []))): best[dt] = x
    for dt, x in sorted(best.items())[-6:]:
        for suf in ('/export', ''):
            grab(f'labour_{dt}{suf.replace("/", "_")}', f'/data/reports/labour-costs/{x["id"]}{suf}', 60000)
except Exception as e: save('probe_labour_queue.txt', 'ERR ' + str(e))
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
