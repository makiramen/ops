"""Probe 6: stock checks since 01/10/2026 for every venue, one full check raw, per-check value summaries; ingredient category lead types."""
import os, re, sys, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
checks, off = [], 0
while True:
    r = k.s.get(BASE + '/data/v2/stock/check', params={'limit': 200, 'offset': off, 'orderBy[log_date]': 'DESC', 'filterBy[log_date][gte]': '2026-10-01'}, timeout=90)
    j = r.json() if r.status_code == 200 else []
    if r.status_code != 200: save('check_list_err.txt', f'{r.status_code} {r.text[:3000]}'); break
    checks += j
    if len(j) < 200: break
    off += 200
save('check_list.json', json.dumps(checks, indent=0))
for n, u in [('ingcat_v2', '/data/v2/stock/ingredient/category'), ('ingcat_v2b', '/data/v2/stock/ingredient-category'), ('ingcat', '/data/stock/ingredient/category'),
             ('leadtype', '/data/lead-type'), ('leadtype2', '/data/v2/lead-type'), ('transfer', '/data/v2/stock/transfer?limit=3&orderBy[id]=DESC')]:
    r = k.s.get(BASE + u, timeout=60); save(f'route_{n}.txt', f'{r.status_code}\n{r.text[:15000]}')
def full(c):
    ents, off = None, 0
    while True:
        r = k.s.get(BASE + f'/data/v2/stock/check/{c["id"]}', params={'limit': 500, 'offset': off}, timeout=120)
        j = r.json()
        if ents is None: base = j; ents = list(j.get('stock_check_entries') or [])
        else: ents += j.get('stock_check_entries') or []
        tot = int(r.headers.get('x-total-count') or 0)
        off += 500
        if off >= tot: break
    base['stock_check_entries'] = ents
    return base
stock = [c for c in checks if c.get('type') == 'stock' and c.get('status') == 'completed']
first = full(stock[0]) if stock else {}
save('check_raw_example.json', json.dumps(first, indent=1)[:200000])
def summ(c):
    try: f = full(c)
    except Exception as e: return {'id': c['id'], 'err': repr(e)}
    agg = {}
    for e in f['stock_check_entries']:
        si = e.get('stock_ingredient') or e.get('stock_product') or {}
        par = si.get('parent') or si
        cat = par.get('stock_ingredient_category_name') or par.get('stock_product_category_name') or '?'
        lt = par.get('lead_type') or par.get('stock_ingredient_category_lead_type') or (par.get('stock_ingredient_category') or {}).get('lead_type') or '?'
        a = agg.setdefault(f'{lt}|{cat}', [0.0, 0.0, 0])
        a[0] += float(e.get('total_value') or 0); a[2] += 1
    return {'id': c['id'], 'venue_id': c.get('venue_id'), 'log_date': c.get('log_date'), 'name': c.get('name'), 'total_value': c.get('total_value'), 'n': len(f['stock_check_entries']), 'by': agg}
with ThreadPoolExecutor(5) as ex: S = list(ex.map(summ, stock[:120]))
save('check_summaries.json', json.dumps(S, indent=0))
print('checks', len(checks), 'stock completed', len(stock))
