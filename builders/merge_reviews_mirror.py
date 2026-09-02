#!/usr/bin/env python3
"""merge_reviews_mirror.py — Reviews Intelligence (Pipe 5c) STEP 1b, CLOUD-NATIVE.

Keeps data/reviews_full.json (the rolling full pull that build_reviews_intel.py consumes) current
WITHOUT a browser: the Google Reviews MIRROR doc (Drive id 1KG2Q5YM8etf614xMpSpeQv3SF2iLdf5SLc978vH3YHY,
a 14-day window of `Raw Data` A:L) is exported as CSV by the Drive MCP, and every row in it is
upserted into the base by reviewId. Rows already in the base are REPLACED (edited text / changed
stars win); new rows are ADDED. Nothing is ever removed, so the base keeps growing from 20/04/2026
and a rolling window can never shrink history.

  python3 merge_reviews_mirror.py --base data/reviews_full.json --mirror data/_raw/reviews_mirror.csv \
      --out data/reviews_full.json

Mapping, DROP list and rating words are IDENTICAL to extract_reviews_fulltext.js (the weekly
browser pull). Rules of the house:
  * Every drop is LOUD. `dropped` and `unmapped` are counted and printed.
  * `Ikigai` is UNMAPPED BY RULING (31/08/2026) — counted, never mapped.
  * ANY OTHER unmapped label is a HARD STOP (exit 3). A new label is not a ruling — ask.
  * A mirror with 0 rows, or with no row for D-1 and D-2, is a HARD STOP (exit 4) — a dark feed
    must never be merged as "no reviews".
"""
import argparse, csv, json, sys, datetime, collections, re

MAP = {
    'Maki1/2': 'M1', 'Fountainbridge': 'M3', 'Bath st': 'M6', 'SJQ': 'M7',
    'Renfield': 'M8', 'Manchester': 'M9', 'Leeds': 'M10', 'Leicester': 'M11',
    'Newcastle': 'M12', 'Aberdeen': 'M13', 'Meadowhall': 'M14', 'Metro': 'M15',
    'Nottingham': 'M16', 'Lakeside': 'M17', 'Soho': 'M18',
    'Maki Shoreditch': 'M19', 'Maki Southampton': 'M20', 'Nori': 'MakiNori',
    'Maki Birmingham': 'M21',
}
DROP = {'Leith', 'West end', 'Maki O2', 'NQ', '#N/A'}
UNMAPPED_BY_RULING = {'Ikigai'}
RW = {'FIVE': 5, 'FOUR': 4, 'THREE': 3, 'TWO': 2, 'ONE': 1, '5': 5, '4': 4, '3': 3, '2': 2, '1': 1}

def log(*a): print(*a, file=sys.stderr)

def iso_of(date_txt, ct):
    s = (date_txt or '').strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m: return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m: return s[:10]
    m = re.match(r'^Date\((\d+),(\d+),(\d+)', s)
    if m: return f"{m.group(1)}-{int(m.group(2))+1:02d}-{int(m.group(3)):02d}"
    if ct and re.match(r'^\d{4}-\d{2}-\d{2}', ct): return ct[:10]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--mirror', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--today', help='YYYY-MM-DD (UK), default today')
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.datetime.now(datetime.timezone.utc).date()

    base = json.load(open(a.base, encoding='utf-8'))
    by_id = {r['id']: r for r in base['reviews']}
    n_base = len(by_id)

    rows = list(csv.reader(open(a.mirror, encoding='utf-8-sig', newline='')))
    if not rows or len(rows) < 2:
        log('🔴 MIRROR IS EMPTY — not merging'); sys.exit(4)
    hdr = [h.strip() for h in rows[0]]
    try:
        iid, ia, ir, ic, ict, isite, idate = (hdr.index(x) for x in ('reviewId', 'author_name', 'rating', 'comment', 'createTime', 'Site', 'Date'))
    except ValueError as e:
        log('🔴 MIRROR HEADER UNEXPECTED:', hdr); sys.exit(4)

    seen, dup, no_stars, no_date = set(), 0, 0, 0
    dropped, unmapped = collections.Counter(), collections.Counter()
    added, replaced, changed = 0, 0, 0
    dates_seen = collections.Counter()
    for r in rows[1:]:
        if len(r) <= max(iid, ia, ir, ic, ict, isite, idate): continue
        rid = (r[iid] or '').strip()
        if not rid: continue
        if rid in seen: dup += 1; continue
        seen.add(rid)
        label = (r[isite] or '').strip()
        if label in DROP: dropped[label] += 1; continue
        code = MAP.get(label)
        if not code: unmapped[label] += 1; continue
        stars = RW.get((r[ir] or '').strip().upper())
        if not stars: no_stars += 1; continue
        ct = (r[ict] or '').strip() or None
        d = iso_of(r[idate], ct)
        if not d: no_date += 1; continue
        dates_seen[d] += 1
        rec = {'id': rid[:26], 'c': code, 's': stars, 'd': d, 'ct': ct,
               'a': (r[ia] or '').strip() or None, 't': (r[ic] or '').strip()}  # newlines kept: the classifier splits clauses on them
        old = by_id.get(rec['id'])
        if old is None: added += 1
        else:
            replaced += 1
            if old.get('t') != rec['t'] or old.get('s') != rec['s'] or old.get('c') != rec['c']: changed += 1
            # keep the first-seen createTime if the mirror lost it
            if not rec['ct'] and old.get('ct'): rec['ct'] = old['ct']
        by_id[rec['id']] = rec

    new_labels = {k: v for k, v in unmapped.items() if k not in UNMAPPED_BY_RULING}
    if new_labels:
        log('🔴 NEW UNMAPPED LABEL(S) IN THE MIRROR — a new label is not a ruling, ASK before shipping:', new_labels)
        sys.exit(3)
    d1, d2 = (today - datetime.timedelta(days=1)).isoformat(), (today - datetime.timedelta(days=2)).isoformat()
    if not dates_seen:
        log('🔴 MIRROR CARRIES NO DATED ROWS — dark feed, not merging'); sys.exit(4)
    if dates_seen.get(d1, 0) == 0 and dates_seen.get(d2, 0) == 0:
        log(f'🔴 MIRROR HAS NO ROWS FOR {d1} OR {d2} — feed looks dark or lagging (newest date {max(dates_seen)}); not merging'); sys.exit(4)

    recs = sorted(by_id.values(), key=lambda x: (x['d'], x.get('ct') or ''))
    first_seen, last_seen, per_site = {}, {}, collections.Counter()
    for x in recs:
        first_seen[x['c']] = min(first_seen.get(x['c'], x['d']), x['d'])
        last_seen[x['c']] = max(last_seen.get(x['c'], x['d']), x['d'])
        per_site[x['c']] += 1
    m0 = base.get('meta', {})
    meta = {
        'pulledAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        'from': m0.get('from', '2026-04-20'),
        'route': 'mirror-merge (merge_reviews_mirror.py) on top of ' + str(m0.get('route', 'browser full pull ' + str(m0.get('pulledAt'))))[:160],
        'rows': m0.get('rows', 0) + (len(rows) - 1), 'kept': len(recs), 'dup': m0.get('dup', 0) + dup,
        'noStars': m0.get('noStars', 0) + no_stars, 'noDate': m0.get('noDate', 0) + no_date,
        'dropped': {k: m0.get('dropped', {}).get(k, 0) + dropped.get(k, 0) for k in set(m0.get('dropped', {})) | set(dropped)},
        'unmapped': {k: m0.get('unmapped', {}).get(k, 0) + unmapped.get(k, 0) for k in set(m0.get('unmapped', {})) | set(unmapped)},
        'firstSeen': first_seen, 'lastSeen': last_seen, 'perSite': dict(per_site),
        'withText': sum(1 for x in recs if x['t']),
        'mirror_merge': {'mirror_rows': len(rows) - 1, 'window': [min(dates_seen), max(dates_seen)], 'added': added,
                         'replaced': replaced, 'changed': changed, 'dup_in_mirror': dup,
                         'dropped': dict(dropped), 'unmapped': dict(unmapped), 'base_reviews': n_base},
    }
    json.dump({'meta': meta, 'reviews': recs}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    log(f"MERGED base {n_base} + mirror {len(rows)-1} rows ({min(dates_seen)}..{max(dates_seen)}) -> {len(recs)} reviews | added {added} replaced {replaced} (changed {changed}) dup {dup} | dropped {dict(dropped)} unmapped {dict(unmapped)} | newest {max(dates_seen)} rows on {d1}: {dates_seen.get(d1,0)}, {d2}: {dates_seen.get(d2,0)}")
    print(json.dumps({'added': added, 'changed': changed, 'kept': len(recs), 'newest': max(dates_seen)}))

if __name__ == '__main__':
    main()
