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
26/11/2026 (Michael: make it as tight as humanly possible against the cash up, last pull at midnight):
  * sit in = eat in + takeaway and covers = eat in + takeaway covers, the cash up basis (takeaway has no table: counted when rung)
  * a run before 10:00 UK pulls YESTERDAY as the final figures: every order counts (the day is over), covers add the Cash Log
    "tabs without covers set", hours come from Rotas > Hours Worked priced at last week's FOH and BOH cost per hour, and once the
    nightly Kobas pull has the day (data/kobas) the labour cost and hours are the cash up's own figures
  * in the day a shift Kobas already shows as worked on the rota (clocked out on any device) uses those times, breaks out
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


def _spans(text):
    out = []
    for m in re.finditer(r'(\d{1,2}):(\d{2})\s*to\s*(\d{1,2}):(\d{2})', text):
        a_ = int(m.group(1)) + int(m.group(2)) / 60.0; b_ = int(m.group(3)) + int(m.group(4)) / 60.0
        out.append((a_, b_ + 24 if b_ <= a_ else b_))
    return out


def rota_today(k, vid, day):
    """The day's rota (index.php?m=full): {name key: {'plan': [(start h, end h)], 'worked': [(start h, end h)]}}. Names never leave
    this run. Each staff row carries seven day cells, Monday first. The italic line in a cell is the shift as worked, which
    Kobas fills once the person has clocked out (on any device, or a manager edit). A cell worked at another venue is skipped."""
    mon = day - datetime.timedelta(day.weekday())
    R = k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()
    rid = next((x['id'] for x in R if x['venueid'] == vid and str(x['rotadate'])[:10] == mon.isoformat()), None)
    if not rid: raise RuntimeError('no rota for the week')
    t = k.s.get(BASE + '/rotas/index.php', params={'m': 'full', 'iRotaID': rid, 'venueid': vid, 'rotashow': f'V_{vid}'}, timeout=120).text
    if not re.search(r'<option value="V_%d"[^>]*selected' % vid, t): raise RuntimeError('rota page not on this venue')
    cells = []
    for seg in t.split('<tr')[1:]:
        if 'class="align-left"' not in seg: continue
        c = re.split(r'<td\b[^>]*>', seg)[1:]
        if len(c) < 8: continue
        nm = re.search(r'<a[^>]*>(.*?)</a>', c[0], re.S)
        if not nm: continue
        cell = c[1 + day.weekday()]
        ven = [txt(v) for v in re.findall(r'<strong[^>]*>(.*?)</strong>', cell, re.S)]
        cells.append((nkey(txt(nm.group(1))), cell, ven))
    cnt = {}
    for _, _, ven in cells:
        for v in ven: cnt[v] = cnt.get(v, 0) + 1
    own = max(cnt, key=cnt.get) if cnt else None
    out = {}
    for key, cell, ven in cells:
        if ven and own and all(v != own for v in ven): continue          # worked or planned at another venue only
        ital = ' '.join(re.findall(r'<i>(.*?)</i>', cell, re.S)); isp = _spans(ital)
        plan = _spans(re.sub(r'<i>.*?</i>', ' ', cell, flags=re.S)); worked = isp
        if not plan: worked, plan = isp[:1], isp[1:]      # an unplanned shift carries its times in italics twice: worked first, then as rota'd
        if re.search(r'another venue|absence|holiday|sick', txt(cell), re.I): worked = []      # "Worked in another venue", "Authorised Absence": not hours here
        if plan or worked:
            e = out.setdefault(key, {'plan': [], 'worked': []}); e['plan'] += plan; e['worked'] += worked
    return out, rid


def _minus(spans, cuts):
    """spans with the cut intervals (breaks) taken out."""
    out = []
    for a_, b_ in spans:
        seg = [(a_, b_)]
        for c, d in cuts:
            seg = [p for x, y in seg for p in ((x, min(y, c)), (max(x, d), y)) if p[1] - p[0] > 1e-9]
        out += seg
    return out


def clock_hours(A, now_h, rota):
    """Hours on shift so far today, breaks out.
    26/11/2026 (Michael: as tight as possible): a shift the rota already shows as worked uses those times (the person clocked out
    somewhere, often not on the till) with the till breaks taken out. Anyone on the rota with a worked shift and no till clock
    in is counted too.
    24/11/2026 (the M11 estimate): a shift still open with nothing worked on the rota runs to now, but no later than that
    person's planned finish. Someone clocked in who is not on the rota is held to the median planned shift length (8 h if no rota)."""
    d0 = min((e['ts'][:10] for e in A), default='')
    def hh(ts): return int(ts[11:13]) + int(ts[14:16]) / 60.0 + (24 if ts[:10] > d0 else 0)
    st, iv, on, by_rota, by_len, by_worked = {}, [], 0, 0, 0, 0
    LONG = 3.0      # a "break" longer than this was never clocked back in from: Kobas takes about an hour off, so does this
    for e in A:
        if e['obj'] != 'user' or e['act'] not in ('clockin', 'clockout', 'breakstart', 'breakend'): continue
        h = hh(e['ts']); a_ = e['act']
        if h >= 29 and e['staff'] not in st: continue      # someone starting the NEXT morning (a past day's log runs on): not this day
        if h > now_h + 0.01: continue
        s = st.setdefault(e['staff'], {'in': None, 'first': None, 'iv': [], 'br': [], 'b0': None})
        if s['first'] is None and a_ in ('clockin', 'breakend'): s['first'] = h
        if a_ == 'clockin':
            if s['in'] is None and s['b0'] is None: s['in'] = h
        elif a_ == 'breakstart':
            if s['in'] is not None: s['iv'].append((s['in'], h)); s['in'] = None
            s['b0'] = h
        elif a_ == 'breakend':
            if s['b0'] is not None:
                if h - s['b0'] <= LONG: s['br'].append((s['b0'], h))
                else: s['br'].append((s['b0'], s['b0'] + 1.0)); s['iv'].append((s['b0'] + 1.0, h))
                s['b0'] = None
            if s['in'] is None: s['in'] = h
        else:      # clockout
            if s['in'] is not None: s['iv'].append((s['in'], h)); s['in'] = None
            elif s['b0'] is not None and h - s['b0'] > LONG: s['br'].append((s['b0'], s['b0'] + 1.0)); s['iv'].append((s['b0'] + 1.0, h))
            s['b0'] = None
    for s in st.values():      # still "on break" after 3 hours: back on the clock an hour after it started
        if s['b0'] is not None and now_h - s['b0'] > LONG: s['br'].append((s['b0'], s['b0'] + 1.0)); s['in'] = s['b0'] + 1.0; s['b0'] = None
        elif s['b0'] is not None: s['br'].append((s['b0'], now_h))
    rota = rota or {}
    lens = sorted(b - a for v in rota.values() for a, b in v['plan']); typical = lens[len(lens) // 2] if lens else 8.0
    rk = {}
    for kname in rota:
        rk[kname] = kname; w = kname.split()
        if len(w) > 1: rk.setdefault(w[0] + ' ' + w[-1], kname)
    used = set(); off = 0.0
    for name, s in st.items():
        w = nkey(name).split(); key = rk.get(' '.join(w)) or (rk.get(w[0] + ' ' + w[-1]) if len(w) > 1 else None)
        r = rota.get(key) if key else None
        if key: used.add(key)
        worked = [(a, min(b, now_h)) for a, b in (r['worked'] if r else []) if a < now_h]
        if worked:
            last = max(b for a, b in worked)
            mine = _minus(worked, s['br']); by_worked += 1
            if s['in'] is not None and s['in'] >= last - 0.01:            # back on for a later shift, still open
                end = min(now_h, max([b for a, b in r['plan'] if a - 3 <= s['in'] <= b] + [s['in']])) if r['plan'] else min(now_h, s['in'] + typical)
                if end > s['in']: mine.append((s['in'], end))
                on += end >= now_h
            iv += mine; continue
        if not r and s['in'] is None: off += sum(max(0.0, b - a) for a, b in s['iv']); continue      # clocked out on the till and Kobas holds no shift here for them (another site's staff): not this site's hours
        mine = list(s['iv'])
        if s['in'] is not None:
            ends = [b for a, b in r['plan'] if a - 3 <= s['first'] <= b] if r else []
            if ends: end = min(now_h, max(max(ends), s['in'])); by_rota += end < now_h
            else: end = min(now_h, s['first'] + typical); by_len += end < now_h
            mine.append((s['in'], end)); on += end >= now_h
        iv += mine
    for key, r in rota.items():                                           # worked per the rota, never clocked in on the till
        if key in used: continue
        worked = [(a, min(b, now_h)) for a, b in r['worked'] if a < now_h]
        if worked: iv += worked; by_worked += 1
    hrs = sum(max(0.0, b - a) for a, b in iv)
    # 24/11/2026 (Michael: wage / revenue per hour): staff hours on shift inside each clock hour
    per = {}
    for a, b in iv:
        for hr in range(int(a), int(b) + 1):
            ov = min(b, hr + 1) - max(a, hr)
            if ov > 0: per[hr] = per.get(hr, 0.0) + ov
    return round(hrs, 2), on, len(st), by_rota, by_len, per, by_worked, round(off, 2)


DEPTS = ('FrontofHouse', 'BackofHouse', 'Management', 'norole')
def hours_worked(k, vid, rid, day, own, detail=None):
    """Rotas > Hours Worked (m=fullhours), the route the nightly uses (kobas_weekly/pull.py): hours of the shifts worked AT this
    venue on the day, all departments. None when Kobas has nothing for the day yet."""
    tot, seen, by = 0.0, 0, {}
    for dep in DEPTS:
        t = k.s.post(BASE + f'/rotas/index.php?m=fullhours&iRotaID={rid}&venueid={vid}', data={'department': dep}, timeout=120).text
        if not re.search(r'<option[^>]*value="%s"[^>]*selected' % dep, t): raise RuntimeError('department filter not applied')
        for m in re.finditer(r'<td[^>]*class="staff_\d+_day_(\d)"[^>]*>(.*?)(?=<td|</tr>)', t, re.S):
            if int(m.group(1)) - 1 != day.weekday(): continue
            for sh in re.findall(r'<div[^>]*>(.*?)</div>', m.group(2), re.S):
                h = re.search(r'</a>\s*<br\s*/?>\s*(\d+)h(?:&nbsp;|\s)*(\d+)m', sh); lm = re.search(r'<strong[^>]*>(.*?)</strong>', sh, re.S)
                if not h: continue
                lab = txt(lm.group(1)) if lm else ''
                if own and lab and lab != own: continue
                hh_ = int(h.group(1)) + int(h.group(2)) / 60.0; tot += hh_; seen += 1; by[dep] = by.get(dep, 0.0) + hh_
                if detail is not None: detail.append([dep[:3], int(h.group(1)) * 60 + int(h.group(2)), ' '.join(re.findall(r'\d{1,2}:\d{2}', txt(sh)))])
    return (round(tot, 2), by) if seen else (None, {})


def cash_log(k, vid, day):
    """Cash Log for the day (exists once the site has cashed up): {'group:name': value}."""
    j = k.s.get(BASE + '/data/reports/cash-log', params=[('venueIds[]', str(vid)), ('fromDate', day.isoformat()), ('toDate', day.isoformat())], timeout=120).json()
    out = {}
    for v in j.get('venues', []):
        for g, lst in (v.get('data') or {}).items():
            for row in lst if isinstance(lst, list) else []:
                val = row.get(day.isoformat())
                try: out[f"{g}:{str(row.get('name', '')).strip()}"] = float(str(val).replace(',', ''))
                except (TypeError, ValueError): pass
    return out


def cost_per_hour(site, day):
    """Hours Worked Cost / Hours Worked over the last completed week in data/kobas (the nightly Kobas pull), plus the FOH and BOH
    rates of that week (26/11/2026: a finished day prices its FOH and BOH hours separately)."""
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'kobas', 'wc_*.json')), reverse=True):
        wc = os.path.basename(f)[3:13]
        if wc > (day - datetime.timedelta(7 + day.weekday())).isoformat(): continue
        try: D = (json.load(open(f))['sites'].get(site) or {}).get('days') or {}
        except Exception: continue
        c = h = cf = hf = cb = hb = 0.0
        for d in D.values():
            lab = (d or {}).get('labour') or {}      # a day the site did not trade is null in the weekly file
            if lab.get('hours_worked_cost') and lab.get('hours'): c += lab['hours_worked_cost']; h += lab['hours']
            if lab.get('foh') and lab.get('hours_foh'): cf += lab['foh']; hf += lab['hours_foh']
            if lab.get('boh') and lab.get('hours_boh'): cb += lab['boh']; hb += lab['hours_boh']
        if h > 0: return round(c / h, 2), wc, {'FrontofHouse': cf / hf if hf else None, 'BackofHouse': cb / hb if hb else None}
    return None, None, {}


def kobas_actual(site, day):
    """The day's labour from the nightly Kobas pull (data/kobas), once it has run: (Hours Worked Cost, hours). This is the cash
    up's own labour figure."""
    mon = day - datetime.timedelta(day.weekday())
    try:
        lab = ((json.load(open(os.path.join(ROOT, 'data', 'kobas', f'wc_{mon.isoformat()}.json')))['sites'].get(site) or {}).get('days') or {}).get(day.isoformat()) or {}
        lab = lab.get('labour') or {}
        if lab.get('hours_worked_cost') and lab.get('hours'): return lab['hours_worked_cost'], lab['hours']
    except Exception: pass
    return None, None


def day_target(site, day):
    try: return (json.load(open(os.path.join(ROOT, 'site_cc', 'data', site, 'labour.json'))).get('open') or {}).get('tgt', {}).get(day.isoformat())
    except Exception: return None


def dbg_block(k, vid, day, rows, A, T, closed):
    """LIVE_DEBUG only: aggregates to reconcile against the cash up. No names, no item text."""
    d = {}
    mr, mo = {}, {}
    for x in rows:
        key = x['mode'] + ('|staff' if x['staff'] else '')
        mr[key] = round(mr.get(key, 0.0) + x['rev'], 2); mo.setdefault(key, set()).add(x['order'])
    d['mode_rev'] = mr; d['mode_orders'] = {a: len(b) for a, b in mo.items()}
    tr = {}
    for x in rows: tr[x['tt']] = round(tr.get(x['tt'], 0.0) + x['rev'], 2)
    d['tt_rev'] = tr; d['totals'] = T
    op = [x for x in rows if x['eat'] and not x['staff'] and not x['closed']]
    d['open'] = {'rev': round(sum(x['rev'] for x in op), 2), 'untied_orders': len({x['order'] for x in op if not x['tid']}),
                 'untied_rev': round(sum(x['rev'] for x in op if not x['tid']), 2), 'tied_open_tabs': len({x['tid'] for x in op if x['tid']}),
                 'tied_open_rev': round(sum(x['rev'] for x in op if x['tid']), 2), 'last_times': sorted({x['time'][:5] for x in op})[-12:]}
    noneat = {}
    for x in rows:
        if not x['eat'] and not x['staff']:
            kk = (x['mode'], 'deliveroo' if re.match(r'deliveroo', x['src'], re.I) else 'till', x['order'])
            noneat[kk] = round(noneat.get(kk, 0.0) + x['rev'], 2)
    d['noneat_orders'] = [[a[0], a[1], v] for a, v in noneat.items()]
    if A is not None:
        acts = {}
        for e in A: acts[e['act'] + ':' + e['obj']] = acts.get(e['act'] + ':' + e['obj'], 0) + 1
        d['audit_acts'] = acts
        ev = {}
        for e in A:
            if e['obj'] == 'user' and e['act'] in ('clockin', 'clockout', 'breakstart', 'breakend'):
                ev.setdefault(e['staff'], []).append(e['act'][:6] + '@' + e['ts'][8:16])
        try:
            mon = day - datetime.timedelta(day.weekday())
            R = k.s.get(BASE + '/data/rota/past', params={'include-current-week': 1}, timeout=120).json()
            rid = next((x['id'] for x in R if x['venueid'] == vid and str(x['rotadate'])[:10] == mon.isoformat()), None)
            t = k.s.get(BASE + '/rotas/index.php', params={'m': 'full', 'iRotaID': rid, 'venueid': vid, 'rotashow': f'V_{vid}'}, timeout=120).text
            rota = {}
            for seg in t.split('<tr')[1:]:
                if 'class="align-left"' not in seg: continue
                c = re.split(r'<td\b[^>]*>', seg)[1:]
                if len(c) < 8: continue
                nm = re.search(r'<a[^>]*>(.*?)</a>', c[0], re.S)
                if not nm: continue
                cell = c[1 + day.weekday()]
                it = [txt(i) for i in re.findall(r'<i>(.*?)</i>', cell, re.S)]
                plan = re.findall(r'\d{1,2}:\d{2}\s*to\s*\d{1,2}:\d{2}', re.sub(r'<i>.*?</i>', ' ', cell, flags=re.S))
                st = re.findall(r'<strong>(.*?)</strong>', cell, re.S)
                if plan or it: rota[nkey(txt(nm.group(1)))] = {'plan': plan, 'worked': it, 'venue': [txt(v)[:20] for v in st]}
            ppl = []; used = set()
            for name, e in ev.items():
                w = nkey(name).split(); key = ' '.join(w)
                if key not in rota and len(w) > 1:
                    key = next((r for r in rota if r.split()[0] == w[0] and r.split()[-1] == w[-1]), key)
                used.add(key); ppl.append({'ev': e, 'rota': rota.get(key)})
            for r, v in rota.items():
                if r not in used: ppl.append({'ev': None, 'rota': v})
            d['people'] = ppl
        except Exception as e: d['people_err'] = repr(e)[:200]
    return d


def build(site, day, now, k, vnames=None):
    vid = V[site]; flags = []; final = day < now.date()
    o = {'site': site, 'day': day.isoformat(), 'asof': now.isoformat(timespec='minutes'), 'final': final, 'flags': flags}
    r = k.s.post(BASE + '/reports/index.php', data={'s_day': f'{day.day:02d}', 's_month': f'{day.month:02d}', 's_year': str(day.year), 'venueid1': str(vid),
                 'm': 'CORE_Reports_DailySalesByOrder', 'v': '1', 'submit': ' View '}, timeout=120)
    rows = parse_orders(r.text) if r.status_code == 200 else None
    if not rows:      # structure only, never row text (the repo is public)
        i = r.text.find('rollover'); print('DEBUG by-order', site, r.status_code, len(r.text), 'rollover at', i, '|', re.sub(r'>[^<]+<', '>#<', r.text[max(0, i - 200):i + 1800].split('<script')[0]).replace('\n', ' ')[:2000], file=sys.stderr)
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
    covers = None; T = None
    try:
        T = k.s.get(BASE + '/data/report/group-sales/totals', params={'start_date': day.isoformat(), 'end_date': day.isoformat(), 'venue_id': vid}, timeout=120).json()
        covers = int(round(T['covers']['eatin']['total'] + (T['covers'].get('takeaway') or {}).get('total', 0)))      # 26/11/2026: the cash up counts takeaway covers too
    except Exception as e: flags.append(f'Sales Breakdown covers missing ({e})')

    cov_src = 'sales breakdown'; CLg = {}
    if final:      # the Cash Log (once cashed up) is the cash up's covers: covers + tabs without covers set (kobas_weekly/build.py)
        try:
            CLg = cash_log(k, vid, day); kc = CLg.get('covers:Covers')
            if kc: covers = int(round(kc + (CLg.get('tabsWithoutCoversSet:Tabs Without Covers Set') or 0) + round((CLg.get('otherPaymentTypes:of which Stripe') or 0) / 22.0))); cov_src = 'cash log'
        except Exception as e: flags.append(f'Cash Log not readable ({repr(e)[:60]}): covers from the Sales Breakdown')
    # 26/11/2026: the cash up's sales are Kobas NET x 1.2 per consumption mode (kobas_weekly/build.py). Zero rated takeaway and
    # delivery lines make that a little more than the till's gross, so each mode is scaled by its own net x 1.2 / gross.
    vf = {'eat in': 1.0, 'takeaway': 1.0, 'delivery': 1.0}
    try:
        for mk, tk in (('eat in', 'eatin'), ('takeaway', 'takeaway'), ('delivery', 'delivery')):
            g_, n_ = T['sales'][tk]['gross'], T['sales'][tk]['net_value']
            if g_ and n_ and 0.95 <= n_ * 1.2 / g_ <= 1.25: vf[mk] = n_ * 1.2 / g_
    except Exception: flags.append('Sales Breakdown net sales missing: sales shown at till gross, not the cash up basis')
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
        x['eat'] = x['mode'] == 'eat in'; x['take'] = x['mode'] == 'takeaway'
        x['staff'] = bool(re.search(r'staff', x['tab'] + ' ' + x['tt'], re.I))
        x['closed'] = True if final else ((x['tid'] in closed) if (x['eat'] and A is not None) else (not x['eat']))       # delivery / takeaway has no table to close; a finished day counts every order
        for u, rx in UPS.items(): x[u] = bool(re.search(rx, x['item'], re.I))
    if nocat: flags.append('No Kobas category for: ' + ', '.join(sorted(nocat)[:8]))
    unmapped = len({x['order'] for x in rows if x['eat'] and not x['tid']}) if A is not None else 0
    if unmapped and not final: flags.append(f'{unmapped} eat in orders could not be tied to a table: counted as open')

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
    rev_closed_eat = round(sum(x['rev'] for x in EC) * vf['eat in'], 2)
    rev_take = round(sum(x['rev'] for x in rows if x['take'] and not x['staff']) * vf['takeaway'], 2)
    rev_sit = round(rev_closed_eat + rev_take, 2)      # 26/11/2026: sit in = eat in + takeaway, the cash up basis
    rev_closed_all = round(rev_closed_eat + rev_take + sum(x['rev'] for x in rows if not x['eat'] and not x['take'] and not x['staff']) * vf['delivery'], 2)
    per100 = (lambda n: round(100.0 * n / covers, 1)) if covers else (lambda n: None)
    uc = units(EC); pc = pair(EC)
    ok = A is not None or final
    sales_src = 'till, cash up basis'
    if final:      # 27/11/2026: once the site has cashed up, the Cash Log's own net sales x 1.2 ARE the cash up (it also carries refunds the till lines do not)
        ce, ct, cd = (CLg.get('expectedNetPaymentsConsumptions:of which ' + n) for n in ('Eat-in sales', 'Takeaway sales', 'Delivery sales'))
        ct, cd = ct or 0.0, cd or 0.0      # a mode with no sales is blank in the Cash Log
        if ce is not None and (ce + ct + cd) > 0:
            rev_take = round(ct * 1.2, 2); rev_sit = round((ce + ct) * 1.2, 2); rev_closed_all = round((ce + ct + cd) * 1.2, 2); sales_src = 'cash log'
    o['closed'] = {'eat_in_sales': rev_sit if ok else None, 'takeaway_sales': rev_take, 'all_sales': rev_closed_all if ok else None, 'sales_source': sales_src, 'covers': covers, 'covers_source': cov_src,
                   'sph': round(rev_sit / covers, 2) if (covers and ok) else None, 'tables': len(bills(EC)),
                   'upsell_per_100_covers': {u: per100(n) for u, n in uc.items()}, 'sushi_per_100_covers': per100(pc['sushi']), 'ramen_per_100_covers': per100(pc['bowls'])}
    o['open_tables'] = len(bills([x for x in E if not x['closed']])) if ok else None
    o['rung'] = {'upsell': units(E), 'pair': pair(E)}
    tgt = day_target(site, day); o['target'] = tgt
    if tgt is None: flags.append('No day sales target in site_cc/data/%s/labour.json' % site)
    close_h = 23.0; now_h = now.hour + now.minute / 60.0
    if tgt is not None and ok:
        left = round(max(0.0, tgt - rev_closed_all), 2); hrs_left = max(0.0, close_h - max(now_h, 11.0))
        o['to_target'] = {'left': left, 'per_hour': round(left / hrs_left, 0) if (left and hrs_left >= 0.25) else (0 if not left else None), 'pct': round(100.0 * rev_closed_all / tgt, 0) if tgt else None}
    H = {}
    for x in E:
        h = H.setdefault(x['time'][:2], {'h': x['time'][:2], 'still': 0, 'spark': 0, 'eda': 0, 'kim': 0, 'bowls': 0, 'sushi': 0, 'sales_closed': 0.0})
        for u in UPS: h[u] += x[u]
        h['bowls'] += x['ramen']; h['sushi'] += x['sushi']
        if x['closed']: h['sales_closed'] = round(h['sales_closed'] + x['rev'], 2)
    HA = {}   # closed sales of every kind (eat in closed tables + delivery and takeaway) by the hour rung: the wage % basis
    for x in rows:
        if x['closed'] and not x['staff']: HA[x['time'][:2]] = round(HA.get(x['time'][:2], 0.0) + x['rev'], 2)
    S = {}
    for x in E: S.setdefault(initials(re.sub(r'\s+-\s+till.*$', '', x['src'], flags=re.I)), []).append(x)
    o['servers'] = sorted(({'i': i, **units(X), **{kk: vv for kk, vv in pair(X).items() if kk != 'bills'}, 'bills': len(bills(X))} for i, X in S.items()), key=lambda s: -s['bills'])
    if A is not None:
        rid = None
        try: rota, rid = rota_today(k, vid, day)
        except Exception as e: rota = None; flags.append(f'Rota not readable ({e}): a missed clock out is held to 8 hours')
        hrs, on, seen, by_rota, by_len, per_h, by_worked, off_rota = clock_hours(A, now_h if day == now.date() else 30.0, rota); rate, wc, drate = cost_per_hour(site, day)
        hsrc = 'clock ins and rota'; model = hrs; dcost = None; act_c, act_h = kobas_actual(site, day) if (final and not os.environ.get('LIVE_NO_ACTUAL')) else (None, None)
        if final and rid:      # the day is over: Kobas's own hours worked, the figure behind the cash up
            try:
                _det = []; hw, hby = hours_worked(k, vid, rid, day, (vnames or {}).get(vid), _det); o['_fh'] = _det
                if hw and hw >= 0.6 * hrs:
                    hrs = hw; hsrc = 'hours worked'
                    if rate: dcost = round(sum(h_ * (drate.get(dep) or rate) for dep, h_ in hby.items()), 2)
                elif hw: flags.append(f'Hours Worked not complete yet ({hw} h against {hrs} h clocked): estimate kept')
            except Exception as e: flags.append(f'Hours Worked not readable ({repr(e)[:60]}): estimate kept')
        if rate is None: flags.append('No cost per hour in data/kobas for the last completed week: wage % estimate not possible')
        cost = dcost if dcost is not None else (round(hrs * rate, 2) if rate else None); est = True; csrc = 'hours x cost per hour last week'
        if act_c: cost, hrs, est, csrc, hsrc = round(act_c, 2), act_h, False, 'kobas labour costs', 'kobas labour costs'      # the nightly has the day: the cash up figure itself
        o['wage_est'] = {'hours_clocked': hrs, 'hours_source': hsrc, 'hours_model': model, 'hours_off_rota': off_rota, 'on_shift_now': 0 if final else on, 'people_clocked': seen,
                         'closed_at_rota_finish': by_rota, 'closed_at_typical_length': by_len, 'from_rota_worked': by_worked, 'on_rota_today': len(rota) if rota is not None else None,
                         'cost_per_hour': rate, 'rate_week': wc, 'cost': cost, 'cost_source': csrc,
                         'pct': round(100.0 * cost / rev_closed_all, 2 if final else 1) if (cost and rev_closed_all > 0) else None, 'estimate': est}
        # per hour, trading hours only (11:00 on): staff hours on shift x cost per hour against the closed sales rung in that hour
        last_h = 23 if day != now.date() else min(23, now.hour)
        for hr in range(11, last_h + 1):
            kk = f'{hr:02d}'
            if kk not in H and per_h.get(hr): H[kk] = {'h': kk, 'still': 0, 'spark': 0, 'eda': 0, 'kim': 0, 'bowls': 0, 'sushi': 0, 'sales_closed': 0.0}
        for kk, h in H.items():
            sh = per_h.get(int(kk)); sa = HA.get(kk, 0.0)
            h['staff_h'] = round(sh, 2) if sh else 0; h['sales_all_closed'] = sa
            h['wage_cost'] = round(sh * rate, 2) if (sh and rate) else None
            h['wage_pct'] = round(100.0 * sh * rate / sa, 1) if (sh and rate and sa > 0) else None
    o['hours'] = [H[h] for h in sorted(H)]
    fh = o.pop('_fh', None)
    if os.environ.get('LIVE_DEBUG'): o['dbg'] = dbg_block(k, vid, day, rows, A, T, closed); o['dbg']['fullhours'] = fh
    return o


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    now = datetime.datetime.now(UK).replace(tzinfo=None)
    # 26/11/2026 (Michael: last pull at midnight): a run before 10:00 UK is the final pull of yesterday
    day = datetime.date.fromisoformat(os.environ['DAY']) if os.environ.get('DAY') else (now.date() if now.hour >= 10 else now.date() - datetime.timedelta(1))
    final = day < now.date()
    sites = [s.strip() for s in (os.environ.get('LIVE_SITES') or 'M18,M11').split(',') if s.strip()]
    sites = [s for s in sites if (s in V and s not in FRANCHISE) or print('skip', s, '(not a corporate site in sitemap)', file=sys.stderr)]
    k = Kobas()
    if not k.login(): print('LOGIN FAILED', file=sys.stderr); sys.exit(30)
    vnames = {}
    if final:
        try:
            vj = k.s.get(BASE + '/data/venue', timeout=120).json(); vj = vj.get('data', vj) if isinstance(vj, dict) else vj
            vnames = {int(x['id']): str(x.get('name', '')).strip() for x in vj if isinstance(x, dict) and x.get('id') is not None}
        except Exception as e: print('venue names not readable', repr(e)[:120], file=sys.stderr)
    bad = 0; O = {}
    def one(s):
        t0 = datetime.datetime.now()
        try: o = build(s, day, now, k, vnames); print('took', s, round((datetime.datetime.now() - t0).total_seconds(), 1), 's', file=sys.stderr); return s, o
        except Exception as e: print('ERR', s, repr(e)[:300], file=sys.stderr); return s, None
    if final:      # a finished day reads Hours Worked too (4 pages a site): 4 sites at a time, as the nightly does, to stay inside the job's time limit
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex: res = list(ex.map(one, sites))
    else: res = [one(s) for s in sites]
    for s, o in res:
        if o is None: bad += 1
        else: O[s] = o
    for s, o in O.items():
        json.dump(o, open(os.path.join(out, s + '.json'), 'w'), separators=(',', ':'))
        c = o['closed']; print(f"{s} {o['day']}{' FINAL' if o['final'] else ''} sit in {c['eat_in_sales']} all {c['all_sales']} covers {c['covers']} ({c['covers_source']}) sph {c['sph']} tables {c['tables']} open {o['open_tables']} "
                               f"rung {o['rung']['upsell']} pair {o['rung']['pair']} wage {o.get('wage_est')} flags {o['flags']}")
    sys.exit(1 if bad else 0)


if __name__ == '__main__': main()
