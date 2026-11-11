"""Probe 4: full html of the reports list page plus every non-vendor script it loads, saved raw."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
p = k.s.get(BASE + '/reports/list/', timeout=60); open(f'{out}/reports_list.html', 'w').write(p.text)
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
    if 'vendor' in s: continue
    url = ('https:' + s) if s.startswith('//') else BASE + s
    t = k.s.get(url, timeout=60).text
    open(f'{out}/js_' + re.sub(r'\W+', '_', s.split('/')[-1])[:80] + '.js', 'w').write(t)
for u in ['/reports/list/data', '/reports/list/?format=json', '/data/reports/list/all', '/data/reports-list']:
    r = k.s.get(BASE + u, timeout=60); open(f'{out}/try_' + re.sub(r'\W+', '_', u) + '.txt', 'w').write(f'{r.status_code}\n{r.text[:20000]}')
print('ok')
