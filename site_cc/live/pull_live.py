"""Site CC Live tab pull (24/11/2026, Michael: live upsells, ramen with a sushi, SPH, sales vs target, live wage %).

Logs into Kobas with the bot user (no Mac, no browser) and writes <out>/<site>.json for each pilot site. Routes are in
the project doc claude/kobas-live-route.md:
  bills + items + servers   Daily Sales By Order      POST /reports/index.php  m=CORE_Reports_DailySalesByOrder
  table closed, clock ins   EPoS audit CSV            GET  /reports/csv-gen/epos_audit.php?v=<venue>&date=<day>
  covers                    Sales Breakdown totals    GET  /data/report/group-sales/totals
  item category             All Item Sales export     POST /data/reports/item-by-sales/export

Michael's rulings 24/11/2026:
  * covers, revenue, SPH and wage % only count tables that are CLOSED (audit action finalpayment on the tab)
  * upsell units and ramen with sushi counts show as rung; their per cover versions use closed tables only
  * eat in only, staff tabs excluded, corporate sites, server initials only (the repo is public), no upsell targets yet
  * live wage % is an ESTIMATE: hours clocked in so far x the site's cost per hour last completed week / closed sales
  * a missing input is flagged by name and left null, never filled with zero
Env: KOBAS_COMPANY_ID / KOBAS_USERNAME / KOBAS_PASSWORD, LIVE_SITES (default M18,M11), DAY (default today, UK).
"""
import os, re, sys, csv, io, json, html, glob, datetime
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'keyline')); sys.path.insert(0, os.path.join(ROOT, 'kobas_weekly'))
from kobas_pull import Kobas, BASE
from sitemap import V, FRANCHISE

UK = ZoneInfo('Europe/London')
SUSHI_RX = r'sushi|maki roll|nigiri|sashimi|hosomaki|hand roll|chef'      # same category rule as kpi_auto/kobas_daily.py
UPS = {'still': r'still water', 'spark': r'sparkling water', 'eda': r'edamame', 'kim': r'kimchi'}


def txt(h): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()
def gbp(s):
    try: return float(re.sub(r'[^0-9.\-]', '', s) or 0)
    except ValueError: return 0.0
def initials(name): return ''.join(w[0] for w in re.split(r'[\s\-]+', name.strip()) if w).upper()[:4] or '?'


def parse_orders(page):
    """Daily Sales By Order -> one dict per item row. Source, Tab and Receipt # sit on an order's first row only."""
    m = re.search(r'<table[^>]*class="[^"]*rollover[^"]*"[^>]*>(.*?)</table>', page, re.S)
    if not m: return None
    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S)
    if not trs: return []
    cells = lambda tr: [txt(x) for x in re.split(r'<t[hd]\b[^>]*>', tr)[1:]]      # Kobas leaves some <td> unclosed: split on the opening tag
    head = [c.lower() for c in cells(trs[0])]
    need = ['time', 'source', 'tab', 'receipt #', 'order #', 'item', 'consumption mode', 'revenue', 'transaction type']
    if any(n not in head for n in need): raise RuntimeError('Daily Sales By Order header changed: ' + ' | '.join(head))
    ix = {n: head.index(n) for n in need}
    rows, cur = [], {'src': '', 'tab': '', 'rc': ''}
    for tr in trs[1:]:
        c = cells(tr)
        if len(c) < len(head): continue
        if c[ix['source']]: cur = {'src': c[ix['source']], 'tab': c[ix['tab']], 'rc': c[ix['receipt #']]}
        rows.append({'time': c[ix['time']][:8], 'src': cur['src'], 'tab': cur['tab'], 'rc': cur['rc'], 'order': c[ix['order #']],
                     'item': c[ix['item']], 'mode': c[ix['consumption mode']].lower(), 'rev': gbp(c[ix['revenue']]),
                     'tt': c[ix['transaction type']]})
    return rows


def parse_audit(text):
    out = []
    rd = csv.reader(io.StringIO(text)); head = [h.strip().lower() for h in next(rd, [])]
    if head[:6] != ['staff', 'till', 'action', 'object', 'target', 'event time']: raise RuntimeError('EPoS audit header changed: ' + ','.join(head))
    for r in rd:
        if len(r) >= 6: out.append({'staff': r[0], 'till': r[1], 'act': r[2], 'obj': r[3], 'tgt': r[4], 'ts': r[5][:19]})
    return out


def tab_id(t):
    m = re.search(r'\((\d+)\)\s*$', t or ''); return m.group(1) if m else None


def audit_maps(A):
    """order # -> tab id (neworder on a tab and addtotab of the order share staff, till and second), closed tab ids.
    A merged tab follows its destination."""
    at, order_tab, closed, merged, last, pend_src = {}, {}, {}, {}, {}, {}
    for e in A:
        if e['act'] in ('neworder', 'new') and e['obj'] == 'tab' and tab_id(e['tgt']): at[(e['staff'], e['till'], e['ts'])] = tab_id(e['tgt'])
    for e in A:
        k = (e['staff'], e['till']); a, o = e['act'], e['obj']
        if a in ('neworder', 'new') and o == 'tab' and tab_id(e['tgt']): last[k] = tab_id(e['tgt'])
        elif a == 'addtotab' and o == 'order':
            t = at.get((e['staff'], e['till'], e['ts'])) or last.get(k)
            if t: order_tab[e['tgt'].strip()] = t
        elif a == 'finalpayment' and o == 'tab' and tab_id(e['tgt']): closed[tab_id(e['tgt'])] = (re.sub(r'\s*\(\d+\)\s*$', '', e['tgt']).strip().lower(), e['ts'][11:19])
        elif a == 'mergetabsource' and o == 'tab': pend_src[k] = tab_id(e['tgt'])
        elif a == 'mergetabdestination' and o == 'tab' and pend_src.get(k): merged[pend_src.pop(k)] = tab_id(e['tgt'])
    def final(t, n=0):
        return final(merged[t], n + 1) if t in merged and n < 6 else t
    return {o: final(t) for o, t in order_tab.items()}, closed


def nkey(name): return ' '.join(re.sub(r'\([^)]*\)', ' ', re.sub(r"[^a-z() ]", ' ', (name or '').lower())).split())


def rota_today(k, vid, day):
    """Planned shifts for the day from Rotas (index.php?m=full): {name key: [(start h, end h)]}. Names never leave this run.
    Each staff row carries seven day cells, Monday first. The italic line in a cell is the hours worked, not the plan."""
    mon = day - datetime.timedelta(day.weekday())
    R = k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()
    rid = next((x['id'] for x in R if x['venueid'] == vid and str(x['rotadate'])[:10] == mon.isoformat()), None)
    if not rid: raise RuntimeError('no rota for the week')
    t = k.s.get(BASE + '/rotas/index.php', params={'m': 'full', 'iRotaID': rid, 'venueid': vid, 'rotashow': f'V_{vid}'}, timeout=120).text
    if not re.search(r'<option value="V_%d"[^>]*selected' % vid, t): raise RuntimeError('rota page not on this venue')
    out = {}
    for seg in t.split('<tr')[1:]:
        if 'class="align-left"' not in seg: continue
        c = re.split(r'<td\b[^>]*>', seg)[1:]
        if len(c) < 8: continue
        nm = re.search(r'<a[^>]*>(.*?)</a>', c[0], re.S)
        if not nm: continue
        cell = re.sub(r'<i>.*?</i>', ' ', c[1 + day.weekday()], flags=re.S); sh = []
        for m in re.finditer(r'(\d{1,2}):(\d{2})\s*to\s*(\d{1,2}):(\d{2})', cell):
            a_ = int(m.group(1)) + int(m.group(2)) / 60.0; b_ = int(m.group(3)) + int(m.group(4)) / 60.0
            sh.append((a_, b_ + 24 if b_ <= a_ else b_))
        if sh: out.setdefault(nkey(txt(nm.group(1))), []).extend(sh)
    return out


def clock_hours(A, now_h, rota):
    """Hours clocked in on the tills so far today, breaks out.
    24/11/2026 (Michael: fix the M11 estimate): some staff never clock out on the till. A shift still open runs to now, but
    no later than that person's planned finish on the rota, which is how Kobas itself closes a missed clock out. Someone
    clocked in who is not on the rota is held to the median planned shift length of the day (8 h if no rota)."""
    def hh(ts): return int(ts[11:13]) + int(ts[14:16]) / 60.0
    st, hrs, on, by_rota, by_len = {}, 0.0, 0, 0, 0
    for e in A:
        if e['obj'] != 'user' or e['act'] not in ('clockin', 'clockout', 'breakstart', 'breakend'): continue
        s = st.setdefault(e['staff'], {'in': None, 'first': None}); h = hh(e['ts'])
        if e['act'] in ('clockin', 'breakend'):
            if s['in'] is None: s['in'] = h
            if s['first'] is None: s['first'] = h
        elif s['in'] is not None: hrs += max(0.0, h - s['in']); s['in'] = None
    lens = sorted(b - a for v in (rota or {}).values() for a, b in v); typical = lens[len(lens) // 2] if lens else 8.0
    rk = {}
    for kname in (rota or {}):
        rk[kname] = kname; w = kname.split()
        if len(w) > 1: rk.setdefault(w[0] + ' ' + w[-1], kname)
    for name, s in st.items():
        if s['in'] is None: continue
        w = nkey(name).split(); key = rk.get(' '.join(w)) or (rk.get(w[0] + ' ' + w[-1]) if len(w) > 1 else None)
        ends = [b for a, b in (rota or {}).get(key, []) if a - 3 <= s['first'] <= b] if key else []
        if ends: end = min(now_h, max(max(ends), s['in'])); by_rota += end < now_h
        else: end = min(now_h, s['first'] + typical); by_len += end < now_h
        hrs += max(0.0, end - s['in']); on += end >= now_h
    return round(hrs, 2), on, len(st), by_rota, by_len


def cost_per_hour(site, day):
    """Hours Worked Cost / Hours Worked over the last completed week in data/kobas (the nightly Kobas pull)."""
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'kobas', 'wc_*.json')), reverse=True):
        wc = os.path.basename(f)[3:13]
        if wc > (day - datetime.timedelta(7 + day.weekday())).isoformat(): continue
        try: D = (json.load(open(f))['sites'].get(site) or {}).get('days') or {}
        except Exception: continue
        c = h = 0.0
        for d in D.values():
            lab = d.get('labour') or {}
            if lab.get('hours_worked_cost') and lab.get('hours'): c += lab['hours_worked_cost']; h += lab['hours']
        if h > 0: return round(c / h, 2), wc
    return None, None


def day_target(site, day):
    try: return (json.load(open(os.path.join(ROOT, 'site_cc', 'data', site, 'labour.json'))).get('open') or {}).get('tgt', {}).get(day.isoformat())
    except Exception: return None


def build(site, day, now, k):
    vid = V[site]; flags = []; o = {'site': site, 'day': day.isoformat(), 'asof': now.isoformat(timespec='minutes'), 'flags': flags}
    r = k.s.post(BASE + '/reports/index.php', data={'s_day': f'{day.day:02d}', 's_month': f'{day.month:02d}', 's_year': str(day.year), 'venueid1': str(vid),
                 'm': 'CORE_Reports_DailySalesByOrder', 'v': '1', 'submit': ' View '}, timeout=120)
    rows = parse_orders(r.text) if r.status_code == 200 else None
    if not rows:      # structure only, never row text (the repo is public)
        i = r.text.find('rollover'); print('DEBUG by-order', site, r.status_code, len(r.text), 'rollover at', i, '|', re.sub(r'>[^<]+<', '>#<', r.text[max(0, i - 200):i + 1800]).replace('\n', ' ')[:2000], file=sys.stderr)
    if rows is None: flags.append('Daily Sales By Order: no table returned'); rows = []
    try: A = parse_audit(k.s.get(BASE + '/reports/csv-gen/epos_audit.php', params={'v': vid, 'date': day.isoformat()}, timeout=120).text)
    except Exception as e: A = None; flags.append(f'EPoS audit log missing ({e}): closed tables and clock ins unknown')
    cat = {}
    try:
        cs = k.s.post(BASE + '/data/reports/item-by-sales/export', data=[('venueIds[]', str(vid)), ('from', day.isoformat()), ('to', day.isoformat()), ('piscMode', ''),
                      ('filterByTill', 'false'), ('seatingArea', ''), ('consumptionMode', '')], timeout=120, headers={'Content-Type': 'application/x-www-form-urlencoded'}).text
        rd = csv.reader(io.StringIO(cs)); H = [h.strip().lower() for h in next(rd, [])]; ii, ic = H.index('item'), H.index('category')
        for c in rd:
            if len(c) > ic and c[ii].strip() and not re.match(r'\s*(of which|total)', c[ii], re.I): cat[c[ii].strip()] = c[ic].strip()
    except Exception as e: flags.append(f'All Item Sales export missing ({e}): sushi and ramen cannot be classified')
    covers = None
    try:
        T = k.s.get(BASE + '/data/report/group-sales/totals', params={'start_date': day.isoformat(), 'end_date': day.isoformat(), 'venue_id': vid}, timeout=120).json()
        covers = int(round(T['covers']['eatin']['total']))
    except Exception as e: flags.append(f'Sales Breakdown covers missing ({e})')

    order_tab, closed = audit_maps(A) if A is not None else ({}, {})
    # An order made by a split or a move has no addtotab event. Tie it to a table by its receipt (shared with a tied
    # order), else by the table name: the first table of that name paid at or after the order was rung.
    rc_tab = {}
    for x in rows:
        if order_tab.get(x['order']) and x['rc']: rc_tab.setdefault(x['rc'], order_tab[x['order']])
    for x in rows:
        if x['order'] in order_tab or x['mode'] != 'eat in': continue
        t = rc_tab.get(x['rc'])
        if not t:
            c = sorted((ts, i) for i, (nm, ts) in closed.items() if nm == x['tab'].strip().lower() and ts >= x['time'])
            t = c[0][1] if c else None
        if t: order_tab[x['order']] = t
    nocat = set()
    for x in rows:
        x['cat'] = cat.get(x['item'])
        if x['cat'] is None and cat: nocat.add(x['item'])
        c = x['cat'] or ''
        x['ramen'] = bool((re.match(r'(vegan )?ramen', c, re.I) or (re.search(r'special|lunch', c, re.I) and re.search(r'ramen', x['item'], re.I))) and not re.search(r'surcharge', x['item'], re.I))
        x['sushi'] = bool(re.search(SUSHI_RX, c, re.I))
        x['tid'] = order_tab.get(x['order'])
        x['bill'] = x['tid'] or ('r' + x['rc'])
        x['eat'] = x['mode'] == 'eat in'
        x['staff'] = bool(re.search(r'staff', x['tab'] + ' ' + x['tt'], re.I))
        x['closed'] = (x['tid'] in closed) if (x['eat'] and A is not None) else (not x['eat'])       # delivery / takeaway has no table to close
        for u, rx in UPS.items(): x[u] = bool(re.search(rx, x['item'], re.I))
    if nocat: flags.append('No Kobas category for: ' + ', '.join(sorted(nocat)[:8]))
    unmapped = len({x['order'] for x in rows if x['eat'] and not x['tid']}) if A is not None else 0
    if unmapped: flags.append(f'{unmapped} eat in orders could not be tied to a table: counted as open')

    E = [x for x in rows if x['eat'] and not x['staff']]; EC = [x for x in E if x['closed']]
    def units(X): return {u: sum(1 for x in X if x[u]) for u in UPS}
    def bills(X):
        b = {}
        for x in X: b.setdefault(x['bill'], []).append(x)
        return list(b.values())
    def pair(X):
        B = bills(X); rb = [b for b in B if any(x['ramen'] for x in b)]
        bowls = sum(1 for x in X if x['ramen']); su = sum(1 for x in X if x['sushi'])
        return {'bowls': bowls, 'sushi': su, 'bills': len(B), 'ramen_bills': len(rb), 'both_bills': sum(1 for b in rb if any(x['sushi'] for x in b)),
                'sushi_per_10_ramen': round(10.0 * su / bowls, 1) if bowls else None}
    rev_closed_eat = round(sum(x['rev'] for x in EC), 2)
    rev_closed_all = round(rev_closed_eat + sum(x['rev'] for x in rows if not x['eat'] and not x['staff']), 2)
    per100 = (lambda n: round(100.0 * n / covers, 1)) if covers else (lambda n: None)
    uc = units(EC); pc = pair(EC)
    o['closed'] = {'eat_in_sales': rev_closed_eat if A is not None else None, 'all_sales': rev_closed_all if A is not None else None, 'covers': covers,
                   'sph': round(rev_closed_eat / covers, 2) if (covers and A is not None) else None, 'tables': len(bills(EC)),
                   'upsell_per_100_covers': {u: per100(n) for u, n in uc.items()}, 'sushi_per_100_covers': per100(pc['sushi']), 'ramen_per_100_covers': per100(pc['bowls'])}
    o['open_tables'] = len(bills([x for x in E if not x['closed']])) if A is not None else None
    o['rung'] = {'upsell': units(E), 'pair': pair(E)}
    tgt = day_target(site, day); o['target'] = tgt
    if tgt is None: flags.append('No day sales target in site_cc/data/%s/labour.json' % site)
    close_h = 23.0; now_h = now.hour + now.minute / 60.0
    if tgt is not None and A is not None:
        left = round(max(0.0, tgt - rev_closed_all), 2); hrs_left = max(0.0, close_h - max(now_h, 11.0))
        o['to_target'] = {'left': left, 'per_hour': round(left / hrs_left, 0) if (left and hrs_left >= 0.25) else (0 if not left else None), 'pct': round(100.0 * rev_closed_all / tgt, 0) if tgt else None}
    H = {}
    for x in E:
        h = H.setdefault(x['time'][:2], {'h': x['time'][:2], 'still': 0, 'spark': 0, 'eda': 0, 'kim': 0, 'bowls': 0, 'sushi': 0, 'sales_closed': 0.0})
        for u in UPS: h[u] += x[u]
        h['bowls'] += x['ramen']; h['sushi'] += x['sushi']
        if x['closed']: h['sales_closed'] = round(h['sales_closed'] + x['rev'], 2)
    o['hours'] = [H[h] for h in sorted(H)]
    S = {}
    for x in E: S.setdefault(initials(re.sub(r'\s+-\s+till.*$', '', x['src'], flags=re.I)), []).append(x)
    o['servers'] = sorted(({'i': i, **units(X), **{kk: vv for kk, vv in pair(X).items() if kk != 'bills'}, 'bills': len(bills(X))} for i, X in S.items()), key=lambda s: -s['bills'])
    if A is not None:
        try: rota = rota_today(k, vid, day)
        except Exception as e: rota = None; flags.append(f'Rota not readable ({e}): a missed clock out is held to 8 hours')
        hrs, on, seen, by_rota, by_len = clock_hours(A, now_h if day == now.date() else 24.0, rota); rate, wc = cost_per_hour(site, day)
        if rate is None: flags.append('No cost per hour in data/kobas for the last completed week: wage % estimate not possible')
        cost = round(hrs * rate, 2) if rate else None
        o['wage_est'] = {'hours_clocked': hrs, 'on_shift_now': on, 'people_clocked': seen, 'closed_at_rota_finish': by_rota, 'closed_at_typical_length': by_len,
                         'on_rota_today': len(rota) if rota is not None else None, 'cost_per_hour': rate, 'rate_week': wc, 'cost': cost,
                         'pct': round(100.0 * cost / rev_closed_all, 1) if (cost and rev_closed_all > 0) else None, 'estimate': True}
    return o


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    now = datetime.datetime.now(UK).replace(tzinfo=None)
    day = datetime.date.fromisoformat(os.environ['DAY']) if os.environ.get('DAY') else now.date()
    sites = [s.strip() for s in (os.environ.get('LIVE_SITES') or 'M18,M11').split(',') if s.strip()]
    k = Kobas()
    if not k.login(): print('LOGIN FAILED', file=sys.stderr); sys.exit(30)
    bad = 0
    for s in sites:
        if s not in V or s in FRANCHISE: print('skip', s, '(not a corporate site in sitemap)', file=sys.stderr); continue
        try:
            o = build(s, day, now, k); json.dump(o, open(os.path.join(out, s + '.json'), 'w'), separators=(',', ':'))
            c = o['closed']; print(f"{s} {o['day']} closed eat in {c['eat_in_sales']} covers {c['covers']} sph {c['sph']} tables {c['tables']} open {o['open_tables']} "
                                   f"rung {o['rung']['upsell']} pair {o['rung']['pair']} wage {o.get('wage_est')} flags {o['flags']}")
        except Exception as e:
            bad += 1; print('ERR', s, repr(e)[:300], file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == '__main__': main()
