"""Asana action sync for the Site Control Centre (07/10/2026).
Asana home: project "Maki & Ramen Management", one section per site (sites.json sources.asana, sites.<CODE>.asana_section).
1. Every page action (actions.json + amcc_actions.json) from w/c sources.asana.from onward with no Asana task yet gets one
   in the site section (name, owner and source in the notes, due date). Map kept in data/<CODE>/asana.json, so a rerun never duplicates.
2. Every task in the site section is read back (open and completed): build.py marks completed ones Completed on the page,
   and tasks created straight in Asana (roundtable, or added on the page through the web app) show as actions too.
Token: env ASANA_TOKEN (GitHub secret). No token: writes nothing, the feed shows Late, the page keeps the last good file.
Usage: python3 pipeline/pull_asana.py --site M7 --data data/M7 [--check]"""
import json, os, sys, argparse, urllib.request, urllib.parse, datetime

ap = argparse.ArgumentParser()
ap.add_argument('--site', required=True); ap.add_argument('--data', required=True); ap.add_argument('--check', action='store_true')
A = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
SJ = json.load(open(os.path.join(HERE, '..', 'sites.json')))
CFG = (SJ.get('sources') or {}).get('asana') or {}
SEC = SJ['sites'][A.site].get('asana_section')
TOK = os.environ.get('ASANA_TOKEN', '').strip()
if not SEC: print(f'{A.site}: no asana_section in sites.json, skipped'); sys.exit(0)
if not TOK: sys.exit('ASANA_TOKEN not set')
API = os.environ.get('ASANA_API', 'https://app.asana.com/api/1.0')  # ASANA_API only for local tests

def call(method, path, body=None, q=None):
    url = API + path + ('?' + urllib.parse.urlencode(q) if q else '')
    req = urllib.request.Request(url, method=method, headers={'Authorization': 'Bearer ' + TOK, 'Accept': 'application/json', 'Content-Type': 'application/json'},
                                 data=json.dumps({'data': body}).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

P = lambda f: os.path.join(A.data, f)
def ld(f, d):
    try: return json.load(open(P(f)))
    except Exception: return d

acts = ld('actions.json', []) + ld('amcc_actions.json', [])
ST = ld('asana.json', {})
MAP = ST.get('map') or {}          # page action id (as str) -> Asana task gid
FROM = CFG.get('from', '2026-09-28')
NAMES_MAP = {k.lower(): v for k, v in (CFG.get('names') or {}).items()}  # Asana users whose display name is their email
def who(t):
    u = t.get('assignee') or {}
    n, e = (u.get('name') or '').strip(), (u.get('email') or '').strip().lower()
    return NAMES_MAP.get(e) or NAMES_MAP.get(n.lower()) or n or None

def section():
    out, off = [], None
    while True:
        q = {'section': SEC, 'limit': 100, 'opt_fields': 'name,completed,completed_at,due_on,assignee.name,assignee.email,created_at,parent'}
        if off: q['offset'] = off
        r = call('GET', '/tasks', q=q)
        out += [t for t in r['data'] if not t.get('parent')]
        off = (r.get('next_page') or {}).get('offset')
        if not off: return out

# 1. create missing tasks (an action whose text already is a task in the section is linked, not duplicated)
NAMES = {t['name'].strip().lower(): t['gid'] for t in section()}
made = 0
for a in acts:
    k = str(a['id'])
    if k in MAP or (a.get('wc') or '') < FROM: continue
    notes = f"Owner: {a.get('o') or 'n/a'}\nSource: {a.get('src') or 'n/a'}, w/c {a.get('wc') or 'n/a'}\nSite Control Centre action {k} ({A.site}). Mark done on the Site CC page completes this task."
    body = {'name': a['t'][:250], 'notes': notes, 'projects': [CFG['project']]}
    if a.get('d'): body['due_on'] = a['d']
    g = NAMES.get(a['t'][:250].strip().lower())
    if g: MAP[k] = g; continue
    if A.check: print('would create:', a['t'][:70]); continue
    try:
        r = call('POST', '/tasks', body); g = r['data']['gid']; call('POST', f'/sections/{SEC}/addTask', {'task': g}); MAP[k] = g; made += 1
    except Exception as e: print('!! create failed', k, e)

# 2. read the whole section back
tasks = section()
T = [{'gid': t['gid'], 't': t['name'], 'c': 1 if t['completed'] else 0, 'ca': (t.get('completed_at') or '')[:10] or None,
      'd': t.get('due_on'), 'o': who(t), 'cr': (t.get('created_at') or '')[:10]} for t in tasks]
out = {'site': A.site, 'section': SEC, 'project': CFG['project'], 'pulled': datetime.date.today().isoformat(), 'map': MAP, 'tasks': T}
print(f'{A.site}: created {made}, section has {len(T)} tasks ({sum(t["c"] for t in T)} completed)')
if not A.check:
    json.dump(out, open(P('asana.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
