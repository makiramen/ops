"""Promotions feed (promos.json) for one site, from the Site CC Marketing Calendar sheet (marketing team maintains it).
Sheet id in sites.json sources.marketing_calendar, read with the service account (share as Viewer with site-cc-reader).
Columns (header row, any order): Start, End, Promotion, Type, Sites, Channel, Offer / mechanic, Owner, Status, Notes, Link.
Sites = ALL, a cluster name, or a comma list of site codes (M14, IKI2, MakiNori). Dates dd/mm/yyyy or yyyy-mm-dd; End blank = ongoing.
A row reaches the page when Sites covers this site and Status is not Cancelled.
Keeps the last good file on any failure. Usage: pull_promos.py --site M14 --data DIR [--check] [--csv FILE]"""
import argparse,csv,datetime,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources'].get('marketing_calendar') or {}
P=os.path.join(A.data,'promos.json')
if not SRC.get('id') and not A.csv:
    save(P,{'src':'Site CC Marketing Calendar: not configured','pulled':None,'items':[]});print(f'promos {A.site}: no marketing_calendar in sites.json');sys.exit(0)
rows=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],SRC.get('range','A:K'))
if not rows:sys.exit('marketing calendar: empty read; last good file kept')
h=[re.sub(r'[^a-z]','',x.lower()) for x in rows[0]]
col=lambda *names:next((i for i,x in enumerate(h) if x in names),None)
I={'start':col('start','startdate','from'),'end':col('end','enddate','to'),'name':col('promotion','promo','name','campaign'),'type':col('type'),
   'sites':col('sites','site','where'),'channel':col('channel','channels'),'offer':col('offermechanic','offer','mechanic'),'owner':col('owner'),
   'status':col('status'),'notes':col('notes','note'),'link':col('link','url')}
if I['start'] is None or I['name'] is None:sys.exit('marketing calendar: Start or Promotion column missing, layout changed; last good file kept')
def iso(v):
    v=(v or '').strip()
    if not v:return None
    for f in ('%Y-%m-%d','%d/%m/%Y','%d/%m/%y','%d %b %Y','%d %B %Y'):
        try:return datetime.datetime.strptime(v,f).date().isoformat()
        except ValueError:pass
    return None
cluster=(C.get('cluster') or '').lower()
def covers(v):
    v=(v or '').strip()
    if not v or v.upper() in ('ALL','ESTATE','ALL SITES'):return True
    toks=[t.strip() for t in re.split(r'[,;/]',v) if t.strip()]
    for t in toks:
        tl=t.lower()
        if tl==A.site.lower() or tl==(C.get('label') or '').lower() or tl==(C.get('name') or '').lower():return True
        if cluster and (tl==cluster or tl in cluster and len(tl)>5):return True
    return False
items=[]
for r in rows[1:]:
    g=lambda k:(r[I[k]] if I[k] is not None and I[k]<len(r) else '').strip()
    if not g('name') or not covers(g('sites')):continue
    if g('status').lower() in ('cancelled','canceled','dropped'):continue
    st=iso(g('start'))
    if not st:continue
    items.append({'start':st,'end':iso(g('end')),'name':g('name'),'type':g('type') or 'Promotion','sites':g('sites') or 'ALL','channel':g('channel'),
                  'offer':g('offer'),'owner':g('owner'),'status':g('status'),'notes':g('notes'),'link':g('link')})
items.sort(key=lambda x:(x['start'],x['name']))
out={'src':'Site CC Marketing Calendar (Google Sheet, marketing team), service account read','pulled':datetime.date.today().isoformat(),'sheet':SRC.get('id'),'items':items,
     'note':'One row per promotion, event or campaign that covers this site. end null = ongoing. Upcoming = start after today; live = start on or before today and end on or after today (or no end).'}
if A.check:
    old=json.load(open(P)) if os.path.exists(P) else {'items':[]}
    print(f'check: {len(items)} rows for {A.site}, stored {len(old["items"])}');sys.exit(0)
save(P,out);print(f'promos {A.site}: {len(items)} rows')
