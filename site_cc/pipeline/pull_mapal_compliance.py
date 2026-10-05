"""Mapal task compliance (mcomp.json) from the Mapal Weekly Compliance Tracker sheet, read with the service account.
The sheet is filled every Monday by the "Mapal weekly compliance pull" scheduled task (Mapal Compliance Hub, previous Mon to Sun).
Columns: Week_Start, Week_End, Scope (CHAIN / SITE), Site (Mapal location), Compliance_%, TasksDone_%, TasksDone, TasksTotal,
OnTime_%, Open_Deviations, Flag. Site rows = Site == sites.json mapal_location.
w = [[week_start, on time %, open deviations, flag, compliance %, tasks done, tasks total], ...] oldest first; chain = same for the estate.
Flag rule (the sheet's): open deviations 10+ RED, else on time 75+ OK, 25 to 74 WATCH, under 25 RED.
Keeps the last good file on any failure. --check prints and writes nothing.
Usage: pull_mapal_compliance.py --site M7 --data DIR [--check] [--csv export.csv]"""
import argparse,csv,datetime,os,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources'].get('mapal_compliance');LOC=C.get('mapal_location')
if not LOC or not SRC:print(f'mapal compliance {A.site}: no Mapal location or source in sites.json, feed stays n/a');sys.exit(0)
rows=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],"A:K")
if not rows or [x.strip() for x in rows[0][:4]]!=['Week_Start','Week_End','Scope','Site']:sys.exit('tracker layout changed; last good file kept')
num=lambda x:float(str(x).replace('%','').strip()) if str(x).strip() not in ('',) else None
def flag(ot,dev):
    if dev is not None and dev>=10:return 'RED'
    if ot is None:return ''
    return 'OK' if ot>=75 else 'WATCH' if ot>=25 else 'RED'
site_w={};chain_w={}
for r in rows[1:]:
    r=[x.strip() for x in r]+['']*(11-len(r))
    ws,we,sc,nm=r[0],r[1],r[2].upper(),r[3]
    if len(ws)!=10 or ws[4]!='-':ws=(datetime.date.fromisoformat(we)-datetime.timedelta(6)).isoformat() if len(we)==10 else None
    if not ws:continue
    ot,dev=num(r[8]),num(r[9])
    row=[ws,ot,int(dev) if dev is not None else None,r[10] or flag(ot,dev),num(r[4]),num(r[6]),num(r[7])]
    if sc=='CHAIN':chain_w[ws]=row
    elif sc=='SITE' and nm==LOC:site_w[ws]=row
if not site_w:sys.exit(f'no tracker rows for {LOC!r}; last good file kept')
w=[site_w[k] for k in sorted(site_w)];ch=[chain_w[k] for k in sorted(chain_w)]
out={'src':'Mapal Weekly Compliance Tracker (Mapal Compliance Hub, weekly pull every Monday)','pulled':datetime.date.today().isoformat(),
     'to':(datetime.date.fromisoformat(w[-1][0])+datetime.timedelta(6)).isoformat(),'location':LOC,'w':w,'chain':ch}
print(f'mapal compliance {A.site}: {len(w)} weeks for {LOC}, latest w/c {w[-1][0]}: on time {w[-1][1]}%, {w[-1][2]} open deviations, {w[-1][3] or "OK"}')
if A.check:sys.exit(0)
save(os.path.join(A.data,'mcomp.json'),out)
