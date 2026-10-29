"""Kobas_Daily (23/10/2026): the KPI sheet Script Data fields for each site and day, built straight from Kobas (no email), in the
exact shape of the Kobas 'Daily Headline Revenue' report the sheet is filled from today. Reads the pull folder, upserts the days
of this run into the Kobas_Daily tab of the KPI Auto sheet (other days are kept, so a daily 04:05 run freezes each morning's figures).

Field rules (proved 23/10 against 408/408 Script Data cells and the Headline report, see KPI_Oct_Reconciliation):
  Sit in      = round((Eat-in + Takeaway net) x 1.2, 2)      Cash Log report, expectedNetPaymentsConsumptions (Nori: no split, net = eat-in)
  Delivery    = round(Delivery net x 1.2, 2)
  Actual      = round((Eat-in + Takeaway + Delivery net) x 1.2, 2)
  Tips        = Service Charge + PDQ Tips + Other Tips + Cash Tips
  Declared Rev= Declared Payments - Tips
  Wet Sales   = Wet sales (net)
  Hours work Cost / Hours Used = Labour Costs report 'Hours Worked Cost' (incl. employer NI) / 'Hours Worked', morning-after report;
                hours 0 on a day with no sales (the Headline blanks them)
  Food Cost Actual = total of supplier orders delivered that day and confirmed (last modified) before the morning cut-off
  Cost of Waste / Comp / Directors = Stock Usage report net cost by usage type
  Potential Gross Revenue Lost: dropped (Michael, 23/10/2026, not needed)
DAY (Input) fields, Michael's rulings 23/10/2026 (one rule for every site), covers rule re-set 29/10/2026:
  Covers      = Kobas covers + Tabs Without Covers Set + ROUND(online Stripe payments £ / 22)   (all from the Cash Log report;
                Stripe = otherPaymentTypes 'of which Stripe', the online orders that carry no cover count; £22 = average spend)
                The parts are kept in their own columns (Kobas Covers, Tabs No Covers, Stripe £) so the sum can be checked.
  Drinks % / Sushi % / Sides % = category sales incl. VAT / total sales incl. VAT (All Item Sales report, every menu incl. delivery)"""
import os, sys, csv, io, json, re, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gretry  # noqa
SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
out = sys.argv[1]
d0 = datetime.date.fromisoformat(os.environ.get('DATE_FROM') or '2026-09-28')
d1 = datetime.date.fromisoformat(os.environ.get('DATE_TO') or '2026-10-21')
V = {'M1': 3, 'M3': 5, 'M6': 43, 'M7': 9, 'M8': 47, 'M9': 2, 'M10': 13, 'M11': 24, 'M12': 27, 'M13': 28, 'M14': 37,
     'M15': 41, 'M16': 42, 'M17': 49, 'M18': 51, 'M19': 58, 'M20': 60, 'M21': 61, 'NORI': 57, 'IKI2': 7}
VID2S = {v: k for k, v in V.items()}
def num(x):
    try: return float(str(x).replace(',', '').replace('£', ''))
    except (TypeError, ValueError): return None
def r2(x): return None if x is None else round(x + 1e-9, 2)
def cutoff(d): return f'{d + datetime.timedelta(1)} {"04:00" if d >= datetime.date(2026, 10, 22) else "08:00"}'

# cash log report per site: data.<group>[i] = {name, <date>: value}
CL, VNAME = {}, {}
for f in glob.glob(os.path.join(out, 'cashlog', '*.json')):
    site = os.path.basename(f)[:-5]
    try: j = json.load(open(f))
    except Exception: continue
    for v in j.get('venues', []):
        VNAME[str(v.get('name', '')).replace('\\/', '/')] = site
        for g, lst in (v.get('data') or {}).items():
            for row in lst if isinstance(lst, list) else []:
                nm = str(row.get('name', '')).strip()
                for kk, val in row.items():
                    if re.match(r'\d{4}-\d{2}-\d{2}$', kk): CL[(site, kk, f'{g}:{nm}')] = num(val) or 0.0
def g(s, d, k): return CL.get((s, d, k), 0.0)
def traded(s, d): return (s, d, 'totalSales:Net Sales') in CL and abs(g(s, d, 'totalSales:Net Sales')) > 0
# labour snapshots
LAB = {}
for f in glob.glob(os.path.join(out, 'labour_snap', '*.csv')):
    day = os.path.basename(f)[:10]
    ls = list(csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())))
    if not ls or day not in ls[0]: continue
    i = ls[0].index(day)
    for l in ls[1:]:
        if len(l) > i: LAB[(l[0].strip(), day, l[1].strip())] = num(l[i])
# orders
ORD = []
try: ORD = json.load(open(os.path.join(out, 'orders.json')))
except Exception: pass
# stock usage
SU = {}
try:
    rd = csv.reader(io.StringIO(open(os.path.join(out, 'stock_usage_export.txt'), encoding='utf-8-sig', errors='replace').read()))
    hh = next(rd); hx = {c.strip(): i for i, c in enumerate(hh)}
    for l in rd:
        if len(l) < len(hh): continue
        try: dt = datetime.datetime.strptime(' '.join(l[hx['Date']].split()[:3]).replace('Sept', 'Sep'), '%d %b %Y').date().isoformat()
        except Exception: continue
        ut = l[hx['Usage Type']].strip().lower()
        if ut in ('waste', 'comp', 'director'):
            kk = (l[hx['Venue']].strip(), dt, ut); SU[kk] = SU.get(kk, 0.0) + (num(l[hx['Net Cost']]) or 0.0)
except Exception: pass
# All Item Sales per site/day (mode all): category gross and the report's TOTAL gross
RX = {'drinks': r'drink|tea|beer|wine|cocktail|mocktail|spirit|sake|shot|alcohol', 'sushi': r'sushi|maki roll|nigiri|sashimi|hosomaki|hand roll|chef',
      'sides': r'^sides'}
PCT = {}
for f in glob.glob(os.path.join(out, 'items', '*_all.csv')):
    site, day, _ = os.path.basename(f)[:-4].rsplit('_', 2)
    ls = [l for l in csv.reader(io.StringIO(open(f, encoding='utf-8-sig').read())) if any(c.strip() for c in l)]
    if not ls: continue
    h = [c.strip() for c in ls[0]]
    try: ii, ci, gi = h.index('Item'), h.index('Category'), h.index('Gross Sales')
    except ValueError: continue
    tot, grp = 0.0, {k: 0.0 for k in RX}
    for l in ls[1:]:
        if len(l) <= max(ii, ci, gi): continue
        nm = l[ii].strip().lower(); gv = num(l[gi]) or 0.0
        if nm == 'total': tot += gv; continue
        if not nm or nm.startswith('of which '): continue
        for k, rx in RX.items():
            if re.search(rx, l[ci].strip(), re.I): grp[k] += gv
    PCT[(site, day)] = {k: (round(100 * v / tot, 2) if tot > 0 else None) for k, v in grp.items()}
SNAME = {v: k for k, v in VNAME.items()}
head = ['date', 'site', 'Sit in', 'Delivery', 'Tips', 'Actual', 'Declared Rev', 'Hours work Cost', 'Hours Used', 'Food Cost Actual', 'Cost of Waste',
        'Cost of Comp', 'Cost of Directors', 'Wet Sales', 'Covers', 'Drinks %', 'Sushi %', 'Sides %', 'pulled_at', 'labour_report',
        'Kobas Covers', 'Tabs No Covers', 'Stripe £']   # 29/10/2026: the three parts of Covers
STRIPE_SPEND = float(os.environ.get('STRIPE_AVG_SPEND', '22'))
def covers_of(s, ds):
    """Covers rule 29/10/2026: Kobas covers + tabs without covers set + round(Stripe online £ / 22). None when the day has no cash log."""
    if (s, ds, 'covers:Covers') not in CL: return None, None, None, None
    kc = CL.get((s, ds, 'covers:Covers')) or 0.0
    tn = CL.get((s, ds, 'tabsWithoutCoversSet:Tabs Without Covers Set')) or 0.0
    st = CL.get((s, ds, 'otherPaymentTypes:of which Stripe')) or 0.0
    return int(round(kc + tn + round(st / STRIPE_SPEND))), kc, tn, r2(st)
rows = []
pulled = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ')
d = d0
while d <= d1:
    ds = d.isoformat()
    for s in V:
        ven = SNAME.get(s, '')
        e, t, dl = (g(s, ds, 'expectedNetPaymentsConsumptions:of which ' + x) for x in ('Eat-in sales', 'Takeaway sales', 'Delivery sales'))
        if e + t + dl == 0: e = g(s, ds, 'totalSales:Net Sales')
        tips = g(s, ds, 'serviceCharge:Service Charge') + g(s, ds, 'PDQPayments:of which PDQ Tips') + g(s, ds, 'voucherTips:Other Tips') + g(s, ds, 'cashTips:Cash Tips')
        hwc = LAB.get((ven, ds, 'Hours Worked Cost')); hrs = LAB.get((ven, ds, 'Hours Worked'))
        food = sum(num(o.get('total')) or 0 for o in ORD if o.get('to_venue_id') == V[s] and o.get('type') == 'delivery'
                   and str(o.get('delivered_date') or '')[:10] == ds and str(o.get('m_date') or '') <= cutoff(d))
        tr = traded(s, ds)
        cov, kc, tn, st = covers_of(s, ds)
        rows.append([ds, s, r2((e + t) * 1.2), r2(dl * 1.2), r2(tips), r2((e + t + dl) * 1.2), r2(g(s, ds, 'declaredPayments:Declared Payments') - tips),
                     r2(hwc), (r2(hrs) if tr else 0.0) if hrs is not None else None, r2(food), r2(SU.get((ven, ds, 'waste'), 0.0)), r2(SU.get((ven, ds, 'comp'), 0.0)),
                     r2(SU.get((ven, ds, 'director'), 0.0)), r2(g(s, ds, 'expectedNetPaymentsLeads:of which Wet sales')),
                     cov, (PCT.get((s, ds)) or {}).get('drinks'), (PCT.get((s, ds)) or {}).get('sushi'), (PCT.get((s, ds)) or {}).get('sides'), pulled,
                     ','.join(os.path.basename(f)[11:].split('_')[0] for f in glob.glob(os.path.join(out, 'labour_snap', f'{ds}_*.csv'))),
                     kc, tn, st])
    d += datetime.timedelta(1)
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']), scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()
have = {x['properties']['title']: x['properties'] for x in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets']}
old = []
if 'Kobas_Daily' in have:
    old = svc.values().get(spreadsheetId=SHEET, range="'Kobas_Daily'").execute().get('values', [])[1:]
keep = [r for r in old if r and not (d0.isoformat() <= r[0] <= d1.isoformat())]
data = [head] + sorted(keep + rows, key=lambda r: (r[0], r[1]))
data = [[('' if c is None else c) for c in r] + [''] * (len(head) - len(r)) for r in data]
if 'Kobas_Daily' not in have:
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': 'Kobas_Daily', 'gridProperties': {'rowCount': len(data) + 50, 'columnCount': len(head)}}}}]}).execute()
else:
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': have['Kobas_Daily']['sheetId'],
        'gridProperties': {'rowCount': len(data) + 50, 'columnCount': len(head)}}, 'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
    svc.values().clear(spreadsheetId=SHEET, range="'Kobas_Daily'").execute()
svc.values().update(spreadsheetId=SHEET, range="'Kobas_Daily'!A1", valueInputOption='RAW', body={'values': data}).execute()
print('wrote Kobas_Daily', len(rows), 'rows for', d0, '..', d1, 'total', len(data) - 1, flush=True)
