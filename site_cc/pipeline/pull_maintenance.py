"""Maintenance (maint.json) from Lincoln's "Required Maintenance/Repair (Responses)" sheet, fed by the Maintenance Log Google Form.
Tabs: "Form responses 1" (one row per job: Month, Timestamp, Location, Your Name, Task, Picture, Urgency, Date of Completion,
Status, Carried Out By, blank, Expenses, Notes) and "Weekly Recap" (Lincoln's ongoing / pending list with his action plan update).
The sheet is link shared (anyone, reader), so the service account reads it without a share.
Site match: Location before " - " ("Maki 7 - SJQ, Edinburgh" = "Maki 7"), against sites.json maint_label or label; "Maki 1/2" matches both.
Open = status not Completed / Cancelled. Keeps the last good file on any failure. --check reports and writes nothing."""
import argparse,json,os,re,datetime,difflib
from common import site,save,sheet_values,today
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site)
src=S['sources'].get('maintenance')
if not src:print('maintenance: no source in sites.json, feed shows n/a');raise SystemExit(0)
P=os.path.join(A.data,'maint.json')
sid=src['id']
key=re.sub(r'\s+',' ',(C.get('maint_label') or C.get('label') or '')).strip().lower()
def keys(loc):
    b=re.sub(r'\s+',' ',(loc or '').split(' - ')[0]).strip().lower()
    m=re.match(r'^(.*?)(\d+)/(\d+)$',b)
    return {m.group(1)+m.group(2),m.group(1)+m.group(3)} if m else {b}
def dmy(s):
    m=re.search(r'(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})',s or '')
    if not m:return None
    y=int(m.group(3));y+=2000 if y<100 else 0
    try:return datetime.date(y,int(m.group(2)),int(m.group(1))).isoformat()
    except ValueError:return None
def money(s):
    try:return round(float(re.sub(r'[^0-9.]','',s)),2) if re.search(r'\d',s or '') else None
    except ValueError:return None
clean=lambda s:re.sub(r'\s+',' ',(s or '').replace('—',', ').replace('–','-')).strip()
rows=sheet_values(sid,"'Form responses 1'!A:M")
if len(rows)<2:raise SystemExit('maintenance: Form responses 1 read but empty, keeping the last good file')
T=today();cut=(T-datetime.timedelta(60)).isoformat()
opn=[];done=[];closed=[]
for r in rows[1:]:
    r=(r+['']*13)[:13]
    if key not in keys(r[2]):continue
    d=dmy(r[1])
    if not d:continue
    st=clean(r[8]) or 'Open';pri=clean(r[6]).replace(' Priority','')
    if pri.lower().startswith('on a scale'):pri=''
    j={'d':d,'t':clean(r[4]),'pri':pri,'st':st,'by':clean(r[3]),'who':clean(r[9]),'note':clean(r[12]),'cost':money(r[11]),'comp':dmy(r[7]),
       'pic':r[5].strip() if r[5].strip().startswith('http') else ''}
    if re.match(r'(?i)complet|cancel',st):
        closed.append(j)
        if d>=cut:done.append(j)
    else:opn.append(j)
# Lincoln's Weekly Recap: rows with no date or site carry on the site above
recap={'asof':None,'items':[]}
try:
    W=sheet_values(sid,"'Weekly Recap'!A1:D120")
    for r in W[:3]:
        m=re.search(r'AS OF\s*-?\s*([A-Za-z]+ \d{1,2},? \d{4})',' '.join(r))
        if m:recap['asof']=datetime.datetime.strptime(m.group(1).replace(',',''),'%B %d %Y').date().isoformat();break
    cur=None;cd=None
    for r in W:
        r=(r+['']*4)[:4]
        if r[2].strip().upper()=='CONCERN' or 'AS OF' in r[0].upper():continue
        if r[1].strip():cur=r[1];cd=dmy(r[0])
        elif r[0].strip():cd=dmy(r[0])
        if cur and key in keys(cur) and r[2].strip():recap['items'].append({'d':cd,'t':clean(r[2]),'upd':clean(r[3])})
except Exception as e:print('maintenance: Weekly Recap not read:',e)
# attach Lincoln's update to the matching open job (same concern text)
for it in recap['items']:
    best=max(opn,key=lambda j:difflib.SequenceMatcher(None,j['t'].lower()[:80],it['t'].lower()[:80]).ratio(),default=None)
    if best and difflib.SequenceMatcher(None,best['t'].lower()[:80],it['t'].lower()[:80]).ratio()>=0.6:best['upd']=it['upd'];it['matched']=True
# a recap line whose job is already Completed or Cancelled (any age) is not shown as still on the recap
sim=lambda a,b:difflib.SequenceMatcher(None,a.lower()[:80],b.lower()[:80]).ratio()
for it in recap['items']:
    if not it.get('matched') and any(sim(j['t'],it['t'])>=0.6 for j in closed):it['closed']=True
opn.sort(key=lambda j:j['d']);done.sort(key=lambda j:j['d'],reverse=True)
d30=[j for j in done if j['d']>=(T-datetime.timedelta(30)).isoformat() and j['st'].lower().startswith('complet')]
out={'src':'Required Maintenance/Repair (Responses), Maintenance Log form','pulled':T.isoformat(),
     'url':f'https://docs.google.com/spreadsheets/d/{sid}/edit','form':src.get('form',''),'open':opn,'done':done,'recap':recap,
     'n':{'open':len(opn),'high':sum(1 for j in opn if j['pri']=='High'),'done30':len(d30),'cost30':round(sum(j['cost'] or 0 for j in d30),2)}}
print(f"maintenance {A.site}: {len(opn)} open ({out['n']['high']} high), {len(d30)} done in 30 days, recap {len(recap['items'])} item(s) as of {recap['asof']}")
if not A.check:save(P,out,indent=1)
