"""Deliveroo daily ops feed from the Deliveroo Daily Master sheet (Daily Summary tab), read with the service account.
The sheet is the source of truth: an Apps Script (DeliverooDailyIngest.gs) ingests Deliveroo's five morning CSV drops hourly and
rebuilds Daily Summary as one row per day per site. This pull only reshapes it.

Writes two things:
  --site CODE --data DIR   droo_daily.json for one site (the Site CC daily tab)
  --estate FILE            one estate file keyed by day then site (the AM CC daily tab and the Area Room)

Row layout per day: [orders, prep_mins, aod_mins, missing_items_pct, cancel_rest_err, cancel_rest_err_pct, rejections, prep_red, rider_wait_gt5_pct, open_hours_pct, busy_mode_pct]
  The last three are the figures in that day's drop (the Apps Script stores RWT, open hours and busy mode on the drop's day from 07/10/2026).
  prep_red = 1 when the sheet says RED (prep above 15.00 min, the Red Light rule), 0 for GREEN, null when there is no prep figure.
  Missing figures are null (Deliveroo reports rejections by neighbourhood, so a site without a mapped hood has null, not 0).
Week rows (w/c Monday): [rider_wait_gt5_pct, open_hours_pct, busy_mode_pct], from the same summary rows (weekly grain on the sheet).
'to' = newest day with a prep figure for the site (or on the estate). Freshness in build.py: max 2 days.
Keeps the last good file on any failure. --check compares and writes nothing. --csv reads a saved export of Daily Summary (testing).
Usage: pull_deliveroo_daily.py [--site M14 --data DIR] [--estate data/deliveroo_daily.json] [--csv F] [--check]"""
import argparse,csv,datetime,json,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import sites,site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site');ap.add_argument('--data');ap.add_argument('--estate')
ap.add_argument('--csv');ap.add_argument('--check',action='store_true');ap.add_argument('--days',type=int,default=60)
A=ap.parse_args()
if not A.site and not A.estate:sys.exit('nothing to do: give --site CODE --data DIR and/or --estate FILE')
S=sites();SRC=S['sources'].get('deliveroo_daily') or {'id':'1wh6eAQw8spWpkQjABeMUCRdUKKJoUf2JDCFEjCRThh8','range':"'Daily Summary'!A:N"}
rows=list(csv.reader(open(A.csv,encoding='utf-8-sig'))) if A.csv else sheet_values(SRC['id'],SRC['range'])
if not rows:sys.exit('Daily Summary is empty; last good file kept')
H=[h.strip() for h in rows[0]]
NEED=['date','site_code','orders_delivered','prep_mins','aod_mins','missing_items_pct','cancel_rest_err','cancel_rest_err_pct','rejections','rider_wait_gt5_pct','open_hours_pct','busy_mode_pct','prep_red']
miss=[c for c in NEED if c not in H]
if miss:sys.exit(f'Daily Summary layout changed, missing columns {miss}; last good file kept')
ix={c:H.index(c) for c in NEED}
def num(x):
    x=str(x).strip().replace('%','').replace(',','')
    if x in ('','n/a','-'):return None
    try:return round(float(x),2)
    except ValueError:return None
today=datetime.date.today();lo=(today-datetime.timedelta(A.days)).isoformat()
def monday(d):
    x=datetime.date.fromisoformat(d);return (x-datetime.timedelta(x.weekday())).isoformat()
DAY={};WEEK={}   # DAY[site][date]=row ; WEEK[site][wc]=[rider,open,busy]
for r in rows[1:]:
    r=r+['']*(len(H)-len(r))
    d=str(r[ix['date']]).strip()[:10];code=str(r[ix['site_code']]).strip()
    if len(d)!=10 or not code or d<lo or d>=today.isoformat():continue
    prep=num(r[ix['prep_mins']]);flag=str(r[ix['prep_red']]).strip().upper()
    red=None if prep is None else (1 if flag=='RED' or (flag=='' and prep>15) else 0)
    row=[num(r[ix['orders_delivered']]),prep,num(r[ix['aod_mins']]),num(r[ix['missing_items_pct']]),num(r[ix['cancel_rest_err']]),num(r[ix['cancel_rest_err_pct']]),num(r[ix['rejections']]),red]
    if row[0] is not None:row[0]=int(row[0])
    if row[4] is not None:row[4]=int(row[4])
    if row[6] is not None:row[6]=int(row[6])
    w=[num(r[ix['rider_wait_gt5_pct']]),num(r[ix['open_hours_pct']]),num(r[ix['busy_mode_pct']])]
    row+=w   # 07/10/2026: RWT, open hours, busy mode as reported in that day's drop (week to date at Deliveroo)
    DAY.setdefault(code,{})[d]=row
    if any(x is not None for x in w):
        wc=monday(d);cur=WEEK.setdefault(code,{}).get(wc,[None,None,None])
        WEEK[code][wc]=[cur[i] if cur[i] is not None else w[i] for i in range(3)]
pulled=today.isoformat();src='Deliveroo Daily Master, Daily Summary (Deliveroo daily ops CSVs, ingested hourly)'
def latest(dd):
    ds=[d for d,v in dd.items() if v[1] is not None];return max(ds) if ds else None
def merge(old,new):
    """Only days inside the window are rewritten; older stored days are left alone (same rule as the cash up pull)."""
    o=dict(old or {});o.update(new);return dict(sorted(o.items()))
def write(path,obj,label):
    try:old=json.load(open(path))
    except Exception:old={}
    if A.check:
        diff=[k for k in set(list(old.get('d',{}))+list(obj['d'])) if old.get('d',{}).get(k)!=obj['d'].get(k)]
        print(label,'check: days differing',len(diff),sorted(diff)[-5:]);return
    obj['d']=merge(old.get('d'),obj['d']);obj['w']=merge(old.get('w'),obj['w']);obj['to']=latest(obj['d']) if 'site' in obj else obj['to']
    save(path,obj);print(label,'days',len(obj['d']),'to',obj['to'])
if A.site:
    if not A.data:sys.exit('--site needs --data')
    _,C=site(A.site)
    if C.get('delivery',True)==False:print(f'deliveroo daily {A.site}: no delivery at this site, feed stays n/a')
    else:
        dd=DAY.get(A.site,{})
        write(os.path.join(A.data,'droo_daily.json'),{'src':src,'pulled':pulled,'site':A.site,'to':latest(dd),'d':dd,'w':WEEK.get(A.site,{}),
              'k':['orders','prep','aod','missing_pct','cancel','cancel_pct','rejections','prep_red','rider_wait_pct','open_pct','busy_pct'],'wk':['rider_wait_pct','open_pct','busy_pct']},f'deliveroo daily {A.site}')
if A.estate:
    byday={};byweek={}
    for code,dd in DAY.items():
        for d,row in dd.items():byday.setdefault(d,{})[code]=row
    for code,ww in WEEK.items():
        for wc,row in ww.items():byweek.setdefault(wc,{})[code]=row
    byday={d:dict(sorted(v.items())) for d,v in byday.items()}
    to=max([d for d,v in byday.items() if any(r[1] is not None for r in v.values())] or [None])
    os.makedirs(os.path.dirname(os.path.abspath(A.estate)),exist_ok=True)
    write(A.estate,{'src':src,'pulled':pulled,'to':to,'d':byday,'w':{wc:dict(sorted(v.items())) for wc,v in byweek.items()},
          'k':['orders','prep','aod','missing_pct','cancel','cancel_pct','rejections','prep_red','rider_wait_pct','open_pct','busy_pct'],'wk':['rider_wait_pct','open_pct','busy_pct'],'prep_red_above':15},'deliveroo daily estate')
