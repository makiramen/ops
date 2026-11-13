"""Probe (13/11/2026, Michael x Remy): find the Kobas report that gives hours worked by department (FOH / BOH),
for FOH and BOH cost per labour hour on the Site CC. Dumps menu links, report keys and column headers ONLY.
No row data, no staff names: the repo is public."""
import os, re, sys, json, html
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas()
if not k.login(): json.dump({'error': 'LOGIN FAILED'}, open(os.path.join(out, 'hours_probe.json'), 'w')); sys.exit(30)
R = {'pages': {}, 'links': {}, 'report_keys': [], 'js': {}}
WANT = re.compile(r'report|staff|rota|timesheet|hours|labour|team|shift|payroll|wage', re.I)
def page(path):
    try:
        r = k.s.get(BASE + path, timeout=90); t = r.text
        R['pages'][path] = [r.status_code, len(t)]
        for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', t, re.S):
            h, lab = html.unescape(m.group(1)), re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(2))).strip()[:80]
            if WANT.search(h) or WANT.search(lab): R['links'][h.split('?')[0]] = lab
        for m in re.finditer(r'["\']([a-z]+(?:_[a-z]+)+_report)["\']', t): R['report_keys'].append(m.group(1))
        return t
    except Exception as e: R['pages'][path] = ['ERR', repr(e)[:150]]; return ''
home = page('/')
for p in ['/reports/', '/reports/labour-costs/', '/staff/', '/rotas/', '/admin/', '/reports/index.php']: page(p)
for p in sorted(R['links'])[:60]:
    if p.startswith('/') and p not in R['pages'] and re.search(r'report|hours|timesheet|rota|labour', p, re.I): page(p)
# script bundles: report keys and data routes that mention hours / shifts / staff
srcs = set(re.findall(r'<script[^>]+src="([^"]+)"', home))
for s in list(srcs)[:25]:
    try:
        u = s if s.startswith('http') else BASE + s
        t = k.s.get(u, timeout=90).text
        keys = sorted(set(re.findall(r'["\']([a-z]+(?:_[a-z]+)+_report)["\']', t)))
        routes = sorted(set(x for x in re.findall(r'["\'`](/(?:data|reports|staff|rotas)/[A-Za-z0-9_\-/:{}$.]{3,80})["\'`]', t) if WANT.search(x)))
        if keys or routes: R['js'][s.split('?')[0][-80:]] = {'report_keys': keys, 'routes': routes[:150]}
    except Exception as e: R['js'][s[-80:]] = {'err': repr(e)[:100]}
R['report_keys'] = sorted(set(R['report_keys']))
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1)
print(json.dumps({'pages': R['pages'], 'n_links': len(R['links']), 'keys': R['report_keys']}))
