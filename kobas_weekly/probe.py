"""Route map probe (11/11/2026): which Kobas reports carry stock-take variance and actual food cost %.
Writes plain-text dumps to the out folder; the workflow commits them to the kobas-probe branch (never main)."""
import os, re, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
def links(html):
    a = re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S)
    return sorted({(h, re.sub(r'<[^>]+>|\s+', ' ', t).strip()[:90]) for h, t in a})
def dataurls(html): return sorted(set(re.findall(r"""['"](/(?:data|api|reports|reporting|stock)/[^'"\s<>]{2,160})['"]""", html)))
# 1) the reports list and the stock menu
for n, u in [('reports_list', '/reports/list/'), ('stock_home', '/stock/'), ('stock_takes', '/stock/takes/'), ('stock_take2', '/stock/stock-take/'),
             ('stock_periods', '/stock/periods/'), ('home', '/dashboard/')]:
    try:
        p = k.s.get(BASE + u, timeout=60)
        save(f'page_{n}.txt', f'{p.status_code} {p.url}\n--links\n' + '\n'.join(f'{h} | {t}' for h, t in links(p.text)) + '\n--data\n' + '\n'.join(dataurls(p.text)))
    except Exception as e: save(f'page_{n}.txt', 'ERR ' + repr(e))
# 2) every report page linked from the list: its data urls + report keys mentioned
try:
    p = k.s.get(BASE + '/reports/list/', timeout=60)
    rep = [h for h, t in links(p.text) if h.startswith('/report') or 'Reports' in h or 'report' in h.lower()]
    lines = []
    for h in rep[:120]:
        try:
            q = k.s.get(BASE + h, timeout=60)
            keys = sorted(set(re.findall(r"report_key['\"]?\s*[:=]\s*['\"]([a-z_]+)['\"]", q.text)) | set(re.findall(r"['\"]([a-z_]+_report)['\"]", q.text)))
            lines.append(f'## {h} {q.status_code} keys={keys}\n  ' + '\n  '.join(dataurls(q.text)[:40]))
        except Exception as e: lines.append(f'## {h} ERR {e}')
    save('report_pages.txt', '\n'.join(lines))
except Exception as e: save('report_pages.txt', 'ERR ' + repr(e))
# 3) report-key oracle
cand = ['stock_variance_report', 'stock_variance', 'stock_take_report', 'stocktake_report', 'stock_take_variance_report', 'stock_period_report',
        'gross_profit_report', 'gp_report', 'cost_of_sales_report', 'actual_gp_report', 'theoretical_gp_report', 'stock_valuation_report',
        'stock_count_report', 'stock_take_summary_report', 'stock_summary_report', 'operational_profitability_report', 'stock_usage_report',
        'supplier_stock_deliveries_report', 'stock_purchases_report', 'purchases_report', 'stock_period_summary_report', 'variance_report',
        'stock_holding_report', 'stock_current_position_report', 'labour_costs_report', 'stock_take_variance', 'gp_variance_report',
        'stock_period_gp_report', 'sales_mix_report', 'stock_transfers_report', 'stock_closing_report', 'consumption_report']
ok = []
for kk in cand:
    try:
        r = k.s.get(BASE + '/data/report-queue', params={'filterBy[report_key][eq]': kk, 'limit': 3}, timeout=60)
        if 'Invalid report key' not in r.text: ok.append(f'{kk} {r.status_code} {r.text[:1500]}')
    except Exception as e: ok.append(f'{kk} ERR {e}')
save('report_keys_valid.txt', '\n\n'.join(ok) or 'none')
# 4) all recent queue entries, whatever key (shows which reports people actually run, eg Matt's food cost source)
try:
    r = k.s.get(BASE + '/data/report-queue', params={'limit': 300, 'orderBy[id]': 'DESC'}, timeout=90)
    j = r.json(); j = j if isinstance(j, list) else j.get('data', [])
    from collections import Counter
    c = Counter(x.get('report_key') for x in j)
    save('queue_recent.txt', json.dumps(c.most_common(), indent=0) + '\n\n' + '\n'.join(json.dumps(x)[:600] for x in j[:80]))
except Exception as e: save('queue_recent.txt', 'ERR ' + repr(e))
# 5) stock take data routes
for n, u in [('take_v2', '/data/v2/stock/take?limit=5&orderBy[id]=DESC'), ('take_v2b', '/data/v2/stock/stock-take?limit=5'),
             ('takes', '/data/stock/takes?limit=5'), ('take_v2c', '/data/v2/stock/stocktake?limit=5'), ('period_v2', '/data/v2/stock/period?limit=5'),
             ('count_v2', '/data/v2/stock/count?limit=5&orderBy[id]=DESC'), ('variance_v2', '/data/v2/stock/variance?limit=5')]:
    try:
        r = k.s.get(BASE + u, timeout=60); save(f'route_{n}.txt', f'{r.status_code} {r.headers.get("content-type","")}\n' + r.text[:12000])
    except Exception as e: save(f'route_{n}.txt', 'ERR ' + repr(e))
print('probe done', sorted(os.listdir(out)))
