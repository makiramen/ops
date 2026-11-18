#!/usr/bin/env python3
"""Green Light covers board on the AM Control Centre basis (Michael, 18/11/2026).

RULE (same as marketing/index.html amCoversAlign, keep the two in step):
  covers actual = AM dash covers (closed week: data/all_sites_wc_<wc>.json;
                  week in progress: data/kobas/wc_<wc>.json)
  covers target = AM weekly sales target x (1 - delivery share) / SPH target
  SPH target    = GBP 22, Ikigai 21, Maki Nori 35
  delivery share= the site's own delivery sales / total sales over the 4 completed
                  weeks before the week (earliest 4 weeks on file if none earlier).
                  Delivery brings no covers, so it comes out of the target.
  RAG           = green at or above 100% of target, amber from 85%, red below.

Usage: python3 marketing/green_light_am.py [--week YYYY-MM-DD] [--repo .] [--json]
Default week = the last complete Monday to Sunday week.
"""
import argparse, datetime as dt, glob, json, os, re, sys

SITES = ['M1', 'M3', 'M6', 'M7', 'M8', 'M9', 'M10', 'M11', 'M12', 'M13', 'M14', 'M15',
         'M16', 'M17', 'M18', 'M19', 'M20', 'MakiNori', 'IKI2']
SPH = {'MakiNori': 35, 'IKI2': 21}
SPH_DEFAULT = 22
HISTORY_WEEKS = 16


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def week_file(repo, wc):
    a = load(os.path.join(repo, 'data', 'all_sites_wc_%s.json' % wc))
    if a and a.get('sites'):
        has_del = any((s.get('kpis') or {}).get('delivery_total', {}) and
                      (s['kpis']['delivery_total'] or {}).get('sales') is not None
                      for s in a['sites'].values())
        return {'kind': 'weekly', 'sites': a['sites'], 'has_del': has_del}
    k = load(os.path.join(repo, 'data', 'kobas', 'wc_%s.json' % wc))
    if k and k.get('sites'):
        return {'kind': 'kobas', 'sites': k['sites'], 'days': k.get('days_pulled') or 0}
    return None


def figures(f, site):
    s = f['sites'].get(site)
    if not s:
        return None
    if f['kind'] == 'weekly':
        k = s.get('kpis') or {}
        cov = (k.get('covers') or {}).get('actual')
        if cov is None:
            return None
        sales = k.get('sales') or {}
        d = (k.get('delivery_total') or {}).get('sales')
        return {'target': sales.get('target'), 'covers': cov, 'days': 7,
                'del': (d or 0) if f['has_del'] else None,
                'sales': (sales.get('actual') or 0) if f['has_del'] else None}
    w = s.get('week') or {}
    days = w.get('days_traded')
    if days is None:
        days = f.get('days') or 0
    return {'target': w.get('target_gross'), 'covers': w.get('covers') or 0, 'days': min(7, days or 0),
            'del': w.get('delivery_gross') or 0, 'sales': w.get('sales_gross') or 0}


def board(repo, wc):
    monday = dt.date.fromisoformat(wc)
    weeks = [(monday - dt.timedelta(7 * i)).isoformat() for i in range(HISTORY_WEEKS, -1, -1)]
    files = {w: week_file(repo, w) for w in weeks}
    hist = {}
    for w in weeks:
        f = files[w]
        if not f:
            continue
        for s in SITES:
            g = figures(f, s)
            if g and g['days'] >= 7 and g['del'] is not None and g['sales'] and g['sales'] > 0:
                hist.setdefault(s, []).append((w, g['del'], g['sales']))

    def share(site):
        h = hist.get(site, [])
        before = [x for x in h if x[0] < wc][-4:]
        use = before or h[:4]
        d = sum(x[1] for x in use)
        s = sum(x[2] for x in use)
        return min(0.9, d / s) if s > 0 else 0.0

    f = files[wc]
    if not f:
        raise SystemExit('No AM file for w/c %s (neither all_sites nor kobas)' % wc)
    rows = []
    for s in SITES:
        g = figures(f, s)
        if not g:
            rows.append({'site': s, 'rag': 'NO AM FIGURE'})
            continue
        sh = share(s)
        tgt = int(float(g['target']) * (1 - sh) / SPH.get(s, SPH_DEFAULT) + 0.5) if g['target'] else None
        pct = round(g['covers'] / tgt * 100, 1) if tgt else None
        rag = 'NO TARGET' if pct is None else 'GREEN' if pct >= 100 else 'AMBER' if pct >= 85 else 'RED'
        rows.append({'site': s, 'covers': g['covers'], 'target': tgt, 'pct': pct, 'rag': rag,
                     'days': g['days'], 'sales_target': g['target'], 'delivery_share_pct': round(sh * 100, 1)})
    return {'week_commencing': wc, 'source': f['kind'], 'complete': all(r.get('days', 0) >= 7 for r in rows if 'days' in r), 'rows': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week')
    ap.add_argument('--repo', default='.')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    wc = a.week
    if not wc:
        today = dt.date.today()
        wc = (today - dt.timedelta(days=today.weekday() + 7)).isoformat()
    b = board(a.repo, wc)
    if a.json:
        print(json.dumps(b, indent=1))
        return
    print('w/c %s (%s, %s)' % (wc, b['source'], 'complete' if b['complete'] else 'IN PROGRESS'))
    tc = tt = 0
    for r in sorted(b['rows'], key=lambda r: (r.get('pct') is None, r.get('pct') or 0)):
        if 'covers' not in r:
            print('%-9s %s' % (r['site'], r['rag']))
            continue
        tc += r['covers']
        tt += r['target'] or 0
        print('%-9s covers %5d  target %5s  %6s%%  %-9s (delivery share %s%%)' % (
            r['site'], r['covers'], r['target'], r['pct'], r['rag'], r['delivery_share_pct']))
    print('ALL       covers %5d  target %5d  %6.1f%%' % (tc, tt, tc / tt * 100 if tt else 0))


if __name__ == '__main__':
    main()
