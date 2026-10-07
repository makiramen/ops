"""Seed a site's data folder: every feed file the build reads gets an empty, valid skeleton if it is missing.
Existing files are never touched. Runs first in the nightly job, so a new site in sites.json builds on its first night;
the pulls then fill what they can and anything with no source stays n/a on the page.
Usage: seed_site.py --site M9 --data data/M9"""
import argparse,json,os
from common import site,save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
A=ap.parse_args();S,C=site(A.site);os.makedirs(A.data,exist_ok=True)
HERE=os.path.dirname(os.path.abspath(__file__))
na='not configured for this site'
SK={
 'weekly.json':{'src':'AM Control Centre weekly site JSON','site':A.site,'k':['wc','sales','target','covers','sph','wage','food','hours','waste','rev','rating','neg','fv','dv','eff','rl'],
                'dk':['wc','r','open','prep','rej','inacc','rider','sales','orders','aov'],'main':[],'droo':[]},
 'droo_backfill.json':{'src':'none','ops':{},'inv':{}},
 'ml_weekly.json':{'src':'Mona Lisa, Input Tabs','w':{}},
 'labour.json':{'src':'Mona Lisa, Input Tabs, labour budget and actual','d':{}},
 'notes.json':{},
 'amcc_actions.json':[],
 'daily.json':{},
 'covers.json':{'_src':'Auto Cash Up, Raw Data 2','_closed':[],'d':{}},
 'delivery.json':{'_src':'Auto Cash Up, Raw Data 2','d':{}},
 'droo_daily.json':{'src':'Deliveroo Daily Master, Daily Summary' if C.get('delivery',True)!=False else 'Deliveroo daily: no delivery at this site','pulled':None,'site':A.site,'to':None,'d':{},'w':{},'k':['orders','prep','aod','missing_pct','cancel','cancel_pct','rejections','prep_red'],'wk':['rider_wait_pct','open_pct','busy_pct']},
 'eff.json':{},'effall.json':{},'stand.json':{'eff':{},'lg':{}},
 'broth.json':{'src':'Mapal Broth Checks' if C.get('broth_label') else 'Broth: '+na,'from':None,'to':None,'spec':{'tk':[6.0,7.0],'tp':[4.0,5.0]},'d':{},'dev':[]},
 'reviews.json':{'src':'Google reviews: Google Reviews sheet Raw Data','built':None,'tax':{},'r':[],'to':None},
 'loyalty.json':{'src':'RAMEN_ROYALTY (AUTO)' if C.get('loyalty_venue') else 'Loyalty: '+na,'launch':S['sources'].get('ramen_royalty',{}).get('launch'),'to':None,'venue':C.get('loyalty_venue'),'venue_members':0,'d':{},'est':{}},
 'keyline.json':{'src':'Keyline Control','pulled':'','check':'','sup':{},'lines':[]},
 'compliance.json':{'src':('NE/Midland Site Compliance Tracker, tab '+C['compliance_tab']) if C.get('compliance_tab') else 'Site compliance tracker: '+na,'url':'','pulled':None,'items':[]},
 'team.json':{'src':'Maki Group Onboarding Tracker 2026','pulled':None,'baseline':None,'team':{},'onboarded':0,'leavers':[],'prev':None},
 'gaps.json':[],
 'eotm.json':{'src':"Hanna's EOTM Manual Input sheets",'pulled':None,'sheets':{'BOH':'','FOH':''},'m':{}},
 'mapal.json':{'src':'Mapal forms' if C.get('mapal_location') else 'Mapal: '+na,'to':None,'location':C.get('mapal_location'),'f':[],'detail':{}},
 'mcomp.json':{'src':'Mapal Weekly Compliance Tracker','to':None,'location':C.get('mapal_location'),'w':[],'chain':[]},
 'maint.json':{'src':'Required Maintenance/Repair (Responses)','pulled':None,'url':'','form':'','open':[],'done':[],'recap':{'asof':None,'items':[]},'n':{}},
 'ppm.json':{'src':'PPM contractors by site','asof':None,'items':[]},
 'revintel.json':{'src':'AM Control Centre Reviews Intelligence','built':None,'to':None,'code':A.site,'tax':{},'praise':{},'ann':{},'r':[]},
}
# reviews.json carries the complaint taxonomy the page labels with; reuse the pipeline copy
try:
    t=json.load(open(os.path.join(HERE,'reviews_taxonomy.json')))
    SK['reviews.json']['tax']={k:{'l':v.get('label',k),'o':v.get('owner',''),'s':{sk:(sv.get('label',sk) if isinstance(sv,dict) else sv) for sk,sv in (v.get('subs') or {}).items()}} for k,v in t['categories'].items()}
except Exception:pass
made=[]
for f,o in SK.items():
    p=os.path.join(A.data,f)
    if not os.path.exists(p):save(p,o);made.append(f)
print(f'seed {A.site}: {len(made)} new skeleton files' + (': '+', '.join(made) if made else ''))
