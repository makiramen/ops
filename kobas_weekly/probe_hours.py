"""Probe (13/11/2026): why Rotas > Hours Worked sums higher than the Labour Costs report hours at M7, M8, M15, MAF1, MAF4.
Aggregates only (hours by day, by shift label, by flag). No staff names: the repo is public."""
import os, re, sys, json, html
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keyline'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kobas_pull import Kobas, BASE
from sitemap import V
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas()
if not k.login(): json.dump({'error': 'LOGIN FAILED'}, open(os.path.join(out, 'hours_probe.json'), 'w')); sys.exit(30)
R = {}
WK = '2026-11-02'
rotas = {(x['venueid'], str(x['rotadate'])[:10]): x['id'] for x in k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()}
txt = lambda h: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()
for site in ('M7', 'M8', 'M15', 'MAF1', 'MAF4', 'M9'):
    vid = V[site]; rid = rotas.get((vid, WK)); o = {'rota_id': rid}
    for dep in ('FrontofHouse', 'BackofHouse', 'Management', 'norole'):
        t = k.s.post(BASE + f'/rotas/index.php?m=fullhours&iRotaID={rid}&venueid={vid}', data={'department': dep}, timeout=180).text
        agg = {}; tot_labels = {}
        for row in re.findall(r'<tr class="tabledata">(.*?)</tr>', t, re.S):
            nm = re.search(r'<strong[^>]*>(.*?)</strong>', row, re.S); name = txt(nm.group(1)) if nm else ''
            for m in re.finditer(r'<td[^>]*class="staff_\d+_day_(\d)"[^>]*>(.*?)(?=<td|$)', row, re.S):
                for cls, sh in re.findall(r'<div[^>]*?(class="[^"]*")?>(.*?)</div>', m.group(2), re.S):
                    h = re.search(r'</a>\s*<br\s*/?>\s*(\d+)h(?:&nbsp;|\s)*(\d+)m', sh)
                    lm = re.search(r'<strong[^>]*>(.*?)</strong>', sh, re.S); lab = txt(lm.group(1)) if lm else '?'
                    if lab and name and lab.lower() in name.lower(): lab = '?'
                    links = '|'.join(sorted(set(txt(x) for x in re.findall(r'<a[^>]*>(.*?)</a>', sh, re.S) if len(txt(x)) < 16 and not re.search(r'\d', txt(x)))))
                    key = f"{lab[:28]} / {'flag' if 'failure' in (cls or '') else 'ok'} / {links[:40]}"
                    a = agg.setdefault(key, [0.0] * 7 + [0])
                    if h: a[int(m.group(1)) - 1] += int(h.group(1)) + int(h.group(2)) / 60.0
                    a[7] += 1
            tc = re.search(r'class="totals_staff_\d+"[^>]*>(.*?)</td>', row, re.S)
            if tc:
                for lb, hh, mm in re.findall(r'([A-Za-z ]{3,20}):\s*(?:<span[^>]*>)?(\d+)h(?:&nbsp;|\s)*(\d+)m', tc.group(1)):
                    tot_labels[lb.strip()] = round(tot_labels.get(lb.strip(), 0) + int(hh) + int(mm) / 60.0, 2)
        o[dep] = {'by_label': {kk: [round(x, 2) for x in v[:7]] + [v[7]] for kk, v in agg.items()}, 'totals_cell': tot_labels,
                  'rows': len(re.findall(r'<tr class="tabledata">', t)), 'venue_words': sorted(set(re.findall(r'(?:charged to|Charged to|on loan|from|at) (Maki [A-Za-z ]{2,25})', txt(t))))[:10]}
    R[site] = o
json.dump(R, open(os.path.join(out, 'hours_probe.json'), 'w'), indent=1); print('ok')
