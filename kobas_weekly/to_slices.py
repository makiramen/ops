"""Turn data/kobas/wc_<monday>.json into the slice files build_site_json.py already reads, so the weekly AM build runs on
Kobas instead of Mona Lisa / KPI Raw Data / the Stocktake Variance sheet, with no change to the builder.

  python3 to_slices.py <kobas dir or https://raw.githubusercontent.com/makiramen/ops/main/data/kobas> <monday> <_slices dir>

Writes (each carries _source = Kobas so a rebuilt week is traceable):
  monalisa_<wk>.json    pipe 1  sales, target, sit in, delivery, tips, covers, avg spend, labour (HWC), hours, wage %, purchases, waste
  covers_sph_<wk>.json  pipe 2  covers (Michael's 29/10 rule) and SPH = sit in gross / covers, current + prior week
  food_cost_<wk>.json   pipe 7  food cost % = deliveries in the week / gross sales (the Mona Lisa ACTUAL basis)
  stock_take_<wk>.json  pipe 3  food / drinks variance % from Kobas Stock Usage Comparison, ±5% band
Fields Kobas does not hold stay null and are named in _not_in_kobas (labourBudgetGBP: the KPI-sheet labour budget).
Existing slices are moved aside to <name>.pre-kobas-<stamp>.json, never overwritten in place."""
import os, sys, json, datetime, urllib.request

src, wk, dst = sys.argv[1], sys.argv[2], sys.argv[3]
mon = datetime.date.fromisoformat(wk)
prev = (mon - datetime.timedelta(7)).isoformat()


def load(w):
    if src.startswith('http'):
        with urllib.request.urlopen(f'{src.rstrip("/")}/wc_{w}.json', timeout=60) as r: return json.loads(r.read())
    p = os.path.join(src, f'wc_{w}.json')
    return json.load(open(p)) if os.path.exists(p) else None


cur, prv = load(wk), None
try: prv = load(prev)
except Exception: prv = None
if not cur: raise SystemExit(f'no Kobas file for w/c {wk}')
if not cur.get('complete'): print(f'[WARN] w/c {wk} is not complete in Kobas yet ({cur.get("days_pulled")}/7 days)')
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
SRC = f"Kobas nightly pull (data/kobas/wc_{wk}.json, generated {cur.get('generated_at')}), via kobas_weekly/to_slices.py"


def r2(x): return None if x is None else round(x + 1e-9, 2)


def put(name, obj):
    os.makedirs(dst, exist_ok=True)
    p = os.path.join(dst, name)
    if os.path.exists(p): os.replace(p, p[:-5] + f'.pre-kobas-{stamp}.json')
    json.dump(obj, open(p, 'w'), indent=2)
    print('wrote', p)


def mlweek(S, doc):
    if not S: return {}
    W = S['week']; D = [d for d in S['days'].values() if d]
    split_days = sum(1 for d in D if (d['labour'] or {}).get('foh') is not None and (d['labour'] or {}).get('boh') is not None)
    pu = S.get('purchases') or {}
    return {'salesActual': W['sales_gross'], 'salesTarget': W['target_gross'], 'vsTargetPct': W['vs_target_pct'],
            'sitIn': W['sit_in_gross'], 'delivery': W['delivery_gross'], 'tips': W['tips'], 'covers': W['covers'],
            'avgSpend': W['avg_spend_all'], 'labourBudgetGBP': None, 'labourActualGBP': W['labour_hours_worked_cost'],
            'labourHours': W['labour_hours'], 'wagePctOfRevenue': W['wage_pct'],
            'foodCostGBP': pu.get('total_gbp') if doc.get('complete') else None, 'foodCostDaysReported': 7 if doc.get('complete') and pu else 0,
            'wasteGBP': W['waste'], 'daysPresent': len(D), 'splitDaysReported': split_days,
            'splitStatus': 'filed' if split_days else 'absent',
            'labourTotalKobas': W['labour_total'], 'wagePctKobasBasis': W['wage_pct_kobas']}


# 16/11/2026 (Michael): the weekly wage % is the SUM OF THE DAILIES (Daily tab labour / Daily tab sales), not the
# Kobas week as it stands later. Kobas re-costs earlier days upward through the week, so the two drift apart.
# A site with no dailies (franchise) keeps the Kobas figure and is named in _meta.wage_basis.
DAILY_SRC = (src.rstrip('/').rsplit('/', 1)[0] + '/daily') if src.startswith('http') else os.path.join(os.path.dirname(os.path.abspath(src.rstrip('/'))), 'daily')
_daily_cache = {}


def daily(day):
    if day not in _daily_cache:
        try:
            if DAILY_SRC.startswith('http'):
                with urllib.request.urlopen(f'{DAILY_SRC}/daily_{day}.json', timeout=60) as r: _daily_cache[day] = json.loads(r.read())
            else:
                _daily_cache[day] = json.load(open(os.path.join(DAILY_SRC, f'daily_{day}.json')))
        except Exception:
            _daily_cache[day] = None
    return _daily_cache[day]


def daily_wage(code, w):
    """(labour GBP, wage %, days used) from the dailies of week w, or None when the site has no daily labour."""
    m = datetime.date.fromisoformat(w); lab = sal = 0.0; n = 0
    for i in range(7):
        d = ((daily((m + datetime.timedelta(i)).isoformat()) or {}).get('sites') or {}).get(code) or {}
        l, a = (d.get('labour') or {}).get('total'), (d.get('sales') or {}).get('actual')
        if l is not None and a:
            lab += l; sal += a; n += 1
    return (r2(lab), r2(100 * lab / sal), n) if n and sal else None


WAGE_BASIS = {}


def mlweek_d(S, doc, code, w):
    o = mlweek(S, doc)
    if not o: return o
    dw = daily_wage(code, w)
    o['labourKobasHWC'] = o.get('labourActualGBP'); o['wagePctKobasHWC'] = o.get('wagePctOfRevenue')
    if dw:
        o['labourActualGBP'], o['wagePctOfRevenue'], o['wageDailyDays'] = dw
        if w == wk: WAGE_BASIS[code] = f'dailies ({dw[2]} days)'
    elif w == wk:
        WAGE_BASIS[code] = 'Kobas (no dailies for this site)'
    return o


NAME = {**{f'M{i}': f'Maki {i}' for i in range(1, 30)}, 'IKI2': 'Ikigai 2', 'MakiNori': 'Maki Nori', 'MAF3': 'Maki O2 Arena', 'MAF1': 'Maki West End', 'MAF2': 'Maki Manchester NQ', 'MAF4': 'Maki Braehead'}


def key(w): d = datetime.date.fromisoformat(w); return f'{w}_to_{(d + datetime.timedelta(6)).isoformat()}'


sites = sorted(set(cur['sites']) | set((prv or {}).get('sites', {})))
put(f'monalisa_{wk}.json', {
    '_meta': {'source': SRC, 'primaryWeek': key(wk), 'priorWeek': key(prev), '_not_in_kobas': ['labourBudgetGBP'],
              'note': 'salesActual = (eat-in + takeaway + delivery net) x 1.2, the KPI sheet Actual basis; labourActualGBP = Kobas Hours Worked Cost; '
                      'wagePctOfRevenue and labourActualGBP = SUM OF THE DAILIES (Michael 16/11/2026), Kobas HWC kept alongside as labourKobasHWC / wagePctKobasHWC; wagePctKobasBasis = Total Labour / net (LAB-01 basis, alongside).'},
    'sites': {s: {'mcode': s, 'venueName': NAME.get(s, s), 'weeks': {key(wk): mlweek_d(cur['sites'].get(s), cur, s, wk),
                                                         **({key(prev): mlweek_d(prv['sites'].get(s), prv, s, prev)} if prv else {})}} for s in sites}})
print('wage basis:', WAGE_BASIS)
put(f'covers_sph_{wk}.json', {
    '_source': SRC + ' | covers = Kobas covers + tabs without covers set + round(Stripe GBP / 22); sph = sit in gross / covers',
    'week_commencing': wk, 'prev_commencing': prev, 'method': 'kobas',
    'sites': {s: {'covers': {'cur': (cur['sites'].get(s) or {}).get('week', {}).get('covers'), 'prev': ((prv or {}).get('sites', {}).get(s) or {}).get('week', {}).get('covers')},
                  'sph': {'cur': (cur['sites'].get(s) or {}).get('week', {}).get('sph'), 'prev': ((prv or {}).get('sites', {}).get(s) or {}).get('week', {}).get('sph')}}
              for s in sites}})
put(f'food_cost_{wk}.json', {
    '_source': SRC + ' | supplier deliveries delivered in the week / gross sales x 100 (Mona Lisa ACTUAL food cost % basis)',
    '_generated_at': cur.get('generated_at'), 'week_commencing': wk, 'units': 'food cost % of gross sales, purchases basis (weekly)',
    'sites_reported': sum(1 for s in cur['sites'].values() if s.get('food_pct') is not None),
    'sites': {s: v.get('food_pct') for s, v in cur['sites'].items()},
    'check_these': {s: v['purchases']['check_these'] for s, v in cur['sites'].items() if (v.get('purchases') or {}).get('check_these')}})


def band(v): return None if v is None else abs(v) <= 5
put(f'stock_take_{wk}.json', {
    '_source': SRC + ' | Kobas Stock Usage Comparison, stock take to stock take: (actual - theory usage) / theory usage',
    'week_commencing': wk, 'units_note': 'variance % only',
    'sites': {s: {k2: {'variance_pct': r2((v.get('stock_variance') or {}).get(f)), 'target': '±5%', 'within_band': band((v.get('stock_variance') or {}).get(f))}
                  for k2, f in (('drinks', 'drinks_pct'), ('food', 'food_pct'))} for s, v in cur['sites'].items()}})
