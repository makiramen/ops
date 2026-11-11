"""Write data/kobas/run_state.json (what the reliable scheduler and the weekly build read) and print a run summary."""
import os, sys, json, glob, datetime
from zoneinfo import ZoneInfo
src, dst = sys.argv[1], sys.argv[2]
log = json.load(open(os.path.join(src, 'raw', 'log.json')))
weeks = {}
for w in log['weeks']:
    j = json.load(open(os.path.join(dst, f'wc_{w}.json')))
    weeks[w] = {'complete': j['complete'], 'days_pulled': j['days_pulled'], 'missing': j['missing']}
state = {'last_run_uk_day': datetime.datetime.now(ZoneInfo('Europe/London')).date().isoformat(),
         'last_run_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
         'weeks': weeks, 'errors': log.get('errors', []),
         'files': sorted(os.path.basename(f) for f in glob.glob(os.path.join(dst, 'wc_*.json')))}
json.dump(state, open(os.path.join(dst, 'run_state.json'), 'w'), indent=1)
print(f"## Kobas nightly {state['last_run_uk_day']}")
for w, v in weeks.items():
    print(f"- w/c {w}: {v['days_pulled']}/7 days, complete={v['complete']}, missing {len(v['missing'])}: {', '.join(v['missing'][:20])}")
for e in state['errors']: print(f'- ERROR {e}')
