"""Loyalty feed (loyalty.json) from RAMEN_ROYALTY (AUTO), read with the service account.
DAILY VISITS: one row per member bill (date, venue, spend_gbp, member_id, status). Site rows = venue == sites.json loyalty_venue.
DAILY METRICS: estate new_members and member_bills by day (est, reference only: Trifft has no venue on a sign up).
d[day] = [member bills, distinct members, member spend GBP]. A trading day after launch with no bill at the site is stored as 0 (not missing).
Keeps the last good file on any failure. --check compares with the stored file and writes nothing.
Usage: pull_loyalty.py --site M14 --data DIR [--check] [--csv-visits F --csv-metrics F]"""
import argparse,csv,datetime,json,os,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv-visits');ap.add_argument('--csv-metrics')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources']['ramen_royalty'];VEN=C['loyalty_venue']
rows=lambda f,sid,rng:list(csv.reader(open(f,encoding='utf-8'))) if f else sheet_values(sid,rng)
def table(rs):
    h=[x.strip() for x in rs[0]];return [dict(zip(h,r+['']*(len(h)-len(r)))) for r in rs[1:] if any(r)]
V=table(rows(A.csv_visits,SRC['id'],"'DAILY VISITS'!A:O"))
M=table(rows(A.csv_metrics,SRC['id'],"'DAILY METRICS'!A:R"))
for need in ('date','venue','spend_gbp','member_id'):
    if V and need not in V[0]:sys.exit(f'DAILY VISITS: column {need} missing, layout changed; last good file kept')
launch=SRC.get('launch','2026-08-18')
num=lambda x:float(str(x).replace('£','').replace(',','') or 0)
day=lambda x:str(x)[:10]
# Latest complete day: the newest date in DAILY METRICS that is before today (today is always partial)
today=datetime.date.today().isoformat()
days=sorted({day(r['date']) for r in M if day(r['date'])>=launch and day(r['date'])<today})
if not days:sys.exit('DAILY METRICS has no complete day; last good file kept')
to=days[-1]
d={};mem=set();est={}
cur=datetime.date.fromisoformat(launch)
while cur.isoformat()<=to:d[cur.isoformat()]=[0,set(),0.0];cur+=datetime.timedelta(1)
for r in V:
    k=day(r['date'])
    if r['venue'].strip()!=VEN or k not in d:continue
    if str(r.get('status','FINAL')).strip().upper() not in ('FINAL',''):continue
    d[k][0]+=1;d[k][1].add(r['member_id']);d[k][2]+=num(r['spend_gbp']);mem.add(r['member_id'])
d={k:[v[0],len(v[1]),round(v[2],2)] for k,v in d.items()}
for r in M:
    k=day(r['date'])
    if launch<=k<=to:est[k]=[int(num(r.get('new_members',0))),int(num(r.get('member_bills',0)))]
out={'src':'RAMEN_ROYALTY (AUTO), DAILY VISITS and DAILY METRICS tabs, service account read','pulled':today,'launch':launch,'to':to,
     'venue':VEN,'venue_members':len(mem),
     'note':'d = [member bills, distinct members, member spend GBP] by day. est = estate [sign ups, member bills] by day (Trifft has no venue on a sign up, so site sign ups are not attributable). Before launch the programme had not launched: n/a.',
     'd':d,'est':est}
P=os.path.join(A.data,'loyalty.json')
if A.check:
    old=json.load(open(P)) if os.path.exists(P) else {'d':{}}
    diff=[(k,old['d'].get(k),v) for k,v in d.items() if k in old['d'] and old['d'][k]!=v]
    print(f'check: {len(d)} days to {to}, {len(diff)} differ from stored');[print(' ',*x) for x in diff[:30]];sys.exit(0)
save(P,out);print(f'loyalty {A.site}: {len(d)} days to {to}, {sum(v[0] for v in d.values())} bills, {len(mem)} members')
