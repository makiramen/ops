"""Probe 12: run Stock Usage Comparison for M1, M3, M9 between the last two stock takes; save the page constants."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
for site, vid in [('M1', 3), ('M3', 5), ('M9', 2)]:
    r = k.s.get(BASE + '/ajax/stock_check', params={'status': 'completed', 'type': 'stock', 'venue_id': vid}, timeout=60)
    open(os.path.join(out, f'{site}_ajax.txt'), 'w').write(r.text[:3000])
    j = k.s.get(BASE + '/data/v2/stock/check', params={'limit': 50, 'orderBy[log_date]': 'DESC', 'filterBy[venue_id][eq]': vid, 'filterBy[type][eq]': 'stock'}, timeout=60).json()
    days = sorted({x['log_date'] for x in j if x.get('status') == 'completed'})
    open(os.path.join(out, f'{site}_checks.json'), 'w').write(json.dumps(days[-12:]))
    want = [d for d in days if d[:10] in ('2026-10-31', '2026-11-01', '2026-11-07', '2026-11-08')]
    op = [d for d in want if d[:10] <= '2026-11-01']; cl = [d for d in want if d[:10] >= '2026-11-07']
    if not (op and cl): open(os.path.join(out, f'{site}_skip.txt'), 'w').write(json.dumps(days[-8:])); continue
    data = {'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venueid': str(vid), 'opening_years': op[-1][:4],
            'opening_days': op[-1], 'closing_years': cl[-1][:4], 'closing_days': cl[-1]}
    p = k.s.post(BASE + '/reports/index.php', data=data, headers={'X-Requested-With': None}, timeout=300)
    open(os.path.join(out, f'{site}_uc.html'), 'w').write(f'{p.status_code} {json.dumps(data)}\n' + p.text)
print('ok')
# how the View Report button submits
p = k.s.get(BASE + '/reports/index.php', params={'m': 'CORE_Reports_UsageComparison'}, timeout=90)
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
    if 'admin-' not in s: continue
    t = k.s.get(('https:' + s) if s.startswith('//') else BASE + s, timeout=60).text
    snips = [t[max(0, m.start() - 600):m.start() + 900] for m in re.finditer(r'view_report|stockusagecomparisonform|createOptionListDays', t)]
    open(os.path.join(out, 'view_report_js.txt'), 'w').write('\n\n=====\n'.join(snips))
inl = [s for s in re.findall(r'<script[^>]*>(.*?)</script>', p.text, re.S) if 'view_report' in s or 'stockusagecomparisonform' in s]
open(os.path.join(out, 'view_report_inline.txt'), 'w').write('\n\n=====\n'.join(inl))
# GET variant for M1
data = {'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venueid': '3', 'opening_years': '2026',
        'opening_days': '2026-10-31 23:59:59', 'closing_years': '2026', 'closing_days': '2026-11-07 23:59:59'}
g = k.s.get(BASE + '/reports/index.php', params=data, timeout=300)
open(os.path.join(out, 'M1_uc_get.html'), 'w').write(f'{g.status_code} {len(g.text)}\n' + g.text)
