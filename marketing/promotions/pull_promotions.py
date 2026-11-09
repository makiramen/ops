#!/usr/bin/env python3
"""pull_promotions.py: Promotions tab feed for the Marketing Hub, straight from Kobas (no Mac, no sheet).

Logs into Kobas as the keyline bot user (KOBAS_COMPANY_ID / KOBAS_USERNAME / KOBAS_PASSWORD, Actions secrets),
lists every trading venue, and pulls the All Item Sales report (/data/reports/item-by-sales/export) per venue per
week (Monday to Sunday). Replaces the hand-filled "Weekly Deals Sales" / "Weekly Sales" tabs of 2026 Weekly Reporting.

Incremental: weeks already in data.json are kept; the last REFRESH_WEEKS full weeks and the current week to date
are always pulled again (late Kobas edits). First run backfills from START (30 Mar 2026, the sheet's first week).

  python3 pull_promotions.py --out marketing/promotions/data.json [--start 2026-03-30] [--refresh 2]

data.json (compact):
  weeks  [monday iso, ...]            partial = monday of the week to date (or null)
  sites  [[venue_id, code, name], ...]
  items  [[name, category], ...]
  cells  {"<siteIdx>": {"<weekIdx>": [[itemIdx, qty, gross], ...]}}
"""
import argparse, csv, datetime, io, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'keyline'))
from kobas_pull import Kobas, BASE  # noqa: E402

UK = ZoneInfo('Europe/London')
# Kobas venue id -> (code, display name). Venues not listed still come through under their Kobas name.
KNOWN = {3: ('M1', 'Nicolson St'), 5: ('M3', 'Fountainbridge'), 43: ('M6', 'Bath St'), 9: ('M7', 'SJQ'),
         47: ('M8', 'Renfield'), 2: ('M9', 'Manchester'), 13: ('M10', 'Leeds'), 24: ('M11', 'Leicester'),
         27: ('M12', 'Newcastle'), 28: ('M13', 'Aberdeen'), 37: ('M14', 'Meadowhall'), 41: ('M15', 'Metrocentre'),
         42: ('M16', 'Nottingham'), 49: ('M17', 'Lakeside'), 51: ('M18', 'Soho'), 58: ('M19', 'Shoreditch'),
         60: ('M20', 'Southampton'), 61: ('M21', 'Birmingham'), 57: ('NORI', 'Maki Nori'), 7: ('IKI2', 'Ikigai Ramen')}
SCHEMA = 9   # bump to force a full backfill (2: modifier "of which" lines kept, 3: discounts report added)
SKIP_NAME = re.compile(r'aahq|head office|\bho\b|factory|warehouse|kitchen ltd|test|training|demo|central', re.I)


def log(*a): print(*a, file=sys.stderr, flush=True)


def num(s):
    try: return float(str(s).replace(',', '').replace('£', '').strip() or 0)
    except ValueError: return 0.0


def venues(k):
    try:
        vs = k.gj('/data/venue')
        vs = vs if isinstance(vs, list) else vs.get('data', [])
    except Exception as e:
        log('venue list failed, using the known map:', e); vs = []
    out = {}
    for v in vs:
        vid = v.get('id'); nm = (v.get('screen_message') or v.get('name') or '').strip()
        if not vid or v.get('is_head_office') or v.get('is_parent'): continue
        if v.get('endweek_date'): continue
        if vid not in KNOWN and SKIP_NAME.search(v.get('name') or ''): continue
        code, disp = KNOWN.get(vid, ('', re.sub(r'^Maki (& Ramen )?', '', nm) or str(vid)))
        out[vid] = (code, disp)
    for vid, cd in KNOWN.items():
        out.setdefault(vid, cd)
    return out


def pull_one(k, vid, d0, d1):
    data = [('venueIds[]', str(vid)), ('from', d0), ('to', d1), ('piscMode', ''), ('filterByTill', 'false'),
            ('seatingArea', ''), ('consumptionMode', '')]
    last = None
    for i in range(4):
        try:
            p = k.s.post(BASE + '/data/reports/item-by-sales/export', data=data, timeout=180,
                         headers={'Content-Type': 'application/x-www-form-urlencoded'})
            if p.status_code == 200: return parse(p.text)
            last = p.status_code
        except Exception as e: last = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(f'venue {vid} {d0}: {last}')


SAMPLE = {'done': False}
DISC_OFF = {'off': False, 'fails': 0}


DISC_NAMES = {}


def _promos(j):
    if not isinstance(j, dict): return None
    p = j.get('promos')
    if p is None and isinstance(j.get('data'), dict): p = j['data'].get('promos')
    if isinstance(p, list): return p
    if isinstance(p, dict):   # keyed by discount id (sometimes by lead type then id)
        out = []
        for kk, v in p.items():
            if isinstance(v, dict) and v and all(isinstance(x, dict) for x in v.values()) and not any(
                    x in v for x in ('count', 'qty', 'value', 'name')):
                out += [dict(x, _id=k2) for k2, x in v.items()]
            elif isinstance(v, dict): out.append(dict(v, _id=kk))
        return out
    return None


def _first(d, keys):
    for kk in keys:
        if kk in d and d[kk] not in (None, ''): return d[kk]
    return None


def disc_parse(j):
    """Kobas /data/report/discount JSON -> {discount name: [uses, £ value]} from its promos list."""
    ps = _promos(j)
    if ps is None: return None
    out = {}
    for pr in ps:
        if not isinstance(pr, dict): continue
        pid = _first(pr, ('id', 'promo_id', 'discount_id', 'promoid', 'discountid', '_id'))
        nm = str(_first(pr, ('name', 'promo_name', 'discount_name', 'public_name', 'title')) or DISC_NAMES.get(str(pid)) or pid or '').strip()
        if not nm: continue
        c = num(_first(pr, ('count', 'qty', 'quantity', 'uses', 'used', 'number', 'num', 'times', 'transactions')) or 0)
        v = abs(num(_first(pr, ('value', 'amount', 'discount', 'total', 'discount_value', 'gross', 'net')) or 0))
        cur = out.setdefault(nm, [0.0, 0.0]); cur[0] += c; cur[1] += v
    return out


def _disc_get(k, vid, d0, d1, timeout=60):
    return k.s.get(BASE + '/data/report/discount', params=[('venueIds[]', str(vid)), ('startDate', d0), ('endDate', d1)], timeout=timeout)


def disc_probe(k, vid, d0, d1):
    """The Discounts report page calls GET /data/report/discount?venueIds[]&startDate&endDate (discountsService.js)."""
    try:
        lst = k.gj('/data/discount')
        lst = lst.get('data', lst) if isinstance(lst, dict) else lst
        for x in lst or []:
            if isinstance(x, dict) and x.get('id') is not None:
                DISC_NAMES[str(x['id'])] = (x.get('name') or x.get('public_name') or '').strip()
        log('till discount names', len(DISC_NAMES))
    except Exception as e:
        log('till discount list failed', repr(e)[:120])
    try:
        r = _disc_get(k, vid, d0, d1)
        log('discounts report', r.status_code, r.headers.get('content-type', ''), len(r.text))
        j = r.json()
        log('discounts report keys', list(j)[:20] if isinstance(j, dict) else type(j).__name__)
        log('discounts promos raw', json.dumps(j.get('promos'))[:900])
        ps = _promos(j)
        if ps: log('discounts first promo', json.dumps(ps[0])[:600])
        res = disc_parse(j)
        if res is not None:
            DISC_OFF['var'] = True
            log('discounts sample', vid, d0, sorted(res.items(), key=lambda x: -x[1][0])[:10])
            return True
    except Exception as e:
        log('discounts report error', repr(e)[:200])
    DISC_OFF['off'] = True; log('discounts report not usable, lunch deals stay off this run')
    return False


def pull_disc(k, vid, d0, d1):
    """Discounts report (lunch deals and other till discounts) for one venue and week: {name: [uses, value]}.
    Best effort: a failure returns None and never stops the item pull."""
    if DISC_OFF['off'] or not DISC_OFF.get('var'): return None
    for i in range(2):
        try:
            r = _disc_get(k, vid, d0, d1)
            if r.status_code == 200:
                res = disc_parse(r.json())
                if res is not None: return res
        except Exception as e:
            last = repr(e)[:120]
        time.sleep(2)
    DISC_OFF['fails'] += 1
    if DISC_OFF['fails'] >= 10: DISC_OFF['off'] = True; log('discounts switched off for this run')
    return None


def parse(txt):
    rows = [l for l in csv.reader(io.StringIO(txt.lstrip('﻿'))) if any(c.strip() for c in l)]
    if not rows: return {}
    h = [c.strip().lower() for c in rows[0]]
    def ix(*names):
        for n in names:
            if n in h: return h.index(n)
        return None
    ii, ci, qi, gi = ix('item'), ix('category'), ix('items sold', 'qty', 'quantity'), ix('gross sales', 'gross')
    if ii is None or qi is None: raise RuntimeError('unexpected export header: ' + ','.join(rows[0][:8]))
    out = {}; parent_cat = ''
    for l in rows[1:]:
        if len(l) <= max(x for x in (ii, ci, qi, gi) if x is not None): continue
        nm = l[ii].strip()
        if not nm or nm.lower() == 'total': continue
        q = num(l[qi]); g = num(l[gi]) if gi is not None else 0.0
        if q == 0 and g == 0: continue
        cat = l[ci].strip() if ci is not None else ''
        if nm.lower().startswith('of which '):
            # modifier / option line, already inside its parent item: kept under its own name for promo matching
            # (lunch deal options, XOXO choices), category tagged so totals never add it to the parent again
            nm = 'of which ' + nm[9:].strip(); cat = 'Modifier' + (' · ' + parent_cat if parent_cat else '')
        else:
            parent_cat = cat
        cur = out.setdefault(nm, [cat, 0.0, 0.0])
        cur[1] += q; cur[2] += g
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'data.json'))
    ap.add_argument('--start', default='2026-03-30')
    ap.add_argument('--refresh', type=int, default=2)
    a = ap.parse_args()

    today = datetime.datetime.now(UK).date()
    this_mon = today - datetime.timedelta(days=today.weekday())
    start = datetime.date.fromisoformat(a.start)
    start -= datetime.timedelta(days=start.weekday())
    mondays = []
    m = start
    while m <= this_mon:
        mondays.append(m); m += datetime.timedelta(days=7)
    partial = this_mon if today > this_mon else None  # Monday morning: nothing traded yet this week
    if partial is None: mondays = [x for x in mondays if x < this_mon]

    # existing data -> raw {(week, vid): {item: [cat, q, g]}}
    raw, old_sites, draw = {}, {}, {}
    disc_ok = True   # whether the last run could read the discounts report (if not, never re-pull settled weeks for it)
    if os.path.exists(a.out):
        try:
            d = json.load(open(a.out))
            if d.get('schema') != SCHEMA: raise ValueError(f"schema {d.get('schema')} -> {SCHEMA}")
            disc_ok = d.get('disc_ok', True)
            for vid, code, name in d['sites']: old_sites[vid] = (code, name)
            for si, wk in d['cells'].items():
                vid = d['sites'][int(si)][0]
                for wi, lst in wk.items():
                    w = d['weeks'][int(wi)]
                    if w == d.get('partial'): continue
                    raw[(w, vid)] = {d['items'][ii][0]: [d['items'][ii][1], q, g] for ii, q, g in lst}
            for si, wk in (d.get('dcells') or {}).items():
                vid = d['sites'][int(si)][0]
                for wi, lst in wk.items():
                    w = d['weeks'][int(wi)]
                    if w != d.get('partial'): draw[(w, vid)] = {d['discounts'][ii]: [c, v] for ii, c, v in lst}
            for w, vid in d.get('empty', []):
                if w != d.get('partial'): raw[(w, vid)] = {}
        except Exception as e:
            log('existing data.json unreadable, full backfill:', e); raw = {}; draw = {}

    k = Kobas()
    if not k.login(): log('Kobas login failed'); sys.exit(30)
    vs = venues(k)
    log('venues', len(vs), sorted(vs.items()))

    fixed = set(x.isoformat() for x in mondays[:-a.refresh - (1 if partial else 0)]) if len(mondays) > a.refresh else set()
    have = {w for (w, _v) in raw}
    jobs = []
    for mon in mondays:
        w = mon.isoformat()
        end = (today - datetime.timedelta(days=1)) if mon == partial else mon + datetime.timedelta(days=6)
        for vid in vs:
            if w in fixed and w in have and (w, vid) in raw and ((w, vid) in draw or not disc_ok): continue   # settled week already pulled
            jobs.append((w, vid, w, end.isoformat()))
    log('jobs', len(jobs))
    if jobs:
        pv = 28 if 28 in vs else next(iter(vs))
        last_full = [x for x in mondays if x != partial][-1]
        disc_probe(k, pv, last_full.isoformat(), (last_full + datetime.timedelta(days=6)).isoformat())

    def run(j):
        w, vid, d0, d1 = j
        try: res = pull_one(k, vid, d0, d1)
        except Exception as e: return j, None, None, str(e)
        try: dres = pull_disc(k, vid, d0, d1)
        except Exception: dres = None
        return j, res, dres, None
    errs = []; derr = 0
    with ThreadPoolExecutor(5) as ex:
        for (w, vid, _, _), res, dres, err in ex.map(run, jobs):
            if err: errs.append(err); continue
            raw[(w, vid)] = res
            if dres is None: derr += 1
            else: draw[(w, vid)] = dres
    log('discount pulls failed', derr)
    log('errors', len(errs), errs[:5])
    if jobs and len(errs) > len(jobs) * 0.3:
        log('too many failures, not writing'); sys.exit(32)

    # compile
    weeks = sorted({w for (w, _v) in raw} | {x.isoformat() for x in mondays})
    sites_all = dict(old_sites); sites_all.update(vs)
    site_ids = sorted({v for (_w, v), r in raw.items() if r},
                      key=lambda v: (sites_all.get(v, ('', ''))[0] == '', sites_all.get(v, ('', str(v)))[1]))
    items, iidx, cells = [], {}, {}
    for si, vid in enumerate(site_ids):
        for wi, w in enumerate(weeks):
            r = raw.get((w, vid))
            if not r: continue
            lst = []
            for nm, (cat, q, g) in sorted(r.items()):
                key = (nm, cat)
                if key not in iidx: iidx[key] = len(items); items.append([nm, cat])
                lst.append([iidx[key], round(q, 2) if q % 1 else int(q), round(g)])
            cells.setdefault(str(si), {})[str(wi)] = lst
    discs, didx, dcells = [], {}, {}
    for si, vid in enumerate(site_ids):
        for wi, w in enumerate(weeks):
            r = draw.get((w, vid))
            if not r: continue
            lst = []
            for nm, (c, v) in sorted(r.items()):
                if nm not in didx: didx[nm] = len(discs); discs.append(nm)
                lst.append([didx[nm], round(c, 2) if c % 1 else int(c), round(v)])
            dcells.setdefault(str(si), {})[str(wi)] = lst
    outd = {'schema': SCHEMA, 'generated_at': datetime.datetime.now(UK).strftime('%Y-%m-%d %H:%M'), 'source': 'Kobas All Item Sales, weekly Mon-Sun',
            'weeks': weeks, 'partial': partial.isoformat() if partial else None,
            'partial_to': (today - datetime.timedelta(days=1)).isoformat() if partial else None,
            'sites': [[vid, sites_all.get(vid, ('', str(vid)))[0], sites_all.get(vid, ('', str(vid)))[1]] for vid in site_ids],
            'items': items, 'cells': cells, 'errors': len(errs), 'discounts': discs, 'dcells': dcells, 'disc_ok': not DISC_OFF['off'],
            'empty': sorted([w, v] for (w, v), r in raw.items() if not r)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(outd, open(a.out, 'w'), separators=(',', ':'))
    print(json.dumps({'discounts': len(discs), 'weeks': len(weeks), 'sites': len(site_ids), 'items': len(items), 'jobs': len(jobs), 'errors': len(errs),
                      'bytes': os.path.getsize(a.out)}))


if __name__ == '__main__':
    main()
