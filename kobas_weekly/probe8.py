"""Probe 8: Operational Profitability view html (existing + fresh for M1 and M9, 2026) and stock transfer totals."""
import os, re, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
p = k.s.get(BASE + '/reports/operational-profitability/28376', timeout=120); save('opprof_view_28376.html', f'{p.status_code} {p.url}\n' + p.text)
ids = {}
for site, vid in [('M1', 3), ('M9', 2)]:
    r = k.s.post(BASE + '/data/report-queue', data=[('reportQueue[report_key]', 'operational_profitability_report'), ('reportQueue[filters][venue_id]', str(vid)), ('reportQueue[filters][year]', '2026')], timeout=60)
    save(f'opprof_queue_{site}.txt', f'{r.status_code} {r.text[:1500]}')
    if r.status_code == 201: ids[site] = r.json()['id']
t0 = time.time(); done = set()
while ids and len(done) < len(ids) and time.time() - t0 < 1200:
    time.sleep(30)
    q = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': 'operational_profitability_report', 'limit': 20}, timeout=60).json()
    for x in q:
        for s, i in ids.items():
            if x['id'] == i and x.get('generated'): done.add(s)
for s, i in ids.items():
    p = k.s.get(BASE + f'/reports/operational-profitability/{i}', timeout=180); save(f'opprof_view_{s}.html', f'{p.status_code} {s in done} {int(time.time()-t0)}s\n' + p.text)
r = k.s.get(BASE + '/data/reports/stock/transfer/totals', params=[('venueIds[]', v) for v in ('3', '2', '11', '5')] + [('from', '2026-10-26'), ('to', '2026-11-01')], timeout=90)
save('transfer_totals.txt', f'{r.status_code}\n{r.text[:20000]}')
print('ok', ids, done)
