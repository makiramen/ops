"""Team, onboarding, starters and leavers (team.json) from Hanna's "Maki Group Onboarding Tracker - 2026", one tab per site
(sites.json onboarding_tab). The sheet is link shared, so the service account reads it without a share.
Tab layout: section header rows in col A ("Mgmt", "FOH/Bar", "BOH" or "BOH/Sushi", "P45 List ..."), staff rows have a title
(Mr, Ms, Miss, Mrs, Mx) in col A, first name in B, last name in C. Onboarded = HR docs (D), Mapal / operational tasks (G)
and contract released (H) all ticked. Names are first name plus last initial only; RTW and document data are never read out.
Starters and leavers: when the roster changes, the previous roster is kept as "prev" (date and names), so the card shows
who joined and left since then. Keeps the last good file on any failure. --check reports and writes nothing."""
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
team={'Management':[],'FOH and bar':[],'BOH':[]};leavers=[];onb=0;cur=None
for r in rows:
    r=(r+['']*8)[:8];a=r[0].strip()
    if a.lower().rstrip('.') in TITLES:
        if not cur or not r[1].strip():continue
        n=short(r[1],r[2])
        if cur=='P45':leavers.append(n)
        else:
            team[cur].append(n)
            if tick(r[3]) and tick(r[6]) and tick(r[7]):onb+=1
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
out={'src':f'Maki Group Onboarding Tracker 2026, tab {tab.strip()}','pulled':t,'baseline':base,'team':team,'onboarded':onb,'leavers':leavers,'prev':prev}
print(f"team {A.site}: {hc} ({', '.join(f'{len(v)} {k}' for k,v in team.items())}), onboarded {onb}/{hc}, P45 {len(leavers)}, "+
      (f"changed since {prev['date']}" if prev else 'baseline'))
if not A.check:save(P,out,indent=1)
