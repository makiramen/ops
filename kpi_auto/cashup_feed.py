"""Auto Cash Up feed (Michael, 29/10/2026): the Auto Cash Up workbook's `Raw Data 2` tab is fed straight from the Kobas_Daily tab
of the KPI Auto sheet, so the cash-up no longer waits for Matt's Z-report script. Runs after kobas_daily.py in the same step.

Target: Auto Cash Up  1T4TtCs-SkBjinToxG45oKksUiPPPIllo2Pqrqbaix6w, tab `Raw Data 2` (header row 1: Venue, Date dd/mm/yyyy, ...),
one row per venue per day, pre-dated years ahead. Same rules as the site KPI sheets (writer.py):
  * NEVER appends: a value only goes into the row that already carries that venue and date.
  * FILL blank or zero cells only; a figure somebody typed is left alone (DIFFERS, reported) unless CASHUP_OVERWRITE=1;
    a formula cell is never written.
  * CASHUP_MODE=plan (default) writes nothing to Auto Cash Up, only the plan to the KPI Auto tab `CashUp_Plan`; apply writes.
Field map (Raw Data 2 header <- Kobas_Daily column):
  Sit In (£) <- Sit in | Delivery (Gross £) <- Delivery | Tips (£) <- Tips | Actual (£) <- Actual | Actual Total Labour (£) <- Hours work Cost
  Actual Total Hours <- Hours Used | No. Of Customers <- Covers | Total Waste (£) <- Cost of Waste | Drinks % | Sushi % | Sides %
  Food Cost <- Food Cost Actual | Average Spend = Actual / Covers | Wages/Revenue (%) = Hours work Cost / Actual
The three Daily Z Reports Script sheets are probed for access and their tab names logged (tab `Z_Sheets`), nothing is written there.
Sheets not shared with the service account are reported as NO ACCESS (shared as Editor with the account in the GitHub secret)."""
import os, re, json, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import gretry  # noqa: retries 429/5xx

AUTO = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
CASHUP = os.environ.get('CASHUP_SHEET', '1T4TtCs-SkBjinToxG45oKksUiPPPIllo2Pqrqbaix6w')
CASHUP_TAB = os.environ.get('CASHUP_TAB', 'Raw Data 2')
Z_SHEETS = {'Daily Z Reports Script Maki 1 - 10, MAF1&2': '1iVhns9T33UxT1U5rfHi9obXMPYxAIhidmMaE4D8KxaM',
            'Daily Z Reports Script Maki 11 - 18': '1BcE63ghGb97SuZ6DoJaPcuMtUqmEWBNZuqjABgG7BT4',
            'Daily Z Reports Script M7, M8, Franchises': '1tuZJIfq3nmmmP9kqG7uzKryruKvCVUsczjjQPvBxs4k'}
MODE = os.environ.get('CASHUP_MODE', 'plan').strip().lower()
OVERWRITE = os.environ.get('CASHUP_OVERWRITE') == '1'
d0 = datetime.date.fromisoformat(os.environ.get('DATE_FROM') or '2026-09-28')
d1 = datetime.date.fromisoformat(os.environ.get('DATE_TO') or '2026-10-21')
# Raw Data 2 venue label (trimmed) -> Kobas_Daily site code
VENUE = {'Maki 1': 'M1', 'Maki 3': 'M3', 'Maki 6': 'M6', 'Maki 7': 'M7', 'Maki 8': 'M8', 'Maki 9': 'M9', 'Maki 10': 'M10', 'Maki 11': 'M11',
         'Maki 12': 'M12', 'Maki 13': 'M13', 'Maki 14': 'M14', 'Maki 15': 'M15', 'Maki 16': 'M16', 'Maki 17': 'M17', 'Maki 18': 'M18',
         'Maki 19': 'M19', 'Maki 20': 'M20', 'Maki 21': 'M21', 'Maki Nori': 'NORI', 'Ikigai 2': 'IKI2'}
# Raw Data 2 header (trimmed, lower) -> Kobas_Daily column, or a derived rule
FIELDS = {'sit in (£)': 'Sit in', 'delivery (gross £)': 'Delivery', 'tips (£)': 'Tips', 'actual (£)': 'Actual',
          'actual total labour (£)': 'Hours work Cost', 'actual total hours': 'Hours Used', 'no. of customers': 'Covers',
          'total waste (£)': 'Cost of Waste', 'drinks %': 'Drinks %', 'sushi %': 'Sushi %', 'sides %': 'Sides %', 'food cost': 'Food Cost Actual',
          'average spend': '=avg', 'wages/revenue (%)': '=wage'}
PCT = {'drinks %', 'sushi %', 'sides %', 'wages/revenue (%)'}
TOL = {'actual total hours': 0.051, 'no. of customers': 0.5, 'drinks %': 0.5, 'sushi %': 0.5, 'sides %': 0.5, 'wages/revenue (%)': 0.5, 'average spend': 0.05}

cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()

def num(s):
    s = re.sub(r'[£,%\s]', '', str(s or ''))
    if s in ('', '-'): return None
    try: return float(s)
    except ValueError: return None
def pdate(s):
    s = str(s).strip()
    for f in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y'):
        try: return datetime.datetime.strptime(s, f).date()
        except ValueError: pass
    return None
def a1col(i):
    s = ''; i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s
def put(tab, data, extra_cols=5):
    have = {x['properties']['title']: x['properties'] for x in svc.get(spreadsheetId=AUTO, fields='sheets.properties').execute()['sheets']}
    w = max(len(r) for r in data); data = [[('' if c is None else c) for c in r] + [''] * (w - len(r)) for r in data]
    if tab not in have:
        svc.batchUpdate(spreadsheetId=AUTO, body={'requests': [{'addSheet': {'properties': {'title': tab,
            'gridProperties': {'rowCount': len(data) + 10, 'columnCount': max(w, extra_cols)}}}}]}).execute()
    else:
        g = have[tab]['gridProperties']
        svc.batchUpdate(spreadsheetId=AUTO, body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': have[tab]['sheetId'],
            'gridProperties': {'rowCount': max(g['rowCount'], len(data) + 10), 'columnCount': max(g['columnCount'], w)}},
            'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
        svc.values().clear(spreadsheetId=AUTO, range=f"'{tab}'").execute()
    svc.values().update(spreadsheetId=AUTO, range=f"'{tab}'!A1", valueInputOption='RAW', body={'values': data}).execute()
    print('wrote', tab, len(data), flush=True)

# ---- Z sheets: access probe only ----
zrows = [['sheet', 'id', 'access', 'tabs']]
for name, sid in Z_SHEETS.items():
    try:
        tabs = [s['properties']['title'] for s in svc.get(spreadsheetId=sid, fields='sheets.properties.title').execute()['sheets']]
        zrows.append([name, sid, 'OK', ' | '.join(tabs)[:2000]]); print('Z sheet OK:', name, len(tabs), 'tabs', flush=True)
    except Exception as e:
        zrows.append([name, sid, 'NO ACCESS', str(e)[:300]]); print('Z sheet NO ACCESS:', name, str(e)[:120], flush=True)
put('Z_Sheets', zrows)

# ---- Kobas side ----
kob = {}
_kd = svc.values().get(spreadsheetId=AUTO, range="'Kobas_Daily'").execute().get('values', [])
for r in _kd[1:]:
    for i, h in enumerate(_kd[0]):
        if i >= 2 and i < len(r) and num(r[i]) is not None: kob[(r[1], r[0], h)] = num(r[i])
def kobas(site, day, field):
    if field == '=avg':
        a, c = kob.get((site, day, 'Actual')), kob.get((site, day, 'Covers'))
        return round(a / c, 2) if a and c else None
    if field == '=wage':
        a, l = kob.get((site, day, 'Actual')), kob.get((site, day, 'Hours work Cost'))
        return round(100 * l / a, 2) if a and l is not None else None
    v = kob.get((site, day, field))
    return None if v is None else round(v, 2)

# ---- Auto Cash Up: Raw Data 2 ----
plan = [['venue', 'site', 'row', 'date', 'field', 'cell', 'sheet', 'kobas', 'diff', 'action']]
summary = [['mode', MODE, 'overwrite', OVERWRITE, 'tab', CASHUP_TAB, 'range', d0.isoformat(), d1.isoformat()]]
ok = True
try:
    tabs = [s['properties']['title'] for s in svc.get(spreadsheetId=CASHUP, fields='sheets.properties.title').execute()['sheets']]
except Exception as e:
    summary.append(['NO ACCESS', 'Auto Cash Up not shared with the service account', str(e)[:300]]); ok = False
    print('Auto Cash Up NO ACCESS:', str(e)[:200], flush=True)
if ok:
    tab = next((t for t in tabs if t.strip().lower() == CASHUP_TAB.lower()), None)
    if not tab:
        summary.append(['TAB MISSING', CASHUP_TAB, ' | '.join(tabs)[:1500]]); ok = False
if ok:
    head = [str(c).strip().lower() for c in (svc.values().get(spreadsheetId=CASHUP, range=f"'{tab}'!1:1").execute().get('values') or [[]])[0]]
    cols = {}
    for f in FIELDS:
        hits = [i for i, h in enumerate(head) if h == f]
        if len(hits) == 1: cols[f] = hits[0]
        else: plan.append(['', '', '', '', f, '', 'COLUMN NOT FOUND' if not hits else 'DUPLICATE HEADER', '', '', 'NO COLUMN'])
    ab = svc.values().get(spreadsheetId=CASHUP, range=f"'{tab}'!A:B", valueRenderOption='FORMATTED_VALUE').execute().get('values', [])
    rows = []   # (row index, site, date)
    for i, r in enumerate(ab[1:], start=1):
        v = str(r[0]).strip() if r else ''
        d = pdate(r[1]) if len(r) > 1 else None
        if v in VENUE and d and d0 <= d <= d1: rows.append((i, VENUE[v], d))
    seen = {(s, d) for _, s, d in rows}
    for s in VENUE.values():
        d = d0
        while d <= d1:
            if (s, d) not in seen and kobas(s, d.isoformat(), 'Actual') is not None:
                plan.append(['', s, '', d.isoformat(), '', '', '', '', '', 'NO ROW'])
            d += datetime.timedelta(1)
    # read the in-range rows in contiguous runs (values + formulas)
    runs = []
    for i, s, d in sorted(rows):
        if runs and i == runs[-1][1] + 1: runs[-1][1] = i
        else: runs.append([i, i])
    vals, form = {}, {}
    last = a1col(max(cols.values())) if cols else 'A'
    for lo, hi in runs:
        fv = svc.values().get(spreadsheetId=CASHUP, range=f"'{tab}'!A{lo + 1}:{last}{hi + 1}", valueRenderOption='FORMATTED_VALUE').execute().get('values', [])
        ff = svc.values().get(spreadsheetId=CASHUP, range=f"'{tab}'!A{lo + 1}:{last}{hi + 1}", valueRenderOption='FORMULA').execute().get('values', [])
        for j in range(hi - lo + 1):
            vals[lo + j] = fv[j] if j < len(fv) else []
            form[lo + j] = ff[j] if j < len(ff) else []
    writes = []
    for i, s, d in rows:
        for f, src in FIELDS.items():
            c = cols.get(f)
            if c is None: continue
            k = kobas(s, d.isoformat(), src)
            cur = vals[i][c] if c < len(vals[i]) else ''
            raw = form[i][c] if c < len(form[i]) else ''
            cv = num(cur)
            if f in PCT and cv is not None and '%' not in str(cur) and 0 < abs(cv) <= 1: cv *= 100
            cell = f'{a1col(c)}{i + 1}'
            if k is None: act = 'NO KOBAS'
            elif isinstance(raw, str) and raw.startswith('='): act = 'FORMULA'
            elif cv is not None and abs(cv - k) <= TOL.get(f, 0.005): act = 'MATCH'
            elif cv is None or cv == 0: act = 'FILL'
            else: act = 'DIFFERS'
            plan.append([ab[i][0] if ab[i] else '', s, i + 1, d.isoformat(), f, cell, cur, k, round(k - cv, 2) if k is not None and cv is not None else '', act])
            if MODE == 'apply' and k is not None and (act == 'FILL' or (act == 'DIFFERS' and OVERWRITE)):
                wv = f'{k}%' if f in PCT else (int(round(k)) if f == 'no. of customers' else k)
                writes.append({'range': f"'{tab}'!{cell}", 'values': [[wv]]})
    if MODE == 'apply':
        for b in range(0, len(writes), 500):
            svc.values().batchUpdate(spreadsheetId=CASHUP, body={'valueInputOption': 'USER_ENTERED', 'data': writes[b:b + 500]}).execute()
        summary.append(['cells written', len(writes)])
    agg = {}
    for r in plan[1:]: agg[(r[4], r[9])] = agg.get((r[4], r[9]), 0) + 1
    summary += [['field', 'action', 'cells']] + [list(k) + [v] for k, v in sorted(agg.items())]
    print('Auto Cash Up', CASHUP_TAB, d0, '..', d1, 'mode', MODE, 'rows in range', len(rows), 'writes', len(writes) if MODE == 'apply' else 'none (plan)', flush=True)
    for (f, a), n in sorted(agg.items()): print(f'  {f:24} {a:14} {n}', flush=True)
put('CashUp_Plan', plan)
put('CashUp_Summary', summary)
if not ok: raise SystemExit('Auto Cash Up feed: ' + str(summary[1][:2]))
