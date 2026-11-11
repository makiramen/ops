"""Probe 9: Stock Usage Comparison report (CORE_Reports_UsageComparison): the form, then a run for M1 between its stock checks."""
import os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'keyline'))
from kobas_pull import Kobas, BASE
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
k = Kobas(); assert k.login(), 'login failed'
def save(n, t): open(os.path.join(out, n), 'w').write(t)
p = k.s.get(BASE + '/reports/index.php', params={'m': 'CORE_Reports_UsageComparison'}, timeout=90)
save('uc_form.html', f'{p.status_code} {p.url}\n' + p.text)
forms = re.findall(r'<form.*?</form>', p.text, re.S)
save('uc_forms.txt', '\n\n=====\n'.join(forms))
# also week on week sales as a reference of the same family
p2 = k.s.get(BASE + '/reports/index.php', params={'m': 'CORE_Reports_WeekonWeekSales'}, timeout=90)
save('wow_form.html', f'{p2.status_code}\n' + '\n\n'.join(re.findall(r'<form.*?</form>', p2.text, re.S)))
print('ok', len(forms))
