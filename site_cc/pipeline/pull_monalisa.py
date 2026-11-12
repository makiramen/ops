"""Weekly Mona Lisa figures for one site: ml_weekly.json (sales, target, wage %, labour hours, waste) and labour.json (budget vs actual labour £).
Source: Mona Lisa 1_yzry0OCWA9N6-I9mWxmAFwfBqMWwEzMN3kPpSp6HJw, tab Input Tabs (gid 1107995776), one row per venue per day.
Usage: python3 pipeline/pull_monalisa.py --site M14 [--data .] [--csv file] [--check]
Only complete Mon to Sun weeks are written. Logic as monalisa_backfill_20261001.py; columns asserted by header name.
10/11/2026 (Michael): budget rota = Input Tabs column "Budget" (J); when a day's Budget is blank it falls back to "Projected" (K).
Found on M3: Budget has been blank since 22/09 while Projected is filled (w/c 02/11 projected 7,319 vs actual 9,026), so the KPI
Sheet showed a 0 budget rota. labour.json 'proj' records, per week, how many of the 7 days came from Projected so the page can label it."""
import csv,sys,os,argparse,datetime
from collections import defaultdict
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import common as C
ap=argparse.ArgumentParser();ap.add_argument('--site',default='M14');ap.add_argument('--data',default='.');ap.add_argument('--csv');ap.add_argument('--check',action='store_true')
ap.add_argument('--from',dest='frm',default='2026-05-04')
a=ap.parse_args()
S,cfg=C.site(a.site);src=S['sources']['mona_lisa']
r=list(csv.reader(open(a.csv,encoding='utf-8-sig'))) if a.csv else C.sheet_values(src['id'],src['range'])
h=[c.strip() for c in r[0]]
need={'act':'Actual (£)','bud':'Budget','lab':'Actual Total Labour (£)','hrs':'Actual Total Hours','waste':'Total Waste (£)','tgt':'Target Sales'}
C_={}
PROJ=h.index('Projected') if 'Projected' in h else None   # fallback column, optional so a renamed header never stops the pull
if PROJ is None:print('WARN: Mona Lisa Input Tabs has no column Projected, no budget rota fallback')
for k,n in need.items():
    if n not in h:sys.exit(f'FATAL: Mona Lisa Input Tabs has no column {n!r}')
    C_[k]=h.index(n)
def num(s):
    s=(s or '').replace('£','').replace(',','').replace('%','').strip()
    try:return float(s) if s not in('','-') else None
    except ValueError:return None
START=datetime.date.fromisoformat(a.frm);T=C.today();rows={}
OW=T-datetime.timedelta(T.weekday());ow={}   # 12/11/2026 (Michael): the gate's week bar needs this week's budget rota and daily sales targets, future days included
for x in r[1:]:
    if not x or x[0].strip()!=cfg['cashup_venue']:continue
    try:d=datetime.datetime.strptime(x[1].strip(),'%d/%m/%Y').date()
    except ValueError:continue
    if OW<=d<OW+datetime.timedelta(7):
        b=num(x[C_['bud']]) if C_['bud']<len(x) else None
        if b is None and PROJ is not None:b=num(x[PROJ]) if PROJ<len(x) else None
        ow[d.isoformat()]={'bud':b,'tgt':num(x[C_['tgt']]) if C_['tgt']<len(x) else None}
    if d<START or d>=T:continue
    rows[d]={k:num(x[i]) if i<len(x) else None for k,i in C_.items()}
    rows[d]['proj']=0
    if rows[d]['bud'] is None and PROJ is not None:   # Budget blank: take Projected for that day
        pv=num(x[PROJ]) if PROJ<len(x) else None
        if pv is not None:rows[d]['bud']=pv;rows[d]['proj']=1
W=defaultdict(list)
for d in sorted(rows):W[d-datetime.timedelta(d.weekday())].append(rows[d])
P=lambda f:os.path.join(a.data,f)
ml=C.json.load(open(P('ml_weekly.json')));lab=C.json.load(open(P('labour.json')));lab.setdefault('proj',{})
for wc,xs in sorted(W.items()):
    if len(xs)<7:continue
    Sx=lambda k:round(sum(v[k] or 0 for v in xs),2)
    act,lm=Sx('act'),Sx('lab');k=wc.isoformat()
    m={'sales':act,'target':Sx('tgt'),'wage':round(lm/act*100,2) if act else None,'hours':Sx('hrs'),'waste':Sx('waste')};lb=[Sx('bud'),lm]
    if a.check:
        if ml['w'].get(k)!=m:print('DIFF ml',k,ml['w'].get(k),m)
        if lab['d'].get(k)!=lb:print('DIFF labour',k,lab['d'].get(k),lb)
    ml['w'][k]=m;lab['d'][k]=lb
    np_=sum(v['proj'] for v in xs)
    if np_:lab['proj'][k]=np_
    else:lab['proj'].pop(k,None)
if not a.check:
    ml['w']=dict(sorted(ml['w'].items()));ml['pulled']=T.isoformat();lab['d']=dict(sorted(lab['d'].items()));lab['proj']=dict(sorted(lab['proj'].items()));lab['pulled']=T.isoformat()
    lab['open']={'wc':OW.isoformat(),'bud':round(sum(v['bud'] for v in ow.values()),2) if len(ow)==7 and all(v['bud'] is not None for v in ow.values()) else None,'tgt':{k:v['tgt'] for k,v in sorted(ow.items())}}
    C.save(P('ml_weekly.json'),ml);C.save(P('labour.json'),lab)
print('mona lisa',a.site,'weeks',sum(1 for x in W.values() if len(x)==7),'last',max(ml['w']))
