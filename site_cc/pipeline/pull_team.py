"""Team, onboarding, starters and leavers (team.json) from Hanna's "Maki Group Onboarding Tracker - 2026", one tab per site
(sites.json onboarding_tab). The sheet is link shared, so the service account reads it without a share.
Tab layout: section header rows in col A ("Mgmt", "FOH/Bar", "BOH" or "BOH/Sushi", "P45 List ..."), staff rows have a title
(Mr, Ms, Miss, Mrs, Mx) in col A, first name in B, last name in C. Onboarded = HR docs (D), Mapal / operational tasks (G)
and contract released (H) all ticked; anyone short of that is listed in pending with the steps still open. Names are first name plus last initial only; RTW and document data are never read out.
Starters and leavers: when the roster changes, the previous roster is kept as "prev" (date and names), so the card shows
who joined and left since then. Keeps the last good file on any failure. --check reports and writes nothing.
10/11/2026 (Michael): team.json also carries 'rows', a carbon copy of the tracker tab for the page's Onboarding tab and the KPI Sheet
People section: [sheet row number, section, short name, [HR docs, Passport & RTW, Operational tasks, Contract released] ticks].
The row number is what the page sends back when someone ticks a document (AsanaSync.gs op 'onb' writes TRUE into that cell after
checking the name on the row still matches). Columns F (RTW expiry date) and I (RTW expiry tracker) are never copied."""
import argparse,json,os,re
from common import site,save,sheet_values,today
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site)
tab=C.get('onboarding_tab')
if not tab:print(f'team: no onboarding tab for {A.site}, feed shows n/a');raise SystemExit(0)
P=os.path.join(A.data,'team.json');old=json.load(open(P)) if os.path.exists(P) else {}
sid=S['sources']['onboarding']['id']
rows=sheet_values(sid,f"'{tab}'!A1:H200")
TITLES={'mr','mrs','miss','ms','mx','dr'}
def sect(a):
    s=a.lower()
    if s.startswith('p45') or 'leaver' in s:return 'P45'
    if s.startswith('mgmt') or s.startswith('manage'):return 'Management'
    if 'boh' in s or 'kitchen' in s or 'sushi' in s:return 'BOH'
    if s.startswith('foh') or 'bar' in s:return 'FOH and bar'
    return None
def short(first,last):
    f=re.sub(r'\s+',' ',first).strip();l=re.sub(r'\s+',' ',last).strip()
    return (f+(' '+l[0].upper() if l else '')).strip()
tick=lambda v:str(v).strip().upper() in ('TRUE','YES','Y','DONE','✓','✔')
team={'Management':[],'FOH and bar':[],'BOH':[]};leavers=[];onb=0;cur=None;pending=[];docs=[];copy=[]
COLS=((3,'D','HR docs'),(4,'E','Passport & RTW'),(6,'G','Operational tasks'),(7,'H','Contract released'))
# 10/11/2026 (Michael): where each person sits on the tracker. pending = [name, section, [steps not ticked]] for anyone not fully onboarded.
STEPS=((3,'HR docs'),(6,'Mapal and operational tasks'),(7,'Contract released'))
# 10/11/2026 (Michael): documents missing per person, for the Starters and leavers card. The tracker holds one tick per group, not per document,
# so a missing HR docs tick names the whole pack. Passport and right to work is the tick only: expiry dates and status are never read out.
DOCS=((3,'HR docs pack'),(4,'Passport and right to work check'),(7,'Contract'))
for ri,r in enumerate(rows,1):
    r=(r+['']*8)[:8];a=r[0].strip()
    if a.lower().rstrip('.') in TITLES:
        if not cur or not r[1].strip():continue
        n=short(r[1],r[2])
        if cur=='P45':leavers.append(n)
        else:
            team[cur].append(n)
            copy.append([ri,cur,n,[tick(r[i]) for i,_,_ in COLS]])
            miss=[lab for i,lab in STEPS if not tick(r[i])]
            dm=[lab for i,lab in DOCS if not tick(r[i])]
            if dm:docs.append([n,cur,dm])
            if miss:pending.append([n,cur,miss])
            else:onb+=1
    elif a:
        s=sect(a)
        if s:cur=s
team={k:v for k,v in team.items() if v}
hc=sum(len(v) for v in team.values())
if hc==0:raise SystemExit(f'team: tab {tab} read but no staff rows found, keeping the last good file')
names=sorted(n for v in team.values() for n in v)
oldnames=sorted(n for v in (old.get('team') or {}).values() for n in v)
t=today().isoformat()
if not oldnames:base,prev=t,None
else:
    base=old.get('baseline') or old.get('pulled') or t
    prev=old.get('prev')
    if names!=oldnames:prev={'date':old.get('pulled') or base,'names':oldnames}
out={'src':f'Maki Group Onboarding Tracker 2026, tab {tab.strip()}','tab':tab,'pulled':t,'baseline':base,'team':team,'onboarded':onb,'pending':pending,'docs':docs,'leavers':leavers,'prev':prev,
     'cols':[[c,l] for _,c,l in COLS],'rows':copy}
print(f"team {A.site}: {hc} ({', '.join(f'{len(v)} {k}' for k,v in team.items())}), onboarded {onb}/{hc}, P45 {len(leavers)}, "+
      (f"changed since {prev['date']}" if prev else 'baseline'))
if not A.check:save(P,out,indent=1)
