"""Probe 11: stock usage comparison inline scripts (how the stock-check pickers are filled and the report is requested)."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
p = k.s.get(BASE + '/reports/index.php', params={'m': 'CORE_Reports_UsageComparison'}, timeout=90)
sc = [s for s in re.findall(r'<script[^>]*>(.*?)</script>', p.text, re.S) if re.search(r'StockCheck|viewReport|opening', s)]
open(os.path.join(out, 'uc_inline.txt'), 'w').write('\n\n=====\n'.join(sc))
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))):
    if 'vendor' in s: continue
    url = ('https:' + s) if s.startswith('//') else BASE + s
    t = k.s.get(url, timeout=60).text
    if re.search(r'getStockCheck|viewReport', t): open(os.path.join(out, 'uc_js_' + re.sub(r'\W+', '_', s.split('/')[-1])[:60] + '.txt'), 'w').write(t)
print('ok')
