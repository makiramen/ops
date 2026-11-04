"""Employee of the Month nominations straight from Guudjob (Mapal Engagement), estate wide, into site_cc/data/guudjob_eotm.json.
04/11/2026 (Michael): "Is there a way to get it here? ... I want it fully offline." So this runs inside the Site CC nightly on GitHub,
no Mac, no Chrome. It signs in to app.guudjob.com through the Mapal OS login (login.mapal-os.com, email then password) with the
secrets GUUDJOB_EMAIL / GUUDJOB_PASSWORD (Michael's own account, pasted into the repo secrets by him, never by Claude), then reads
the same pages the browser does:
  /premium/internal/main_companies/1754-maki-ramen/push_surveys                 the survey list (one FOH and one BOH survey per month,
                                                                                 named "FOH/Bartender Employee of the Month (October 2026)." and
                                                                                 "BOH Employee of the Month (October 2026)")
  .../push_surveys/<id>/answers                                                  the blocks (data-block-id)
  .../push_surveys/<id>/load_block_answers?block_id=<b>                          the questions in a block, with their show_respondents links
  .../push_surveys/<id>/show_respondents?question_id=<q>[&question_option_id=<o>] who answered what: open questions list respondent + text,
                                                                                 choice questions list the respondents per option
Respondent rows read "Justyna Anna Polak / General Manager · Maki Bath St": the workplace label after the dot is matched to sites.json
(guudjob_label, mapal_location or broth_label, case and punctuation insensitive, 1 and I treated alike for "M1TOO Ltd").
Output per month, site and department: nominee (n), role, by (the GM/AGM who nominated, first name plus initial), byrole, answers
(every open question, short title -> text), choices (every choice question, short title -> option picked), first seen date (on).
Keeps the last good file on any failure (a month already stored is never blanked). --check prints and writes nothing.
Browser: Playwright chromium (already installed for the key lines engine). The data calls go through the page's own session
(page.request), so one login per run."""
import argparse,datetime,html,json,os,re,sys,time
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
from common import sites,save
ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--check',action='store_true');ap.add_argument('--months',type=int,default=3)
ap.add_argument('--shot',default='',help='write a screenshot here when the login fails (uploaded as a workflow artifact)')
A=ap.parse_args()
BASE='https://app.guudjob.com';CO='/premium/internal/main_companies/1754-maki-ramen'
EMAIL=os.environ.get('GUUDJOB_EMAIL','').strip();PW=os.environ.get('GUUDJOB_PASSWORD','')
if not EMAIL or not PW:sys.exit('GUUDJOB_EMAIL / GUUDJOB_PASSWORD not set; last good file kept')
old=json.load(open(A.out)) if os.path.exists(A.out) else {}
MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
def norm(s):return re.sub(r'[^a-z0-9]','',(s or '').lower().replace('1','i'))
LABELS={}
for code,c in sites()['sites'].items():
    for k in ('guudjob_label','mapal_location','broth_label'):
        if c.get(k):LABELS.setdefault(norm(c[k]),code)
    for k in c.get('guudjob_aliases',[]) or []:LABELS.setdefault(norm(k),code)
def site_of(label):
    n=norm(label)
    if n in LABELS:return LABELS[n]
    for k,v in LABELS.items():
        if k and (k in n or n in k):return v
    return None
def short(n):
    p=(n or '').split();return (p[0].capitalize()+(' '+p[-1][0].upper()+'.' if len(p)>1 else '')) if p else ''
def clean(t):
    t=html.unescape(re.sub(r'<[^>]+>',' ',t or ''));t=re.sub(r'\s+',' ',t.replace('\u2014',', ').replace('\u2013','-')).strip()
    return t
def unjs(t):
    """show_respondents / load_block_answers answer as text/javascript with the HTML in a JS string: unescape it."""
    if '<' in t[:200] and '\\"' not in t[:2000]:return t
    t=t.replace('\\n','\n').replace('\\"','"').replace("\\'","'").replace('\\/','/')
    return t
def qshort(t):
    t=clean(t).rstrip('*').strip();return t if len(t)<=70 else t[:67].rsplit(' ',1)[0]+'...'
def respondents(frag):
    """[(name, role, workplace, answer_or_None)] from a show_respondents fragment. Rows: avatar initials div, name span, 'Role · Workplace' div, then the answer cell if any."""
    frag=unjs(frag);out=[]
    tb=frag.split('<tbody',1)
    if len(tb)>1:  # open question: table rows, two cells
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',tb[1],re.S):
            tds=re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S)
            if len(tds)<2:continue
            name,role,place=person(tds[0]);out.append((name,role,place,clean(tds[1])))
        return out
    cont=frag.split('answer-respondents-table-container',1)
    body=cont[1] if len(cont)>1 else frag
    for m in re.finditer(r'<span[^>]*title="[^"]*"[^>]*>(.*?)</span>\s*</div>\s*<div[^>]*>(.*?)</div>',body,re.S):
        name=clean(m.group(1));rp=clean(m.group(2));role,place=(rp.split('·',1)+[''])[:2] if '·' in rp else (rp,'')
        out.append((name,role.strip(),place.strip(),None))
    return out
def person(cell):
    parts=[clean(x) for x in re.findall(r'<div[^>]*>([^<]*)</div>|<span[^>]*>([^<]*)</span>',cell,re.S) for x in x if clean(x)]
    name=parts[1] if len(parts)>1 else (parts[0] if parts else '')
    rp=next((p for p in parts if '·' in p),'')
    role,place=(rp.split('·',1)+[''])[:2] if rp else ('','')
    return name,role.strip(),place.strip()
# ---- browser session ----
from playwright.sync_api import sync_playwright
def login(page):
    page.goto(BASE+CO+'/push_surveys',wait_until='domcontentloaded',timeout=60000)
    for _ in range(6):
        if 'app.guudjob.com' in page.url and 'push_surveys' in page.url and page.locator('table').count():return True
        page.wait_for_timeout(1500)
        pw=page.locator('input[type="password"]:visible');us=page.locator('#username:visible, input[name="username"]:visible, input[type="email"]:visible')
        if pw.count():pw.first.fill(PW)
        elif us.count():us.first.fill(EMAIL)
        else:page.wait_for_timeout(3000);continue
        btn=page.locator('button[type="submit"]:visible, input[type="submit"]:visible')
        (btn.first.click() if btn.count() else page.keyboard.press('Enter'))
        try:page.wait_for_load_state('networkidle',timeout=30000)
        except Exception:pass
    return 'app.guudjob.com' in page.url and page.locator('table').count()>0
def get(page,path):
    r=page.request.get(BASE+path,headers={'X-Requested-With':'XMLHttpRequest','Accept':'text/javascript, text/html, */*'})
    if r.status!=200:raise RuntimeError(f'{path} -> HTTP {r.status}')
    return r.text()
with sync_playwright() as p:
    br=p.chromium.launch();ctx=br.new_context(viewport={'width':1400,'height':900});page=ctx.new_page()
    try:
        if not login(page):
            if A.shot:page.screenshot(path=A.shot,full_page=True)
            sys.exit(f'Guudjob login did not reach the survey list (landed on {page.url}); last good file kept')
        listing=page.content()
        # survey rows: name + data-survey-id on the active toggle (also push_surveys/<id>/answers links)
        rows=[]
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',listing,re.S):
            m=re.search(r'push_surveys/(\d+)/answers',tr);
            if not m:continue
            name=clean(re.search(r'<td[^>]*>(.*?)</td>',tr,re.S).group(1)) if re.search(r'<td',tr) else ''
            mm=re.search(r'(FOH|BOH)\b.*Employee of the Month\s*\(([A-Za-z]+)\s+(\d{4})\)',name,re.I)
            if not mm or mm.group(2).lower() not in MONTHS:continue
            rows.append({'id':int(m.group(1)),'name':name,'dept':mm.group(1).upper(),'month':f'{int(mm.group(3))}-{MONTHS[mm.group(2).lower()]:02d}'})
        if not rows:sys.exit('no Employee of the Month surveys found on the list page; last good file kept')
        months=sorted({r['month'] for r in rows})[-A.months:]
        rows=[r for r in rows if r['month'] in months]
        print('surveys:',[(r['id'],r['dept'],r['month']) for r in rows])
        M={}
        for sv in rows:
            ans=get(page,f'{CO}/push_surveys/{sv["id"]}/answers')
            blocks=re.findall(r'data-block-id="(\d+)"',ans)
            te=(re.search(r'total_employees=(\d+)',ans) or [None,'0'])[1]
            qs=[]  # (qid, title, [(oid, label)])
            for b in dict.fromkeys(blocks):
                frag=unjs(get(page,f'{CO}/push_surveys/{sv["id"]}/load_block_answers?block_id={b}&total_employees={te}'))
                # split on the per question header: the "N out of M people answered" link carries the question id
                for qid in dict.fromkeys(re.findall(r'show_respondents\?question_id=(\d+)&(?:amp;)?total_employees',frag)):
                    i=frag.find(f'question_id={qid}&');j=frag.find(f'question_id={qid}&amp;') if i<0 else i
                    head=frag[max(0,j-2500):j]
                    spans=[clean(s) for s in re.findall(r'<span[^>]*>(.*?)</span>',head,re.S)]
                    spans=[s for s in spans if len(s)>8 and not re.match(r'^\d+ out of',s)]
                    title=spans[-1] if spans else f'Q{qid}'
                    seg=frag[j:];nxt=re.search(r'show_respondents\?question_id=(?!%s)\d+&(?:amp;)?total_employees'%qid,seg)
                    seg=seg[:nxt.start()] if nxt else seg
                    opts=[]
                    for om in re.finditer(r'<span[^>]*>([^<]{1,80})</span>\s*<div[^>]*>\s*<a[^>]*question_option_id=(\d+)',seg,re.S):
                        opts.append((om.group(2),clean(om.group(1))))
                    qs.append((qid,title,opts))
            per={}  # respondent name -> record
            def rec(name,role,place):
                r=per.setdefault(name,{'by':name,'byrole':role,'place':place,'answers':{},'choices':{}});return r
            for qid,title,opts in qs:
                st=qshort(title)
                if opts:
                    for oid,label in opts:
                        for name,role,place,_ in respondents(get(page,f'{CO}/push_surveys/{sv["id"]}/show_respondents?question_id={qid}&question_option_id={oid}')):
                            rec(name,role,place)['choices'][st]=label
                else:
                    for name,role,place,text in respondents(get(page,f'{CO}/push_surveys/{sv["id"]}/show_respondents?question_id={qid}&total_employees={te}')):
                        if text:rec(name,role,place)['answers'][st]=text
            print(f'  {sv["dept"]} {sv["month"]} survey {sv["id"]}: {len(qs)} questions, {len(per)} respondents')
            for name,r in per.items():
                code=site_of(r['place'])
                if not code:print(f'    !! no site for workplace "{r["place"]}" (respondent {name}); add guudjob_label to sites.json');continue
                nm=next((v for k,v in r['answers'].items() if 'full name' in k.lower()),'') or next(iter(r['answers'].values()),'')
                role=next((v for k,v in r['choices'].items() if 'role' in k.lower()),'')
                prev=(((old.get('m') or {}).get(sv['month']) or {}).get(code) or {}).get(sv['dept']) or {}
                M.setdefault(sv['month'],{}).setdefault(code,{})[sv['dept']]={'n':clean(nm),'role':role,'by':short(name),'byrole':r['byrole'],
                    'on':prev.get('on') or datetime.date.today().isoformat(),'survey':sv['id'],
                    'answers':{k:v for k,v in r['answers'].items() if 'full name' not in k.lower()},'choices':{k:v for k,v in r['choices'].items() if 'role' not in k.lower()}}
    finally:br.close()
out={'src':'Guudjob push surveys (Mapal Engagement), read nightly with Michael\'s login','pulled':datetime.date.today().isoformat(),
     'surveys':{f'{r["month"]}/{r["dept"]}':{'id':r['id'],'name':r['name'],'url':f'{BASE}{CO}/push_surveys/{r["id"]}/answers'} for r in rows},'m':dict(old.get('m',{}))}
for mo,v in M.items():
    o=dict(out['m'].get(mo) or {})
    for code,d in v.items():o.setdefault(code,{}).update(d)
    out['m'][mo]=o
out['m']=dict(sorted(out['m'].items()))
for mo,v in out['m'].items():print(mo,{c:{d:x.get('n') for d,x in dd.items()} for c,dd in v.items()})
if A.check:sys.exit(0)
save(A.out,out)
