"""AM CC notes ingest (offline route, 07/10/2026).
A cloud Claude task writes am_cc_notes_wc_<MONDAY>.json into the Drive folder "AM CC notes inbox"
(shared with the site-cc-reader service account). This script, run by GitHub Actions, reads every new
file, patches sites[CODE].notes into data/<CODE>_wc_<MONDAY>.json and data/all_sites_wc_<MONDAY>.json,
and records what it ingested in data/_notes_ingest_state.json. No laptop involved.

File format: {"week":"YYYY-MM-DD","mode":"replace"|"merge","sites":{"M7":{"issues":[..],"actions":[..],
"carryover":[..],"empty":false,"docId":"..","source":".."}, ...}}
replace: the site's notes become exactly the file's notes (an empty:true site keeps any existing content).
merge: new lines are appended, duplicates skipped; existing lines are never removed.
Local test: python3 ingest_am_notes.py --data <dir with *_wc_*.json> --file notes.json
"""
import argparse, datetime, io, json, os, re, sys

KEYS = ('issues', 'actions', 'carryover')
DASH = re.compile(r'\s*[‒–—―]\s*')

def clean(s):
    s = DASH.sub(', ', str(s)).strip()
    return re.sub(r'\s{2,}', ' ', s)

def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def dumps_like(raw, obj):
    pretty = json.dumps(obj, indent=2, ensure_ascii=True)
    return pretty + ('\n' if raw.endswith('\n') else '')

def drive():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    cred = service_account.Credentials.from_service_account_info(
        json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
        scopes=['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive', 'v3', credentials=cred, cache_discovery=False)

def drive_files(dv):
    q = "name contains 'am_cc_notes_wc_' and trashed = false"
    r = dv.files().list(q=q, fields='files(id,name,modifiedTime)', orderBy='modifiedTime',
                        pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    return r.get('files', [])

def drive_get(dv, fid):
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO(); dl = MediaIoBaseDownload(buf, dv.files().get_media(fileId=fid))
    done = False
    while not done: _, done = dl.next_chunk()
    return json.loads(buf.getvalue().decode('utf-8'))

def validate(doc):
    wk = doc.get('week', '')
    d = datetime.date.fromisoformat(wk)
    if d.weekday() != 0: raise ValueError(f'week {wk} is not a Monday')
    if doc.get('mode', 'merge') not in ('replace', 'merge'): raise ValueError('mode must be replace or merge')
    if not isinstance(doc.get('sites'), dict) or not doc['sites']: raise ValueError('no sites')
    for code, n in doc['sites'].items():
        for k in KEYS:
            if not isinstance(n.get(k, []), list) or not all(isinstance(x, str) for x in n.get(k, [])):
                raise ValueError(f'{code}.{k} must be a list of strings')
    return wk

def merge_notes(old, new, mode):
    old = old or {}
    inc = {k: [clean(x) for x in new.get(k, []) if str(x).strip()] for k in KEYS}
    has_new = any(inc[k] for k in KEYS)
    if not has_new:
        return old if any(old.get(k) for k in KEYS) else {**{k: [] for k in KEYS}, 'empty': True,
                'docId': new.get('docId', old.get('docId', '')), 'source': clean(new.get('source', old.get('source', 'No notes filed for this week.')))}
    if mode == 'replace' or not any(old.get(k) for k in KEYS):
        out = {k: inc[k] for k in KEYS}
    else:
        out = {}
        for k in KEYS:
            seen = {norm(x) for x in old.get(k, [])}
            out[k] = list(old.get(k, [])) + [x for x in inc[k] if norm(x) not in seen and not seen.add(norm(x))]
    out['empty'] = False
    out['docId'] = new.get('docId') or old.get('docId', '')
    src_new = clean(new.get('source', ''))
    src_old = old.get('source', '')
    out['source'] = src_new if (mode == 'replace' or not src_old) else (src_old if src_new in src_old else (src_old + ' Top up: ' + src_new).strip())
    return out

def apply(doc, data_dir):
    wk = validate(doc); mode = doc.get('mode', 'merge')
    allp = os.path.join(data_dir, f'all_sites_wc_{wk}.json')
    if not os.path.exists(allp): raise FileNotFoundError(f'{allp} missing (week not registered yet)')
    changed = []; report = []
    araw = open(allp).read(); A = json.loads(araw)
    for code, n in doc['sites'].items():
        sp = os.path.join(data_dir, f'{code}_wc_{wk}.json')
        if code not in A['sites'] or not os.path.exists(sp):
            report.append(f'{code}: skipped, not in week {wk}'); continue
        sraw = open(sp).read(); S = json.loads(sraw)
        new = merge_notes(S['sites'][code].get('notes'), n, mode)
        if new != S['sites'][code].get('notes'):
            S['sites'][code]['notes'] = new
            open(sp, 'w').write(dumps_like(sraw, S)); changed.append(sp)
        if new != A['sites'][code].get('notes'):
            A['sites'][code]['notes'] = new
        report.append(f"{code}: {'empty' if new.get('empty') else str(len(new['issues']))+' issues, '+str(len(new['actions']))+' actions'}")
    newraw = dumps_like(araw, A)
    if newraw != araw:
        open(allp, 'w').write(newraw); changed.append(allp)
    return wk, changed, report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data'); ap.add_argument('--file')
    a = ap.parse_args()
    statep = os.path.join(a.data, '_notes_ingest_state.json')
    state = json.load(open(statep)) if os.path.exists(statep) else {}
    changed_all = []; lines = []; fails = 0
    if a.file:
        jobs = [('local', 'local', lambda: json.load(open(a.file)))]
    else:
        dv = drive()
        jobs = [(f['id'], f['modifiedTime'], (lambda fid=f['id']: drive_get(dv, fid)))
                for f in drive_files(dv) if state.get(f['id']) != f['modifiedTime']]
        if not jobs: print('No new notes files.')
    for fid, mt, get in jobs:
        try:
            wk, ch, rep = apply(get(), a.data)
            changed_all += ch; lines.append(f'wc {wk}: ' + '; '.join(rep))
            if fid != 'local': state[fid] = mt
        except FileNotFoundError as e:
            print('WAIT:', e)          # retried next run, state not marked
        except Exception as e:
            fails += 1; print('!! REJECTED', fid, e)
            if fid != 'local': state[fid] = mt   # a bad file is not retried; the next upload is
    if jobs and not a.file:
        open(statep, 'w').write(json.dumps(state, indent=2, sort_keys=True) + '\n')
    print('\n'.join(lines))
    changed_all = sorted(set(changed_all))
    print('Changed files:', len(changed_all)); [print(' ', c) for c in changed_all]
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as g: g.write(f"changed={len(changed_all)}\n")
    sys.exit(1 if fails and not changed_all else 0)

if __name__ == '__main__':
    main()
