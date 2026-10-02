"""Key lines feed (keyline.json) from Keyline Control, the page keyline-daily.yml builds into the ops checkout (keyline.html, 06:55 UK).
Runs that page's own engine in headless Chromium (Europe/London clock) and keeps the rows for this site, so the Site CC shows
exactly what Keyline Control shows. Columns: item, supplier, on hand, used a day, days left, runs out, on order, Baseline,
order today, status, why (the engine's own instruction). sup = per supplier [next cut-off, next delivery, minimum].
Keeps the last good file on any failure. --check prints and writes nothing.
Usage: pull_keyline.py --site M14 --data DIR --page OPS_ROOT/keyline.html [--check]"""
import argparse,json,os,sys
os.environ['TZ']='Europe/London'
from common import site,save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--page',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args();site(A.site)
if not os.path.exists(A.page):sys.exit(f'{A.page} not found; last good file kept')
JS="""(code)=>{
 const L={URGENT:'Urgent',ORDER:'Order today',WATCH:'Watch',CHECK:'Check',OK:'OK',OVER:'Over',DATA:'Data'};
 const K=window.KEYLINE_DATA, m=K.meta, sm=(K.siteMeta||{})[code];
 const rows=ROWS.filter(r=>r.site===code);
 const day=d=>d?d.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short',timeZone:'Europe/London'}).replace(',',''):'';
 const q=(v,it)=>v==null?'':fmtQty(v,it);
 const one=v=>v==null||!isFinite(v)?null:Math.round(v*10)/10;
 const lines=rows.map(r=>{
   const chk=r.status==='CHECK'||r.status==='DATA', c=r.comp||{};
   const oo=c.onOrder>0?q(c.onOrder,r.item)+(c.inbound>0&&c.inboundDue?', due '+dayShort(c.inboundDue):''):'';
   const ot=(r.netOrder===0&&r.inbound>0)?'Covered':((r.netOrder>0)?q(r.netOrder,r.item):'');
   return [r.item.name,r.sup||'',q(r.stock,r.item),chk||r.usage==null?null:Math.round(r.usage*100)/100,
           chk?null:(r.cover<10?one(r.cover):Math.round(r.cover)),chk?'':day(r.runOut),oo,chk?'':q(r.baseline,r.item),chk?'':ot,
           L[r.status]||r.status,r.why||''];});
 const ord={Urgent:0,'Order today':1,Watch:2,Check:3,Data:4,OK:5,Over:6};
 lines.sort((a,b)=>(ord[a[9]]-ord[b[9]])||((a[4]==null?1e9:a[4])-(b[4]==null?1e9:b[4])));
 const sup={};
 rows.forEach(r=>{if(!r.sup||sup[r.sup])return;
   sup[r.sup]=r.del?[r.del.next.cut.toLocaleDateString('en-GB',{weekday:'short',timeZone:'Europe/London'})+' '+r.del.next.cutTime,day(r.del.next.del),(r.route&&r.route.min)?'\\u00a3'+r.route.min+' min':'']
                   :[(r.route&&r.route.note)||'cut-off not confirmed','',''];});
 let chkd='';if(sm&&sm.checkDate){const p=sm.checkDate.split('/');chkd=(+p[1])+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[0]-1];}
 return {n:rows.length,pulled:(m.importedLabel||'').replace(/^pulled from /,''),check:chkd,version:m.version,sup,lines};}"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(timezone_id='Europe/London');errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file://'+os.path.abspath(A.page));pg.wait_for_timeout(800)
    R=pg.evaluate(JS,A.site);b.close()
if errs:print('page errors:',errs[:3])
if not R['n']:sys.exit(f'Keyline Control has no rows for {A.site} (site not in Keyline yet); last good file kept')
out={'src':'Keyline Control (keyline.html in makiramen/ops, keyline-daily.yml), engine v'+str(R['version']),'pulled':R['pulled'],'check':R['check'],'sup':R['sup'],'lines':R['lines']}
for l in out['lines']:
    for i,v in enumerate(l):
        if isinstance(v,str):l[i]=v.replace('—',', ').replace('–','-')
print(f"keyline {A.site}: {R['n']} lines, {out['pulled']}, check {out['check']}, statuses",{s:sum(1 for l in out['lines'] if l[9]==s) for s in {l[9] for l in out['lines']}})
if A.check:print(json.dumps(out,ensure_ascii=False,indent=0)[:3000]);sys.exit(0)
save(os.path.join(A.data,'keyline.json'),out)
