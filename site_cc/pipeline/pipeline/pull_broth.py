"""Broth checks for one site from the Mapal broth matrix the Control Centre Broth tab builds (GitHub Actions broth-tab.yml).
Source: <ops checkout>/builders/broth/live_matrix.txt (first line "days:d1,d2,..."; "<label>~pork:" and "<label>~chicken:" readings; "<label>|..." deviations).
Usage: python3 pipeline/pull_broth.py --site M14 --matrix path/to/live_matrix.txt [--data .]
Merges into broth.json: days at source replace stored days, older stored days are kept. Spec unchanged (Tonkotsu 6.0 to 7.0, Tori Paitan 4.0 to 5.0, after water)."""
import sys,os,argparse
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import common as C
ap=argparse.ArgumentParser();ap.add_argument('--site',default='M14');ap.add_argument('--matrix',required=True);ap.add_argument('--data',default='.')
a=ap.parse_args();S,cfg=C.site(a.site);lab=cfg.get('broth_label')
if not lab:print(f'broth {a.site}: no Mapal broth label in sites.json, feed stays n/a');sys.exit(0)
L=open(a.matrix).read().splitlines();days=L[0].split(':',1)[1].split(',')
def row(k):
    for l in L:
        if l.startswith(lab+'~'+k+':'):
            return [float(x) if x.strip() else None for x in l.split(':',1)[1].split(',')]
    return []
pk,ck=row('pork'),row('chicken')
if not pk and not ck:sys.exit(f'FATAL: no broth rows for {lab!r} in the matrix')
P=os.path.join(a.data,'broth.json');B=C.json.load(open(P))
for i,d in enumerate(days):B['d'][d]=[pk[i] if i<len(pk) else None,ck[i] if i<len(ck) else None]
dev={(x[0],x[1],x[2]):x for x in B.get('dev',[])}
for l in L:
    if l.startswith(lab+'|'):
        x=l.split('|');y=[x[2],x[1],x[3],x[4]];dev[tuple(y[:3])]=y
B['d']=dict(sorted(B['d'].items()));B['dev']=sorted(dev.values());B['from']=min(B['d']);B['to']=max(B['d']);B['pulled']=C.today().isoformat()
C.save(P,B);print('broth',a.site,len(days),'days at source, to',B['to'])
