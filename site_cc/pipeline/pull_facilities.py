"""Compliance / PPM from Ross's M&R Facilities app (Flask + SQLite on PythonAnywhere, rossmward.eu.pythonanywhere.com), 10/11/2026.
Michael: the app holds all the updated compliance, use it as the source. The app is login only, so the nightly downloads its database
(/home/rossmward/mysite/maintenance.db) through the PythonAnywhere files API with a token (secret PYTHONANYWHERE_TOKEN), once per run.
Tables used: site (name, code), equipment (name, site), maintenance_task (title, due_date, frequency_months, booked_date, booked_note,
equipment_id), maintenance_log (task_id, date_completed, certificate_expires, contractor_name, external_url). Column names are checked
at runtime (PRAGMA), anything missing just leaves that field blank.
Writes ppm.json in the shape the page already reads: items = [[ppm, contractor, next due, months, note, last done, url], ...].
The app's tasks REPLACE the schedule lines (ppm_contractors.json + Mapal logs, pull_ppm.py) for the site; schedule lines the app does
not carry are kept underneath. No token, no network or no rows for the site = ppm.json left exactly as pull_ppm.py wrote it.
Usage: pull_facilities.py --site M14 --data DIR [--check] [--db maintenance.db]"""
import argparse,datetime,json,os,re,sqlite3,sys,time,urllib.request
from common import site,save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--db')
A=ap.parse_args();S,C=site(A.site)
APP='https://rossmward.eu.pythonanywhere.com';USER='rossmward';DBPATH='/home/rossmward/mysite/maintenance.db'
TOK=os.environ.get('PYTHONANYWHERE_TOKEN','').strip()
P=os.path.join(A.data,'ppm.json')
# Our code -> the names the app uses for the site (Site.name / Equipment.site). Seeds use "Maki 12", "Maki 1/2", "Ikigai SB", "Maki Nori".
NAMES={'M1':['Maki 1/2','Maki 1','Maki 2','Maki 1/2 (Nicolson St)'],'IKI2':['Ikigai SB','Ikigai','Ikigai Ramen','Ikigai South Bridge'],
       'MakiNori':['Maki Nori','Maki Nori Ltd']}
names=NAMES.get(A.site) or [C.get('label',A.site)]
names=names+[C.get('label','')]+[n+' Ltd' for n in names]+[A.site];names=[n for n in dict.fromkeys(x for x in names if x)]
def norm(s):return re.sub(r'[^a-z0-9]','',str(s or '').lower())
NN={norm(n) for n in names}
def fetch_db():
    if A.db:return A.db
    if not TOK:print(f'facilities {A.site}: no PYTHONANYWHERE_TOKEN, ppm.json left as pull_ppm.py wrote it');sys.exit(0)
    cache=os.path.join(os.environ.get('SCC_CACHE') or '/tmp','facilities_maintenance.db')
    if os.path.exists(cache) and time.time()-os.path.getmtime(cache)<3*3600:return cache
    url=f'https://eu.pythonanywhere.com/api/v0/user/{USER}/files/path{DBPATH}'
    req=urllib.request.Request(url,headers={'Authorization':'Token '+TOK})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:b=r.read()
    except Exception as e:sys.exit(f'facilities {A.site}: database download failed ({str(e)[:120]}); ppm.json kept')
    if not b.startswith(b'SQLite format 3'):sys.exit(f'facilities {A.site}: download is not a SQLite file ({len(b)} bytes); ppm.json kept')
    open(cache,'wb').write(b);return cache
db=sqlite3.connect(fetch_db());db.row_factory=sqlite3.Row
def cols(t):
    try:return [r[1] for r in db.execute(f'PRAGMA table_info({t})')]
    except Exception:return []
tabs=[r[0] for r in db.execute("select name from sqlite_master where type='table'")]
def tab(*cands):
    for c in cands:
        if c in tabs:return c
    return None
T_EQ,T_TASK,T_LOG,T_SITE=tab('equipment'),tab('maintenance_task','task'),tab('maintenance_log','log'),tab('site','sites')
if not (T_EQ and T_TASK):sys.exit(f'facilities {A.site}: tables not found ({tabs}); ppm.json kept')
EQ,TK,LG=cols(T_EQ),cols(T_TASK),cols(T_LOG) if T_LOG else []
def pick(cs,*cands):
    for c in cands:
        if c in cs:return c
    return None
eq_site=pick(EQ,'site','site_name','location');eq_name=pick(EQ,'name')
tk_title=pick(TK,'title','name');tk_due=pick(TK,'due_date','next_due','due');tk_freq=pick(TK,'frequency_months','months','interval_months')
tk_eq=pick(TK,'equipment_id');tk_booked=pick(TK,'booked_date');tk_bnote=pick(TK,'booked_note');tk_who=pick(TK,'assigned_email','contractor','contractor_name')
lg_task=pick(LG,'task_id');lg_done=pick(LG,'date_completed','completed_at','date');lg_exp=pick(LG,'certificate_expires','expires')
lg_con=pick(LG,'contractor_name','contractor');lg_url=pick(LG,'external_url','url')
if not (eq_site and tk_title and tk_eq):sys.exit(f'facilities {A.site}: columns not recognised (equipment {EQ}, task {TK}); ppm.json kept')
def d10(x):
    x=str(x or '').strip()
    m=re.match(r'(\d{4})-(\d{2})-(\d{2})',x)
    if m:return '-'.join(m.groups())
    m=re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})',x)
    return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else ''
rows=db.execute(f'select e.{eq_site} as esite, e.{eq_name or eq_site} as ename, t.* from {T_TASK} t join {T_EQ} e on e.id=t.{tk_eq}').fetchall()
mine=[r for r in rows if norm(r['esite']) in NN]
allsites=sorted({r['esite'] for r in rows})
if not mine:print(f'facilities {A.site}: no tasks for {names[:3]} in the app (sites there: {allsites}); ppm.json kept');sys.exit(0)
items=[]
for r in mine:
    last=None
    if T_LOG and lg_task:
        last=db.execute(f'select * from {T_LOG} where {lg_task}=? order by {lg_done or "id"} desc limit 1',(r['id'],)).fetchone()
    done=d10(last[lg_done]) if last and lg_done else ''
    exp=d10(last[lg_exp]) if last and lg_exp else ''
    due=exp or d10(r[tk_due] if tk_due else '')
    months=int(r[tk_freq]) if tk_freq and r[tk_freq] not in (None,'') else 0
    who=(last[lg_con] if last and lg_con and last[lg_con] else '') or (r[tk_who] if tk_who and r[tk_who] else '') or ''
    note='Facilities app'+(f', booked {d10(r[tk_booked])}' if tk_booked and r[tk_booked] else '')+(f': {r[tk_bnote]}' if tk_bnote and r[tk_bnote] else '')
    if r['ename'] and norm(r['ename']) not in norm(r[tk_title]):note+=f' ({r["ename"]})'
    url=(last[lg_url] if last and lg_url and last[lg_url] else '') or f'{APP}/tasks'
    items.append([str(r[tk_title]).strip(),str(who).strip(),due or None,months,note,done or None,url])
items.sort(key=lambda x:(x[2] or '9999',x[0]))
# keep schedule lines the app does not carry (matched on the first keyword of the title)
try:OLD=json.load(open(P))
except Exception:OLD={'items':[]}
have={norm(x[0])[:12] for x in items}
kept=[x for x in OLD.get('items',[]) if norm(x[0])[:12] not in have and not str(x[4] or '').startswith('Facilities app')]
asof=max([x[5] for x in items if x[5]]+[datetime.date.today().isoformat()])
out={'src':f'M&R Facilities app (Ross, {APP}), tasks + latest logs'+(' + schedule lines not in the app' if kept else ''),
     'asof':asof,'items':items+kept,'app_site':mine[0]['esite'],'pulled':datetime.date.today().isoformat()}
print(f'facilities {A.site}: {len(items)} tasks as {mine[0]["esite"]!r}, {sum(1 for x in items if x[5])} with a completion log, {len(kept)} schedule lines kept')
if A.check:print(json.dumps(out['items'],ensure_ascii=False,indent=1));sys.exit(0)
save(P,out,indent=1)
