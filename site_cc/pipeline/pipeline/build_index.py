"""Site directory: site/index.html links every live Site Control Centre, grouped by cluster, with its last build
and any late feeds (from site/<CODE>/build_log.json). Offline, Maki orange, no dashes. Written after every nightly run.
Usage: build_index.py --root OPS_ROOT"""
import argparse,datetime,html,json,os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);A=ap.parse_args()
S=json.load(open(os.path.join(HERE,'..','sites.json')))
E=html.escape
groups={}
for code,c in S['sites'].items():
    if not c.get('live'):continue
    groups.setdefault(c.get('cluster','Other'),[]).append((code,c))
def card(code,c):
    p=os.path.join(A.root,'site',code,'build_log.json')
    if not os.path.exists(p):
        return f'<div class="c off"><b>{E(c.get("label") or code)}</b><span>{E(c["name"])}</span><small>Not built yet</small></div>'
    L=json.load(open(p));late=[f['feed'] for f in L.get('feeds',[]) if f.get('status') in ('stale','missing')]
    b=L.get('built','')
    when=f'{b[8:10]}/{b[5:7]} {b[11:16]} UTC' if len(b)>=16 else b
    st=f'<small class="late">Late: {E(", ".join(late))}</small>' if late else '<small class="ok">All feeds in</small>'
    return f'<a class="c" href="{code}/"><b>{E(c.get("label") or code)}</b><span>{E(c["name"])}</span><small>Built {E(when)}</small>{st}</a>'
order=list((S.get('clusters') or {}).keys())+[g for g in groups if g not in (S.get('clusters') or {})]
body=''
for g in order:
    if g not in groups:continue
    cl=(S.get('clusters') or {}).get(g,{})
    who=' · '.join(x for x in (('AM '+cl['am']) if cl.get('am') else '',('DAM '+cl['dam']) if cl.get('dam') else '') if x)
    body+=f'<section><h2>{E(g)}</h2><div class="who">{E(who)}</div><div class="g">'+''.join(card(k,c) for k,c in groups[g])+'</div></section>'
now=datetime.datetime.now(datetime.timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Site Control Centres</title><style>
:root{{--o:#E94E1B;--od:#C43E12;--cream:#FFF8F0;--ink:#0f172a;--ink2:#475569;--line:#e2e8f0;--bg:#f4f5f9}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}}
header{{background:var(--cream);border-bottom:2px solid var(--o);padding:16px clamp(16px,3vw,32px)}}
header b{{letter-spacing:.14em;text-transform:uppercase;font-size:13px}}header b i{{color:var(--o);font-style:normal;margin:0 6px}}
header div{{color:var(--od);font-weight:600}}
main{{max-width:1200px;margin:0 auto;padding:20px clamp(16px,3vw,32px) 48px}}
h2{{margin:22px 0 2px;font-size:13px;letter-spacing:.1em;text-transform:uppercase}}.who{{color:var(--ink2);font-size:12.5px;margin-bottom:10px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}}
.c{{display:flex;flex-direction:column;gap:2px;background:#fff;border:1px solid var(--line);border-top:4px solid var(--o);border-radius:12px;padding:12px 14px;text-decoration:none;color:inherit}}
a.c:hover{{border-color:var(--o)}}.c b{{font-size:17px}}.c span{{color:var(--ink2)}}.c small{{font-size:12px;color:var(--ink2)}}
.c small.late{{color:#b91c1c;font-weight:700}}.c small.ok{{color:#047857;font-weight:700}}.c.off{{opacity:.6;border-top-color:#94a3b8}}
p.f{{color:var(--ink2);font-size:12px;margin-top:24px}}
</style></head><body><header><b>Maki<i>&bull;</i>Ramen</b><div>Site Control Centres · every site</div></header><main>{body}
<p class="f">Rebuilt by the Site Control Centre nightly job, {now}. Each page runs offline once opened.</p></main></body></html>'''
if '—' in page or '–' in page:sys.exit('index has a dash, not written')
os.makedirs(os.path.join(A.root,'site'),exist_ok=True)
open(os.path.join(A.root,'site','index.html'),'w').write(page)
print('site index:',sum(len(v) for v in groups.values()),'sites')
