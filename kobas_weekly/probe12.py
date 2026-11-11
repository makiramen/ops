"""Probe 12: run Stock Usage Comparison for M1, M3, M9 between the last two stock takes; save the page constants."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
for site, vid in [('M1', 3), ('M3', 5), ('M9', 2)]:
    r = k.s.get(BASE + '/ajax/stock_check', params={'status': 'completed', 'type': 'stock', 'venue_id': vid}, timeout=60)
    days = sorted({x['log_date'] for x in r.json() if str(x.get('venue_id')) == str(vid)})
    open(os.path.join(out, f'{site}_checks.json'), 'w').write(json.dumps(days[-12:]))
    want = [d for d in days if d[:10] in ('2026-10-31', '2026-11-01', '2026-11-07', '2026-11-08')]
    op = [d for d in want if d[:10] <= '2026-11-01']; cl = [d for d in want if d[:10] >= '2026-11-07']
    if not (op and cl): open(os.path.join(out, f'{site}_skip.txt'), 'w').write(json.dumps(days[-8:])); continue
    data = {'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venueid': str(vid), 'opening_years': op[-1][:4],
            'opening_days': op[-1], 'closing_years': cl[-1][:4], 'closing_days': cl[-1]}
    p = k.s.post(BASE + '/reports/index.php', data=data, headers={'X-Requested-With': None}, timeout=300)
    open(os.path.join(out, f'{site}_uc.html'), 'w').write(f'{p.status_code} {json.dumps(data)}\n' + p.text)
print('ok')
