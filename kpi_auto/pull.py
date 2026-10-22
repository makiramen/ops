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
