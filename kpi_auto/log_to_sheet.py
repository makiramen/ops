"""Write the step's console output (stdout+stderr of to_sheet.py and kpi_sheets.py, incl. any traceback) to the
Run_Log tab of the KPI Auto sheet, so a failed run can be diagnosed without downloading the GitHub log.
Usage: log_to_sheet.py LOGFILE [LOGFILE...]"""
import os, sys, json, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()
rows = [['file', 'line'], ['written', datetime.datetime.utcnow().isoformat() + 'Z'],
        ['run', os.environ.get('GITHUB_RUN_ID', '')]]
for f in sys.argv[1:]:
    try: txt = open(f, encoding='utf-8', errors='replace').read()
    except OSError as e: txt = f'(missing: {e})'
    for line in txt.splitlines()[-2000:]: rows.append([os.path.basename(f), line[:4000]])
have = {s['properties']['title'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties.title').execute()['sheets']}
if 'Run_Log' not in have:
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': 'Run_Log',
        'gridProperties': {'rowCount': len(rows) + 100, 'columnCount': 5}}}}]}).execute()
else:
    svc.values().clear(spreadsheetId=SHEET, range="'Run_Log'").execute()
svc.values().update(spreadsheetId=SHEET, range="'Run_Log'!A1", valueInputOption='RAW', body={'values': rows}).execute()
print('wrote Run_Log', len(rows), flush=True)
