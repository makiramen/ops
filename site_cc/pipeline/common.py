"""Shared helpers for the Site Control Centre nightly pulls.
Google access: one read only service account. Env GOOGLE_SERVICE_ACCOUNT_JSON (GitHub secret SITE_CC_SERVICE_ACCOUNT_JSON) (the key file contents) in GitHub Actions.
No browser, no personal login. Every sheet it reads must be shared with the service account email as Viewer."""
import json,os,datetime
HERE=os.path.dirname(os.path.abspath(__file__))
def sites():return json.load(open(os.path.join(HERE,'..','sites.json')))
def site(code):
    S=sites()
    if code not in S['sites']:raise SystemExit(f'unknown site {code}; add it to sites.json')
    return S,S['sites'][code]
def today():return datetime.date.today()
def save(path,obj,**kw):
    kw.setdefault('separators',(',',':'));kw.setdefault('ensure_ascii',False)
    json.dump(obj,open(path+'.tmp','w'),**kw);os.replace(path+'.tmp',path)
_svc=None
CACHE=os.environ.get('SCC_CACHE')  # run_nightly.sh sets a per run folder, so 20 sites read each sheet once
def sheet_values(sheet_id,rng,render='FORMATTED_VALUE'):
    """Rows of strings for a range, via the Sheets API and the service account (cached for the run when SCC_CACHE is set)."""
    import hashlib
    cp=os.path.join(CACHE,hashlib.sha1(f'{sheet_id}|{rng}|{render}'.encode()).hexdigest()+'.json') if CACHE else None
    if cp and os.path.exists(cp):return json.load(open(cp))
    out=_sheet_values(sheet_id,rng,render)
    if cp:os.makedirs(CACHE,exist_ok=True);json.dump(out,open(cp,'w'))
    return out
def _sheet_values(sheet_id,rng,render):
    global _svc
    if _svc is None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info=json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
        cred=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        _svc=build('sheets','v4',credentials=cred,cache_discovery=False)
    r=_svc.spreadsheets().values().get(spreadsheetId=sheet_id,range=rng,valueRenderOption=render).execute()
    return [[str(c) for c in row] for row in r.get('values',[])]
