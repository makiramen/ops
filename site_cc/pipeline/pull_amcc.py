"""Weekly KPI rows and Deliveroo weekly for one site, from the AM Control Centre weekly site JSON.
Source: <amcc_data>/<SITE>_wc_<monday>.json (built by build_site_json.py in the AM CC weekly refresh).
Usage: python3 pipeline/pull_amcc.py --amcc ../am_rebuild/data --site M14 [--data .] [--from 2026-05-04] [--check]
Writes weekly.json. Only weeks present at source are written; a week missing at source keeps its stored row.
--check compares with the stored weekly.json and writes nothing."""
import json,glob,os,re,argparse,datetime
ap=argparse.ArgumentParser();ap.add_argument('--amcc',required=True);ap.add_argument('--site',default='M14')
ap.add_argument('--data',default='.');ap.add_argument('--from',dest='frm',default='2026-05-04');ap.add_argument('--check',action='store_true')
a=ap.parse_args()
g=lambda o,*p:(o:=o) and [o:=(o or {}).get(k) for k in p][-1]
def row(s,wc):
    k=s.get('kpis',{});st=s.get('stock_take',{});rv=s.get('reviews',{});ef=s.get('efficiency_score',{})
    m=[wc,g(k,'sales','actual'),g(k,'sales','target'),g(k,'covers','actual'),g(k,'sph','actual'),g(k,'wage_pct','actual'),g(k,'food_pct','actual'),
       g(k,'labour_hours','actual'),g(k,'waste','actual'),rv.get('new_reviews'),rv.get('week_avg_rating'),rv.get('negatives'),
       g(st,'food','variance_pct'),g(st,'drinks','variance_pct'),ef.get('score'),g(s,'red_light','status')]
    d=s.get('deliveroo') or {}
    r=[wc]+[d.get(x) for x in ('rating','open_hours_pct','avg_prep_min','rejection_pct','inaccuracy_pct','rider_wait_5min_pct','sales','orders','aov')]
    return m,r
P=os.path.join(a.data,'weekly.json');W=json.load(open(P))
M={r[0]:r for r in W['main']};D={r[0]:r for r in W['droo']}
got=[]
for f in sorted(glob.glob(os.path.join(a.amcc,f"{a.site}_wc_*.json"))):
    wc=re.search(r'_wc_(\d{4}-\d{2}-\d{2})\.json$',f)
    if not wc or wc.group(1)<a.frm:continue
    wc=wc.group(1);s=json.load(open(f))['sites'].get(a.site)
    if not s:continue
    m,r=row(s,wc);got.append(wc)
    if a.check:
        for lab,old,new in (('main',M.get(wc),m),('droo',D.get(wc),r)):
            if old!=new:print('DIFF',lab,wc,'\n  stored',old,'\n  source',new)
    else:M[wc]=m;D[wc]=r
print('weeks at source',len(got),got[:1],got[-1:])
# Efficiency detail (eff.json), estate ladder (effall.json), site standing (stand.json eff); stand.json lg (league) is kept as stored
EF=json.load(open(os.path.join(a.data,'eff.json')));EA=json.load(open(os.path.join(a.data,'effall.json')));SD=json.load(open(os.path.join(a.data,'stand.json')))
for wc in got:
    s=json.load(open(os.path.join(a.amcc,f"{a.site}_wc_{wc}.json")))['sites'][a.site].get('efficiency_score') or {}
    ef={'s':s.get('score'),'c':{k:[v.get('value'),v.get('basis')] for k,v in (s.get('components') or {}).items()},'x':s.get('components_dropped',[])}
    fa=os.path.join(a.amcc,f"all_sites_wc_{wc}.json")
    lad=None
    if os.path.exists(fa):
        al=json.load(open(fa))['sites']
        lad=sorted([[c,(v.get('efficiency_score') or {}).get('score')] for c,v in al.items() if (v.get('efficiency_score') or {}).get('score') is not None],key=lambda x:-x[1])
    st=None
    if lad:
        sc=ef['s'];st=[1+sum(1 for c,v in lad if v>sc),len(lad),sc] if sc is not None else None
    for lab,store,new in (('eff',EF,ef),('effall',EA,lad),('stand',SD['eff'],st)):
        if new is None:continue
        if a.check:
            if store.get(wc)!=new:print('DIFF',lab,wc,'\n  stored',str(store.get(wc))[:300],'\n  source',str(new)[:300])
        else:store[wc]=new
if not a.check:
    for f,o in (('eff.json',EF),('effall.json',EA),('stand.json',SD)):
        q=os.path.join(a.data,f);json.dump(o,open(q+'.tmp','w'),ensure_ascii=False,separators=(',',':'));os.replace(q+'.tmp',q)
if not a.check:
    W['main']=[M[k] for k in sorted(M)];W['droo']=[D[k] for k in sorted(D)];W['pulled']=datetime.date.today().isoformat()
    json.dump(W,open(P+'.tmp','w'),separators=(',',':'));os.replace(P+'.tmp',P);print('weekly.json written, last',max(M))
