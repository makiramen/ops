"""PPM schedule (ppm.json): planned maintenance and certificates per site (fire, gas, EICR, PAT, TR19, pest, grease, legionella)
with contractor and next due date. Source: site_cc/ppm_contractors.json, converted from ppm_contractors_by_site.xlsx
(Michael, 05/10/2026). Static until a live source is linked; the feed shows Late after 35 days so it gets refreshed."""
import argparse,json,os
from common import site,save
ap=argparse.ArgumentParser();ap.add_argument('--site',required=True);ap.add_argument('--data',required=True)
A=ap.parse_args();S,C=site(A.site)
HERE=os.path.dirname(os.path.abspath(__file__))
src=json.load(open(os.path.join(HERE,'..','ppm_contractors.json')))
it=[[x['ppm'],x['who'],x['due'],x['m'],x['note']] for x in src['items'] if x['code']==A.site]
save(os.path.join(A.data,'ppm.json'),{'src':src['src'],'asof':src['asof'] if it else None,'items':it},indent=1)
print(f'ppm {A.site}: {len(it)} items')
