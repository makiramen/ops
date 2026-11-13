"""Probe (13/11/2026, Michael x Remy): how Kobas exposes hours worked by department (FOH / BOH).
Dumps code snippets around the rota / hours routes and the SHAPE of the rota data (keys, types, role and category
names). No staff names, no pay, no row values: the repo is public."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas()
if not k.login(): json.dump({'error': 'LOGIN FAILED'}, open(os.path.join(out, 'hours_probe.json'), 'w')); sys.exit(30)
R = {'snips': {}, 'shapes': {}, 'status': {}}
OKV = re.compile(r'role|categor|depart|type|status|approved|is_|has_', re.I)
def shape(o, key='', d=0):
    if d > 7: return '...'
    if isinstance(o, dict):
        ks = list(o)
        if len(ks) > 12 and all(re.fullmatch(r'[\d\-: ]+', str(x)) for x in ks[:12]): return {'<id or date> x%d' % len(ks): shape(o[ks[0]], '', d + 1)}
        return {x: shape(v, x, d + 1) for x, v in list(o.items())[:60]}
    if isinstance(o, list): return ['x%d' % len(o), shape(o[0], key, d + 1)] if o else []
    if isinstance(o, (int, float)) or o is None or isinstance(o, bool): return type(o).__name__
    return ('str:' + str(o)[:40]) if (OKV.search(key) and 'name' not in key.lower() or key in ('role_name', 'category', 'category_name', 'department')) else 'str'
def get(path, params=None, label=None):
    lab = label or path
    try:
        r = k.s.get(BASE + path, params=params, timeout=120, headers={'Accept': 'application/json'})
        R['status'][lab] = [r.status_code, len(r.text), r.headers.get('content-type', '')[:30]]
        if r.status_code != 200: return None
        try: j = r.json()
        except Exception:
            t = r.text; R['shapes'][lab] = {'html_words': sorted(set(re.findall(r'(?:Front of House|Back of House|Management|Uncategorised|Hours Worked|Paid Hours|Approved|Department|Role)', t)))}
            return t
        R['shapes'][lab] = shape(j); return j
    except Exception as e: R['status'][lab] = ['ERR', repr(e)[:150]]; return None
home = k.s.get(BASE + '/rotas/', timeout=90).text
for s in set(re.findall(r'<script[^>]+src="([^"]+)"', home + k.s.get(BASE + '/reports/labour-costs/', timeout=90).text + k.s.get(BASE + '/', timeout=90).text)):
    if not re.search(r'core/rotas|core/daily|core/staff|labour-costs|angular/staff-|angular/week', s): continue
    t = k.s.get('https:' + s if s.startswith('//') else s, timeout=90).text
    for w in ['gethoursworkedinfo.php', 'getrotapaidshifts.php', '/data/rota/', '/data/rota/past', 'hours-approved', 'getrotadetails.php', 'getrotainfo.php', 'getroles.php', '/ajax/rota_staff', 'getbackpayshifts.php', '/data/week/', '/data/staff/pay-details/']:
        for m in list(re.finditer(re.escape(w), t))[:3]:
            R['snips'].setdefault(w, []).append(t[max(0, m.start() - 260):m.end() + 260])
VID = 9  # M7 St James Quarter
get('/data/rota/past', {'venue_id': VID, 'limit': 3}, 'rota/past venue_id')
get('/data/rota/past', None, 'rota/past')
get('/data/rota/', {'venue_id': VID}, 'rota venue_id')
get('/data/week/last', None, 'week/last'); get('/data/week/till-now', None, 'week/till-now')
get('/rotas/getroles.php', None, 'getroles'); get('/rotas/gethoursworkedinfo.php', {'venue_id': VID}, 'gethoursworkedinfo')
get('/rotas/getrotapaidshifts.php', {'venue_id': VID}, 'getrotapaidshifts'); get('/rotas/getrotainfo.php', {'venue_id': VID}, 'getrotainfo')
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1)
print(json.dumps(R['status']))
