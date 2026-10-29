"""Undo the Auto Cash Up Raw Data 2 feed (29/10/2026). Raw Data 2 is ONE IMPORTRANGE array in A1; the feed's 80
writes into it collapsed the array to #REF! and stopped the daily cash-up. This clears EXACTLY the cells the feed
wrote (the FILL rows of the CashUp_Plan tab in the KPI Auto workbook) and nothing else. Dry run unless UNDO_APPLY=1."""
import json, os, re
from google.oauth2 import service_account
from googleapiclient.discovery import build

AUTO = '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y'
CASHUP = '1T4TtCs-SkBjinToxG45oKksUiPPPIllo2Pqrqbaix6w'
TAB = 'Raw Data 2'
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()

plan = svc.values().get(spreadsheetId=AUTO, range="'CashUp_Plan'").execute().get('values', [])
fill = [r for r in plan[1:] if len(r) > 9 and r[9] == 'FILL' and re.fullmatch(r'[A-Z]+\d+', r[5] or '')]
cells = sorted({r[5] for r in fill})
# a cell that held a typed 0 (cur non-empty) goes back to that exact text; a blank goes back to blank
prev = {r[5]: (r[6] if len(r) > 6 else '') for r in fill}
# every FILL cell sits inside the IMPORTRANGE array: its 'cur' value was the array's own output, never a typed value.
# Writing anything back blocks the array again (AD1368, 14:09). Clear them all.
restore = []
clear = [f"'{TAB}'!{c}" for c in cells]
print('plan rows', len(plan) - 1, 'FILL cells', len(cells), cells, flush=True)
print(f"::notice title=undo::plan rows {len(plan)-1}, FILL cells {len(cells)}: {' '.join(cells)[:900]}", flush=True)
a1 = svc.values().get(spreadsheetId=CASHUP, range=f"'{TAB}'!A1").execute().get('values', [['']])[0][0]
print('A1 before:', a1, flush=True); print(f'::notice title=A1 before::{a1}', flush=True)
if os.environ.get('UNDO_APPLY') != '1':
    print('dry run, nothing cleared'); raise SystemExit
if not cells: raise SystemExit('no FILL cells in the plan, nothing to clear')
print('clear', len(clear), 'restore', len(restore), flush=True)
for b in range(0, len(clear), 500): svc.values().batchClear(spreadsheetId=CASHUP, body={'ranges': clear[b:b+500]}).execute()
for b in range(0, len(restore), 500): svc.values().batchUpdate(spreadsheetId=CASHUP, body={'valueInputOption': 'USER_ENTERED', 'data': restore[b:b+500]}).execute()
a1 = svc.values().get(spreadsheetId=CASHUP, range=f"'{TAB}'!A1:C1").execute().get('values', [['']])[0]
print('cleared', len(cells), 'cells. A1:C1 after:', a1, flush=True); print(f'::notice title=after::cleared {len(cells)} cells, A1:C1 now {a1}', flush=True)
if a1 and str(a1[0]).startswith('#'): raise SystemExit('A1 still an error after the clear: ' + str(a1))
