"""Sales mix (mix.json): drinks %, sushi % and sides % by day and by week for one site, read from the KPI Auto sheet's Kobas_Daily tab
(kpi_auto/kobas_daily.py writes it every morning at 04:10 from Kobas: category sales incl. VAT / total sales incl. VAT, All Item Sales report,
every menu incl. delivery; Michael's ruling 23/10/2026). 10/11/2026 (Michael): shown on the Weekly KPI Sheet under Sales, as blocks, for the
week the sheet is on, against the regional targets 10% drinks, 20% sushi, 13.5% sides. Weekly % = sales weighted (sum of category £ / sum of
total £ over the days with a figure). Keeps the last good file on any failure. --check reports and writes nothing."""
import argparse,json,os,datetime
from common import site,save,sheet_values,today
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site)
SHEET=(S.get('sources',{}).get('kpi_auto') or {}).get('id') or '14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y'
TARGETS={'drinks':10.0,'sushi':20.0,'sides':13.5}
KD={'MakiNori':'NORI'}  # Kobas_Daily site codes, Site CC codes elsewhere
code=KD.get(A.site,A.site)
P=os.path.join(A.data,'mix.json')
rows=sheet_values(SHEET,"'Kobas_Daily'!A1:X2000",render='UNFORMATTED_VALUE')
if not rows:raise SystemExit('mix: Kobas_Daily tab empty, keeping the last good file')
H=[str(h).strip().lower() for h in rows[0]];ix=lambda n:H.index(n)
try:cd,cs,ca,c1,c2,c3=ix('date'),ix('site'),ix('actual'),ix('drinks %'),ix('sushi %'),ix('sides %')
except ValueError as e:raise SystemExit(f'mix: Kobas_Daily header missing {e}')
def num(v):
    try:return float(str(v).replace('%','').replace(',','').strip())
    except ValueError:return None
def iso(v):
    s=str(v).strip()
    if isinstance(v,(int,float)) and not isinstance(v,bool):return (datetime.date(1899,12,30)+datetime.timedelta(days=int(v))).isoformat()
    for f in ('%Y-%m-%d','%d/%m/%Y','%d/%m/%y'):
        try:return datetime.datetime.strptime(s[:10],f).date().isoformat()
        except ValueError:pass
    return None
days={}
for r in rows[1:]:
    r=(r+['']*24)[:24]
    if str(r[cs]).strip()!=code:continue
    d=iso(r[cd]);
    if not d:continue
    a=num(r[ca]);v=[num(r[c1]),num(r[c2]),num(r[c3])]
    if all(x is None for x in v):continue
    days[d]=[v[0],v[1],v[2],a]
weeks={}
for d,v in days.items():
    dt=datetime.date.fromisoformat(d);wc=(dt-datetime.timedelta(days=dt.weekday())).isoformat()
    w=weeks.setdefault(wc,{'n':0,'tot':0.0,'cat':[0.0,0.0,0.0],'avg':[[0.0,0],[0.0,0],[0.0,0]]})
    w['n']+=1
    if v[3]:
        w['tot']+=v[3]
        for i in range(3):
            if v[i] is not None:w['cat'][i]+=v[i]/100*v[3]
    for i in range(3):
        if v[i] is not None:w['avg'][i][0]+=v[i];w['avg'][i][1]+=1
out_w={}
for wc,w in weeks.items():
    if w['tot']>0:vals=[round(w['cat'][i]/w['tot']*100,2) for i in range(3)]
    else:vals=[round(w['avg'][i][0]/w['avg'][i][1],2) if w['avg'][i][1] else None for i in range(3)]
    out_w[wc]={'drinks':vals[0],'sushi':vals[1],'sides':vals[2],'n':w['n']}
out={'src':'KPI Auto sheet, Kobas_Daily tab (Kobas All Item Sales, incl. VAT)','sheet':SHEET,'pulled':today().isoformat(),'targets':TARGETS,
     'days':dict(sorted(days.items())),'weeks':dict(sorted(out_w.items()))}
last=max(days) if days else None
print(f"mix {A.site}: {len(days)} days, {len(out_w)} weeks, latest {last}")
if not days:raise SystemExit('mix: no rows for this site, keeping the last good file')
if not A.check:save(P,out,indent=1)
