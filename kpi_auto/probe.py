"""KPI sheet automation probe: find the Kobas data routes for labour costs and the cash log."""
import os, re, sys, json, csv, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas()
assert k.login(), 'login failed'
def save(name, txt): open(os.path.join(out, name), 'w').write(txt)
# 1) every report key in the queue
r = k.s.get(BASE + '/data/report-queue', timeout=60)
save('report_queue.json', r.text[:400000])
# 2) pages: grab every /data/ or api-ish url referenced
for name, url in [('labour', '/reports/labour-costs/'), ('reports_list', '/reports/list/'),
                  ('cashlog', '/daily/cashlog/edit/18833'), ('cashlog_list', '/daily/cashlog/'),
                  ('sales_breakdown', '/reporting/sales-breakdown')]:
    try:
        p = k.s.get(BASE + url, timeout=60)
        urls = sorted(set(re.findall(r"""['"](/(?:data|api|reports|daily|reporting)/[^'"\s<>]{2,160})['"]""", p.text)))
        scripts = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text)))
        save(f'page_{name}.txt', f'{p.status_code} {p.url}\n' + '\n'.join(urls) + '\n--scripts\n' + '\n'.join(scripts) + '\n--html\n' + p.text[:60000])
    except Exception as e:
        save(f'page_{name}.txt', 'ERR ' + str(e))
# 3) guessed labour endpoints
for g in ['/data/reports/labour-costs?date=2026-10-12', '/data/reports/labour-costs/history?date=2026-10-12',
          '/data/report-queue?filterBy[report_key][eq]=labour_costs_report', '/data/reports/labour-costs']:
    try:
        p = k.s.get(BASE + g, timeout=60); save('guess_' + re.sub(r'\W+', '_', g) + '.txt', f'{p.status_code}\n' + p.text[:20000])
    except Exception as e: pass
# 4) one item export, M14 one day, eat-in vs delivery
for mode in ['', 'eat-in', 'delivery', 'takeaway']:
    d = [('venueIds[]', '37'), ('from', '2026-10-01'), ('to', '2026-10-01'), ('piscMode', ''), ('filterByTill', 'false'),
         ('seatingArea', ''), ('consumptionMode', mode)]
    p = k.s.post(BASE + '/data/reports/item-by-sales/export', data=d, timeout=120,
                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    save(f'items_M14_20261001_{mode or "all"}.csv', f'{p.status_code}\n' + p.text)
print('done')
