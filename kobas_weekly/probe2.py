"""Probe 2: the nav menu (all module links), the reports list JSON, and the operational profitability report shape."""
import os, re, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
def links(html):
    a = re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S)
    return sorted({(h, re.sub(r'<[^>]+>|\s+', ' ', t).strip()[:90]) for h, t in a})
for n, u in [('root', '/'), ('index', '/index.php'), ('reports_list', '/reports/list/')]:
    p = k.s.get(BASE + u, timeout=60)
    save(f'nav_{n}.txt', f'{p.status_code} {p.url}\n' + '\n'.join(f'{h} | {t}' for h, t in links(p.text)) +
         '\n--scripts\n' + '\n'.join(sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text)))) +
         '\n--inline-urls\n' + '\n'.join(sorted(set(re.findall(r"""['"](/[a-z][^'"\s<>]{2,160})['"]""", p.text)))))
res = []
for u in ['/data/reports', '/data/reports/list', '/data/report/list', '/data/report', '/data/reports/menu', '/data/report-list', '/data/reports/available',
          '/data/menu', '/data/navigation', '/data/user/menu', '/data/reports/favourites']:
    try:
        r = k.s.get(BASE + u, timeout=60); res.append(f'## {u} {r.status_code} {r.headers.get("content-type","")}\n{r.text[:6000]}')
    except Exception as e: res.append(f'## {u} ERR {e}')
save('reports_json.txt', '\n\n'.join(res))
# operational profitability: export the newest generated one (Mia's, venue 61 2026)
try:
    q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'operational_profitability_report', 'limit': 5}, timeout=60).json()
    save('opprof_queue.txt', json.dumps(q, indent=1)[:5000])
    rid = [x for x in q if x.get('generated')][0]['id']
    for path in (f'/data/reports/operational-profitability/{rid}', f'/data/reports/operational-profitability/{rid}/export'):
        r = k.s.get(BASE + path, timeout=120); save('opprof_' + path.rsplit('/', 1)[-1] + '.txt', f'{r.status_code} {r.headers.get("content-type","")}\n' + r.text[:60000])
except Exception as e: save('opprof_err.txt', repr(e))
print('done')
