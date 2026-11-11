"""Probe 13: Stock Usage Comparison CSV export for M1, M3, M9, w/c 02/11 (stock take 31/10 or 01/11 -> 07/11 or 08/11)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
for site, vid, a, b in [('M1', 3, '2026-10-31', '2026-11-07'), ('M3', 5, '2026-11-01', '2026-11-08'), ('M9', 2, '2026-10-31', '2026-11-07'),
                        ('M1prev', 3, '2026-10-24', '2026-10-31')]:
    r = k.s.get(BASE + '/reports/csv-gen/usagecomparison.php', params={'venue_id': vid, 'from': a + ' 23:59:59', 'to': b + ' 23:59:59'}, timeout=300)
    open(os.path.join(out, f'{site}_uc.csv'), 'w').write(f'{r.status_code} {r.headers.get("content-type","")}\n' + r.text)
    p = k.s.post(BASE + '/reports/index.php', data={'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venue_id': vid, 'venueid': vid,
                 'opening_years': a[:4], 'opening_days': a + ' 23:59:59', 'closing_years': b[:4], 'closing_days': b + ' 23:59:59'}, timeout=300)
    open(os.path.join(out, f'{site}_uc_view.html'), 'w').write(p.text)
print('ok')
