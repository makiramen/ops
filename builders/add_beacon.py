"""One-off: put the usage beacon on a page that is not written by a builder.
    python3 builders/add_beacon.py <file.html> "<Page name>"
Idempotent. Builders (site_cc/build.py, site_cc/pipeline/build_index.py, keyline/keyline_cloud_run.py) call
usage_beacon.inject themselves, so new pages from those never need this.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usage_beacon import inject, MARK

f, page = sys.argv[1], sys.argv[2]
s = open(f, encoding="utf-8").read()
t = inject(s, page)
if t == s:
    print("already present:", f)
else:
    open(f, "w", encoding="utf-8").write(t); print("beacon added:", f, "as", repr(page))
