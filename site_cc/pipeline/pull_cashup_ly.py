"""Last year's daily cash up for one site, from Auto Cash Up tab Raw Data 2 (same source and parsing as pull_cashup.py).
Usage: python3 pipeline/pull_cashup_ly.py --site M7 [--data .] [--csv file]
Writes ly.json: d[date] = [sales, covers, delivery] for every cashed up day at least 357 days old (so next week's
comparison is already there), from 2025-04-01. The whole slice is rewritten each run, so edits to history are picked up.
The page compares a day with the same weekday 364 days earlier (52 weeks), the way the old KPI sheet did year on year (Rory, 13/10/2026).
A site that was not trading last year gets an empty slice and the page shows n/a."""
import csv,sys,os,argparse,datetime
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import common as C, vendor_cashup as V
ap=argparse.ArgumentParser();ap.add_argument('--site',default='M14');ap.add_argument('--data',default='.');ap.add_argument('--csv')
a=ap.parse_args()
S,cfg=C.site(a.site);src=S['sources']['auto_cash_up']
rows=list(csv.reader(open(a.csv,encoding='utf-8-sig'))) if a.csv else C.sheet_values(src['id'],src['range'])
h=rows[0]
for i,e in V.EXPECTED_HEADERS.items():
    if (h[i] if i<len(h) else '').strip()!=e.strip():sys.exit(f'FATAL: Raw Data 2 column {i} is {h[i] if i<len(h) else None!r}, expected {e!r}')
T=C.today();hi=(T-datetime.timedelta(357)).isoformat();lo='2025-04-01'
d={}
for r in rows[1:]:
    r=r+['']*(30-len(r))
    if r[V.IDX_VENUE].strip()!=cfg['cashup_venue']:continue
    dt=V.iso_date(r[V.IDX_DATE])
    if not dt or dt<lo or dt>hi:continue
    sales=V.num(r[V.IDX_ACTUAL])
    if not sales:continue   # a £0 row is not cashed up
    d[dt]=[round(sales,2),int(V.num(r[V.IDX_COVERS]) or 0),round(V.num(r[V.IDX_DELIVERY]) or 0.0,2)]
P=os.path.join(a.data,'ly.json')
o={'src':'Auto Cash Up, Raw Data 2 (last year)','pulled':T.isoformat(),'from':min(d) if d else None,'to':max(d) if d else None,'d':dict(sorted(d.items()))}
C.save(P,o);print('cash up LY',a.site,'days',len(d),'to',o['to'])
