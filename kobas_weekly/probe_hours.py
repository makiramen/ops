"""Probe (13/11/2026, Michael x Remy): find the Kobas report that gives hours worked by department (FOH / BOH),
for FOH and BOH cost per labour hour on the Site CC. Dumps menu links, report keys and column headers ONLY.
No row data, no staff names: the repo is public."""
import os, re, sys, json, html
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas()
if not k.login(): json.dump({'error': 'LOGIN FAILED'}, open(os.path.join(out, 'hours_probe.json'), 'w')); sys.exit(30)
R = {'pages': {}, 'paths': [], 'report_keys': [], 'titles': {}, 'scripts': []}
P = set(); KEYS = set()
ROUTE = re.compile(r'["\'`(=]\s*(/?(?:data|reports?|staff|rotas?|teams?|admin|timesheets?|payroll|hr)/[A-Za-z_\-/.]{2,90})')
def scan(t):
    for m in re.finditer(r'href="([^"#?]+)', t):
        h = html.unescape(m.group(1))
        if not re.search(r'\d', h) and not h.startswith('http'): P.add(h)
    for m in ROUTE.finditer(t):
        if not re.search(r'\d', m.group(1)): P.add(m.group(1))
    for m in re.finditer(r'["\']([a-z]+(?:_[a-z]+)+_report)["\']', t): KEYS.add(m.group(1))
    for m in re.finditer(r'report_key["\']?\s*[:=\]]+\s*["\']([a-z_]+)["\']', t): KEYS.add(m.group(1))
def page(path):
    try:
        r = k.s.get(BASE + path, timeout=90); t = r.text
        ti = re.search(r'<title>(.*?)</title>', t, re.S)
        R['pages'][path] = [r.status_code, len(t)]; R['titles'][path] = (ti.group(1).strip()[:80] if ti else None)
        if r.status_code == 200: scan(t)
        return t if r.status_code == 200 else ''
    except Exception as e: R['pages'][path] = ['ERR', repr(e)[:150]]; return ''
home = page('/'); lc = page('/reports/labour-costs/'); page('/rotas/'); page('/rota/manage/'); page('/staff/')
for p in ['/reports/hours-worked/', '/reports/staff-hours/', '/reports/timesheets/', '/reports/rota-vs-actual/', '/reports/labour/', '/reports/wages/',
          '/reports/staff-hours-worked/', '/reports/hours/', '/reports/payroll/', '/reports/shift-hours/', '/staff/hours/', '/staff/timesheets/',
          '/staff/hours-worked/', '/staff/reports/', '/rotas/reports/', '/reports/labour-hours/', '/reports/clock-ins/', '/reports/attendance/',
          '/reports/labour-costs-by-role/', '/reports/labour-by-department/', '/payroll/', '/hr/', '/teams/']: page(p)
srcs = set()
for t in (home, lc):
    srcs |= set(re.findall(r'<script[^>]+src="([^"]+)"', t))
for s in sorted(srcs)[:40]:
    try:
        u = s if s.startswith('http') else BASE + (s if s.startswith('/') else '/' + s)
        if 'kobas' not in u: continue
        t = k.s.get(u, timeout=90).text; R['scripts'].append([s.split('?')[0][-70:], len(t)]); scan(t)
    except Exception as e: R['scripts'].append([s[-70:], repr(e)[:80]])
# the labour costs page: which column / filter names does it know (headers only)
R['labour_page_words'] = sorted(set(re.findall(r'(?:of which [A-Z][A-Za-z ]+|Hours Worked[A-Za-z ()\.]*|by (?:role|department|category)[a-z ]*)', lc)))[:40]
R['paths'] = sorted(P)
R['report_keys'] = sorted(KEYS)
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1)
print(json.dumps({'pages': R['pages'], 'n_paths': len(R['paths']), 'keys': R['report_keys']}))
