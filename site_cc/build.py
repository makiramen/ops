"""Site Control Centre build. Data free: every figure comes from a feed file.
Usage: python3 build.py [--data DIR] [--out DIR] [--today YYYY-MM-DD]
Writes site_control_centre.html (artifact body), Site_Control_Centre_full.html (standalone, offline) and build_log.json.
A build that fails a check writes nothing, so the last good page stays live."""
import json,re,os,sys,datetime,argparse
ap=argparse.ArgumentParser();ap.add_argument('--data',default='.');ap.add_argument('--out',default='.');ap.add_argument('--today');ap.add_argument('--site')
A=ap.parse_args()
TODAY=datetime.date.fromisoformat(A.today) if A.today else datetime.date.today()
P=lambda f:os.path.join(A.data,f)
J=lambda f:json.load(open(P(f)))
R=lambda f:open(P(f)).read().strip()
def JD(f,d):
    try:return J(f)
    except Exception:return d
# Site config (sites.json): code, names, cluster, AM / DAM, league tier and which feeds exist for this site
SJ=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'sites.json')))
CODE=A.site or JD('weekly.json',{}).get('site') or 'M14'
if CODE not in SJ['sites']:sys.exit(f'BUILD FAILED, nothing written: {CODE} not in sites.json')
SC=SJ['sites'][CODE];TIERS=SJ.get('tiers') or {}
TN=[k for k,v in TIERS.items() if CODE in v]
SITE={'code':CODE,'name':SC['name'],'label':SC.get('label') or CODE,'cluster':SC.get('cluster',''),'am':SC.get('am',''),'dam':SC.get('dam',''),
      'tier':TN[0] if TN else None,'tiers':TIERS,'dec':(SJ.get('clusters') or {}).get(SC.get('cluster'),{}).get('dec',''),'sph':SC.get('sph',22),'gm':None,'tierSites':TIERS[TN[0]] if TN else [],'compTab':SC.get('compliance_tab'),
      'has':{'delivery':SC.get('delivery',True)!=False,'loyalty':bool(SC.get('loyalty_venue')),'mapal':bool(SC.get('mapal_location')),'broth':bool(SC.get('broth_label')),'comp':bool(SC.get('compliance_tab'))},
      'sites':[[c,v.get('label') or c,v['name']] for c,v in SJ['sites'].items() if v.get('live')]}

# Weekly KPI rows and Deliveroo weekly (pull_amcc.py writes weekly.json)
W=J('weekly.json');main=W['main'];droo=W['droo']
D={r[0]:r for r in droo} if SC.get('delivery',True)!=False else {}  # no delivery site (sites.json delivery:false): no Deliveroo rows
DB=J('droo_backfill.json')  # Deliveroo backfill 01/10/2026: ops fill gaps only; Tax Invoice sales replace the row (orders, GMV, AOV)
for wc,v in DB['ops'].items():
    r=D.get(wc)
    if not r:continue
    for i,x in enumerate(v):
        if r[1+i] is None and x is not None:r[1+i]=x
for wc,(n,g) in DB['inv'].items():
    r=D.get(wc)
    if not r:continue
    if r[7] is None or r[8] is None:r[7]=g;r[8]=n;r[9]=round(g/n,2)
K=W['k'];WK=[]
ML=J('ml_weekly.json')['w']  # Mona Lisa weekly gap fill: stored values win
for r in main:
    o=dict(zip(K,r));d=D.get(r[0],[r[0]]+[None]*9)
    m=ML.get(r[0])
    if m:
        for k in ('sales','target','wage','hours','waste'):
            if o.get(k) is None and m.get(k) is not None:o[k]=m[k]
    o['d']=dict(zip(W['dk'][1:],d[1:]))
    WK.append(o)

# GM/HC and AM meeting notes
N=J('notes.json');out={}
for k,v in N.items():
    items=[]
    for s in v['i']:
        if re.search(r'disciplinary|Gemma',s,re.I):continue
        s=s.replace(' \u2014 ',': ').replace('\u2014',', ').replace('\u2013','-')
        s=re.sub(r'^Region-wide \(North England & Midlands\): ','Region: ',s)
        items.append(s)
    out[k]={'i':items,'a':v['a']}

# Freshness: every feed gets an as-of date and a maximum age in days
def d10(s):
    try:return datetime.date.fromisoformat(str(s)[:10])
    except Exception:return None
def wkend(keys):
    ks=[k for k in keys if d10(k)];return d10(max(ks))+datetime.timedelta(6) if ks else None
def kobas(s):
    m=re.search(r'(\d{1,2}) ([A-Z][a-z]{2})',s or '')
    if not m:return None
    d=datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {TODAY.year}",'%d %b %Y').date()
    return d if d<=TODAY else d.replace(year=d.year-1)
MP=JD('mapal.json',{'f':[],'to':None,'src':'Mapal forms not pulled yet'})
RI=JD('revintel.json',{'r':[],'tax':{},'praise':{},'ann':{},'built':None,'to':None,'src':'Reviews Intelligence not pulled yet'})
SITE['gm']=RI.get('gm')
ACTS=J('actions.json') if os.path.exists(P('actions.json')) else JD('amcc_actions.json',[])
MT=JD('maint.json',{'pulled':None,'open':[],'done':[],'recap':{'items':[]},'n':{}});PPM=JD('ppm.json',{'asof':None,'items':[]})
dly=J('daily.json');cov=J('covers.json');dlv=J('delivery.json') if SC.get('delivery',True)!=False else {'d':{}};br=J('broth.json');rv=J('reviews.json');loy=J('loyalty.json')
mx=lambda o:max(o) if o else None
FEEDS=[  # name, as of, max age days
 ('Weekly KPIs',wkend([r[0] for r in main]),9),('Deliveroo weekly',wkend([r[0] for r in droo]),9),
 ('Daily cash up',d10(mx(dly)),2),('Covers',d10(mx(cov['d'])),2),('Delivery sales',d10(mx(dlv['d'])),2),
 ('Labour budget',wkend(J('labour.json')['d']),9),('Efficiency',wkend(J('eff.json')),9),('Estate ladder',wkend(J('effall.json')),9),
 ('Broth',d10(br.get('to')),2),('Google reviews',d10(rv.get('built')),2),('Loyalty',d10(loy.get('to')),2),
 ('Key lines',kobas(J('keyline.json').get('pulled')),2),('Meeting notes',wkend(N)+datetime.timedelta(2) if N else None,10),('Reviews intelligence',d10(RI.get('built')),3),('Mapal compliance',d10(JD('mcomp.json',{}).get('to')),9),
 ('Compliance',d10(J('compliance.json').get('pulled')),8),('Team',d10(J('team.json').get('pulled')),8),('EOTM',d10(J('eotm.json').get('pulled')),35),('Mapal forms',d10(MP.get('to')),3),('Maintenance',d10(MT.get('pulled')),2),('PPM schedule',d10(PPM.get('asof')),35)]
# Feeds that do not exist for this site (no source in sites.json) are n/a, not late
NA={'Deliveroo weekly':not SITE['has']['delivery'],'Delivery sales':not SITE['has']['delivery'],'Loyalty':not SITE['has']['loyalty'],'Broth':not SITE['has']['broth'],'Mapal forms':not SITE['has']['mapal'],'Mapal compliance':not SITE['has']['mapal'],'Compliance':not J('compliance.json').get('pulled'),
    'Team':not J('team.json').get('pulled'),'Key lines':not J('keyline.json').get('pulled'),'EOTM':not J('eotm.json').get('pulled'),'PPM schedule':not PPM.get('items')}
LOG=[];STALE=[]
for n,asof,mx in FEEDS:
    if NA.get(n) and (asof is None or n in ('Deliveroo weekly','Delivery sales')):LOG.append({'feed':n,'asof':None,'status':'n/a'});continue
    age=(TODAY-asof).days if asof else None
    st='missing' if asof is None else ('stale' if age>mx else 'ok')
    LOG.append({'feed':n,'asof':asof.isoformat() if asof else None,'age_days':age,'max_days':mx,'status':st})
    if st!='ok':STALE.append([n,asof.strftime('%d/%m') if asof else 'n/a'])

C=lambda o:json.dumps(o,ensure_ascii=False,separators=(',',':'))
T={'__TODAY__':TODAY.isoformat(),'__WK__':json.dumps(WK,separators=(',',':')),'__STAND__':R('stand.json'),'__EALL__':R('effall.json'),
   '__EFF__':R('eff.json').replace(' \u2014 ',', ').replace('\u2014',', '),'__LOY__':R('loyalty.json'),'__COV__':R('covers.json'),'__DEL__':C(dlv),
   '__ACTS__':C(ACTS),'__COMP__':C(J('compliance.json')),'__TEAM__':C(J('team.json')),'__GAPS__':C(J('gaps.json')),'__DAILY__':R('daily.json'),
   '__KL__':C(J('keyline.json')),'__BROTH__':R('broth.json'),'__REV__':R('reviews.json'),'__LAB__':R('labour.json'),'__EOTM__':C(J('eotm.json')),'__NOTES__':C(out),'__MAPAL__':C(MP).replace(' \u2014 ',', ').replace('\u2014',', ').replace('\u2013','-'),'__MCOMP__':C(JD('mcomp.json',{'w':[],'chain':[],'to':None,'src':'Mapal compliance not pulled yet'})),'__RI__':C(RI).replace(' \u2014 ',', ').replace('\u2014',', ').replace('\u2013','-'),'__SITE__':C(SITE),'__MAINT__':C(MT).replace(' \u2014 ',', ').replace('\u2014',', ').replace('\u2013','-'),'__PPM__':C(PPM)}
s=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'src.html')).read()
ND=lambda v:v.replace(' \u2014 ',', ').replace('\u2014',', ').replace('\u2013','-')  # feed text (reviews, notes, actions) never brings a dash in
for k,v in T.items():s=s.replace(k,ND(v))

# Stale feed bar: shows only when a feed is late, Maki orange, never hides the data
if STALE:
    s+=('\n<div id="sccStale" style="position:fixed;left:12px;right:12px;bottom:12px;z-index:9999;background:#fff;border:2px solid #E94E1B;border-radius:10px;'
        'padding:8px 12px;font:600 12px/1.4 system-ui,sans-serif;color:#0f172a;box-shadow:0 4px 14px rgba(15,23,42,.15)">'
        '<span style="color:#E94E1B">Late data:</span> '+', '.join(f'{n} (last {d})' for n,d in STALE)+
        ' <button onclick="this.parentNode.remove()" style="float:right;border:0;background:none;color:#475569;cursor:pointer;font:inherit">Hide</button></div>\n')

# Checks: no dashes, no unfilled token. Fail closed.
bad=[]
if '\u2014' in s or '\u2013' in s:bad.append('dash in output')
left=sorted(set(re.findall(r'__[A-Z]{2,8}__',s)))
if left:bad.append('unfilled tokens '+','.join(left))
if bad:sys.exit('BUILD FAILED, nothing written: '+'; '.join(bad))

os.makedirs(A.out,exist_ok=True)
def wr(f,t):
    p=os.path.join(A.out,f);open(p+'.tmp','w').write(t);os.replace(p+'.tmp',p)
wr('site_control_centre.html',s)
wr('t.js',s.split('<script>')[1].split('</script>')[0])
full='<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'+s.split('</style>')[0]+'</style>\n</head>\n<body>\n'+s.split('</style>',1)[1]+'\n</body>\n</html>\n'
wr('Site_Control_Centre_full.html',full)
wr('build_log.json',json.dumps({'site':CODE,'name':SITE['name'],'built':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),'today':TODAY.isoformat(),'feeds':LOG,'stale':len(STALE)},indent=1))
print('built',len(s),'stale feeds:',len(STALE),[x[0] for x in STALE])
