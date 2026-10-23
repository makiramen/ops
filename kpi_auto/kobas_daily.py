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
  Potential Gross Revenue Lost = not yet rebuilt (left blank)"""
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
SNAME = {v: k for k, v in VNAME.items()}
head = ['date', 'site', 'Sit in', 'Delivery', 'Tips', 'Actual', 'Declared Rev', 'Hours work Cost', 'Hours Used', 'Food Cost Actual', 'Cost of Waste',
        'Cost of Comp', 'Cost of Directors', 'Potential Gross Revenue Lost Due To Comp/Waste/Dir', 'Wet Sales', 'pulled_at', 'labour_report']
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
        rows.append([ds, s, r2((e + t) * 1.2), r2(dl * 1.2), r2(tips), r2((e + t + dl) * 1.2), r2(g(s, ds, 'declaredPayments:Declared Payments') - tips),
                     r2(hwc), (r2(hrs) if tr else 0.0) if hrs is not None else None, r2(food), r2(SU.get((ven, ds, 'waste'), 0.0)), r2(SU.get((ven, ds, 'comp'), 0.0)),
                     r2(SU.get((ven, ds, 'director'), 0.0)), '', r2(g(s, ds, 'expectedNetPaymentsLeads:of which Wet sales')), pulled,
                     ','.join(os.path.basename(f)[11:].split('_')[0] for f in glob.glob(os.path.join(out, 'labour_snap', f'{ds}_*.csv')))])
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
