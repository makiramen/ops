#!/usr/bin/env python3
"""patch_reviews_tab.py — adds the "Reviews" tab to the AM Control Centre shell (index.html).

  python3 patch_reviews_tab.py --in index.live.html --out index.patched.html [--summary-url data/reviews_summary.json]

Surgical and idempotent: three insertions, nothing else touched. Re-running on an already patched shell
is a no-op. The tab is an <iframe> onto reviews.html?embed=1&week=<selected week>, loaded the first time
the tab is opened (so the 3 MB reviews JSON never slows the Daily tab). The shell's week selector drives
the iframe (postMessage rv-week), the iframe reports its height back (rv-height). The badge reads the tiny
data/reviews_summary.json written by build_reviews_intel.py --summary.
Never hand-edit index.html; run this, then diff and count the changed lines before deploying.
"""
import argparse, sys, re
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--summary-url", default="data/reviews_summary.json")
a = ap.parse_args()
h = open(a.inp, encoding="utf-8").read()
MARK = 'data-tab="reviews"'
if MARK in h:
    print("already patched — no-op", file=sys.stderr); open(a.out, "w", encoding="utf-8").write(h); sys.exit(0)

# 1) tab button, placed BEFORE Budget Burn (Michael 25/08): Daily · This Week · Deliveroo RAG · Reviews · Budget Burn …
anchor = '<button class="tabbtn" data-tab="ecbudget">Budget Burn</button>'
assert h.count(anchor) == 1, "Budget Burn tab button not found exactly once"
btn = '<button class="tabbtn" data-tab="reviews">Reviews <span class="tb-badge" id="tb-reviews" style="display:none">0</span></button>\n    '
h = h.replace(anchor, btn + anchor)

# 2) the panel, inserted just before the Budget Burn panel comment
panel_anchor = '<!-- ============ TAB: BUDGET BURN'
i = h.find(panel_anchor)
assert i > 0, "Budget Burn panel comment not found"
panel = '''<!-- ============ TAB: REVIEWS INTELLIGENCE (Pipe 5c, added 25/08/2026 by patch_reviews_tab.py) ============ -->
  <div class="tabpanel" id="tab-reviews">
    <style>
      #tab-reviews .rv-frame { width:100%; border:0; display:block; min-height:900px; background:transparent; }
      #tab-reviews .rv-note { font-size:11.5px; color:var(--ink-3); margin:0 0 10px; display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
      #tab-reviews .rv-note a { color:var(--maki-orange); font-weight:700; text-decoration:none; }
    </style>
    <div class="rv-note"><span id="rv-status">Reviews Intelligence loads when you open this tab.</span><a href="reviews.html" target="_blank">Open full page ↗</a></div>
    <iframe class="rv-frame" id="rv-frame" title="Reviews Intelligence" loading="lazy"></iframe>
    <script>
    (function(){
      var frame = document.getElementById('rv-frame'), loaded = false;
      function wk(){ var s = document.getElementById('week-select'); return s && s.value ? s.value : ''; }
      function open_(){ if (loaded) return; loaded = true; frame.src = 'reviews.html?embed=1' + (wk() ? '&week=' + encodeURIComponent(wk()) : ''); document.getElementById('rv-status').textContent = 'Reviews Intelligence · week follows the selector above.'; }
      document.querySelectorAll('.tabbtn[data-tab="reviews"]').forEach(function(b){ b.addEventListener('click', open_); });
      var ws = document.getElementById('week-select'); if (ws) ws.addEventListener('change', function(){ if (loaded && frame.contentWindow) frame.contentWindow.postMessage({type:'rv-week', week: ws.value}, '*'); });
      window.addEventListener('message', function(e){ var d = e.data || {}; if (d.type === 'rv-height' && d.h) frame.style.height = (Math.max(900, d.h) + 20) + 'px'; if (d.type === 'rv-scrolltop') window.scrollTo({ top: 0, behavior: 'smooth' }); });
      fetch('SUMMARY_URL?cb=' + Date.now()).then(function(r){ return r.ok ? r.json() : null; }).then(function(s){
        if (!s) return; var b = document.getElementById('tb-reviews'); var n = (s.red_sites || 0) + (s.food_safety_mentions || 0);
        if (n > 0) { b.textContent = s.red_sites || s.food_safety_mentions; b.style.display = ''; b.title = (s.red_sites || 0) + ' red site(s), ' + (s.food_safety_mentions || 0) + ' food-safety mention(s), w/c ' + s.week; }
      }).catch(function(){});
    })();
    </script>
  </div>

  '''.replace('SUMMARY_URL', a.summary_url)
h = h[:i] + panel + h[i:]
open(a.out, "w", encoding="utf-8").write(h)
print("patched:", a.out, file=sys.stderr)
