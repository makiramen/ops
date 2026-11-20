"""Franchise weekly KPIs from Matt's per-site KPI sheet (17/11/2026, Michael: "wire them into the franchise Site Control Centre pages").
Matt's email "Franchise Site KPIs" (12/11/2026) gave one KPI sheet per franchise site (sites.json kpi_sheet): MAF1 West End, MAF2 NQ,
MAF3 O2, MAF4 Braehead; same template as the corporate KPI sheets, fed from the same raw files.
Reads the sheet's 'Analysis' tab (one row per week commencing, five blocks each starting with a 'Commencing' column:
Sales | Labour | Covers & Spend | Food Cost | Additionals) and, for every CLOSED week from 04/05/2026 with sales, overwrites
sales, target, covers, SPH (avg spend), wage %, food cost %, hours and waste in weekly.json (the AM CC carries no franchise
figures, its MAF rows were wrong: wage 71%, food 62.9%). Reviews, Deliveroo and the rest of each row are kept.
Drinks / sushi / sides % go to mix.json weeks when the site has no Kobas_Daily mix of its own.
Only runs for sites with a kpi_sheet id; a site without one exits quietly. Keeps the last good files on any failure. --check writes nothing."""
import argparse,json,os,datetime
from common import site,save,sheet_values,today
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site)
SID=C.get('kpi_sheet')
if not SID:print(f'kpisheet {A.site}: no kpi_sheet in sites.json, nothing to do');raise SystemExit(0)
FROM='2026-05-04'
rows=sheet_values(SID,"'Analysis'!A1:AD400")
if not rows:raise SystemExit(f'kpisheet {A.site}: Analysis tab empty or not shared with site-cc-reader, keeping the last good files')
hi=next((i for i,r in enumerate(rows[:15]) if any(str(c).strip().lower().startswith('commencing') for c in r)),None)
if hi is None:raise SystemExit(f'kpisheet {A.site}: no Commencing header row in Analysis, keeping the last good files. First rows: {rows[:6]}')
H=[str(h).strip().lower() for h in rows[hi]]
starts=[i for i,h in enumerate(H) if h.startswith('commencing')]+[len(H)]
blocks=[{H[j]:j for j in range(starts[b],starts[b+1])} for b in range(len(starts)-1)]
def col(b,*names):
    if b>=len(blocks):return None
    for n in names:
        for h,j in blocks[b].items():
            if h==n or h.startswith(n):return j
    return None
c_sales,c_tgt=col(0,'actual'),col(0,'sales target')
c_lab,c_hrs,c_wage=col(1,'labour cost'),col(1,'actual hours'),col(1,'wage revenue','wage')
c_cov,c_sph=col(2,'covers'),col(2,'avg spend')
c_food=col(3,'food cost %')
c_waste,c_dr,c_su,c_si=col(4,'waste'),col(4,'drinks'),col(4,'sushi'),col(4,'sides')
miss=[n for n,c in (('sales',c_sales),('target',c_tgt),('wage',c_wage),('covers',c_cov),('food',c_food)) if c is None]
if miss:raise SystemExit(f'kpisheet {A.site}: Analysis header missing {miss}: {H}')
def num(v):
    s=str(v).replace('£','').replace('%','').replace(',','').strip()
    if s in ('','-'):return None
    try:return float(s)
    except ValueError:return None
def iso(v):
    for f in ('%d/%m/%Y','%Y-%m-%d','%d/%m/%y'):
        try:return datetime.datetime.strptime(str(v).strip()[:10],f).date()
        except ValueError:pass
    return None
def g(r,c):return num(r[c]) if c is not None and c<len(r) else None
lastclosed=today()-datetime.timedelta(days=today().weekday()+7)   # Monday of the last completed week
wk={};mixw={}
for r in rows[hi+1:]:
    d=iso(r[starts[0]]) if len(r)>starts[0] else None
    if not d or d.isoformat()<FROM or d>lastclosed:continue
    sales=g(r,c_sales)
    if not sales:continue
    cov=g(r,c_cov);sph=g(r,c_sph)
    if sph is None and cov:sph=round(sales/cov,2)
    food=g(r,c_food)
    if food is not None and (food<=0 or food>100):food=None   # a 0.00% or 164% at source is an unfilled week, not a measurement
    wage=g(r,c_wage)
    if wage is not None and wage<=0:wage=None
    wk[d.isoformat()]={'sales':round(sales,2),'target':g(r,c_tgt),'covers':int(cov) if cov else None,'sph':sph,'wage':wage,'food':food,
                       'hours':g(r,c_hrs),'waste':g(r,c_waste)}
    m=[g(r,c_dr),g(r,c_su),g(r,c_si)]
    if any(x for x in m):mixw[d.isoformat()]={'drinks':m[0] or None,'sushi':m[1] or None,'sides':m[2] or None,'n':7}
print(f'kpisheet {A.site}: {len(wk)} closed weeks from {FROM}, latest {max(wk) if wk else None}, mix weeks {len(mixw)}')
if not wk:raise SystemExit(f'kpisheet {A.site}: no closed weeks with sales, keeping the last good files')
P=os.path.join(A.data,'weekly.json')
W=json.load(open(P)) if os.path.exists(P) else {'src':'','site':A.site,'k':["wc","sales","target","covers","sph","wage","food","hours","waste","rev","rating","neg","fv","dv","eff","rl"],
   'dk':["wc","r","open","prep","rej","inacc","rider","sales","orders","aov"],'main':[],'droo':[]}
K=W['k'];rowsby={r[0]:r for r in W['main']}
for wc,v in wk.items():
    r=rowsby.get(wc) or [wc]+[None]*(len(K)-1)
    for k,x in v.items():r[K.index(k)]=x
    if 'rl' in K:r[K.index('rl')]=None   # the AM CC red light was built on its own (wrong) franchise figures; franchise is not red-lit
    rowsby[wc]=r
W['main']=[rowsby[k] for k in sorted(rowsby)]
W['src']=f"Franchise KPI sheet (Matt), Analysis tab, {SID}: sales, target, covers, SPH, wage %, food cost %, hours, waste. Reviews and Deliveroo from the AM Control Centre."
W['pulled']=today().isoformat()
if A.check:print(json.dumps(W['main'][-3:]));raise SystemExit(0)
save(P,W)
MP=os.path.join(A.data,'mix.json')
cur=json.load(open(MP)) if os.path.exists(MP) else {}
if mixw and not cur.get('days'):   # the site's own Kobas_Daily mix wins; franchise sites have none
    save(MP,{'src':'Franchise KPI sheet (Matt), Analysis tab','srctxt':'the franchise KPI sheet (Analysis tab)','sheet':SID,'pulled':today().isoformat(),
             'targets':{'drinks':10.0,'sushi':20.0,'sides':13.5},'days':{},'weeks':dict(sorted(mixw.items()))})

# 20/11/2026 (Michael: "site cc's should be taken from here", Matt's KPI sheets): the gate week bar's daily sales targets and
# budget rota (Sales to target, Labour left) come from the KPI sheet's 'Targets by DAY' tab, not Mona Lisa (MAF1/MAF2 are not
# in Mona Lisa at all, MAF4 had no Target Sales there). Cols: A date, C sales target, G 2026 budget £. Overwrites labour.json 'open'.
try:
    td=sheet_values(SID,"'Targets by DAY'!A1:H800")
    OW=today()-datetime.timedelta(today().weekday());ow={}
    for r in td:
        d=iso(r[0]) if r else None
        if d and OW<=d<OW+datetime.timedelta(7):ow[d.isoformat()]={'tgt':g(r,2),'bud':g(r,6)}
    if len(ow)==7:
        LP=os.path.join(A.data,'labour.json');L=json.load(open(LP)) if os.path.exists(LP) else {}
        b=[v['bud'] for v in ow.values()]
        L['open']={'wc':OW.isoformat(),'bud':round(sum(b),2) if all(x is not None for x in b) else None,'tgt':{k:v['tgt'] for k,v in sorted(ow.items())},
                   'src':'Franchise KPI sheet, Targets by DAY'}
        print(f"kpisheet {A.site}: open week {OW} from Targets by DAY, budget {L['open']['bud']}, targets {list(L['open']['tgt'].values())}")
        save(LP,L)
    else:print(f'kpisheet {A.site}: Targets by DAY has {len(ow)} of 7 days for w/c {OW}, open week left as is')
except SystemExit:raise
except Exception as e:print(f'kpisheet {A.site}: Targets by DAY read failed ({e}), open week left as is')
