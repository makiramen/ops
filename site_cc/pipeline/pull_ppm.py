"""PPM schedule (ppm.json): planned maintenance and certificates per site (fire, gas, EICR, PAT, TR19, pest, grease, legionella)
with contractor and next due date. Base: site_cc/ppm_contractors.json, converted from ppm_contractors_by_site.xlsx (Michael, 05/10/2026).
08/10/2026: overlaid with Mapal. Tab "certs" of the Mapal Broker Data sheet (SiteCC_Certs.gs, daily 08:15 UK) lists every completed
Mapal certificate or contractor form; for each PPM line the newest matching Mapal form (same location) sets last done and
next due = last done + the PPM interval, with who and the Mapal link. Lines Mapal has no log for keep the schedule's date.
Item = [ppm, contractor, next due, months, note, last done, mapal url]. --check prints and writes nothing."""
import argparse,datetime,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args();S,C=site(A.site)
HERE=os.path.dirname(os.path.abspath(__file__))
src=json.load(open(os.path.join(HERE,'..','ppm_contractors.json')))
it=[[x['ppm'],x['who'],x['due'],x['m'],x['note'],None,''] for x in src['items'] if x['code']==A.site]
# PPM line -> Mapal form name test. Conservative: a weekly in house log (Fire Alarm Testing) must not close a contractor service.
MATCH=[(r'fire risk',r'fire risk'),(r'fire alarm',r'fire alarm.*(service|servic|maint|contractor|certif)'),(r'emergency light',r'emergency light.*(3|three|annual|service|certif|test)'),
       (r'extinguisher',r'extinguisher.*(service|servic|annual|certif|inspection)'),(r'gas safety|cp42',r'gas safety|cp42'),(r'eicr',r'eicr|electrical installation'),
       (r'\bpat\b',r'\bpat\b|portable appliance'),(r'tr19|extraction|duct',r'tr19|extraction clean|duct'),(r'pest',r'pest control'),   # not the daily 'check for signs of pest activity' task(r'grease',r'grease'),
       (r'legionella',r'legionella|water (hygiene|risk)'),(r'\blift\b',r'\blift\b'),(r'sprinkler',r'sprinkler'),(r'asbestos',r'asbestos')]
def addm(d,m):
    y,mo=d.year,d.month+int(m);y+=(mo-1)//12;mo=(mo-1)%12+1
    try:return d.replace(year=y,month=mo)
    except ValueError:return d.replace(year=y,month=mo,day=28)
LOC=C.get('mapal_location');hits=0;asof=src['asof']
if LOC and it:
    try:rows=sheet_values(S['sources']['mapal_broker']['id'],"'certs'!A:H")
    except Exception as e:rows=[];print('certs tab not readable, schedule dates kept:',str(e)[:120])
    if rows and rows[0][:4]==['form_id','form_name','location','date']:
        H=rows[0];F=[dict(zip(H,r+['']*(len(H)-len(r)))) for r in rows[1:] if r and r[0]]
        mine=[f for f in F if f['location'].strip()==LOC and f['date'][:10]]
        for x in it:
            key=x[0].lower();best=None
            for pk,fk in MATCH:
                if re.search(pk,key):
                    c=[f for f in mine if re.search(fk,f['form_name'],re.I)]
                    if c:best=max(c,key=lambda f:f['date'][:10])
                    break
            if not best:continue
            d=datetime.date.fromisoformat(best['date'][:10]);due=addm(d,x[3]) if x[3] else None
            x[5]=d.isoformat();x[6]=best.get('url','');hits+=1
            if due:x[2]=due.isoformat()
            x[4]='Mapal: '+best['form_name'].strip()+(' by '+best['who'].strip() if best.get('who','').strip() else '')+(' (form '+str(best['form_id'])+')')
        if mine:asof=max(asof,max(f['date'][:10] for f in mine))
if A.check:print(json.dumps(it,ensure_ascii=False,indent=1));sys.exit(0)
save(os.path.join(A.data,'ppm.json'),{'src':src['src']+(' + Mapal certificate logs' if hits else ''),'asof':asof if it else None,'items':it},indent=1)
print(f'ppm {A.site}: {len(it)} items, {hits} dated from Mapal')
