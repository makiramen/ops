"""Budget burn feed (budget.json) for one site, from the EC ledger snapshot the AM Control Centre already bakes.
Source: <root>/data/ec_budget_snapshot.json (Budget Burn snapshot workflow, twice daily, from the EC Daily Spend Ledger sheet).
Same numbers as the AM Control Centre Budget Burn tab: daily spend per site (Head Chef daily report), the HC weekly base
(Total Spend From Sunday + Budget Left This Week, Sun to Sat week), the interim month cap (23% x Mar to May MA revenue).
Site code map: the ledger uses IK2 for IKI2 and MN for MakiNori.
Writes budget.json: ledger = {day: spend GBP or null (not filed)}, wk = {Sunday: weekly budget}, cap = month cap.
Keeps the last good file on any failure. Usage: pull_budget.py --site M14 --data DIR --root OPS_ROOT [--check]"""
import argparse,datetime,json,os,sys
from common import save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--root',default='..');ap.add_argument('--check',action='store_true')
A=ap.parse_args()
CODE={'IKI2':'IK2','MakiNori':'MN'}.get(A.site,A.site)
SNAP=os.path.join(A.root,'data','ec_budget_snapshot.json')
if not os.path.exists(SNAP):sys.exit(f'budget {A.site}: {SNAP} missing; last good file kept')
d=json.load(open(SNAP)).get('daily_spend') or {}
ledger=d.get('ledger') or {}
if not ledger:sys.exit(f'budget {A.site}: snapshot has no ledger; last good file kept')
live_from=(d.get('live_from') or {}).get(CODE)
L={}
for day in sorted(ledger):
    if live_from and day<live_from:continue
    v=ledger[day].get(CODE) if isinstance(ledger[day],dict) else None
    L[day]=None if v is None else round(float(v),2)
if not L:
    out={'src':'EC Daily Spend Ledger via data/ec_budget_snapshot.json','pulled':datetime.date.today().isoformat(),'as_at':d.get('as_at'),'code':CODE,'cap':None,'ledger':{},'wk':{},'note':f'{CODE} is not in the EC ledger: no Head Chef daily report for this site'}
    save(os.path.join(A.data,'budget.json'),out);print(f'budget {A.site}: not in the ledger, feed stays n/a');sys.exit(0)
site=next((s for s in d.get('sites') or [] if s.get('code')==CODE),{})
cap=site.get('cap')
# Weekly budget per HC week (Sunday): locked or derived value from the ledger; the live week falls back to the site's current HC base
wk={}
for sun,row in (d.get('weeks_budget') or {}).items():
    if isinstance(row,dict) and row.get(CODE) is not None:wk[sun]=round(float(row[CODE]),2)
def week_sun(day):
    x=datetime.date.fromisoformat(day);return (x-datetime.timedelta((x.weekday()+1)%7)).isoformat()
last=max(L);cur=week_sun(last)
if cur not in wk and site.get('wk_budget') is not None:wk[cur]=round(float(site['wk_budget']),2)
# standing budgets (sites whose HC never files a budget) and the dated 27% override week, as the AM CC applies them
for code,s in (d.get('standing_budget') or {}).items():
    if code==CODE and s.get('amount') is not None:
        for sun in {week_sun(x) for x in L}:
            if not s.get('from') or sun>=week_sun(s['from']):wk[sun]=round(float(s['amount']),2)
for sun,o in (d.get('budget_override') or {}).items():
    v=(o.get('by_code') or {}).get(CODE)
    if v is not None:wk[sun]=round(float(v),2)
closure=None
try:
    c=(json.load(open(os.path.join(A.root,'builders','covers_accepted.json'))).get('closures') or {}).get(A.site)
    if c:closure={'from':c.get('from'),'until':c.get('until'),'why':c.get('why')}
except Exception:pass
jb=d.get('june_baseline') or {}
out={'src':'EC Daily Spend Ledger (Head Chef daily report) via data/ec_budget_snapshot.json, the AM Control Centre Budget Burn source','pulled':datetime.date.today().isoformat(),
     'as_at':d.get('as_at'),'through':last,'code':CODE,'cap':cap,'cap_basis':d.get('june_cap_basis'),'wk_basis':d.get('weekly_budget_basis'),
     'live_from':live_from,'closure':closure,'june_baseline':{'through':jb.get('through'),'amt':(jb.get('by_code') or {}).get(CODE)} if jb else None,
     'note':'ledger = spend GBP by day as the Head Chef filed it (null = not filed that day). wk = weekly food budget keyed by the HC week Sunday (Sun to Sat). cap = interim monthly cap, calendar month. Same figures as the AM Control Centre Budget Burn tab.',
     'ledger':L,'wk':dict(sorted(wk.items()))}
P=os.path.join(A.data,'budget.json')
if A.check:
    old=json.load(open(P)) if os.path.exists(P) else {'ledger':{}}
    diff=[(k,old['ledger'].get(k),v) for k,v in L.items() if k in old['ledger'] and old['ledger'][k]!=v]
    print(f'check: {len(L)} days to {last}, cap {cap}, {len(diff)} differ');[print(' ',*x) for x in diff[:20]];sys.exit(0)
save(P,out);print(f'budget {A.site}: {len(L)} days to {last}, cap {cap}, {len(wk)} weekly budgets')
