#!/bin/bash
# Site Control Centre nightly run. One site per entry in sites.json with "live": true.
# Each pull is its own fault domain: a failed pull is logged, its feed keeps the last good file, the build still runs and the page shows "Late data".
# Layout inside makiramen/ops:  site_cc/ (this folder: build.py, src.html, pipeline/, sites.json)
#   site_cc/data/<CODE>/*.json  feed files per site      site/<CODE>/index.html  published page (offline, standalone)
#   data/<CODE>_wc_*.json  AM CC weekly (read only)       builders/broth/live_matrix.txt  Mapal broth (read only)
set -u
cd "$(dirname "$0")/.."
ROOT="${OPS_ROOT:-..}"
FAILS=0
step(){ echo "== $*"; "$@" || { echo "!! FAILED: $*"; FAILS=$((FAILS+1)); }; }
for CODE in $(python3 -c "import json;print(' '.join(k for k,v in json.load(open('sites.json'))['sites'].items() if v.get('live')))"); do
  D="data/$CODE"; [ -d "$D" ] || { echo "!! no data folder for $CODE, skipped"; FAILS=$((FAILS+1)); continue; }
  step python3 pipeline/pull_cashup.py   --site "$CODE" --data "$D" --days 21
  step python3 pipeline/pull_monalisa.py --site "$CODE" --data "$D"
  step python3 pipeline/pull_amcc.py     --site "$CODE" --data "$D" --amcc "$ROOT/data"
  [ -f "$ROOT/builders/broth/live_matrix.txt" ] && step python3 pipeline/pull_broth.py --site "$CODE" --data "$D" --matrix "$ROOT/builders/broth/live_matrix.txt"
  OUT=$(mktemp -d); mkdir -p "$ROOT/site/$CODE"
  if python3 build.py --data "$D" --out "$OUT"; then
    cp "$OUT/Site_Control_Centre_full.html" "$ROOT/site/$CODE/index.html"
    cp "$OUT/build_log.json" "$ROOT/site/$CODE/build_log.json"
  else echo "!! BUILD FAILED for $CODE, last good page left live"; FAILS=$((FAILS+1)); fi
done
echo "== done, failures: $FAILS"
exit 0
