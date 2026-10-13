"""Usage beacon for every published Maki page (13/10/2026).

Each page open posts one row to the Area Room log sheet (Who = page name, What = "viewed") through the same
Apps Script web app the Area Room gate uses, so Michael can see which dashboards are actually being opened.
Rows: When (UK time), Who, What, Device, Screen width. No names, no cookies, nothing in the repo but this snippet.

Rules
  * One row per browser per page per 30 minutes (localStorage), so a reload does not look like a new visit.
  * Never logs a local copy (file://) or an embedded frame (?embed=1), so AM CC tabs that iframe another page count once.
  * Fails silently: the dashboard never waits on it and never breaks because of it.

Every builder that writes a page calls inject(html, page_name) before writing; a page built outside a builder gets
the same call once (see builders/add_beacon.py). Idempotent: a page already carrying the marker is left alone.
"""
import os

LOG_URL = os.environ.get("GATE_LOG_URL", "https://script.google.com/macros/s/AKfycbyVrmiIOv3loHNtR-s6c_d5tfJKe8HXWfy29XdvKt3iz_uWJzK2Ul_89q9BMFYbWu2B/exec")
MARK = "<!-- maki usage beacon -->"

JS = (
    MARK + '<script>(function(){var P=__PAGE__,U=__URL__;try{'
    'if(location.protocol==="file:"||/[?&]embed=1/.test(location.search))return;'
    'var k="maki_seen_"+P,n=Date.now();if(+(localStorage.getItem(k)||0)>n-30*60e3)return;localStorage.setItem(k,n);'
    'fetch(U,{method:"POST",mode:"no-cors",headers:{"Content-Type":"text/plain"},keepalive:true,'
    'body:JSON.stringify({name:P,kind:"viewed",at:new Date(n).toISOString(),w:screen.width,ua:navigator.userAgent.slice(0,160)})}).catch(function(){})'
    '}catch(e){}})();</script>'
)


def snippet(page):
    import json
    return JS.replace("__PAGE__", json.dumps(page)).replace("__URL__", json.dumps(LOG_URL))


def inject(html, page):
    """Return html with the beacon just before </body> (or appended). No-op if already present."""
    if MARK in html:
        return html
    s = snippet(page) + "\n"
    i = html.rfind("</body>")
    return html[:i] + s + html[i:] if i >= 0 else html + "\n" + s
