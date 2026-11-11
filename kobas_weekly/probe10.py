"""Probe 10: the stock usage comparison page JS."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
for u in ['/assets/js/pages/reports/stock-usage-comparison.js', 'https://d2grh73qm0bzjk.cloudfront.net/js/core/reports-de40b6f8d358e55be.js']:
    r = k.s.get(u if u.startswith('http') else BASE + u, timeout=60)
    open(os.path.join(out, re.sub(r'\W+', '_', u.split('/')[-1]) + '.txt'), 'w').write(f'{r.status_code}\n{r.text}')
print('ok')
