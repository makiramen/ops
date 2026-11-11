"""Probe 5: the system report list (/data/report/system) and the Stock Checks module routes."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
r = k.s.get(BASE + '/data/report/system', timeout=60); save('report_system.json', r.text)
for n, u in [('checks', '/operations/checks'), ('checks2', '/operations/checks/')]:
    p = k.s.get(BASE + u, timeout=60)
    save(f'page_{n}.html', f'{p.status_code} {p.url}\n' + p.text)
    for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
        if 'vendor' in s or 'staff-details' in s: continue
        url = ('https:' + s) if s.startswith('//') else BASE + s
        t = k.s.get(url, timeout=60).text
        if re.search(r'check|stock', t, re.I): save('js_' + re.sub(r'\W+', '_', s.split('/')[-1])[:80] + '.js', t)
print('ok')
