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
# NO link text, NO free text: headers, department / view options, and masked cells only (letters -> a, digits -> 9)
past = k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()
mine = sorted([x for x in past if x.get('venueid') == 9], key=lambda x: x['rotadate'])[-3:]
rid = mine[-2]['id'] if len(mine) > 1 else mine[-1]['id']; R['shapes']['rota'] = {kk: mine[-2][kk] for kk in ('id', 'rotadate', 'status')}
mask = lambda v: re.sub(r'[A-Za-z]', 'a', re.sub(r'\d', '9', v))
txt = lambda h: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h)).strip()
LAB = re.compile(r'^(total|totals|front of house|back of house|foh|boh|management|uncategorised|department|kitchen|hours|all)\b', re.I)
for lab, params in [('fullhours', {'m': 'fullhours', 'iRotaID': rid, 'venueid': 9}), ('fullhours FOH', {'m': 'fullhours', 'iRotaID': rid, 'venueid': 9, 'department': 'FOH'}),
                    ('print ALL', {'m': 'print', 'iRotaID': rid, 'venueid': 9, 'department': 'ALL'})]:
    r = k.s.get(BASE + '/rotas/index.php', params=params, timeout=180); R['status'][lab] = [r.status_code, len(r.text)]
    if r.status_code != 200: continue
    x = r.text; o = {}
    o['th'] = sorted(set(txt(y)[:40] for y in re.findall(r'<th[^>]*>(.*?)</th>', x, re.S) if not re.search(r'[a-z]{3,} [A-Z][a-z]{3,}', txt(y))))[:80]
    for nm in ('department', 'view'):
        m = re.search(r'<select[^>]+name="%s"[^>]*>(.*?)</select>' % nm, x, re.S)
        if m: o['options ' + nm] = re.findall(r'<option[^>]*value="([^"]*)"', m.group(1))[:30]
    tabs = re.findall(r'<table[^>]*>(.*?)</table>', x, re.S); o['tables'] = []
    for tb in tabs[:12]:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tb, re.S); info = {'rows': len(rows), 'sample': [], 'labelled': []}
        for rw in rows:
            cells = [txt(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', rw, re.S)]
            if not cells: continue
            if LAB.search(cells[0]) and len(info['labelled']) < 12: info['labelled'].append([cells[0][:30]] + [mask(c)[:14] for c in cells[1:14]])
            elif len(info['sample']) < 2: info['sample'].append([mask(c)[:14] for c in cells[:14]])
        o['tables'].append(info)
    o['words'] = sorted(set(re.findall(r'Front of House|Back of House|Management|Uncategorised|Hours Worked|Paid Hours|Approved|Department|FOH|BOH|Export[A-Za-z ]{0,20}|CSV', x)))
    o['exports'] = sorted(set(re.sub(r'\d+', 'N', h.replace('&amp;', '&'))[:120] for h in re.findall(r'href="([^"]*(?:export|csv|print|m=)[^"]*)"', x, re.I)))[:30]
    R['shapes'][lab] = o
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1)
print(json.dumps(R['status']))
