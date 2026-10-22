"""Copy each site's KPI sheet rows (Script Data and DAY (Input)) for the pull range into the KPI Auto sheet (22/10/2026),
so the October reconciliation can compare them with the Kobas pull. Uses the same service account as to_sheet.py;
a site sheet not shared with it is listed as NO ACCESS. Tabs written: KPI_Script, KPI_Day (site, tab, row number, raw cells)."""
import os, re, json, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sites import SITES
d0 = datetime.date.fromisoformat(os.environ.get('DATE_FROM') or '2026-09-28')
d1 = datetime.date.fromisoformat(os.environ.get('DATE_TO') or '2026-10-21')
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()
def pdate(s):
    s = str(s).strip()
    for f in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y', '%a %d/%m/%Y', '%d %b %Y', '%d-%b-%Y'):
        try: return datetime.datetime.strptime(s, f).date()
        except ValueError: pass
    return None
out = {'Script Data': [['site', 'tab', 'row', 'cells...']], 'DAY (Input)': [['site', 'tab', 'row', 'cells...']]}
for site, sid in SITES.items():
    try:
        tabs = [s['properties']['title'] for s in svc.get(spreadsheetId=sid, fields='sheets.properties.title').execute()['sheets']]
    except Exception as e:
        for k in out: out[k].append([site, 'NO ACCESS', '', str(e)[:300]])
        print(site, 'NO ACCESS', str(e)[:200], flush=True)
        continue
    for want in out:
        t = next((x for x in tabs if x.strip().lower() == want.lower()), None) or next((x for x in tabs if x.lower().startswith(want.lower())), None)
        if not t: out[want].append([site, 'TAB MISSING', '', ' | '.join(tabs)[:2000]]); continue
        try:
            rows = svc.values().get(spreadsheetId=sid, range=f"'{t}'", valueRenderOption='FORMATTED_VALUE').execute().get('values', [])
        except Exception as e:
            out[want].append([site, 'READ FAILED', '', str(e)[:300]]); continue
        for i, r in enumerate(rows):
            keep = i < 4 or any((d := pdate(c)) and d0 <= d <= d1 for c in r[:4])
            if keep: out[want].append([site, t, i + 1] + [str(c)[:500] for c in r])
        print(site, t, 'rows', len(rows), flush=True)
have = {s['properties']['title']: s['properties'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets']}
for want, tab in (('Script Data', 'KPI_Script'), ('DAY (Input)', 'KPI_Day')):
    data = out[want]; w = max(len(r) for r in data); data = [r + [''] * (w - len(r)) for r in data]
    if tab not in have:
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': tab,
            'gridProperties': {'rowCount': len(data) + 10, 'columnCount': w}}}}]}).execute()
    else:
        g = have[tab]['gridProperties']
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': have[tab]['sheetId'],
            'gridProperties': {'rowCount': max(g['rowCount'], len(data) + 10), 'columnCount': max(g['columnCount'], w)}},
            'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
        svc.values().clear(spreadsheetId=SHEET, range=f"'{tab}'").execute()
    svc.values().update(spreadsheetId=SHEET, range=f"'{tab}'!A1", valueInputOption='RAW', body={'values': data}).execute()
    print('wrote', tab, len(data), flush=True)
