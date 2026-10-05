"""Mapal forms feed (mapal.json) from the Mapal Broker Data sheet, read with the service account.
Tab "forms" (SiteCC_Mapal.gs, daily 07:00 UK): one row per completed Mapal form:
form_id, form_name, location, date, score, max_score, pct, answers, deviations, open_deviations, auditor, state,
deviation_items, last_modified. Site rows = location == sites.json mapal_location.
f = [date, form, pct, score, max, deviations, open, auditor, items, form_id]. to = newest form date for the estate (feed age).
Tab "form_answers" (added 05/10/2026): every answer of the audit forms, so the page opens the full report.
detail = {form_id: [[section, question, answer, score, max, is_dev, open_dev, comment, deviation text, action, [photo ids]], ...]}
Tab "photo_index" + Drive folder "Site CC Mapal photos": audit photos, downsized here to 640 px JPEG and embedded
(photos = {id: data URI}), so the page stays fully offline. Photo budget 2.5 MB a site, red points first.
Keeps the last good file on any failure; a missing answers tab or photo just leaves that part out.
--check prints and writes nothing.
Usage: pull_mapal.py --site M14 --data DIR [--check] [--csv forms_export.csv] [--csv-answers answers_export.csv]"""
import argparse,base64,csv,datetime,io,json,os,re,sys
from common import site,save,sheet_values
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
ap.add_argument('--check',action='store_true');ap.add_argument('--csv');ap.add_argument('--csv-answers')
A=ap.parse_args()
S,C=site(A.site);SRC=S['sources']['mapal_broker'];LOC=C.get('mapal_location')
if not LOC:print(f'mapal {A.site}: no Mapal location in sites.json, feed stays n/a');sys.exit(0)
rows=list(csv.reader(open(A.csv,encoding='utf-8'))) if A.csv else sheet_values(SRC['id'],"'forms'!A:O")
if not rows or rows[0][:4]!=['form_id','form_name','location','date']:sys.exit('forms tab missing or layout changed; last good file kept')
H=rows[0];R=[dict(zip(H,r+['']*(len(H)-len(r)))) for r in rows[1:] if r and r[0]]
if not R:sys.exit('forms tab is empty; last good file kept')
def tidy(x):
    cut=len(x.strip())>=90 and not x.strip()[-1] in '?.)';x=re.sub(r'\s*[—–]\s*',', ',x.strip());x=re.sub(r'\s+,\s*',', ',x);x=re.sub(r'\s{2,}',' ',x)
    return x[:x.rfind(' ')].rstrip(' ,')+'...' if cut and ' ' in x else x   # broker cuts items at 90 chars
def clean(x):return re.sub(r'\s{2,}',' ',re.sub(r'\s*[—–]\s*',', ',str(x or '').strip()))
num=lambda x:float(x) if str(x).strip() not in ('',) else None
f=[]
for r in R:
    if r['location'].strip()!=LOC:continue
    f.append([r['date'][:10],r['form_name'].strip(),num(r['pct']),num(r['score']),num(r['max_score']),int(num(r['deviations']) or 0),
              int(num(r['open_deviations']) or 0),r['auditor'].strip(),[tidy(x) for x in r['deviation_items'].split('|') if x.strip()],str(r['form_id']).strip(),r.get('url','').strip()])
f.sort(key=lambda x:(x[0],x[1]))
mine={x[9] for x in f}

# Full answers for the audit forms
detail={};pid_for={}
try:
    ar=list(csv.reader(open(A.csv_answers,encoding='utf-8'))) if A.csv_answers else sheet_values(SRC['id'],"'form_answers'!A:U")
except Exception as e:
    ar=[];print('  no form_answers tab yet:',str(e)[:120])
if ar and ar[0][:4]==['form_id','form_name','location','date']:
    AH=ar[0];got={}
    for v in ar[1:]:
        d=dict(zip(AH,v+['']*(len(AH)-len(v))))
        fid=str(d['form_id']).strip()
        if fid not in mine:continue
        got.setdefault(fid,[]).append(d)
    for fid,L in got.items():
        L.sort(key=lambda d:float(d['seq'] or 0))
        out=[]
        for d in L:
            out.append([clean(d['section']),clean(d['question']),clean(d['answer']),num(d['score']),num(d['max_score']),int(num(d['is_dev']) or 0),
                        int(num(d['open_dev']) or 0),clean(d['comment']),clean(d['dev_desc']),clean(d['direct_action'] or d['corrective_action']),[]])
            pid_for[str(d['answer_id']).strip()]=(fid,len(out)-1)
        detail[fid]=out
    print(f'  answers: {sum(len(v) for v in detail.values())} for {len(detail)} audit forms')
elif ar:print('  form_answers layout changed; full reports left out')

# Photos: Drive files listed in photo_index, red points first, inside the size budget
photos={}
try:
    pi=sheet_values(SRC['id'],"'photo_index'!A:F") if not A.csv else []
except Exception as e:
    pi=[];print('  no photo_index tab yet:',str(e)[:120])
todo=[]
for v in pi[1:]:
    v=v+['']*(6-len(v))
    if v[5]!='ok' or not v[2] or v[0].strip() not in pid_for:continue
    fid,i=pid_for[v[0].strip()];todo.append((-detail[fid][i][5],fid,i,v[2]))
if todo:
    try:
        from PIL import Image
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        cred=service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),scopes=['https://www.googleapis.com/auth/drive.readonly'])
        dv=build('drive','v3',credentials=cred,cache_discovery=False);budget=2_500_000
        for _,fid,i,gid in sorted(todo):
            if budget<=0:break
            try:
                buf=io.BytesIO();dl=MediaIoBaseDownload(buf,dv.files().get_media(fileId=gid));done=False
                while not done:_,done=dl.next_chunk()
                im=Image.open(io.BytesIO(buf.getvalue()));im=im.convert('RGB');im.thumbnail((640,640))
                o=io.BytesIO();im.save(o,'JPEG',quality=62,optimize=True);b=o.getvalue()
                photos[gid]='data:image/jpeg;base64,'+base64.b64encode(b).decode();budget-=len(b)*4//3
                detail[fid][i][10].append(gid)
            except Exception as e:print('  photo',gid,'skipped:',str(e)[:100])
        print(f'  photos: {len(photos)} embedded of {len(todo)} listed')
    except Exception as e:print('  photos skipped:',str(e)[:150])

out={'src':'Mapal (GetCompliant) forms via the Mapal Broker, tabs forms, form_answers, photo_index','pulled':datetime.date.today().isoformat(),
     'to':max(r['date'][:10] for r in R),'location':LOC,'f':f,'detail':detail,'photos':photos}
print(f"mapal {A.site}: {len(f)} forms for {LOC}, estate newest {out['to']}:",{n:sum(1 for x in f if x[1]==n) for n in sorted({x[1] for x in f})})
if A.check:sys.exit(0)
save(os.path.join(A.data,'mapal.json'),out)
