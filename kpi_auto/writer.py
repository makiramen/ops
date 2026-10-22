"""KPI sheet writer (22/10/2026, Michael). Fills the site KPI sheets from the Kobas pull. Runs after to_sheet.py (reads its
Day_Totals tab) in the same workflow step.

Rules (Michael, 22/10/2026):
  * NEVER appends. A value only goes into a row that already exists in the site sheet and carries that date in its Date column.
  * When the pre-dated rows run out, a new period sheet is created from the template (ROLLOVER below), never a new row.
  * Nothing is overwritten until the automated figures match the sheet (ruling 22/10): default WRITE_MODE=plan writes NOTHING
    to the site sheets, it only writes the plan to the KPI Auto sheet, which doubles as the reconciliation.

Modes (env WRITE_MODE):
  plan   (default) read every site sheet, write Layout + Write_Plan tabs to KPI Auto. No site sheet is touched.
  apply  write only cells whose action is FILL (cell blank or zero, not a formula, field listed in APPLY_FIELDS).
         Cells holding a different non-zero value are left alone unless OVERWRITE=1. Formula cells are never written.

Plan actions, per site / date / field:
  MATCH    sheet already equals Kobas within TOL (default 1.00)
  FILL     sheet cell blank or 0.00, would be written in apply
  DIFFERS  sheet holds another figure: the reconciliation gap, never overwritten unless OVERWRITE=1
  FORMULA  the cell is a formula, never written (the sheet works it out itself)
  NO ROW   the date is not pre-dated in the tab: ROLLOVER needed
  NO KOBAS no Kobas figure for that site/date (pull failed or site shut)

ROLLOVER: needs a template. ROLLOVER_TEMPLATE (env, JSON {site or '*': '<tab name in the site sheet to duplicate>'}).
Until it is set the plan reports 'ROLLOVER NEEDED' with the last pre-dated date and nothing is created. With it set and
WRITE_MODE=apply, the template tab is duplicated inside the same spreadsheet (no Drive copy, so no service-account storage
quota problem), renamed '<tab> from dd-mm-yyyy', and its Date column is re-dated from the day after the last pre-dated row."""
import os, re, json, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sites import SITES

AUTO = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
MODE = os.environ.get('WRITE_MODE', 'plan').strip().lower()
OVERWRITE = os.environ.get('OVERWRITE') == '1'
APPLY_FIELDS = {f.strip().lower() for f in os.environ.get('APPLY_FIELDS', '').split(',') if f.strip()}
TOL = float(os.environ.get('TOL', '1.00'))
TEMPLATE = json.loads(os.environ.get('ROLLOVER_TEMPLATE') or '{}')
d0 = datetime.date.fromisoformat(os.environ.get('DATE_FROM') or '2026-09-28')
d1 = datetime.date.fromisoformat(os.environ.get('DATE_TO') or '2026-10-21')

# Target tab (first one found wins) and field -> Kobas source. Sources are sums of Day_Totals total_gross by mode.
# Script Data is the tab the email skim fills today, so it is the one the automation replaces.
TARGETS = [('Script Data', {'Actual': ['all'], 'Sit in': ['eat-in', 'takeaway'], 'Delivery': ['delivery']})]

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
    s = ''
    i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s

# ---- Kobas side: Day_Totals written by to_sheet.py this run ----
kob = {}
for r in svc.values().get(spreadsheetId=AUTO, range="'Day_Totals'").execute().get('values', [])[1:]:
    if len(r) >= 4 and num(r[3]) is not None: kob[(r[1], r[0], r[2])] = num(r[3])
def kobas(site, day, modes):
    v = [kob.get((site, day, m)) for m in modes]
    return None if all(x is None for x in v) else round(sum(x or 0 for x in v), 2)

layout = [['site', 'tab', 'header row', 'first date', 'last pre-dated date', 'last row', 'days of headroom after DATE_TO',
           'rollover', 'input cols (in range)', 'formula cols (in range)']]
plan = [['site', 'tab', 'row', 'date', 'field', 'cell', 'sheet', 'kobas', 'diff', 'action']]
writes, rollovers = {}, []
for site, sid in SITES.items():
    try:
        tabs = [s['properties'] for s in svc.get(spreadsheetId=sid, fields='sheets.properties').execute()['sheets']]
    except Exception as e:
        layout.append([site, 'NO ACCESS', '', '', '', '', '', '', str(e)[:200], '']); continue
    names = [t['title'] for t in tabs]
    tab = fields = None
    for want, f in TARGETS:
        tab = next((x for x in names if x.strip().lower() == want.lower()), None)
        if tab: fields = f; break
    if not tab:
        layout.append([site, 'NO TARGET TAB', '', '', '', '', '', '', ' | '.join(names)[:1500], '']); continue
    vals = svc.values().get(spreadsheetId=sid, range=f"'{tab}'", valueRenderOption='FORMATTED_VALUE').execute().get('values', [])
    hr = next((i for i, r in enumerate(vals[:10]) if r and str(r[0]).strip().lower() == 'date'), None)
    if hr is None:
        layout.append([site, tab, 'NO HEADER', '', '', '', '', '', '', '']); continue
    head = [str(c).strip().lower() for c in vals[hr]]
    rowof = {}
    for i, r in enumerate(vals[hr + 1:], start=hr + 1):
        d = pdate(r[0]) if r else None
        if d: rowof.setdefault(d, i)
    first, last = (min(rowof), max(rowof)) if rowof else (None, None)
    inr = sorted(i for d, i in rowof.items() if d0 <= d <= d1)
    fcols, icols = set(), set()
    form = {}
    if inr:
        lo, hi = inr[0], inr[-1]
        fr = svc.values().get(spreadsheetId=sid, range=f"'{tab}'!A{lo + 1}:{a1col(len(head) - 1)}{hi + 1}",
                              valueRenderOption='FORMULA').execute().get('values', [])
        for j, r in enumerate(fr):
            for c, v in enumerate(r):
                isf = isinstance(v, str) and v.startswith('=')
                form[(lo + j, c)] = isf
                (fcols if isf else icols).add(c)
    headroom = (last - d1).days if last else ''
    need = not last or last < d1
    layout.append([site, tab, hr + 1, first.isoformat() if first else '', last.isoformat() if last else '',
                   max(rowof.values()) + 1 if rowof else '', headroom, 'ROLLOVER NEEDED' if need else '',
                   ', '.join(vals[hr][c].strip() for c in sorted(icols) if c < len(vals[hr])),
                   ', '.join(vals[hr][c].strip() for c in sorted(fcols - icols) if c < len(vals[hr]))])
    if need: rollovers.append((site, sid, tab, tabs, last))
    for field, modes in fields.items():
        c = next((i for i, h in enumerate(head) if h == field.lower()), None)
        if c is None:
            plan.append([site, tab, '', '', field, '', 'COLUMN NOT FOUND', '', '', 'NO COLUMN']); continue
        d = d0
        while d <= d1:
            k = kobas(site, d.isoformat(), modes)
            i = rowof.get(d)
            if i is None:
                plan.append([site, tab, '', d.isoformat(), field, '', '', k, '', 'NO ROW']); d += datetime.timedelta(1); continue
            cur = vals[i][c] if c < len(vals[i]) else ''
            cv = num(cur)
            cell = f'{a1col(c)}{i + 1}'
            if k is None: act = 'NO KOBAS'
            elif form.get((i, c)): act = 'FORMULA'
            elif cv is not None and abs(cv - k) <= TOL: act = 'MATCH'
            elif cv is None or cv == 0: act = 'FILL'
            else: act = 'DIFFERS'
            plan.append([site, tab, i + 1, d.isoformat(), field, cell, cur, k,
                         round(k - cv, 2) if k is not None and cv is not None else '', act])
            if MODE == 'apply' and k is not None and field.lower() in APPLY_FIELDS and \
                    (act == 'FILL' or (act == 'DIFFERS' and OVERWRITE)):
                writes.setdefault(sid, []).append({'range': f"'{tab}'!{cell}", 'values': [[k]]})
            d += datetime.timedelta(1)

# ---- apply ----
done = [['site sheet', 'cells written']]
if MODE == 'apply':
    for sid, data in writes.items():
        for i in range(0, len(data), 500):
            svc.values().batchUpdate(spreadsheetId=sid, body={'valueInputOption': 'USER_ENTERED', 'data': data[i:i + 500]}).execute()
        done.append([sid, len(data)])
    for site, sid, tab, tabs, last in rollovers:
        tpl = TEMPLATE.get(site) or TEMPLATE.get('*')
        src = next((t for t in tabs if tpl and t['title'] == tpl), None)
        if not src:
            done.append([site, f'ROLLOVER NEEDED, no template tab set ({tpl or "ROLLOVER_TEMPLATE empty"})']); continue
        start = (last or d0) + datetime.timedelta(1)
        name = f"{tab} from {start:%d-%m-%Y}"
        if any(t['title'] == name for t in tabs): done.append([site, f'rollover tab {name} already exists']); continue
        new = svc.batchUpdate(spreadsheetId=sid, body={'requests': [{'duplicateSheet': {'sourceSheetId': src['sheetId'],
              'newSheetName': name, 'insertSheetIndex': len(tabs)}}]}).execute()['replies'][0]['duplicateSheet']['properties']
        tv = svc.values().get(spreadsheetId=sid, range=f"'{name}'!A1:A").execute().get('values', [])
        hr = next((i for i, r in enumerate(tv[:10]) if r and str(r[0]).strip().lower() == 'date'), 0)
        n = max(len(tv) - hr - 1, 0)
        dates = [[(start + datetime.timedelta(j)).strftime('%d/%m/%Y')] for j in range(n)]
        if dates:
            svc.values().update(spreadsheetId=sid, range=f"'{name}'!A{hr + 2}", valueInputOption='USER_ENTERED',
                                body={'values': dates}).execute()
        done.append([site, f'rollover tab {name} created, {n} rows dated from {start:%d/%m/%Y}'])

# ---- write the plan to the KPI Auto sheet ----
have = {s['properties']['title']: s['properties'] for s in svc.get(spreadsheetId=AUTO, fields='sheets.properties').execute()['sheets']}
summary = {}
for r in plan[1:]: summary[(r[0], r[4], r[9])] = summary.get((r[0], r[4], r[9]), 0) + 1
plan_sum = [['mode', MODE, 'overwrite', OVERWRITE, 'apply fields', ','.join(sorted(APPLY_FIELDS)) or '(none)'],
            ['site', 'field', 'action', 'days']] + [list(k) + [v] for k, v in sorted(summary.items())]
for tab, data in (('Layout', layout), ('Write_Plan', plan), ('Write_Summary', plan_sum + [[]] + done)):
    w = max(len(r) for r in data); data = [[('' if c is None else c) for c in r] + [''] * (w - len(r)) for r in data]
    if tab not in have:
        svc.batchUpdate(spreadsheetId=AUTO, body={'requests': [{'addSheet': {'properties': {'title': tab,
            'gridProperties': {'rowCount': len(data) + 10, 'columnCount': max(w, 5)}}}}]}).execute()
    else:
        g = have[tab]['gridProperties']
        svc.batchUpdate(spreadsheetId=AUTO, body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': have[tab]['sheetId'],
            'gridProperties': {'rowCount': max(g['rowCount'], len(data) + 10), 'columnCount': max(g['columnCount'], w)}},
            'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
        svc.values().clear(spreadsheetId=AUTO, range=f"'{tab}'").execute()
    svc.values().update(spreadsheetId=AUTO, range=f"'{tab}'!A1", valueInputOption='RAW', body={'values': data}).execute()
    print('wrote', tab, len(data), flush=True)
