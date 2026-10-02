"""Employee of the Month feed (eotm.json) from Hanna's monthly Manual Input sheets (one per site and department, form row 2).
Sheets found two ways: (1) the "12. Employee of the Month" folder (sources.eotm.folder), listed with the Drive API, files named
"<CODE> BOH|FOH EOTM Manual Input ..." (needs the folder shared with the service account); (2) sites.json eotm_sheets ids
(these sheets are link shared, so they read without a folder share). "IGNORE" in a title skips it.
Month = Completed date (col A). Latest nomination per month and department wins. Nominee shown as first name plus initial.
"why" = col AG (what makes this employee stand out), trimmed; staff names other than the nominee are not shown.
Keeps the last good file on any failure (a month already stored is never blanked). --check reports and writes nothing."""
import argparse,datetime,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site)
P=os.path.join(A.data,'eotm.json');old=json.load(open(P)) if os.path.exists(P) else {'m':{}}
ids={d:list(v) for d,v in C.get('eotm_sheets',{}).items()}
def drive_list(folder):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    cred=service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),scopes=['https://www.googleapis.com/auth/drive.readonly'])
    dv=build('drive','v3',credentials=cred,cache_discovery=False);out=[];q=[folder]
    while q:
        f=q.pop();tok=None
        while True:
            r=dv.files().list(q=f"'{f}' in parents and trashed=false",fields='nextPageToken,files(id,name,mimeType)',pageSize=200,pageToken=tok,
                              supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
            for x in r['files']:
                (q.append(x['id']) if x['mimeType'].endswith('folder') else out.append(x))
            tok=r.get('nextPageToken')
            if not tok:break
    return out
folder=S['sources'].get('eotm',{}).get('folder')
if folder:
    try:
        n=0
        for f in drive_list(folder):
            m=re.match(rf"^{re.escape(A.site)}\s+(BOH|FOH)\s+EOTM Manual Input",f['name'],re.I)
            if m and 'IGNORE' not in f['name'].upper() and f['mimeType'].endswith('spreadsheet'):
                L=ids.setdefault(m.group(1).upper(),[])
                if f['id'] not in L:L.append(f['id']);n+=1
        print(f'eotm folder: {n} sheets found')
    except Exception as e:print('eotm folder not readable (share it with the service account), using sites.json ids only:',str(e)[:160])
def dmy(s):
    m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})',s or '');return datetime.date(int(m.group(3)),int(m.group(2)),int(m.group(1))) if m else None
def short(n):
    p=(n or '').split();return (p[0].capitalize()+(' '+p[-1][0].upper()+'.' if len(p)>1 else '')) if p else ''
def why(t):
    t=re.sub(r'\s+',' ',(t or '').replace('—',', ').replace('–','-')).strip()
    t=t[:1].upper()+t[1:] if t else t
    return t if len(t)<=220 else t[:217].rsplit(' ',1)[0]+'...'
M={};errs=0
for dept,L in ids.items():
    for sid in L:
        try:rows=sheet_values(sid,'A1:AH50')
        except Exception as e:print(f'  {dept} {sid}: not readable: {str(e)[:120]}');errs+=1;continue
        for r in rows[1:]:
            r=r+['']*(34-len(r));d=dmy(r[0])
            if not d or not r[8].strip():continue
            key=d.strftime('%Y-%m');cur=M.setdefault(key,{}).get(dept)
            if cur and cur['on']>=d.isoformat():continue
            M[key][dept]={'n':short(r[8]),'role':r[9].strip(),'by':short(r[1]),'on':d.isoformat(),'why':why(r[32] or r[11])}
if errs and not M:sys.exit('no EOTM sheet readable; last good file kept')
out={'src':"Hanna's EOTM Manual Input sheets (one per site and department), service account read",'pulled':datetime.date.today().isoformat(),
     'sheets':{d:('https://docs.google.com/spreadsheets/d/'+L[0]) if L else '' for d,L in {'BOH':ids.get('BOH',[]),'FOH':ids.get('FOH',[])}.items()},'m':dict(old.get('m',{}))}
for k,v in M.items():
    o=dict(out['m'].get(k) or {'BOH':None,'FOH':None})
    o.update(v);out['m'][k]=o
out['m']=dict(sorted(out['m'].items()))
print(f'eotm {A.site}:',{k:{d:(x or {}).get('n') for d,x in v.items()} for k,v in out['m'].items()})
if A.check:sys.exit(0)
save(P,out)
