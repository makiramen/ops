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
SAFE = re.compile(r'hours|worked|approv|view|edit|export|rota|report|paid|cost|labour|role|csv|print|summary', re.I)
def links(t, lab):
    o = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        h = re.sub(r'\d+', 'N', m.group(1).replace('&amp;', '&')); tx = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(2))).strip()
        if 'rota' in h.lower() or SAFE.search(tx): o[h[:120]] = tx[:40] if SAFE.search(tx) and not re.search(r'\d', tx) else ''
    for m in re.finditer(r'<(?:select|input)[^>]+name="([^"]+)"', t): o['FIELD ' + m.group(1)] = ''
    for m in re.finditer(r'<form[^>]+action="([^"]*)"', t): o['FORM ' + re.sub(r'\d+', 'N', m.group(1))[:100]] = ''
    R['shapes'][lab] = o
def heads(t, lab):
    R['shapes'][lab + ' heads'] = {'th': sorted(set(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x)).strip()[:40] for x in re.findall(r'<th[^>]*>(.*?)</th>', t, re.S)))[:80],
        'words': sorted(set(re.findall(r'Front of House|Back of House|Management|Uncategorised|Hours Worked|Paid Hours|Approved|Department|Kitchen|FOH|BOH', t))),
        'role_options': sorted(set(re.sub(r'\s+', ' ', x).strip()[:40] for sel in re.findall(r'<select[^>]+(?:name|id)="[^"]*role[^"]*"[^>]*>(.*?)</select>', t, re.S | re.I) for x in re.findall(r'<option[^>]*>([^<]*)', sel)))[:80],
        'len': len(t)}
past = k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()
mine = sorted([x for x in past if x.get('venueid') == 9], key=lambda x: x['rotadate'])[-3:]
R['shapes']['past M7'] = [{kk: x[kk] for kk in ('id', 'rotadate', 'status')} for x in mine]
rid = mine[-2]['id'] if len(mine) > 1 else mine[-1]['id']
t = k.s.get(BASE + '/rotas/', timeout=120).text; links(t, 'rotas'); heads(t, 'rotas')
t = k.s.get(BASE + '/rotas/index.php', params={'filtervenueid': 9}, timeout=120).text; links(t, 'rotas venue')
for lab, params in [('m=view', {'m': 'view', 'rotaid': rid}), ('m=hours', {'m': 'hours', 'rotaid': rid}), ('m=hoursworked', {'m': 'hoursworked', 'rotaid': rid}), ('id', {'id': rid}), ('rotaid', {'rotaid': rid}), ('m=edit', {'m': 'edit', 'rotaid': rid})]:
    r = k.s.get(BASE + '/rotas/index.php', params=params, timeout=120); R['status']['rotas ' + lab] = [r.status_code, len(r.text)]
    if r.status_code == 200: heads(r.text, 'rotas ' + lab)
r = k.s.get(BASE + '/rotas/gethoursworkedinfo.php', params={'venueid': 9, 'rotaid': rid, 'staffid': 0}, timeout=60); R['status']['hwinfo'] = [r.status_code, len(r.text)]
r = k.s.get(BASE + '/data/rota/%s' % rid, timeout=60, headers={'Accept': 'application/json'}); R['status']['data/rota/id'] = [r.status_code, len(r.text)]
if r.status_code == 200:
    try: R['shapes']['data/rota/id'] = shape(r.json())
    except Exception: pass
r = k.s.get(BASE + '/data/reports/labour-costs/', timeout=60); R['status']['lc list'] = [r.status_code, len(r.text)]
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1)
print(json.dumps(R['status']))
