"""Daily cash up, covers and delivery for one site from Auto Cash Up, tab Raw Data 2.
Usage: python3 pipeline/pull_cashup.py --site M14 [--data .] [--days 21 | --from YYYY-MM-DD] [--csv file] [--check]
--csv reads a saved export of Raw Data 2 instead of the API (testing).
Rules (as covers_pull.py and pull_daily_cashup.py): drop days before opening and today onwards (partial day);
daily: a £0 row is not cashed up yet and is skipped; covers: 25/12 kept as 0 (closed);
FOH/BOH split located by reconciliation (vendor_cashup.extract_split); a split that fails validation is stored as nulls with status failed_validation.
Only days inside the window are rewritten; older stored days are left alone."""
import csv,sys,os,argparse,datetime
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import common as C, vendor_cashup as V
ap=argparse.ArgumentParser();ap.add_argument('--site',default='M14');ap.add_argument('--data',default='.')
ap.add_argument('--days',type=int,default=21);ap.add_argument('--from',dest='frm');ap.add_argument('--csv');ap.add_argument('--check',action='store_true')
a=ap.parse_args()
S,cfg=C.site(a.site);src=S['sources']['auto_cash_up']
rows=list(csv.reader(open(a.csv,encoding='utf-8-sig'))) if a.csv else C.sheet_values(src['id'],src['range'])
h=rows[0]
for i,e in V.EXPECTED_HEADERS.items():
    if (h[i] if i<len(h) else '').strip()!=e.strip():sys.exit(f'FATAL: Raw Data 2 column {i} is {h[i] if i<len(h) else None!r}, expected {e!r}')
T=C.today().isoformat();lo=a.frm or (C.today()-datetime.timedelta(a.days)).isoformat();lo=max(lo,cfg.get('opened') or '2026-04-20')
dly,cov,dlv=[C.json.load(open(os.path.join(a.data,f))) for f in ('daily.json','covers.json','delivery.json')]
n=0;warn=[]
for r in rows[1:]:
    r=r+['']*(30-len(r))
    if r[V.IDX_VENUE].strip()!=cfg['cashup_venue']:continue
    d=V.iso_date(r[V.IDX_DATE])
    if not d or d<lo or d>=T:continue
    sales=V.num(r[V.IDX_ACTUAL]);cust=V.num(r[V.IDX_COVERS])
    # covers and delivery: every trading day from opening, zero kept (closed day)
    c=int(cust or 0)
    tdel=V.num(r[V.IDX_DELIVERY_TARGET]);gdel=V.num(r[V.IDX_DELIVERY]) or 0.0
    newc,newd=c,[tdel if tdel else None,round(gdel,2)]
    if sales or d in cov.get('_closed',[]):
        if a.check and (cov['d'].get(d)!=newc or dlv['d'].get(d)!=newd):print('DIFF cov/del',d,cov['d'].get(d),dlv['d'].get(d),'source',newc,newd)
        cov['d'][d]=newc;dlv['d'][d]=newd
    if not sales:continue
    lab=V.num(r[V.IDX_LABOUR_TOTAL]);w=V.pct(r[V.IDX_WAGE_PCT])
    if w is None and lab and sales:w=round(lab/sales*100,2)
    foh,_,boh,_,st=V.extract_split(r,lab,a.site,d,warn)
    ts,td=V.num(r[V.IDX_SIT_IN_TARGET]),V.num(r[V.IDX_DELIVERY_TARGET])
    tgt=None if (ts is None and td is None) else round((ts or 0)+(td or 0),2)
    row=[round(sales,2),tgt or None,int(cust or 0),V.num(r[V.IDX_AVG_SPEND]),foh,boh,w,st]
    if a.check and dly.get(d)!=row:print('DIFF daily',d,dly.get(d),'source',row)
    dly[d]=row;n+=1
if not a.check:
    for f,o in (('daily.json',dict(sorted(dly.items()))),):C.save(os.path.join(a.data,f),o)
    cov['d']=dict(sorted(cov['d'].items()));cov['_pulled']=T;C.save(os.path.join(a.data,'covers.json'),cov)
    dlv['d']=dict(sorted(dlv['d'].items()));dlv['_pulled']=T;C.save(os.path.join(a.data,'delivery.json'),dlv)
print('cash up',a.site,'days',n,'from',lo,'last',max(dly),'warnings',len(warn))
