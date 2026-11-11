"""Probe 3: read the reports-list JS bundle (report names + links) and grep every bundle for stock-take / variance / GP routes."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
srcs = set()
for u in ['/reports/list/', '/', '/reports/labour-costs/', '/reports/stock-usage/', '/reports/stock-current-position/']:
    try:
        p = k.s.get(BASE + u, timeout=60)
        srcs |= set(re.findall(r'<script[^>]+src="([^"]+)"', p.text))
    except Exception: pass
hits, names = [], []
for s in sorted(srcs):
    if 'vendor' in s: continue
    url = ('https:' + s) if s.startswith('//') else (BASE + s if s.startswith('/') else s)
    try: t = k.s.get(url, timeout=60).text
    except Exception as e: hits.append(f'## {s} ERR {e}'); continue
    found = sorted(set(re.findall(r"""['"](/(?:data|reports|reporting|stock)[^'"\s]{2,140})['"]""", t)))
    keys = sorted(set(re.findall(r"""['"]([a-z_]{4,60}_report)['"]""", t)))
    hits.append(f'## {s} len={len(t)}\nkeys={keys}\n' + '\n'.join(found))
    for m in re.finditer(r'name\s*:\s*["\']([^"\']{3,80})["\']\s*,[^{}]{0,300}?link\s*:\s*["\']([^"\']{2,140})["\']', t):
        names.append(f'{m.group(2)} | {m.group(1)}')
    for m in re.finditer(r'link\s*:\s*["\']([^"\']{2,140})["\']\s*,[^{}]{0,300}?name\s*:\s*["\']([^"\']{3,80})["\']', t):
        names.append(f'{m.group(1)} | {m.group(2)}')
save('bundles.txt', '\n\n'.join(hits)); save('report_names.txt', '\n'.join(sorted(set(names))) or 'none')
print('done', len(srcs))
