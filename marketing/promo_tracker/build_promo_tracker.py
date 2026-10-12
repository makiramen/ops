"""Deliveroo / Slerp 30% promo tracker (M10 Leeds, M11 Leicester, M16 Nottingham), started 05/10/2026.

Automated. Three inputs, no manual Deliveroo counting:
  1. data/deliveroo_daily.json        Deliveroo orders per site per day (Deliveroo Daily Master, via the daily tab run)
  2. data/daily/daily_YYYY-MM-DD.json  delivery sales GBP per site per day (Auto Cash Up, via the daily tab run)
  3. Inka's manual sheet               Slerp orders + scratch cards claimed in store, per site per day
     https://docs.google.com/spreadsheets/d/1GvaIFJn_CHOxY5LxzgSN8guW66s5OPy4gIPqsrQem7w
     Read with the Site CC service account (sheet must be shared with it as Viewer). Optional: if the read fails the
     tracker still builds from 1 and 2 and says the Slerp / scratch columns are not connected.

Baseline = the four full weeks before the promo (07/09 to 04/10/2026), averaged by weekday, in delivery GBP (hard number
from the cash-up). Baseline ORDERS are an estimate: baseline GBP / the site's median promo-period GBP per Deliveroo
order. Pre-promo baskets were bigger (no 30% off), so this slightly OVERSTATES baseline orders and keeps the uplift
conservative. Cash-up delivery GBP covers all delivery channels and is recorded net of the discount.

Writes marketing/promo_tracker/data.json and index.html. Usage: python3 marketing/promo_tracker/build_promo_tracker.py [--repo .]
"""
import argparse, datetime, glob, json, os, re, statistics as st, sys

ap = argparse.ArgumentParser(); ap.add_argument('--repo', default='.'); A = ap.parse_args()
R = os.path.abspath(A.repo); OUT = os.path.join(R, 'marketing', 'promo_tracker')
sys.path.insert(0, os.path.join(R, 'site_cc', 'pipeline'))

SITES = {'M10': 'Leeds', 'M11': 'Leicester', 'M16': 'Nottingham'}
SHEET_NAME = {'Maki Leeds': 'M10', 'Maki Leicester': 'M11', 'Maki Nottingham': 'M16'}
PROMO_START = '2026-10-05'; BASE_FROM = '2026-09-07'; BASE_TO = '2026-10-04'
SHEET_ID = '1GvaIFJn_CHOxY5LxzgSN8guW66s5OPy4gIPqsrQem7w'
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
TODAY = datetime.date.today().isoformat()

def wd(d): return datetime.date.fromisoformat(d).weekday()
def monday(d): x = datetime.date.fromisoformat(d); return (x - datetime.timedelta(x.weekday())).isoformat()

# 1. Deliveroo orders
try:
    DR = json.load(open(os.path.join(R, 'data', 'deliveroo_daily.json')))
except Exception as e:
    sys.exit(f'no deliveroo_daily.json: {e}')
droo = {s: {d: v[s][0] for d, v in DR['d'].items() if v.get(s) and v[s][0] is not None} for s in SITES}

# 2. delivery GBP from the cash-up
sales = {s: {} for s in SITES}
for f in sorted(glob.glob(os.path.join(R, 'data', 'daily', 'daily_2026-*.json'))):
    try: d = json.load(open(f))
    except Exception: continue
    if 'sites' not in d: continue
    for s in SITES:
        x = d['sites'].get(s)
        if x and x.get('sales', {}).get('delivery') is not None: sales[s][d['date']] = round(float(x['sales']['delivery']), 2)

# 3. manual sheet: Slerp + scratch cards. Layout: a date row (dd/mm/yyyy, Deliveroo, Slerp, Discount Claimed in Store), then one row per site.
manual = {s: {} for s in SITES}; manual_status = 'not connected'; manual_note = ''
rows = None; src_note = ''
try:
    from common import sheet_values
    rows = sheet_values(SHEET_ID, 'Sheet1!A:D'); manual_status = 'live'
except KeyError:
    src_note = 'GOOGLE_SERVICE_ACCOUNT_JSON not set (local run)'
except Exception as e:
    src_note = str(e)[:160]
if rows is None:
    # fallback: the last CSV export of the sheet committed beside this script (12/10/2026 snapshot) so Slerp / scratch still show
    import csv
    fb = os.path.join(OUT, 'manual_fallback.csv')
    if os.path.exists(fb):
        rows = list(csv.reader(open(fb, encoding='utf-8-sig'))); manual_status = 'snapshot CSV, not live'
try:
    if rows is None: raise RuntimeError(src_note or 'no rows')
    cur = None
    for r in rows:
        r = (r + [''] * 4)[:4]
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', r[0].strip())
        if m: cur = f'{m.group(3)}-{m.group(2)}-{m.group(1)}'; continue
        code = SHEET_NAME.get(r[0].strip())
        if cur and code:
            def n(x):
                try: return int(float(str(x).strip() or 0))
                except ValueError: return 0
            manual[code][cur] = {'droo_manual': n(r[1]), 'slerp': n(r[2]), 'scratch': n(r[3])}
    days = sorted({d for s in manual for d in manual[s]})
    manual_note = f'{len(days)} day(s), last {days[-1] if days else "none"}' + (f' · live read failed: {src_note}' if src_note else '')
except Exception as e:
    manual_status = 'not connected'; manual_note = str(e)[:160]
print('manual sheet:', manual_status, manual_note, file=sys.stderr)

# baseline by weekday (GBP) and the implied GBP per Deliveroo order during the promo
out_sites = {}
for s, name in SITES.items():
    by = {}
    for d, v in sales[s].items():
        if BASE_FROM <= d <= BASE_TO: by.setdefault(wd(d), []).append(v)
    base_gbp = [round(st.mean(by[i]), 2) if by.get(i) else None for i in range(7)]
    ratios = [sales[s][d] / droo[s][d] for d in droo[s] if d >= PROMO_START and d in sales[s] and droo[s][d]]
    ppo = round(st.median(ratios), 2) if ratios else None
    base_orders = [round(g / ppo) if (g is not None and ppo) else None for g in base_gbp]
    days = []
    for d in sorted(set(list(droo[s]) + list(sales[s]) + list(manual[s]))):
        if d < PROMO_START or d >= TODAY: continue
        g = sales[s].get(d); o = droo[s].get(d); m = manual[s].get(d, {})
        bg = base_gbp[wd(d)]; bo = base_orders[wd(d)]
        days.append({'date': d, 'wd': WD[wd(d)], 'droo': o, 'slerp': m.get('slerp'), 'scratch': m.get('scratch'),
                     'droo_manual': m.get('droo_manual'), 'gbp': g, 'base_gbp': bg, 'base_orders': bo,
                     'gbp_uplift_pct': round((g / bg - 1) * 100) if (g and bg) else None,
                     'orders_uplift_pct': round((o / bo - 1) * 100) if (o and bo) else None})
    # promo weeks vs baseline, like for like days only
    weeks = {}
    for x in days:
        w = weeks.setdefault(monday(x['date']), {'wc': monday(x['date']), 'days': 0, 'droo': 0, 'slerp': 0, 'scratch': 0, 'gbp': 0.0, 'base_gbp': 0.0, 'base_orders': 0})
        w['days'] += 1; w['droo'] += x['droo'] or 0; w['slerp'] += x['slerp'] or 0; w['scratch'] += x['scratch'] or 0
        if x['gbp'] is not None and x['base_gbp'] is not None: w['gbp'] += x['gbp']; w['base_gbp'] += x['base_gbp']
        if x['droo'] is not None and x['base_orders'] is not None: w['base_orders'] += x['base_orders']
    for w in weeks.values():
        w['gbp'] = round(w['gbp'], 2); w['base_gbp'] = round(w['base_gbp'], 2)
        w['gbp_uplift_pct'] = round((w['gbp'] / w['base_gbp'] - 1) * 100) if w['base_gbp'] else None
        w['orders_uplift_pct'] = round((w['droo'] / w['base_orders'] - 1) * 100) if w['base_orders'] else None
    pre = [x for x in days]  # all promo days to date
    tot_g = sum(x['gbp'] for x in pre if x['gbp'] is not None and x['base_gbp'] is not None)
    tot_bg = sum(x['base_gbp'] for x in pre if x['gbp'] is not None and x['base_gbp'] is not None)
    tot_o = sum(x['droo'] for x in pre if x['droo'] is not None and x['base_orders'] is not None)
    tot_bo = sum(x['base_orders'] for x in pre if x['droo'] is not None and x['base_orders'] is not None)
    out_sites[s] = {'code': s, 'name': name, 'base_gbp': base_gbp, 'base_orders': base_orders, 'base_week_gbp': round(sum(g for g in base_gbp if g), 2),
                    'base_week_orders': sum(o for o in base_orders if o), 'promo_gbp_per_order': ppo, 'days': days, 'weeks': sorted(weeks.values(), key=lambda w: w['wc']),
                    'to_date': {'days': len(pre), 'droo': sum(x['droo'] or 0 for x in pre), 'slerp': sum(x['slerp'] or 0 for x in pre), 'scratch': sum(x['scratch'] or 0 for x in pre),
                                'gbp': round(tot_g, 2), 'base_gbp': round(tot_bg, 2), 'gbp_uplift_pct': round((tot_g / tot_bg - 1) * 100) if tot_bg else None,
                                'base_orders': tot_bo, 'orders_uplift_pct': round((tot_o / tot_bo - 1) * 100) if tot_bo else None,
                                'extra_gbp': round(tot_g - tot_bg, 2)}}

data = {'built': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'promo_start': PROMO_START, 'baseline': {'from': BASE_FROM, 'to': BASE_TO, 'weeks': 4},
        'deliveroo_to': DR.get('to'), 'sales_to': max((d for s in sales for d in sales[s]), default=None), 'manual': {'status': manual_status, 'note': manual_note, 'sheet': SHEET_ID},
        'sites': out_sites}
os.makedirs(OUT, exist_ok=True)
json.dump(data, open(os.path.join(OUT, 'data.json'), 'w'), separators=(',', ':'), ensure_ascii=False)

tpl = open(os.path.join(OUT, 'template.html'), encoding='utf-8').read()
html = tpl.replace('/*__DATA__*/null', json.dumps(data, separators=(',', ':'), ensure_ascii=False))
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print('promo tracker built', data['built'], 'deliveroo to', data['deliveroo_to'], 'sales to', data['sales_to'], file=sys.stderr)
