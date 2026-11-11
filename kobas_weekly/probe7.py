"""Probe 7: Operational Profitability report route (the Kobas food cost / GP view) and the stock transfer route."""
import os, re, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
for pg in ['/reports/operational-profitability', '/reports/stock-transfers', '/reports/supplier-stock-deliveries']:
    p = k.s.get(BASE + pg, timeout=60)
    keep = []
    for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
        if 'vendor' in s or 'staff-details' in s or 'common' in s: continue
        url = ('https:' + s) if s.startswith('//') else BASE + s
        t = k.s.get(url, timeout=60).text
        if re.search(r'profitab|transfer|deliver', t, re.I): keep.append(f'##### {s}\n{t}')
    save('pg_' + re.sub(r'\W+', '_', pg) + '.txt', f'{p.status_code}\n' + '\n'.join(re.findall(r'ng-[a-z-]+="[^"]{0,200}"', p.text)) + '\n\n' + '\n'.join(keep))
# newest generated op-prof report ids, and try both json routes on them
q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'operational_profitability_report', 'limit': 20}, timeout=60).json()
save('opprof_queue.json', json.dumps(q, indent=0))
rid = [x for x in q if x.get('generated')][0]['id']
for path in [f'/data/reports/operational-profitability?id={rid}', f'/data/reports/operational-profitability/{rid}/json', f'/data/report-queue/{rid}',
             f'/data/report-queue/{rid}/download', f'/data/report-queue/{rid}/export', f'/data/reports/operational_profitability/{rid}']:
    r = k.s.get(BASE + path, timeout=90); save('try_' + re.sub(r'\W+', '_', path) + '.txt', f'{r.status_code} {r.headers.get("content-type","")}\n' + r.text[:40000])
for path in ['/data/v2/stock/order?limit=5&filterBy[type][eq]=transfer&orderBy[id]=DESC', '/data/v2/stock/transfer/?limit=3', '/data/v2/stock/order?limit=3&orderBy[id]=DESC']:
    r = k.s.get(BASE + path, timeout=90); save('try_' + re.sub(r'\W+', '_', path)[:90] + '.txt', f'{r.status_code}\n' + r.text[:8000])
print('ok')
