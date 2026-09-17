#!/usr/bin/env python3
"""keyline_cloud_run.py: the whole Keyline morning, offline, in one deterministic step (17 Sep 2026).

Runs inside a clone of github.com/makiramen/ops, from the keyline/ folder. Replaces the Mac-bound
Claude task: no Chrome, no saved password, no folder-access prompt, no permission classifier.

  cd keyline && python3 keyline_cloud_run.py [--no-pull] [--no-email] [--no-push] [--report /tmp/keyline_report.json]

The cycle, in order (the order is load-bearing, see README):
  1. kobas_pull.py           Kobas login, nine stock reports, orders and deliveries  -> pull.txt, part_orders.html
  2. build_data.py <ver>     pull.txt -> part_data.html
  3. build_asks.py prepare   part_asks.html = every ask day UP TO YESTERDAY (never today)
  4. cat (8 parts)           keyline-control.html
  5. render.py               verifies the page, stamps redSites into part_data, writes asks-<date>.json, mail.html
  6. cat again               so the stamped part_data is in the page
  7. build_asks.py commit    remembers today for tomorrow
  8. mkmail + compact + PDF  email-compact.html, keyline-<date>.pdf
  9. email                   Gmail SMTP to Sophie and O (GMAIL_USER / GMAIL_APP_PASSWORD), PDF attached
 10. wrap + commit + push    ../keyline.html (the ops site) plus the keyline/ state files

Exit codes: 0 shipped · 30 Kobas login failed (estate-blind email sent, nothing built) · 31/32 reports failed
(same) · 40 render failed · 20 built but not pushed · 2 a step died. The report JSON on stdout always says why.

Every timestamp the page or the email carries is Europe/London: the whole script runs with TZ forced to
Europe/London below, because part_c / part_e read the device clock and the ask timestamps must match the
cut-offs (naive UK wall clock, never toISOString).
"""
import argparse, datetime, json, os, re, subprocess, sys, time
os.environ['TZ'] = 'Europe/London'
try: time.tzset()
except AttributeError: pass
from zoneinfo import ZoneInfo
UK = ZoneInfo('Europe/London')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
PARTS = ['part_a.html', 'part_b.html', 'part_data.html', 'part_orders.html', 'part_asks.html', 'part_c.html', 'part_e.html', 'part_d.html']
TO = ['sophie@makiramen.com', 'srawut@makiramen.com']      # fixed, never changes, never a supplier or a site
OPS_URL = 'https://makiramen.github.io/ops/keyline.html'
STATE_FILES = ['part_data.html', 'part_orders.html', 'part_asks.html', 'asks-store.json', 'pull.txt']

def log(*a): print(*a, file=sys.stderr, flush=True)
def sh(cmd, check=True, env=None, cwd=None):
    r = subprocess.run(cmd, cwd=cwd or HERE, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        log('CMD FAILED:', ' '.join(cmd), '\n', r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit(2)
    return r

def version():
    m = re.search(r'"version":\s*"([\d.]+)"', open(os.path.join(HERE, 'part_data.html')).read())
    return os.environ.get('KEYLINE_VERSION') or (m.group(1) if m else '1.11.0')

def cat():
    with open(os.path.join(HERE, 'keyline-control.html'), 'w') as f:
        for p in PARTS: f.write(open(os.path.join(HERE, p)).read())

def wrap():
    """ops-site copy: a full document around the unwrapped build (same wrap as the README, built to a new file)."""
    s = open(os.path.join(HERE, 'keyline-control.html')).read()
    head = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
    s = s.replace('<title>Keyline Control</title>\n', '<title>Keyline Control</title></head><body>\n', 1)
    open(os.path.join(REPO, 'keyline.html'), 'w').write(head + s + '\n</body></html>\n')

def send_mail(subject, html, pdf_path, plain_fallback):
    import smtplib, ssl
    from email.message import EmailMessage
    user, pw = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pw): return 'NOT SENT: GMAIL_USER / GMAIL_APP_PASSWORD missing'
    m = EmailMessage()
    m['From'] = f'Keyline Control <{user}>'; m['To'] = ', '.join(TO); m['Subject'] = subject
    m.set_content(plain_fallback); m.add_alternative(html, subtype='html')
    if pdf_path and os.path.exists(pdf_path):
        m.add_attachment(open(pdf_path, 'rb').read(), maintype='application', subtype='pdf', filename=os.path.basename(pdf_path))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=60) as s:
        s.login(user, pw); s.send_message(m)
    return 'sent'

def estate_blind(a, R, why):
    """Kobas could not be pulled. Tell Sophie and O plainly, never an alarm dressed as stock."""
    now = datetime.datetime.now(UK)
    subj = 'Keyline: no Kobas pull today, estate blind'
    body = (f'<p>Morning both. Keyline could not pull the Kobas stock position at {now:%H:%M} UK ({why}). '
            f'No order guide today: follow the normal supplier routine and order to the PAR sheet. '
            f'The board at <a href="{OPS_URL}">{OPS_URL}</a> still shows the last pull, read the date on it.</p>')
    R['email'] = 'skipped (--no-email)' if a.no_email else send_mail(subj, body, None, re.sub('<[^>]+>', '', body))
    R['subject'] = subj

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-pull', action='store_true', help='build from the pull.txt / part_orders.html already in keyline/')
    ap.add_argument('--no-email', action='store_true'); ap.add_argument('--no-push', action='store_true')
    ap.add_argument('--report'); a = ap.parse_args()
    os.chdir(HERE)
    now = datetime.datetime.now(UK); day = now.strftime('%Y-%m-%d')
    R = {'run_at': now.strftime('%Y-%m-%dT%H:%M UK'), 'day': day, 'pull': None, 'counts': None, 'rag': None,
         'email': None, 'subject': None, 'commit': None, 'pushed': False, 'warnings': [], 'result': None}
    def finish(code):
        R['exit'] = code; R['result'] = R['result'] or f'exit {code}'
        if a.report: json.dump(R, open(a.report, 'w'), indent=1)
        print(json.dumps(R)); sys.exit(code)

    # 1. pull
    if not a.no_pull:
        r = sh([sys.executable, 'kobas_pull.py', '--out', '.', '--report', '/tmp/kobas_pull_report.json'], check=False)
        log(r.stderr[-3000:])
        try: R['pull'] = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception: R['pull'] = {'exit': r.returncode, 'raw': r.stdout[-500:]}
        code = r.returncode
        if code in (30, 31, 32):
            why = {30: 'Kobas login failed', 31: 'Kobas never generated the nine reports', 32: 'the report export failed'}[code]
            R['result'] = 'ESTATE BLIND: ' + why
            estate_blind(a, R, why); finish(code)
        if code == 33:
            R['warnings'].append('orders pull failed; page built on the previous orders file, On order and closure are stale')
    ver = version()

    # 2 to 7. build, verify, remember
    sh([sys.executable, 'build_data.py', ver])
    sh([sys.executable, 'build_asks.py', 'prepare'])
    cat()
    rr = sh([sys.executable, 'render.py'], check=False)
    log(rr.stdout[-3000:], rr.stderr[-2000:])
    if rr.returncode != 0 or 'errors []' not in rr.stdout:
        R['result'] = 'RENDER FAILED: ' + (rr.stdout + rr.stderr)[-400:]; R['warnings'].append('page did not render clean, nothing shipped, nothing emailed'); finish(40)
    m = re.search(r'^(\{.*?\}) (.*?) assumed', rr.stdout, re.M)
    if m:
        R['counts'] = json.loads(m.group(1)); R['rag'] = dict(x.split(':') for x in m.group(2).split())
    cat()
    sh([sys.executable, 'build_asks.py', 'commit', day])
    reds = [s for s, v in (R['rag'] or {}).items() if v == 'RED']; ambers = [s for s, v in (R['rag'] or {}).items() if v == 'AMBER']
    urgent = (R['counts'] or {}).get('URGENT', 0); order = (R['counts'] or {}).get('ORDER', 0)

    # 8. the email body and the PDF
    sh([sys.executable, 'mkmail.py'])                       # mail.html (+ a playwright PDF we replace below)
    open('email-body.html', 'w').write(open('mail.html').read())
    sh([sys.executable, 'compact_mail.py'])                 # email-compact.html
    label = re.search(r'"importedLabel": "([^"]+)"', open('part_data.html').read()).group(1)
    sh([sys.executable, 'make_rl2.py', f'{now:%d %b %Y}, {label}'])   # keyline-<date>.pdf, small, table based
    pdf = f'keyline-{day}.pdf'
    subj = f'Keyline: {urgent} urgent, {order} to order' + (' today' if order == 0 and now.weekday() >= 5 else '') + \
           (f' (red: {" ".join(reds)})' if reds else ' (no red sites)')
    weekend = ' No supplier cut-off falls on a weekend, so 0 to order is expected and the short lines are on watch.' if (order == 0 and now.weekday() >= 5) else ''
    intro = (f'<p style="margin:0 0 10px">Morning both. Red-light sites today: <b>{", ".join(reds) if reds else "none"}</b>'
             f'{(" (amber: " + ", ".join(ambers) + ")") if ambers else ""}. Live board: <a href="{OPS_URL}">{OPS_URL}</a>.{weekend}</p>')
    html = intro + open('email-compact.html').read()
    assert '—' not in html and '–' not in html, 'dash in the email body'
    R['subject'] = subj
    R['email'] = 'skipped (--no-email)' if a.no_email else send_mail(subj, html, pdf, re.sub('<[^>]+>', ' ', intro) + f'\nSee the attached PDF or {OPS_URL}')
    if R['email'] != 'sent' and not a.no_email: R['warnings'].append('email ' + str(R['email']))

    # 9. ship
    wrap()
    ship = ['keyline.html'] + ['keyline/' + f for f in STATE_FILES] + [f'keyline/asks-{day}.json', f'keyline/pull-{day}.txt', f'keyline/{pdf}']
    open(f'pull-{day}.txt', 'w').write(open('pull.txt').read())
    sh(['git', 'config', 'user.email', 'keyline@makiramen.com'], cwd=REPO); sh(['git', 'config', 'user.name', 'Keyline Control'], cwd=REPO)
    sh(['git', 'add', '--'] + ship, cwd=REPO)
    if not sh(['git', 'diff', '--cached', '--quiet'], check=False, cwd=REPO).returncode:
        R['result'] = 'nothing changed'; finish(0)
    head = f'Keyline daily refresh {now:%d %b %Y}: {urgent} urgent, {order} to order, red {" ".join(reds) or "none"}'
    body = f'Offline run (keyline_cloud_run.py). {label}. Email {R["email"]}. Files: {", ".join(ship)}'
    sh(['git', 'commit', '-q', '-m', head, '-m', body], cwd=REPO)
    R['commit'] = sh(['git', 'rev-parse', 'HEAD'], cwd=REPO).stdout.strip()
    if a.no_push: R['result'] = 'built and committed locally, --no-push'; finish(20)
    tok = os.environ.get('GH_TOKEN')
    if not tok: R['result'] = 'committed but NO GH_TOKEN, not pushed'; finish(20)
    env = dict(os.environ); env['GIT_TERMINAL_PROMPT'] = '0'
    url = f'https://x-access-token:{tok}@github.com/makiramen/ops.git'
    pr = subprocess.run(['git', 'push', url, 'HEAD:main'], cwd=REPO, capture_output=True, text=True, env=env)
    if pr.returncode != 0:
        subprocess.run(['git', 'fetch', url, 'main'], cwd=REPO, capture_output=True, env=env)
        rb = subprocess.run(['git', 'rebase', 'FETCH_HEAD'], cwd=REPO, capture_output=True, text=True, env=env)
        if rb.returncode == 0:
            pr = subprocess.run(['git', 'push', url, 'HEAD:main'], cwd=REPO, capture_output=True, text=True, env=env)
            R['commit'] = sh(['git', 'rev-parse', 'HEAD'], cwd=REPO).stdout.strip()
        else:
            subprocess.run(['git', 'rebase', '--abort'], cwd=REPO, capture_output=True)
        if pr.returncode != 0:
            R['result'] = 'PUSH FAILED: ' + (pr.stderr + pr.stdout).replace(tok, '***')[-500:]; finish(20)
    remote = subprocess.run(['git', 'ls-remote', url, 'refs/heads/main'], cwd=REPO, capture_output=True, text=True, env=env).stdout.split()
    R['pushed'] = bool(remote) and remote[0] == R['commit']
    R['result'] = ('SHIPPED ' + R['commit'][:7]) if R['pushed'] else 'push ok but remote HEAD differs, CHECK'
    finish(0)

if __name__ == '__main__':
    main()
