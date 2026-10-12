"""Certificate tracker (compliance.json) from the NE/Midland Site Compliance Tracker, the site's own tab (sites.json compliance_tab),
read with the service account (sheet is shared anyone with link, reader). Tab layout: row 3 contractor (merged across its columns),
row 4 item header, row 5 last done (dd/mm/yyyy, "On Site", or blank).
items = [[label, owner, last (ISO date | 'on site' | ''), months, note], ...]. Labels, months and notes already in the file are kept
(matched by header); new columns get a label and months from the header text. Keeps the last good file on any failure.
Usage: pull_compliance.py --site M14 --data DIR [--check]"""
import argparse,datetime,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True);ap.add_argument('--check',action='store_true')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources'].get('compliance_ne_midlands');TAB=C.get('compliance_tab')
if not TAB or not SRC:print(f'compliance {A.site}: no tracker tab in sites.json, feed stays n/a');sys.exit(0)
P=os.path.join(A.data,'compliance.json')
try:OLD=json.load(open(P))
except Exception:OLD={}
rows=sheet_values(SRC['id'],f"'{TAB}'!A1:Z6")
rows=[r+['']*(26-len(r)) for r in rows]+[['']*26]*(6-len(rows))
own,hdr,val=rows[2],rows[3],rows[4]
if not any('fire' in h.lower() for h in hdr):sys.exit(f'tracker tab {TAB} layout changed; last good file kept')
key=lambda s:re.sub(r'[^a-z]','',s.lower())
def months(h):
    h=h.lower()
    if 'anual' in h or 'annual' in h:return 12
    m=re.search(r'\((\d+)\s*(?:-\s*(\d+))?\s*months?\)',h)
    if m:return int(m.group(2) or m.group(1))
    if 'per month' in h:return 1
    return 0
def last(v):
    v=v.strip()
    if re.fullmatch(r'on\s*site',v,re.I):return 'on site'
    m=re.search(r'(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})',v)
    if m:
        d,mo,y=map(int,m.groups());y=y+2000 if y<100 else y
        try:return datetime.date(y,mo,d).isoformat()
        except ValueError:return ''
    return ''
def owner(o):
    o=o.strip();return o.split(' - ',1)[1].strip() if ' - ' in o else o
old=OLD.get('items') or [];items=[];cur=''
for i,h in enumerate(hdr):
    if not h.strip():continue
    cur=owner(own[i]) or cur
    prev=old[len(items)] if len(items)<len(old) else None
    who=prev[1] if prev and key(cur) and (key(cur) in key(prev[1]) or key(prev[1]) in key(cur)) else cur
    lab=prev[0] if prev else re.sub(r'\s*\(.*$','',h).strip().capitalize()
    items.append([lab,who,last(val[i]),prev[3] if prev else months(h),prev[4] if prev else ''])
if not items:sys.exit(f'no items on tab {TAB}; last good file kept')
out={'src':f'NE/Midland Site Compliance Tracker, tab {TAB}','url':f"https://docs.google.com/spreadsheets/d/{SRC['id']}",
     'pulled':datetime.date.today().isoformat(),'items':items}
print(f'compliance {A.site}: {len(items)} items from tab {TAB}, {sum(1 for x in items if x[2] and x[2]!="on site")} dated')
if A.check:print(json.dumps(items,indent=0));sys.exit(0)
save(P,out)
