"""Push the daily sales forecast from each site's KPI sheet into Kobas (Rotas > Sales Budgets), rolling 28 days.

Source: DAY (Input) tab of every site KPI sheet, target = Sit In target + Delivery Gross target (cols C + D,
the 'Targets' block). Michael's ruling 23/10/2026: 25 Dec is skipped (never written; Kobas stores 0 for a blank
day on a new week and an existing 25 Dec value is left as it is).

Kobas holds budgets as one row per venue per week (Mon..Sun):
  new week      POST /admin/budgets/index.php multipart (budgetfile=CSV startdate,venueid,mon..sun; m=save)
                -> re-uploading an existing week is silently ignored, so existing weeks go through the PUT below
  existing week PUT  /admin/budgets/getupdatesbudget.php  form id, mon..sun  (returns the saved row as json)
  read          GET  /admin/budgets/  (html table, spans id="Mon_<id>" data-raw="9250.00", venue by name)
Only days inside [today, today+27] (UK) are changed; days before today and after the window keep the Kobas value
(a brand-new week takes the sheet value for its out-of-window days, since Kobas needs all seven).

Env: KOBAS_* (keyline bot), GOOGLE_SERVICE_ACCOUNT_JSON, FORECAST_MODE=plan|apply (default plan), FORECAST_DAYS=28,
FORECAST_SITES=comma list (default all). Writes the Forecast_Push tab of the KPI Auto sheet."""
import os, re, sys, json, csv, io, html, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kobas_pull import Kobas, BASE
from sites import SITES
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gretry  # noqa: retries 429/5xx

SHEET = os.environ.get('KPI_AUTO_SHEET', '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y')
VENUE = {'M1': 3, 'M3': 5, 'M6': 43, 'M7': 9, 'M8': 47, 'M9': 2, 'M10': 13, 'M11': 24, 'M12': 27, 'M13': 28, 'M14': 37,
         'M15': 41, 'M16': 42, 'M17': 49, 'M18': 51, 'M19': 58, 'M20': 60, 'M21': 61, 'NORI': 57, 'IKI2': 7}
DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
SKIP = {(12, 25)}  # month, day: never written
MODE = os.environ.get('FORECAST_MODE', 'plan').strip().lower()
N = int(os.environ.get('FORECAST_DAYS') or 28)
today = datetime.datetime.now(ZoneInfo('Europe/London')).date()
w0, w1 = today, today + datetime.timedelta(N - 1)
want_sites = [s.strip().upper() for s in (os.environ.get('FORECAST_SITES') or '').split(',') if s.strip()] or list(SITES)


def pdate(v):
    if isinstance(v, (int, float)):  # sheets serial
        return datetime.date(1899, 12, 30) + datetime.timedelta(int(v))
    s = str(v).strip()
    for f in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y'):
        try: return datetime.datetime.strptime(s, f).date()
        except ValueError: pass
    return None


def num(v):
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r'[£,\s]', '', str(v or ''))
    try: return float(s)
    except ValueError: return None


# ---------- 1) sheet targets ----------
cred = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                                             scopes=['https://www.googleapis.com/auth/spreadsheets'])
svc = build('sheets', 'v4', credentials=cred, cache_discovery=False).spreadsheets()
target = {}   # site -> {date: value}
notes = []
for site in want_sites:
    sid = SITES[site]
    try:
        tabs = [s['properties']['title'] for s in svc.get(spreadsheetId=sid, fields='sheets.properties.title').execute()['sheets']]
        tab = next((t for t in tabs if t.strip().lower().startswith('day (input)')), None)
        if not tab: notes.append([site, 'NO DAY (Input) TAB']); continue
        rows = svc.values().get(spreadsheetId=sid, range=f"'{tab}'!A1:D", valueRenderOption='UNFORMATTED_VALUE',
                                dateTimeRenderOption='FORMATTED_STRING').execute().get('values', [])
    except Exception as e:
        notes.append([site, 'READ FAILED ' + str(e)[:200]]); continue
    hdr = next((i for i, r in enumerate(rows[:10]) if r and str(r[0]).strip().lower() == 'date'), None)
    if hdr is None or len(rows[hdr]) < 4 or 'sit in' not in str(rows[hdr][2]).lower() or 'delivery' not in str(rows[hdr][3]).lower():
        notes.append([site, 'HEADER NOT AS EXPECTED: ' + ' | '.join(map(str, rows[hdr] if hdr is not None else rows[:3]))[:300]]); continue
    t = {}
    for r in rows[hdr + 1:]:
        d = pdate(r[0]) if r else None
        if not d or d < w0 - datetime.timedelta(7) or d > w1 + datetime.timedelta(7): continue
        a, b = (num(r[2]) if len(r) > 2 else None), (num(r[3]) if len(r) > 3 else None)
        if a is None and b is None: continue
        t[d] = round((a or 0) + (b or 0), 2)
    target[site] = t
    print(site, tab, 'targets in window', sum(1 for d in t if w0 <= d <= w1), flush=True)

# ---------- 2) Kobas current budgets ----------
k = Kobas(); assert k.login(), 'Kobas login failed'
vname = {v['name'].strip(): v['id'] for v in k.gj('/data/venue', params={'fields': 'id,name'})}
MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def kobas_rows():
    p = k.s.get(BASE + '/admin/budgets/', timeout=90)
    assert p.status_code == 200 and 'Sales Budgets' in p.text, f'budgets page {p.status_code}'
    out = {}
    for tr in re.findall(r'<tr[^>]*class="tabledata"[^>]*>(.*?)</tr>', p.text, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
        if len(tds) < 9: continue
        name = html.unescape(re.sub(r'<[^>]+>', '', tds[0])).strip()
        m = re.match(r'(\d+)\w*\s+(\w{3})\s+(\d{4})', re.sub(r'<[^>]+>', '', tds[1]).strip())
        raw = {d.lower(): float(v) for v, d in re.findall(r'data-raw="([\d.\-]+)" id="(Mon|Tue|Wed|Thu|Fri|Sat|Sun)_\d+"', tr)}
        bid = re.search(r'id="Mon_(\d+)"', tr)
        if not (m and bid and name in vname): continue
        wk = datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
        out[(vname[name], wk)] = {'id': int(bid.group(1)), **raw}
    return out


have = kobas_rows()
print('kobas budget rows', len(have), flush=True)

# ---------- 3) plan ----------
mondays = sorted({w0 - datetime.timedelta(w0.weekday()) + datetime.timedelta(7 * i) for i in range((N + 13) // 7 + 1)})
mondays = [m for m in mondays if m <= w1]
log = [['site', 'venue', 'week', 'day', 'date', 'sheet target', 'kobas before', 'kobas after', 'action']]
new_csv, puts = [], []
for site in want_sites:
    if site not in target: continue
    vid = VENUE[site]; t = target[site]
    for mon in mondays:
        cur = have.get((vid, mon))
        vals, changed = {}, False
        for i, dn in enumerate(DAYS):
            d = mon + datetime.timedelta(i)
            before = cur.get(dn) if cur else None
            inwin = w0 <= d <= w1
            skip = (d.month, d.day) in SKIP
            if cur:
                v = before if (not inwin or skip or t.get(d) is None) else t[d]
            else:
                v = None if skip else t.get(d)
            vals[dn] = v
            act = ('skip 25 Dec' if skip else 'no sheet value' if t.get(d) is None else
                   'outside window' if not inwin and cur else
                   'unchanged' if cur and before is not None and abs(before - v) < 0.005 else 'set')
            if act == 'set': changed = True
            log.append([site, vid, mon.isoformat(), dn, d.isoformat(), t.get(d, ''), '' if before is None else before,
                        '' if v is None else v, act if (cur or act != 'set') else 'set (new week)'])
        if not cur:
            if any(vals[dn] is not None for dn in DAYS):
                new_csv.append([mon.isoformat(), vid] + ['' if vals[dn] is None else f'{vals[dn]:.2f}' for dn in DAYS])
        elif changed:
            puts.append({'id': cur['id'], **{dn: f'{(vals[dn] or 0):.2f}' for dn in DAYS}, '_site': site, '_wk': mon.isoformat()})
print(f'window {w0}..{w1} mode={MODE}: {len(new_csv)} new weeks, {len(puts)} week updates', flush=True)

# ---------- 4) apply ----------
errors = 0
if MODE == 'apply':
    if new_csv:
        buf = io.StringIO(); w = csv.writer(buf, lineterminator='\n')
        w.writerow(['startdate', 'venueid'] + DAYS); w.writerows(new_csv)
        r = k.s.post(BASE + '/admin/budgets/index.php', data={'m': 'save', 'save': ' Save Budget '},
                     files={'budgetfile': ('forecast.csv', buf.getvalue(), 'text/csv')}, headers={'X-Requested-With': None}, timeout=120)
        added = re.findall(r'Budget for (.*?) W/C (.*?) added', r.text)
        print('upload', r.status_code, 'added', len(added), 'of', len(new_csv), flush=True)
        if len(added) != len(new_csv): errors += 1; print('UPLOAD SHORT: expected', len(new_csv), flush=True)
    for p in puts:
        body = {kk: v for kk, v in p.items() if not kk.startswith('_')}
        r = k.s.put(BASE + '/admin/budgets/getupdatesbudget.php', data=body, timeout=60)
        ok = r.status_code == 200 and all(abs(float(r.json().get(dn, -1)) - float(body[dn])) < 0.005 for dn in DAYS)
        if not ok: errors += 1
        print('put', p['_site'], p['_wk'], 'ok' if ok else f'FAILED {r.status_code} {r.text[:200]}', flush=True)
    # read back and verify every in-window day
    after = kobas_rows(); bad = 0
    for site in target:
        for d, v in target[site].items():
            if not (w0 <= d <= w1) or (d.month, d.day) in SKIP: continue
            row = after.get((VENUE[site], d - datetime.timedelta(d.weekday())))
            got = row.get(DAYS[d.weekday()]) if row else None
            if got is None or abs(got - v) >= 0.005:
                bad += 1; print('VERIFY MISMATCH', site, d, 'sheet', v, 'kobas', got, flush=True)
    print('verify: mismatches', bad, flush=True)
    errors += bad

# ---------- 5) Forecast_Push tab ----------
rows = [['run', datetime.datetime.utcnow().isoformat() + 'Z', 'mode', MODE, 'window', f'{w0}..{w1}', '', '', '']] + \
       [['NOTE'] + n + [''] * 7 for n in notes] + log
have_tabs = {s['properties']['title']: s['properties'] for s in svc.get(spreadsheetId=SHEET, fields='sheets.properties').execute()['sheets']}
if 'Forecast_Push' not in have_tabs:
    svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'addSheet': {'properties': {'title': 'Forecast_Push',
        'gridProperties': {'rowCount': len(rows) + 50, 'columnCount': 9}}}}]}).execute()
else:
    g = have_tabs['Forecast_Push']['gridProperties']
    if g['rowCount'] < len(rows) + 10:
        svc.batchUpdate(spreadsheetId=SHEET, body={'requests': [{'updateSheetProperties': {'properties': {
            'sheetId': have_tabs['Forecast_Push']['sheetId'], 'gridProperties': {'rowCount': len(rows) + 50, 'columnCount': 9}},
            'fields': 'gridProperties(rowCount,columnCount)'}}]}).execute()
    svc.values().clear(spreadsheetId=SHEET, range="'Forecast_Push'").execute()
svc.values().update(spreadsheetId=SHEET, range="'Forecast_Push'!A1", valueInputOption='RAW', body={'values': rows}).execute()
print('wrote Forecast_Push', len(rows), 'notes', notes, flush=True)
sys.exit(1 if errors else 0)
