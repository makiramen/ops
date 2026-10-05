"""Google reviews feed (reviews.json) from the Google Reviews Maki & Ramen sheet, Raw Data tab, read with the service account.
The sheet is filled nightly by MakiManc/google-reviews (03:00 UTC). Columns: A reviewId, D author_name, E rating (word), F comment,
G createTime, K Site (label), L Date (dd/mm/yyyy text, the local day; falls back to createTime).
Merge rule: reviews already in reviews.json keep their labels (AM CC Reviews Intelligence, Claude checked); only the star rating is refreshed.
New reviews are labelled by the same keyword rules (reviews_rules.py, reviews_taxonomy.json). Dedupe on reviewId.
No reply column exists in the sheet, so "Needs a reply" still clears from the page outbox only.
Keeps the last good file on any failure. --check reports and writes nothing.
Usage: pull_reviews.py --site M14 --data DIR [--check] [--csv raw_data_export.csv]"""
import argparse,csv,datetime,json,os,re,sys
from common import site,save,sheet_values
import reviews_rules as RR
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources']['google_reviews'];LABEL=C.get('reviews_site')
if not LABEL:print(f'reviews {A.site}: no Google Reviews site label in sites.json, feed stays n/a');sys.exit(0)
HERE=os.path.dirname(os.path.abspath(__file__))
P=os.path.join(A.data,'reviews.json')
old=json.load(open(P));FROM=min(r['d'] for r in old['r']) if old['r'] else '2026-04-20'
raw=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],"'Raw Data'!A:L")
if len(raw)<100:sys.exit(f'Raw Data returned {len(raw)} rows, too few; last good file kept')
STARS={'FIVE':5,'FOUR':4,'THREE':3,'TWO':2,'ONE':1,'5':5,'4':4,'3':3,'2':2,'1':1}
def iso(L,G):
    m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})',L or '')
    if m:return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    m=re.match(r'^(\d{4}-\d{2}-\d{2})',L or '') or re.match(r'^(\d{4}-\d{2}-\d{2})',G or '')
    return m.group(1) if m else None
def nm(a):
    p=(a or '').split()
    return (p[0].capitalize()+(' '+p[-1][0].upper()+'.' if len(p)>1 else '')) if p else 'Anonymous'
def clean(t):
    t=(t or '').replace('—',', ').replace('–','-').strip()
    return t[:317].rsplit(' ',1)[0]+'...' if len(t)>320 else t
TAX=RR.compile_tax(json.load(open(os.path.join(HERE,'reviews_taxonomy.json'))))
# Old records (AM CC) carry a different id scheme from the sheet, so match on received day + reviewer as well as id.
# Clean up: drop any rule-labelled copy of a review that also exists with AM CC labels (run #8, 02/10/2026, duplicated 276).
dk=lambda r:(r['d'],r['a'])
amcc={dk(r) for r in old['r'] if not r.get('lab')}
old['r']=[r for r in old['r'] if not (r.get('lab') and dk(r) in amcc)]
have={r['id']:r for r in old['r']};byk={}
for r in old['r']:byk.setdefault(dk(r),r)
seen=set();new=[];restar=0;latest=None
for row in raw[1:]:
    row=row+['']*(12-len(row))
    if row[10].strip()!=LABEL or not row[0] or row[0] in seen:continue
    seen.add(row[0]);d=iso(row[11],row[6]);s=STARS.get(str(row[4]).strip().upper())
    if not d or d<FROM or not s:continue
    latest=max(latest or d,d);rid=row[0][-10:]
    hit=have.get(rid) or byk.get((d,nm(row[3])))
    if hit:
        if hit['s']!=s:hit['s']=s;restar+=1
        continue
    text,_,_=RR.norm_text(row[5]);cl=RR.classify({'t':row[5],'s':s},TAX)
    wc=(datetime.date.fromisoformat(d)-datetime.timedelta(datetime.date.fromisoformat(d).weekday())).isoformat()
    new.append({'id':rid,'d':d,'wc':wc,'s':s,'a':nm(row[3]),'t':clean(text),'i':[[x['cat'],x['sub']] for x in cl.get('issues',[])],
                'ds':cl.get('dishes',[]),'lab':'rules'})
if latest is None:sys.exit(f'no rows for site label {LABEL!r}; last good file kept')
allr=sorted(list(have.values())+new,key=lambda x:(x['d'],x['id']))
print(f'reviews {A.site}: {len(seen)} source rows, {len(new)} new, {restar} star changes, latest {latest}')
for r in new[:20]:print('  new',r['d'],r['s'],r['a'],r['i'])
# Freshness: the date the google-reviews job last wrote the sheet (Raw Data Q1:R1 'Last updated'), not today, so a dead upstream job shows as Late data
stamp=None
if not A.csv:
    try:
        q=sheet_values(SRC['id'],"'Raw Data'!Q1:R1");stamp=q[0][1][:10] if q and len(q[0])>1 else None
    except Exception as e:print('  no Last updated stamp:',e)
print('  sheet last updated',stamp)
if A.check:sys.exit(0)
old.update(src='Google reviews: Google Reviews sheet Raw Data (nightly google-reviews job); history labelled by AM CC Reviews Intelligence, new reviews by the same keyword rules',
           built=stamp or latest,to=latest,r=allr)
save(P,old)
