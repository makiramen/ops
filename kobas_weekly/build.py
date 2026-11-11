"""Build data/kobas/wc_<monday>.json from a pull.py folder. One file per week, every site inside.

Rules (Michael's standing rules): key every source by header / field name, never by position; a missing input is
named in 'missing' and left null, never filled with zero; Kobas venue ids map through sitemap.py only.

Per site, per week:
  sales      gross = net x 1.2 (the KPI sheet / Mona Lisa basis: Actual = (eat-in + takeaway + delivery net) x 1.2)
             sit_in = (eat-in + takeaway) x 1.2, delivery = delivery x 1.2; net, food net, wet net as Kobas reports them
  target     Kobas Sales Budgets week row (the KPI sheet targets kpi-auto pushes in daily), Mon..Sun sum
  covers     Kobas covers + tabs without covers set + round(Stripe GBP / 22)    (Michael 29/10/2026, all 20 sites)
  sph        sit_in gross / covers                                             (KPI Raw Data 'Avg Spend' basis)
  labour     Labour Costs report: Hours Worked Cost (incl. employer NI), Total Labour, FOH / BOH / Management /
             Uncategorised, Hours Worked.  wage_pct = HWC / gross (today's dashboard basis);
             wage_pct_kobas = Total Labour / net (the LAB-01 basis, published alongside, not instead)
  item mix   All Item Sales for the week: categories (qty, gross, net, lead type) + top 25 items. TOTAL rows and the
             'of which' modifier rows are excluded (trap 1); the item sum is checked against the report's own TOTAL rows
  waste      Stock Usage History net cost by usage type (waste / comp / director)
  purchases  supplier deliveries delivered in the week, valued line by line, split food / wet / controllables
  stock      the stock take closing the week (completed Stock Checks logged Fri..Mon after the week start + 4; per category the
             latest count wins): counted value by food / wet / controllables
  food cost  food_pct = supplier deliveries delivered in the week (order totals) / gross sales: the Mona Lisa ACTUAL food cost %
             basis (proved 11/11/2026, M1 w/c 26/10 6,944.49 / 25,925.99 = 26.79% exactly). Deliveries over 8k or over 40% of the
             week are listed under purchases.check_these (eg M7 TRUE WORLD FOODS 51,064.76 on 31/10/2026).
  variance   Kobas Stock Usage Comparison, stock take to stock take: stock_variance = (actual - theory usage) / theory usage,
             food and drinks (M1 w/c 02/11: food -0.68 vs the sheet's -0.6, drinks +0.07 vs +0.1); food_cost_actual_pct = actual
             usage / attributed net revenue (true cost of sales, beside the purchases-basis figure)
"""
import os, re, sys, csv, io, json, glob, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitemap import V, VID2S, FRANCHISE, WET_CATS, CTRL_RX

src, dst = sys.argv[1], sys.argv[2]
RAW = os.path.join(src, 'raw')
LOG = json.load(open(os.path.join(RAW, 'log.json')))
weeks = [datetime.date.fromisoformat(w) for w in LOG['weeks']]
last_day = datetime.date.fromisoformat(LOG['days'][1])
os.makedirs(dst, exist_ok=True)


def num(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = re.sub(r'[£,%\s]', '', str(x))
    try: return float(s)
    except ValueError: return None


def r2(x): return None if x is None else round(x + 1e-9, 2)
def pct(a, b): return None if a is None or not b else round(100.0 * a / b, 2)
def jload(p, d=None):
    try: return json.load(open(p))
    except Exception: return d
def lead_of(cat):
    c = (cat or '').upper()
    if any(w in c for w in WET_CATS): return 'wet'
    if re.search(CTRL_RX, c): return 'controllables'
    return 'food'


# ---------------- cash log ----------------
CL, VNAME = {}, {}
for f in glob.glob(os.path.join(RAW, 'cashlog', '*.json')):
    site = os.path.basename(f)[:-5]
    j = jload(f, {})
    for v in j.get('venues', []):
        VNAME[str(v.get('name', '')).replace('\\/', '/').strip()] = site
        for g, lst in (v.get('data') or {}).items():
            for row in lst if isinstance(lst, list) else []:
                nm = str(row.get('name', '')).strip()
                for kk, val in row.items():
                    if re.match(r'\d{4}-\d{2}-\d{2}$', kk): CL[(site, kk, f'{g}:{nm}')] = num(val)
CL_KEYS = sorted({k[2] for k in CL})
def cl(s, d, key): return CL.get((s, d, key))

# ---------------- labour ----------------
LAB = {}
for f in glob.glob(os.path.join(RAW, 'labour', '*.csv')):
    rows = list(csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())))
    if not rows: continue
    h = [c.strip() for c in rows[0]]
    dcols = {i: c for i, c in enumerate(h) if re.match(r'\d{4}-\d{2}-\d{2}$', c)}
    for l in rows[1:]:
        if len(l) < 2: continue
        site = VNAME.get(l[0].strip())
        if not site: continue
        for i, d in dcols.items():
            if i < len(l): LAB[(site, d, l[1].strip())] = num(l[i])
LAB_KEYS = sorted({k[2] for k in LAB})
def lab(s, d, *names):
    for n in names:
        if (s, d, n) in LAB: return LAB[(s, d, n)]
    return None

# ---------------- stock usage ----------------
SU = {}
p = os.path.join(RAW, 'stock_usage.csv')
if os.path.exists(p):
    rd = csv.reader(io.StringIO(open(p, encoding='utf-8-sig', errors='replace').read()))
    hh = [c.strip() for c in next(rd, [])]; hx = {c: i for i, c in enumerate(hh)}
    if {'Date', 'Venue', 'Usage Type', 'Net Cost'} <= set(hx):
        for l in rd:
            if len(l) < len(hh): continue
            try: dt = datetime.datetime.strptime(' '.join(l[hx['Date']].split()[:3]).replace('Sept', 'Sep'), '%d %b %Y').date().isoformat()
            except Exception: continue
            site = VNAME.get(l[hx['Venue']].strip()); ut = l[hx['Usage Type']].strip().lower()
            if site and ut in ('waste', 'comp', 'director'):
                SU[(site, dt, ut)] = SU.get((site, dt, ut), 0.0) + (num(l[hx['Net Cost']]) or 0.0)

# ---------------- purchases (delivery lines) ----------------
DL = jload(os.path.join(RAW, 'delivery_lines.json'), None)
PUR = {}
for x in DL or []:
    site = VID2S.get(x.get('to_venue_id'))
    if not site: continue
    d = str(x.get('log_date') or '')[:10]
    for cat, v in (x.get('cats') or {}).items():
        kk = (site, d, lead_of(cat)); PUR[kk] = PUR.get(kk, 0.0) + v

# ---------------- transfers ----------------
TR = {}
for f in glob.glob(os.path.join(RAW, 'transfers', '*.json')):
    TR[os.path.basename(f)[:-5]] = jload(f)

# ---------------- budgets ----------------
BUD = {}
for b in jload(os.path.join(RAW, 'budgets.json'), []) or []:
    site = VID2S.get(b['venue_id'])
    if site: BUD[(site, b['week'])] = sum(b.get(d, 0) or 0 for d in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'))

# ---------------- stock checks ----------------
CHK = jload(os.path.join(RAW, 'stock_checks.json'), None)
def stock_close(site, mon):
    """Stock take that closes the week starting mon: completed checks logged Sat (mon+5) .. Mon (mon+7). Per category the
    latest count wins (re-counts and split food / drinks checks both handled)."""
    if CHK is None: return None
    lo, hi = (mon + datetime.timedelta(4)).isoformat(), (mon + datetime.timedelta(7)).isoformat() + ' 23:59:59'
    cs = sorted([c for c in CHK if VID2S.get(c['venue_id']) == site and lo <= c['log_date'] <= hi], key=lambda c: (c['log_date'], c.get('c_date') or ''))
    if not cs: return None
    bycat = {}
    for c in cs:
        cats = {}
        for cat, val, theo, *_ in c['entries']:
            a = cats.setdefault(cat, [0.0, 0.0, 0]); a[0] += val or 0
            if theo is not None: a[1] += theo; a[2] += 1
        for cat, a in cats.items(): bycat[cat] = (c['id'], a)
    res = {'check_ids': sorted({i for i, _ in bycat.values()}), 'logged': sorted({c['log_date'][:10] for c in cs})}
    for lt in ('food', 'wet', 'controllables'):
        val = sum(a[0] for cat, (i, a) in bycat.items() if lead_of(cat) == lt)
        theo = sum(a[1] for cat, (i, a) in bycat.items() if lead_of(cat) == lt)
        res[lt] = {'counted_gbp': r2(val), 'theoretical_gbp': r2(theo), 'variance_gbp': r2(val - theo) if theo else None,
                   'variance_pct': pct(val - theo, theo) if theo else None}
    return res

# ---------------- Stock Usage Comparison (food cost %, stock variance %) ----------------
CATNAME = {}
for c in CHK or []:
    for e in c['entries']:
        if len(e) > 3 and e[3] is not None: CATNAME[str(e[3])] = e[0]
UC = jload(os.path.join(RAW, 'usage_comparison.json'), []) or []
COUNTED = {}                                   # (site, closing date) -> category ids counted in that day's stock checks
for c in CHK or []:
    site = VID2S.get(c['venue_id'])
    if site:
        COUNTED.setdefault((site, c['log_date'][:10]), set()).update(str(e[3]) for e in c['entries'] if len(e) > 3 and e[3] is not None)
def usage(site, mon):
    """Kobas Stock Usage Comparison over the stock period(s) closing the week. Matches Mona Lisa's variance sheet:
    variance % = (actual - theory usage) / theory usage; actual cost % = actual usage / attributed net revenue; both over the
    categories Kobas attributes sales to (net_rev > 0: packaging / controllables carry usage but no revenue, Kobas excludes them
    from GP). Sites that split the stock take over two days get one period per closing day; each category is read from the period
    whose closing check counted it (categories counted on neither day come from the latest period, flagged)."""
    lo, hi = (mon + datetime.timedelta(4)).isoformat(), (mon + datetime.timedelta(8)).isoformat()
    runs = sorted([u for u in UC if u['site'] == site and lo <= (u.get('closing') or '') <= hi], key=lambda u: u['closing'])
    if not runs: return None
    good = [u for u in runs if not u.get('error')]
    if not good: return {'periods': [[u.get('opening'), u.get('closing')] for u in runs], 'error': runs[-1]['error']}
    pick, uncounted = {}, []
    for u in good:
        for cid, c in (u.get('categories') or {}).items():
            if cid in COUNTED.get((site, u['closing']), set()) or cid not in pick: pick[cid] = (u, c)
    for cid, (u, c) in pick.items():
        if not any(cid in COUNTED.get((site, x['closing']), set()) for x in good) and (c.get('net_rev') or 0) > 0.5: uncounted.append(cid)
    agg, unk, excl = {}, [], {}
    for cid, (u, c) in pick.items():
        name = CATNAME.get(str(cid))
        if name is None: unk.append(cid)
        lt = lead_of(name) if name else 'food'
        if not (c.get('net_rev') or 0) > 0.5:
            if c.get('usage_value'): excl[name or cid] = r2(c['usage_value'])
            continue
        a = agg.setdefault(lt, {'net_rev': 0.0, 'actual': 0.0, 'theory': 0.0, 'variance': 0.0, 'waste': 0.0, 'comp': 0.0, 'director': 0.0})
        a['net_rev'] += c['net_rev'] or 0; a['actual'] += c['usage_value'] or 0; a['theory'] += c['theory_value'] or 0
        a['variance'] += c['variance_value'] or 0; a['waste'] += c.get('cow_value') or 0; a['comp'] += c.get('coc_value') or 0; a['director'] += c.get('cod_value') or 0
    res = {'periods': [[u['opening'], u['closing']] for u in good], 'total_net_revenue': r2(max(u.get('total_net_revenue') or 0 for u in good)),
           'excluded_no_revenue_gbp': excl, 'unnamed_category_ids': unk, 'uncounted_category_ids': uncounted}
    for lt in ('food', 'wet'):
        a = agg.get(lt)
        res[lt] = None if not a else {'attributed_net_rev': r2(a['net_rev']), 'actual_usage_gbp': r2(a['actual']), 'theory_usage_gbp': r2(a['theory']),
                                      'variance_gbp': r2(a['variance']), 'cost_pct': pct(a['actual'], a['net_rev']), 'theory_cost_pct': pct(a['theory'], a['net_rev']),
                                      'variance_pct': pct(a['variance'], a['theory']),
                                      'waste_gbp': r2(a['waste']), 'comp_gbp': r2(a['comp']), 'director_gbp': r2(a['director'])}
    return res

# ---------------- purchases (Mona Lisa food cost basis): supplier deliveries delivered in the week, order totals ----------------
ORD = jload(os.path.join(RAW, 'orders.json'), None)
def purchases(site, mon):
    if ORD is None: return None
    a, b = mon.isoformat(), (mon + datetime.timedelta(6)).isoformat()
    xs = [o for o in ORD if o.get('to_venue_id') == V[site] and o.get('type') == 'delivery' and a <= str(o.get('delivered_date') or '')[:10] <= b]
    tot = sum(num(o.get('total')) or 0 for o in xs)
    flags = [{'order_id': o['id'], 'supplier': o.get('from_supplier_name'), 'delivered': str(o.get('delivered_date'))[:10], 'total': num(o.get('total'))}
             for o in xs if (num(o.get('total')) or 0) > 8000 or (tot and (num(o.get('total')) or 0) > 0.4 * tot and (num(o.get('total')) or 0) > 3000)]
    return {'deliveries': len(xs), 'total_gbp': r2(tot), 'check_these': flags}

# ---------------- item mix ----------------
def item_mix(site, mon):
    f = os.path.join(RAW, 'items', mon.isoformat(), f'{site}.csv')
    if not os.path.exists(f): return None
    ls = [l for l in csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())) if any(c.strip() for c in l)]
    if not ls: return {'categories': [], 'top_items': [], 'check': 'empty export'}
    h = [c.strip() for c in ls[0]]
    need = ['Item', 'Lead Type', 'Category', 'Items Sold', 'Gross Sales', 'Net Sales']
    if any(n not in h for n in need): return {'error': f'unexpected header {h[:8]}'}
    ix = {n: h.index(n) for n in h}
    cats, items, tot_g, tot_n, it_g, it_n = {}, {}, 0.0, 0.0, 0.0, 0.0
    for l in ls[1:]:
        if len(l) < len(h): continue
        nm = l[ix['Item']].strip(); g = num(l[ix['Gross Sales']]) or 0.0; n = num(l[ix['Net Sales']]) or 0.0
        if nm.lower() == 'total': tot_g += g; tot_n += n; continue
        if not nm or nm.lower().startswith('of which '): continue
        q = num(l[ix['Items Sold']]) or 0.0; it_g += g; it_n += n
        ck = (l[ix['Category']].strip(), l[ix['Lead Type']].strip())
        c = cats.setdefault(ck, [0.0, 0.0, 0.0]); c[0] += q; c[1] += g; c[2] += n
        ik = (nm, ck[0]); i = items.setdefault(ik, [0.0, 0.0, 0.0]); i[0] += q; i[1] += g; i[2] += n
    lead = {}
    for (cat, lt), v in cats.items(): lead[lt] = lead.get(lt, 0.0) + v[1]
    return {'categories': [{'category': c, 'lead_type': lt, 'qty': round(v[0], 2), 'gross': r2(v[1]), 'net': r2(v[2]),
                            'share_gross_pct': pct(v[1], it_g)} for (c, lt), v in sorted(cats.items(), key=lambda kv: -kv[1][1])],
            'top_items': [{'item': nm, 'category': c, 'qty': round(v[0], 2), 'gross': r2(v[1]), 'net': r2(v[2])}
                          for (nm, c), v in sorted(items.items(), key=lambda kv: -kv[1][1])[:25]],
            'lead_type_gross': {k: r2(v) for k, v in lead.items()},
            'items_gross': r2(it_g), 'items_net': r2(it_n), 'report_total_gross': r2(tot_g), 'report_total_net': r2(tot_n),
            'check': 'ok' if abs(it_n - tot_n) < 0.05 else f'item rows {it_n:.2f} vs report TOTAL {tot_n:.2f}'}

# ---------------- transfers for a site/week (net value in minus out, by lead type when the report gives it) -----------
def transfers(site, mon):
    j = TR.get(mon.isoformat())
    if j is None: return None
    vid = V[site]; tin = tout = 0.0; seen = False
    rows = j.get('data', j) if isinstance(j, dict) else j
    for r in rows if isinstance(rows, list) else []:
        s, rcv = r.get('sender') or r.get('sender_id') or r.get('from_venue_id'), r.get('receiver') or r.get('receiver_id') or r.get('to_venue_id')
        v = num(r.get('total') or r.get('value') or r.get('net_total'))
        if v is None: continue
        if str(rcv) == str(vid): tin += v; seen = True
        if str(s) == str(vid): tout += v; seen = True
    return {'in_gbp': r2(tin), 'out_gbp': r2(tout), 'net_gbp': r2(tin - tout), 'lead_type_split': False}


# ---------------- assemble ----------------
def day_list(mon): return [(mon + datetime.timedelta(i)).isoformat() for i in range(7)]
def ssum(vals):
    vals = [v for v in vals if v is not None]
    return r2(sum(vals)) if vals else None

written = []
for mon in weeks:
    days = day_list(mon)
    pulled = [d for d in days if d <= last_day.isoformat()]
    doc = {'schema': 'kobas_weekly/1', 'source': 'Kobas, scripted login (keyline bot), kobas_weekly/pull.py + build.py on GitHub Actions',
           'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
           'week_commencing': mon.isoformat(), 'week_ending': days[-1], 'days_pulled': len(pulled), 'complete': len(pulled) == 7,
           'sites': {}, 'missing': [], 'pull_errors': LOG.get('errors', [])}
    prev = jload(os.path.join(dst, f'wc_{(mon - datetime.timedelta(7)).isoformat()}.json'), {}) or {}
    for site in V:
        S = {'venue_id': V[site], 'franchise': site in FRANCHISE, 'days': {}}
        for d in pulled:
            e, t, dl = (cl(site, d, 'expectedNetPaymentsConsumptions:of which ' + x) for x in ('Eat-in sales', 'Takeaway sales', 'Delivery sales'))
            net = cl(site, d, 'totalSales:Net Sales')
            if net is None and e is None:
                S['days'][d] = None; continue
            e, t, dl = e or 0.0, t or 0.0, dl or 0.0
            if e + t + dl == 0 and net: e = net                       # Nori: no consumption split
            kc = cl(site, d, 'covers:Covers'); tn = cl(site, d, 'tabsWithoutCoversSet:Tabs Without Covers Set')
            st = cl(site, d, 'otherPaymentTypes:of which Stripe')
            cov = None if kc is None else int(round((kc or 0) + (tn or 0) + round((st or 0) / 22.0)))
            tips = sum(cl(site, d, k2) or 0 for k2 in ('serviceCharge:Service Charge', 'PDQPayments:of which PDQ Tips', 'voucherTips:Other Tips', 'cashTips:Cash Tips'))
            S['days'][d] = {
                'net': r2(net), 'gross': r2((e + t + dl) * 1.2), 'sit_in_gross': r2((e + t) * 1.2), 'delivery_gross': r2(dl * 1.2),
                'eat_in_net': r2(e), 'takeaway_net': r2(t), 'delivery_net': r2(dl),
                'food_net': r2(cl(site, d, 'expectedNetPaymentsLeads:of which Food sales')), 'wet_net': r2(cl(site, d, 'expectedNetPaymentsLeads:of which Wet sales')),
                'covers': cov, 'kobas_covers': kc, 'tabs_no_covers': tn, 'stripe_gbp': r2(st), 'tips': r2(tips),
                'labour': {'hours_worked_cost': lab(site, d, 'Hours Worked Cost', 'Hours Worked Cost (incl. Employer NIC)'),
                           'total_labour': lab(site, d, 'Total Labour'), 'foh': lab(site, d, 'of which Front of House'),
                           'boh': lab(site, d, 'of which Back of House'), 'management': lab(site, d, 'of which Management'),
                           'uncategorised': lab(site, d, 'of which Uncategorised'), 'hours': lab(site, d, 'Hours Worked')},
                'waste': r2(SU.get((site, d, 'waste'))), 'comp': r2(SU.get((site, d, 'comp'))), 'director': r2(SU.get((site, d, 'director'))),
                'purchases': {lt: r2(PUR.get((site, d, lt))) for lt in ('food', 'wet', 'controllables')} if DL is not None else None}
        D = [x for x in S['days'].values() if x]
        def tot(f): return ssum([f(x) for x in D])
        gross, net, sit = tot(lambda x: x['gross']), tot(lambda x: x['net']), tot(lambda x: x['sit_in_gross'])
        covers = None if not D or any(x['covers'] is None for x in D) else sum(x['covers'] for x in D)
        hwc, tl, hrs = tot(lambda x: x['labour']['hours_worked_cost']), tot(lambda x: x['labour']['total_labour']), tot(lambda x: x['labour']['hours'])
        target = BUD.get((site, mon.isoformat()))
        food_net, wet_net = tot(lambda x: x['food_net']), tot(lambda x: x['wet_net'])
        W = {'days_traded': len(D), 'sales_gross': gross, 'sales_net': net, 'sit_in_gross': sit, 'delivery_gross': tot(lambda x: x['delivery_gross']),
             'food_net': food_net, 'wet_net': wet_net, 'tips': tot(lambda x: x['tips']),
             'target_gross': r2(target), 'vs_target_pct': pct((gross or 0) - target, target) if (target and gross is not None) else None,
             'covers': covers, 'sph': r2(sit / covers) if (sit and covers) else None, 'avg_spend_all': r2(gross / covers) if (gross and covers) else None,
             'labour_hours_worked_cost': hwc, 'labour_total': tl, 'labour_hours': hrs,
             'labour_foh': tot(lambda x: x['labour']['foh']), 'labour_boh': tot(lambda x: x['labour']['boh']),
             'labour_management': tot(lambda x: x['labour']['management']), 'labour_uncategorised': tot(lambda x: x['labour']['uncategorised']),
             'wage_pct': pct(hwc, gross), 'wage_pct_kobas': pct(tl, net), 'rev_per_labour_hour': r2(net / hrs) if (net and hrs) else None,
             'waste': tot(lambda x: x['waste']), 'comp': tot(lambda x: x['comp']), 'director': tot(lambda x: x['director'])}
        if DL is not None:
            W['purchases'] = {lt: tot(lambda x, lt=lt: (x['purchases'] or {}).get(lt)) for lt in ('food', 'wet', 'controllables')}
        S['week'] = W
        S['item_mix'] = item_mix(site, mon)
        close = stock_close(site, mon)
        S['stock'] = close
        S['transfers'] = transfers(site, mon)
        uc = usage(site, mon)
        S['usage_comparison'] = uc
        pu = purchases(site, mon)
        S['purchases'] = pu
        # food_pct = the dashboard / Mona Lisa basis (proved 11/11/2026: Mona Lisa w/c 26/10 M1 6,944.49 / 25,925.99 = 26.79%):
        # supplier deliveries delivered in the week / gross sales. Stock-period actual cost sits beside it.
        S['food_pct'] = pct((pu or {}).get('total_gbp'), gross) if (pu and gross and doc['complete']) else None
        S['food_cost_actual_pct'] = ((uc or {}).get('food') or {}).get('cost_pct')
        S['wet_cost_actual_pct'] = ((uc or {}).get('wet') or {}).get('cost_pct')
        S['stock_variance'] = {'food_pct': ((uc or {}).get('food') or {}).get('variance_pct'), 'drinks_pct': ((uc or {}).get('wet') or {}).get('variance_pct'),
                               'target': '±5%', 'basis': '(actual - theory usage) / theory usage, Kobas Stock Usage Comparison'}
        doc['sites'][site] = S
        if site not in FRANCHISE:
            for what, v in (('sales', gross), ('covers', covers), ('labour', hwc), ('target', target), ('item mix', S['item_mix']),
                            ('stock take', close), ('food cost %', S['food_pct'])):
                if v is None and (what not in ('stock take', 'food cost %') or doc['complete']): doc['missing'].append(f'{site}: {what}')
    doc['field_keys_seen'] = {'cash_log': CL_KEYS, 'labour': LAB_KEYS}
    fn = os.path.join(dst, f'wc_{mon.isoformat()}.json')
    json.dump(doc, open(fn, 'w'), indent=1, sort_keys=False)
    written.append(fn)
print('wrote', written)
