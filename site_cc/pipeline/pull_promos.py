"""Promotions feed (promos.json) for one site, from the marketing team's "2026-2027 MAKI & RAMEN OFFICIAL CALENDAR" sheet.
Sheet id in sites.json sources.marketing_calendar, read with the service account (share as Viewer with site-cc-reader).
Layout (Becca's sheet, 20/10/2026): row 1 = MONTH then one column per month (a "2027" marker column starts the next year);
row 2 = PROMOTIONS; one free text cell per promotion under each month, e.g.
  "Slerp 50% Off First Order Promo - Wave 3 Launch\n30/10\nNewcastle, Meadowhall, Birmingham"
  "BLACK FRIDAY: Deliveroo\n30% off - Black Garlic Tonkotsu\n... Meadowhall ... 20-30/11/26"
Each cell is parsed for dates (dd/mm, dd/mm-dd/mm, dd-dd/mm, optional /yy) and site names. A cell with no site named,
or "All sites" / "All Locations", covers every site. Rows from KEY downwards are ignored.
Also accepts a plain table (header row Start, End, Promotion, Type, Sites, ...) if the sheet is ever rebuilt that way.
Keeps the last good file on any failure. Usage: pull_promos.py --site M14 --data DIR [--check] [--csv FILE]"""
import argparse,csv,datetime,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources'].get('marketing_calendar') or {}
P=os.path.join(A.data,'promos.json')
if not SRC.get('id') and not A.csv:
    save(P,{'src':'Marketing calendar: not configured','pulled':None,'items':[]});print(f'promos {A.site}: no marketing_calendar in sites.json');sys.exit(0)
rows=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],SRC.get('range','A1:Z60'))
if not rows:sys.exit('marketing calendar: empty read; last good file kept')
MON={m:i+1 for i,m in enumerate(['january','february','march','april','may','june','july','august','september','october','november','december'])}
# site name aliases as the marketing team writes them -> site codes. A city with several sites maps to all of them.
ALIAS={'meadowhall':['M14'],'sheffield':['M14'],'fountainbridge':['M3'],'bath street':['M6'],'bath st':['M6'],'newcastle':['M12'],'aberdeen':['M13'],
 'metrocentre':['M15'],'metro centre':['M15'],'manchester':['M9'],'leeds':['M10'],'leicester':['M11'],'nottingham':['M16'],'lakeside':['M17'],'soho':['M18'],
 'shoreditch':['M19'],'southampton':['M20'],'birmingham':['M21'],'nicolson':['M1'],'st james':['M7'],'sjq':['M7'],'renfield':['M8'],'ikigai':['IKI2'],
 'maki nori':['MakiNori'],'nori':['MakiNori'],'glasgow':['M6','M8'],'edinburgh':['M1','M3','M7','IKI2'],'edin ':['M1','M3','M7','IKI2'],'edin m3':['M3'],
 'london':['M18','M19','MakiNori','M17'],'scotland':['M1','M3','M6','M7','M8','IKI2','M13'],'west end':[]}
ALL_RE=re.compile(r'all\s+(sites|locations|customers|branches)',re.I)
D1=re.compile(r'(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?')   # 15/11-31/12, 28/09-12/10
D2=re.compile(r'(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?')              # 20-30/11/26, 07-18/12/26
D3=re.compile(r'(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/])')           # 31/10, 10/10
def yr(y,default):
    if not y:return default
    y=int(y);return y+2000 if y<100 else y
def iso(d,m,y):
    try:return datetime.date(y,m,d).isoformat()
    except ValueError:return None
def parse_dates(txt,year):
    m=D1.search(txt)
    if m:
        y=yr(m.group(5),year);return iso(int(m.group(1)),int(m.group(2)),y),iso(int(m.group(3)),int(m.group(4)),y if int(m.group(4))>=int(m.group(2)) else y+1),m
    m=D2.search(txt)
    if m:
        y=yr(m.group(4),year);return iso(int(m.group(1)),int(m.group(3)),y),iso(int(m.group(2)),int(m.group(3)),y),m
    m=D3.search(txt)
    if m:
        s=iso(int(m.group(1)),int(m.group(2)),yr(m.group(3),year));return s,s,m
    return None,None,None
def sites_in(txt):
    t=' '+txt.lower()+' ';out=[]
    if ALL_RE.search(t):return 'ALL',True
    for k in sorted(ALIAS,key=len,reverse=True):   # longest alias first, and it consumes its text ("edin m3" beats "edin ")
        if k in t:
            t=t.replace(k,' ')
            for c in ALIAS[k]:
                if c not in out:out.append(c)
    return (out if out else 'ALL'),bool(out)
def has_site_or_date(line):
    l=' '+line.lower()+' '
    return bool(D3.search(line) or ALL_RE.search(l) or any(k in l for k in ALIAS))
def kind(txt):
    t=txt.lower()
    if 'deliveroo' in t:return 'Deliveroo'
    if 'slerp' in t:return 'Slerp'
    if 'event' in t or 'workshop' in t or 'night' in t:return 'Event'
    if 'cook book' in t or 'cookbook' in t or 'pre order' in t:return 'E-commerce'
    if 'b2b' in t:return 'B2B'
    return 'Promotion'
items=[]
h=[re.sub(r'[^a-z]','',x.lower()) for x in rows[0]]
if 'start' in h and ('promotion' in h or 'name' in h):
    # plain table fallback
    col=lambda *n:next((i for i,x in enumerate(h) if x in n),None)
    I={'start':col('start'),'end':col('end'),'name':col('promotion','name'),'type':col('type'),'sites':col('sites'),'channel':col('channel'),'offer':col('offermechanic','offer'),'owner':col('owner'),'status':col('status'),'notes':col('notes'),'link':col('link')}
    def g(r,k):return (r[I[k]] if I[k] is not None and I[k]<len(r) else '').strip()
    def isod(v):
        for f in ('%Y-%m-%d','%d/%m/%Y','%d/%m/%y'):
            try:return datetime.datetime.strptime(v.strip(),f).date().isoformat()
            except ValueError:pass
    for r in rows[1:]:
        if not g(r,'name') or g(r,'status').lower() in ('cancelled','canceled'):continue
        sc,named=sites_in(g(r,'sites'))
        if sc!='ALL' and A.site not in sc and g(r,'sites').upper()!='ALL':
            if A.site.lower() not in g(r,'sites').lower():continue
        st=isod(g(r,'start'))
        if st:items.append({'start':st,'end':isod(g(r,'end')) if g(r,'end') else None,'name':g(r,'name'),'type':g(r,'type') or 'Promotion','sites':g(r,'sites') or 'ALL','offer':g(r,'offer'),'owner':g(r,'owner'),'notes':g(r,'notes'),'link':g(r,'link')})
    layout='table'
else:
    # Becca's month grid
    hdr=rows[0];year=None;cols=[]
    for ci,cell in enumerate(hdr):
        c=cell.strip().lower()
        if re.fullmatch(r'20\d\d',c):year=int(c);continue
        if c in MON:
            if year is None:year=datetime.date.today().year if MON[c]>=datetime.date.today().month-2 else datetime.date.today().year+1
            cols.append((ci,MON[c],year))
    if not cols:sys.exit('marketing calendar: no month columns in row 1, layout changed; last good file kept')
    # first year: the leftmost months are the current calendar year (the sheet starts October 2026, the 2027 marker comes later)
    first_year=min(y for _,_,y in cols)
    for r in rows[1:]:
        lab=(r[0] if r else '').strip().upper()
        if lab=='KEY':break
        for ci,mo,y in cols:
            txt=(r[ci] if ci<len(r) else '').strip()
            if not txt:continue
            st,en,m=parse_dates(txt,y)
            if not st:st=iso(1,mo,y);en=iso(1,mo+1,y) if mo<12 else iso(31,12,y);en=en and (datetime.date.fromisoformat(en)-datetime.timedelta(1)).isoformat() if mo<12 else en
            sc,named=sites_in(txt)
            if sc!='ALL' and A.site not in sc:continue
            lines=[x.strip() for x in txt.replace('\r','').split('\n') if x.strip()]
            nl=[];
            for x in lines:
                if has_site_or_date(x) and nl:break
                nl.append(x)
                if len(nl)==2:break
            name=' '.join(nl) if nl else txt
            name=D1.sub('',D2.sub('',D3.sub('',name))).strip(' :-,')
            rest=' · '.join(lines[len(nl):])
            if not m:rest=(rest+' · ' if rest else '')+'whole month, no dates in the calendar' 
            if m:rest=rest.replace(m.group(0),'').strip(' ·,-')
            if re.search(r'launch|pre order|live on',txt,re.I) and st==en:en=None  # a launch is a start, not a one day event
            key=(name,st,en)
            if any((i['name'],i['start'],i['end'])==key for i in items):continue   # the same cell repeated in two month columns
            items.append({'start':st,'end':en,'name':name,'type':kind(txt),'sites':'ALL' if sc=='ALL' else ', '.join(sc),'offer':rest,'owner':'','notes':'' if named or sc=='ALL' else '','link':''})
    layout='month grid'
items.sort(key=lambda x:(x['start'],x['name']))
out={'src':'2026-2027 MAKI & RAMEN OFFICIAL CALENDAR (marketing team sheet), service account read','pulled':datetime.date.today().isoformat(),'sheet':SRC.get('id'),'layout':layout,'items':items,
     'note':'One entry per promotion, event or campaign whose cell names this site, its city, or no site at all (estate wide). end null = ongoing or no end given. Dates and site names parsed from the free text cells.'}
if A.check:
    old=json.load(open(P)) if os.path.exists(P) else {'items':[]}
    print(f'check: {len(items)} rows for {A.site}, stored {len(old["items"])}');[print(' ',i['start'],i['end'],i['name'],'|',i['sites']) for i in items];sys.exit(0)
save(P,out);print(f'promos {A.site}: {len(items)} rows ({layout})')
