"""Probe 14: admin js in full, then Stock Usage Comparison variants until the page names the venue."""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
p = k.s.get(BASE + '/reports/index.php', params={'m': 'CORE_Reports_UsageComparison'}, timeout=90)
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
    if 'admin-' in s: open(os.path.join(out, 'admin.js'), 'w').write(k.s.get(('https:' + s) if s.startswith('//') else BASE + s, timeout=60).text)
open(os.path.join(out, 'form_section.html'), 'w').write(p.text[p.text.find('stockusagecomparisonform') - 3000: p.text.find('stockusagecomparisonform') + 6000])
ts = lambda d: str(int(datetime.datetime.fromisoformat(d).timestamp() * 1000))
res = []
for name, a, b in [('date', '2026-10-31', '2026-11-07'), ('datetime', '2026-10-31 23:59:59', '2026-11-07 23:59:59'),
                   ('ms', ts('2026-10-31T23:59:59'), ts('2026-11-07T23:59:59')), ('s', ts('2026-10-31T23:59:59')[:-3], ts('2026-11-07T23:59:59')[:-3])]:
    for method in ('post', 'get'):
        data = {'m': 'CORE_Reports_UsageComparison', 'v': '1', 'category': '', 'venueid': '3', 'opening_years': '2026', 'opening_days': a,
                'closing_years': '2026', 'closing_days': b}
        r = (k.s.post(BASE + '/reports/index.php', data=data, timeout=300) if method == 'post' else k.s.get(BASE + '/reports/index.php', params=data, timeout=300))
        h = re.search(r'Viewing report for[^<]*', r.text); tdl = re.search(r"table_data', (.{0,80})", r.text)
        res.append(f'{name} {method} {r.status_code} len={len(r.text)} | {h.group(0) if h else None} | {tdl.group(1) if tdl else None}')
        if tdl and not tdl.group(1).startswith('[]'):
            open(os.path.join(out, f'uc_{name}_{method}.html'), 'w').write(r.text)
open(os.path.join(out, 'variants.txt'), 'w').write('\n'.join(res))
print('\n'.join(res))
