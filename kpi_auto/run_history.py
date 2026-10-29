"""One log line per run (29/10/2026): appends a row to the Run_History tab of the KPI Auto sheet (never cleared, unlike Run_Log)
and, when the run failed, emails Michael the tail of the logs (Gmail SMTP, GMAIL_USER / GMAIL_APP_PASSWORD, the keyline secrets).
Usage: run_history.py ok|FAILED LOGFILE [LOGFILE...]
The line: time (UTC), run id, status, range, mode, write mode, and a one-line summary pulled from the logs
(Kobas_Daily rows, site-sheet cells written, Auto Cash Up cells written, forecast result, NO ACCESS sheets, first traceback line)."""
import os, re, sys, json, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import gretry  # noqa
SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
TO = os.environ.get('KPI_ALERT_TO', 'michael@makiramen.com')
status = sys.argv[1] if len(sys.argv) > 1 else 'unknown'
logs = {}
for f in sys.argv[2:]:
    try: logs[os.path.basename(f)] = open(f, encoding='utf-8', errors='replace').read()
    except OSError: logs[os.path.basename(f)] = '(missing)'
alltxt = '\n'.join(logs.values())
def grab(rx, default=''):
    m = re.search(rx, alltxt, re.M); return m.group(1) if m else default
bits = []
if (v := grab(r'^wrote Kobas_Daily (\d+) rows')): bits.append(f'Kobas_Daily {v} rows')
if (v := grab(r'^DAY \(Input\) plan .*? mode (\w+)')): bits.append(f'site sheets {v}')
if (v := grab(r'^Auto Cash Up .*?writes (\S+)')): bits.append(f'cash-up writes {v}')
if grab(r'^(Auto Cash Up NO ACCESS)'): bits.append('Auto Cash Up NO ACCESS')
if (v := grab(r'^(Z sheet NO ACCESS: .*)$')): bits.append(v[:80])
if (v := grab(r'^(forecast .*)$')): bits.append(v[:80])
if (v := grab(r'^(Traceback[\s\S]*?\n(\w+Error.*|.*Exception.*))$')): bits.append('ERROR: ' + v.splitlines()[-1][:160])
if (v := grab(r'^((?:AssertionError|RuntimeError|HttpError|SystemExit).*)$')) and 'ERROR' not in ' '.join(bits): bits.append('ERROR: ' + v[:160])
row = [datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M') + 'Z', os.environ.get('GITHUB_RUN_ID', ''), status,
       f"{os.environ.get('DATE_FROM', '')}..{os.environ.get('DATE_TO', '')}", os.environ.get('MODE', ''), os.environ.get('WRITE_MODE', ''),
       os.environ.get('CASHUP_MODE', ''), '; '.join(bits)[:1500],
       f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'makiramen/ops')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"]
try:
    cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                                 scopes=['https://www.googleapis.com/auth/spreadsheets'])
    svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()
    have = {s['properties']['title'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties.title').execute()['sheets']}
    if 'Run_History' not in have:
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': 'Run_History', 'gridProperties': {'rowCount': 2000, 'columnCount': 9}}}}]}).execute()
        svc.values().update(spreadsheetId=SHEET, range="'Run_History'!A1", valueInputOption='RAW',
                            body={'values': [['time', 'run', 'status', 'range', 'mode', 'write mode', 'cash-up mode', 'summary', 'log']]}).execute()
    svc.values().append(spreadsheetId=SHEET, range="'Run_History'!A1", valueInputOption='RAW', insertDataOption='INSERT_ROWS', body={'values': [row]}).execute()
    print('Run_History:', ' | '.join(str(c) for c in row), flush=True)
except Exception as e:
    print('Run_History write failed:', str(e)[:300], flush=True)
if status.lower() != 'ok':
    import smtplib, ssl
    from email.message import EmailMessage
    user, pw = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pw):
        print('failure email NOT SENT: GMAIL_USER / GMAIL_APP_PASSWORD missing', flush=True); sys.exit(0)
    m = EmailMessage()
    m['Subject'] = f"kpi-auto FAILED {row[3]} ({'; '.join(bits)[:90] or 'see log'})"
    m['From'] = user; m['To'] = TO
    body = [f"KPI sheet automation run failed.", f"Range {row[3]}, mode {row[4]}, write {row[5]}, cash-up {row[6]}.", f"Summary: {row[7]}", f"Log: {row[8]}",
            f"Run_History / Run_Log: https://docs.google.com/spreadsheets/d/{SHEET}/edit", '']
    for name, txt in logs.items():
        tail = txt.splitlines()[-40:]
        body += [f'--- {name} (last {len(tail)} lines) ---'] + tail + ['']
    m.set_content('\n'.join(body))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=60) as s:
            s.login(user, pw); s.send_message(m)
        print('failure email sent to', TO, flush=True)
    except Exception as e:
        print('failure email NOT SENT:', str(e)[:300], flush=True)
