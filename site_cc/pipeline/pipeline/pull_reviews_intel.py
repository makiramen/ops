"""Reviews Intelligence slice for one site (revintel.json), from the AM Control Centre data/reviews_intel.json
(built by the AM CC reviews pass: every Google review labelled with issues and evidence, praise themes, dishes,
staff named with sentiment, a one line summary, plus the weekly / monthly / quarterly site write ups).
No Google access needed: the file sits in makiramen/ops data/, which the nightly job has checked out.
r = [id, date, stars, author, text, issues[[cat,sub,evidence]], praise[], staff[[name,sent]], dishes[[name,sent]], summary]
Keeps the last good file on any failure. --check prints and writes nothing.
Usage: pull_reviews_intel.py --site M14 --data DIR --intel ../data/reviews_intel.json [--check]"""
import argparse,datetime,json,os,sys
from common import site,save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--intel',required=True);ap.add_argument('--check',action='store_true');ap.add_argument('--since',default='2026-04-20')
A=ap.parse_args()
S,C=site(A.site)
code=C.get('reviews_code',A.site)
try:D=json.load(open(A.intel,encoding='utf-8'))
except Exception as e:sys.exit(f'reviews_intel.json unreadable ({e}); last good file kept')
if 'reviews' not in D or 'taxonomy' not in D:sys.exit('reviews_intel.json layout changed; last good file kept')
R=[]
for x in D['reviews']:
    if x.get('site')!=code or (x.get('date') or '')<A.since:continue
    R.append([x.get('id'),x['date'],x.get('stars'),(x.get('author') or '').strip(),(x.get('text') or '').strip(),
              [[i.get('cat'),i.get('sub'),(i.get('evidence') or '').strip()] for i in x.get('issues') or []],
              list(x.get('praise') or []),
              [[s.get('name'),s.get('sent')] for s in x.get('staff') or [] if s.get('name')],
              [[d.get('name'),d.get('sent')] for d in x.get('dishes') or [] if d.get('name')],
              (x.get('summary') or '').strip()])
R.sort(key=lambda r:(r[1],r[0] or ''))
ann={k:{'t':v.get('text',''),'w':v.get('written')} for k,v in (D.get('annotations') or {}).items() if k.endswith('|site|'+code)}
tax={k:{'l':v.get('label'),'o':v.get('owner'),'c':v.get('colour'),'s':v.get('subs',{})} for k,v in D['taxonomy'].items()}
ro=(D.get('roster') or {}).get(code,{})
built=(D.get('meta') or {}).get('built_at','')[:10]
out={'src':'AM Control Centre Reviews Intelligence (data/reviews_intel.json)','built':built,'pulled':datetime.date.today().isoformat(),
     'to':max([r[1] for r in R]) if R else None,'code':code,'gm':ro.get('gm'),'tax':tax,'praise':D.get('praise_themes',{}),'ann':ann,'r':R}
neg=sum(1 for r in R if r[2] is not None and r[2]<=3)
print(f"revintel {A.site}: {len(R)} reviews since {A.since}, {neg} at 3 stars or below, {len(ann)} write ups, intel built {built}")
if A.check:sys.exit(0)
save(os.path.join(A.data,'revintel.json'),out)
