"""Mapal forms feed (mapal.json) from the Mapal Broker Data sheet, tab "forms", read with the service account.
The broker Apps Script (SiteCC_Mapal.gs, daily 07:00 UK) writes one row per completed Mapal form:
form_id, form_name, location, date, score, max_score, pct, answers, deviations, open_deviations, auditor, state,
deviation_items, last_modified. Site rows = location == sites.json mapal_location.
f = [date, form, pct, score, max, deviations, open, auditor, items]. to = newest form date for the estate (feed age).
Keeps the last good file on any failure. --check prints and writes nothing.
Usage: pull_mapal.py --site M14 --data DIR [--check] [--csv forms_export.csv]"""
import argparse,csv,datetime,json,os,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources']['mapal_broker'];LOC=C['mapal_location']
rows=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],"'forms'!A:N")
if not rows or rows[0][:4]!=['form_id','form_name','location','date']:sys.exit('forms tab missing or layout changed; last good file kept')
H=rows[0];R=[dict(zip(H,r+['']*(len(H)-len(r)))) for r in rows[1:] if r and r[0]]
if not R:sys.exit('forms tab is empty; last good file kept')
import re
def tidy(x):
    cut=len(x.strip())>=90 and not x.strip()[-1] in '?.)';x=re.sub(r'\s*[—–]\s*',', ',x.strip());x=re.sub(r'\s+,\s*',', ',x);x=re.sub(r'\s{2,}',' ',x)
    return x[:x.rfind(' ')].rstrip(' ,')+'...' if cut and ' ' in x else x   # broker cuts items at 90 chars
num=lambda x:float(x) if str(x).strip() not in ('',) else None
f=[]
for r in R:
    if r['location'].strip()!=LOC:continue
    f.append([r['date'][:10],r['form_name'].strip(),num(r['pct']),num(r['score']),num(r['max_score']),int(num(r['deviations']) or 0),
              int(num(r['open_deviations']) or 0),r['auditor'].strip(),[tidy(x) for x in r['deviation_items'].split('|') if x.strip()]])
f.sort(key=lambda x:(x[0],x[1]))
out={'src':'Mapal (GetCompliant) forms via the Mapal Broker, tab forms','pulled':datetime.date.today().isoformat(),
     'to':max(r['date'][:10] for r in R),'location':LOC,'f':f}
print(f"mapal {A.site}: {len(f)} forms for {LOC}, estate newest {out['to']}:",{n:sum(1 for x in f if x[1]==n) for n in sorted({x[1] for x in f})})
if A.check:sys.exit(0)
save(os.path.join(A.data,'mapal.json'),out)
