#!/usr/bin/env python3
"""Area Room (secret gate) builder.

Inputs (same folder):
  sites_weekly.json   South site weekly KPIs (from the AM CC all_sites_wc_*.json + Deliveroo rag_ops)
  b2b.xlsx            MR South England B2B Master Tracker (Lincoln), downloaded live from Drive each build; this file is the fallback copy
  vouchers.json       fallback for RR voucher redemptions per site (nightly reads the RR sheet live)
  cleanliness.json    optional, Lincoln's weekly walk round scores (not wired yet)
  deliveroo_daily.json  optional, Deliveroo daily ops (copy of makiramen/ops data/deliveroo_daily.json, or env DROO_DAILY=path)
  gate_template.html  page shell
Output:
  area_room.html      the gate page; all data AES-GCM encrypted with the gate password

Runs every morning on GitHub (.github/workflows/area-room.yml in makiramen/ops): 10:00 UK, or straight after the
AM CC daily tab lands if that is later. No Mac needed.

Logins and the B2B tracker id never sit in the public repo. They come from the AREA_ROOM_CONFIG GitHub secret,
{"users": {name: password}, "b2b_file_id": "..."}; on the Mac from area_room_config.json (or users.json) in this
folder, which is never pushed.
"""
import base64, datetime as dt, json, os, re, sys, collections
from zoneinfo import ZoneInfo
import openpyxl
import hashlib, hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HERE = os.path.dirname(os.path.abspath(__file__))
UK = ZoneInfo("Europe/London")


def _config():
    raw = os.environ.get("AREA_ROOM_CONFIG")
    if raw:
        return json.loads(raw)
    p = os.path.join(HERE, "area_room_config.json")
    if os.path.exists(p):
        return json.load(open(p))
    p = os.path.join(HERE, "users.json")
    return {"users": json.load(open(p))} if os.path.exists(p) else {}


CONFIG = _config()
ITER = 100000
LOG_URL = os.environ.get("GATE_LOG_URL", "https://script.google.com/macros/s/AKfycbyVrmiIOv3loHNtR-s6c_d5tfJKe8HXWfy29XdvKt3iz_uWJzK2Ul_89q9BMFYbWu2B/exec")  # Apps Script web app that writes each login to the Area Room log sheet
TODAY = dt.date.fromisoformat(os.environ.get("GATE_TODAY", dt.datetime.now(UK).date().isoformat()))

# Plan calendar (Month 1: Mon 12 Oct to Sun 8 Nov 2026)
PERIODS = [
    ("base", "Baseline", "2026-09-28", "2026-10-04"),
    ("w1", "Week 1", "2026-10-12", "2026-10-18"),
    ("w2", "Week 2", "2026-10-19", "2026-10-25"),
    ("w3", "Week 3", "2026-10-26", "2026-11-01"),
    ("w4", "Week 4", "2026-11-02", "2026-11-08"),
]
SITES = {
    "M18": {"name": "Soho", "region": "South", "lead": "Kaitlin", "droo": True},
    "MakiNori": {"name": "Maki Nori", "region": "South", "lead": "Kaitlin", "droo": False},
    "M19": {"name": "Shoreditch", "region": "South", "lead": "Lincoln and Kaitlin", "droo": True},
    "M17": {"name": "Lakeside", "region": "South", "lead": "Lincoln, Kei acting GM", "droo": True},
    "M20": {"name": "Southampton", "region": "South", "lead": "Lincoln", "droo": True},
    "O2": {"name": "The O2", "region": "South", "lead": "Lincoln (support)", "droo": True, "support": True},
}
GM_OVERRIDE = {"M19": "Lesley", "M20": "Diana"}  # confirmed by Michael 07/10/2026
DAILY_URL = "https://raw.githubusercontent.com/makiramen/ops/main/data/daily/"
TARGETS = {  # weekly site targets from the stabilisation plan (7 Oct 2026)
    "M18": {"labour": 25, "reviews": 40, "signups": 100},
    "MakiNori": {"labour": 35, "reviews": 30, "signups": None},
    "M19": {"labour": 25, "reviews": 40, "signups": 100},
    "M17": {"labour": 23, "reviews": 40, "signups": 100},
    "M20": {"labour": 24, "reviews": 40, "signups": 150},
}


def d(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v.strip())
        if m:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
    return None


def money(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.findall(r"\d+(?:\.\d+)?", v.replace(",", ""))
        if m:
            return float(m[0]) * (1000 if "k" in v.lower() and float(m[0]) < 100 else 1)
    return None


# ------------------------------------------------------------------ sites
def build_sites():
    sw = json.load(open(os.path.join(HERE, "sites_weekly.json")))["weeks"]
    if os.environ.get("OPS_DATA"):   # add any newer AM CC weeks straight from the repo data
        from refresh_sites_weekly import add_new_weeks
        add_new_weeks(sw, os.environ["OPS_DATA"])
    for wk in sw.values():
        for c, g in GM_OVERRIDE.items():
            if c in wk:
                wk[c]["gm"] = g
    weeks = sorted(sw)
    out = {"weeks_available": weeks, "by_week": sw}
    return out


# ------------------------------------------------------------------ B2B
SITE_TABS = {
    "Maki Ramen Soho": "Soho",
    "Maki Nori": "Maki Nori",
    "Maki Ramen Shoreditch": "Shoreditch",
    "Maki Ramen Lakeside": "Lakeside",
    "Maki Ramen Southampton": "Southampton",
}
LIVE = {"active", "complete"}
CONTACTED = {"contacted", "email sent", "no response", "follow up", "meeting booked", "negotiating", "close", "lost", "active", "complete"}
FROZEN_TABS = {"Lakeside": "Lakeside", "Soho": "Soho", "Shoreditch": "Shoreditch", "Southampton": "Southampton"}


B2B_FILE_ID = CONFIG.get("b2b_file_id", "")   # MR South England B2B Master Tracker.xlsx (Lincoln); id kept out of the public repo
B2B_URL = "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % B2B_FILE_ID


def _b2b_workbook():
    """Live from Drive first (file is link shared, reader), local b2b.xlsx as fallback. Returns (workbook, source) or (None, None)."""
    import io, urllib.request
    try:
        if not B2B_FILE_ID:
            raise RuntimeError("no b2b_file_id in the config")
        with urllib.request.urlopen(B2B_URL, timeout=60) as r:
            raw = r.read()
        if raw[:2] == b"PK":
            open(os.path.join(HERE, "b2b.xlsx"), "wb").write(raw)   # keep the last good copy
            return openpyxl.load_workbook(io.BytesIO(raw), data_only=True), "Drive, live"
        print("b2b download was not an xlsx, using local copy")
    except Exception as e:
        print("b2b download failed, using local copy:", e)
    p = os.path.join(HERE, "b2b.xlsx")
    if os.path.exists(p):
        return openpyxl.load_workbook(p, data_only=True), "local copy " + dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%d/%m/%Y %H:%M")
    return None, None


def build_b2b():
    wb, src = _b2b_workbook()
    if wb is None:
        c = os.environ.get("B2B_CACHE")
        return json.load(open(c)) if c and os.path.exists(c) else None
    leads = []
    for tab, site in SITE_TABS.items():
        ws = wb[tab]
        hdr = [c.value for c in ws[1]]
        ix = {h: i for i, h in enumerate(hdr) if h}
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r[0]:
                continue
            st = (str(r[ix["Status"]]).strip() if r[ix["Status"]] else "")
            leads.append({
                "site": site, "business": str(r[0]).strip(), "cat": r[ix["Category"]] or "",
                "status": st, "first": str(d(r[ix["First Contact"]]) or ""), "last": str(d(r[ix["Last Contact"]]) or ""),
                "next": str(d(r[ix["Next Follow-up"]]) or ""), "value": money(r[ix["Est. Monthly Value"]]),
                "offer": (str(r[ix["Outcome"]]) if r[ix["Outcome"]] not in (None, "") else ""),
                "priority": r[ix["Priority"]] or "",
            })
    # events
    events = []
    ws = wb["Events & Promos"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[1]:
            continue
        events.append({"name": str(r[1]).strip(), "type": r[2] or "", "site": r[3] or "", "date": str(d(r[4]) or (r[4] or "")),
                       "status": r[7] or "", "next": r[9] or ""})
    # student accommodation
    stud = []
    ws = wb["Student Accommodations"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[1]:
            continue
        stud.append({"building": r[1], "city": r[3], "site": r[7], "status": r[14] or "Not Contacted",
                     "last_stand": str(d(r[15]) or ""), "next_stand": str(d(r[16]) or ""),
                     "signups": r[17] if isinstance(r[17], (int, float)) else None,
                     "vouchers": r[18] if isinstance(r[18], (int, float)) else None})
    # catering
    cat = collections.Counter()
    ws = wb["Catering Orders"]
    cat_won = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[0]:
            continue
        cat[r[9] or "Not started"] += 1
        if (r[9] or "").lower() == "won":
            cat_won.append({"name": r[0], "hub": r[8], "date": str(d(r[10]) or "")})
    # frozen prospects
    frozen = {}
    for tab, site in FROZEN_TABS.items():
        ws = wb[tab]
        c = collections.Counter()
        neg = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r[0]:
                continue
            c[r[8] or "Not Contacted"] += 1
            if (r[8] or "").lower() == "negotiating":
                neg.append(r[0])
        frozen[site] = {"counts": dict(c), "negotiating": neg}

    def in_p(datestr, a, b):
        x = d(datestr)
        return x is not None and d(a) <= x <= d(b)

    kpi_periods = [("sep", "Sep", "2026-09-01", "2026-09-30")] + [(k, l, a, b) for k, l, a, b in PERIODS if k != "base"]
    k = {}
    for key, lab, a, b in kpi_periods:
        started = d(a) <= TODAY
        if not started:
            k[key] = None
            continue
        row = {}
        row["partnerships"] = sum(1 for l in leads if l["status"].lower() in LIVE and in_p(l["last"], a, b))
        row["stands"] = sum(1 for s in stud if in_p(s["last_stand"], a, b))
        su = [s["signups"] for s in stud if in_p(s["last_stand"], a, b) and s["signups"] is not None]
        row["signups_stands"] = sum(su) if su else None
        for site in ["Soho", "Maki Nori", "Shoreditch", "Lakeside", "Southampton"]:
            row["out_" + site] = sum(1 for l in leads if l["site"] == site and in_p(l["first"], a, b))
        row["paid_events"] = sum(1 for e in events if e["type"] not in ("Freshers Fair", "Site Promo") and str(e["status"]).lower() in ("confirmed", "booked", "complete") and in_p(e["date"], a, b)) \
            + sum(1 for c_ in cat_won if in_p(c_["date"], a, b))
        k[key] = row

    # pipeline snapshot by site
    snap = {}
    for site in ["Soho", "Maki Nori", "Shoreditch", "Lakeside", "Southampton"]:
        L = [l for l in leads if l["site"] == site]
        snap[site] = {
            "leads": len(L),
            "contacted": sum(1 for l in L if l["status"].lower() in CONTACTED),
            "live": sum(1 for l in L if l["status"].lower() in LIVE),
            "in_play": sum(1 for l in L if l["status"].lower() in ("meeting booked", "negotiating", "follow up")),
            "value": round(sum(l["value"] or 0 for l in L if l["status"].lower() in LIVE)),
            "overdue": sum(1 for l in L if l["next"] and d(l["next"]) < TODAY and l["status"].lower() not in LIVE | {"close", "lost"}),
            "no_follow": sum(1 for l in L if l["status"].lower() in ("contacted", "email sent", "no response") and l["last"] and (TODAY - d(l["last"])).days > 7),
        }
    live_list = sorted([l for l in leads if l["status"].lower() in LIVE], key=lambda l: l["last"] or "", reverse=True)
    centres = [l for l in leads if "shopping centre" in str(l["cat"]).lower() and l["site"] in ("Lakeside", "Southampton")]
    # Westquay sits in the Southampton tab with no status; keep it visible
    return {
        "kpi": k, "snap": snap, "live": live_list, "centres": centres, "events": events,
        "stud": {"total": len(stud), "london": sum(1 for s in stud if s["city"] == "London"),
                 "southampton": sum(1 for s in stud if s["city"] == "Southampton"),
                 "contacted": sum(1 for s in stud if s["status"] != "Not Contacted"),
                 "stands_done": sum(1 for s in stud if s["last_stand"])},
        "catering": {"counts": dict(cat), "won": cat_won, "total": sum(cat.values())},
        "frozen": frozen,
        "src": src,
        "dash_note": "Tracker dashboard counts only 'Complete'. Lakeside (8), Southampton (7) and Maki Nori (2) mark live partners as 'Active', so the dashboard under counts them. This page counts both.",
    }


def _get(name):
    """Repo checkout first (DAILY_DIR, on GitHub), then the live AM CC daily feed, then the local daily/ folder."""
    import urllib.request
    dd = os.environ.get("DAILY_DIR")
    if dd and os.path.exists(os.path.join(dd, name)):
        return json.load(open(os.path.join(dd, name)))
    try:
        with urllib.request.urlopen(DAILY_URL + name, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception:
        p = os.path.join(HERE, "daily", name)
        return json.load(open(p)) if os.path.exists(p) else None


def build_daily(days=7):
    idx = _get("daily_index.json")
    dates = sorted((idx or {}).get("dates", []), reverse=True)[:days]
    if not dates:
        dates = sorted([f[6:16] for f in os.listdir(os.path.join(HERE, "daily")) if f.startswith("daily_2")], reverse=True)[:days]
    out = {"dates": dates, "sites": {}, "reviews_latest": "none"}
    for d_ in dates:
        cu, rv = _get("daily_%s.json" % d_), _get("daily_reviews_%s.json" % d_)
        if rv and out["reviews_latest"] == "none":
            out["reviews_latest"] = d_   # newest day with a reviews file; the build marker carries it
        for c in ["M17", "M18", "M19", "M20", "MakiNori", "O2"]:
            row = {"day": (cu or {}).get("day") or dt.date.fromisoformat(d_).strftime("%A")}
            s = ((cu or {}).get("sites") or {}).get(c)
            if s:
                sa, lb = s.get("sales") or {}, s.get("labour") or {}
                row.update(sales=sa.get("actual"), target=sa.get("target"), vs=sa.get("vs_target_pct"), sit_in=sa.get("sit_in"),
                           delivery=sa.get("delivery"), covers=s.get("covers"), spend=s.get("avg_spend"),
                           wage=lb.get("wage_pct"), hours=lb.get("hours"), labour=lb.get("total"))
            r = ((rv or {}).get("sites") or {}).get(c)
            if r:
                day = r.get("day") or {}
                row.update(rev_n=day.get("n"), rev_avg=day.get("avg"), rev_neg=day.get("neg"))
                row["neg_list"] = [x for x in (r.get("reviews") or []) if (x.get("stars") or 5) <= 3 and str(x.get("date", ""))[:10] == d_]
                if d_ == dates[0]:
                    row["reviews"] = [x for x in (r.get("reviews") or []) if x.get("has_comment")][:40]
                    row["window"] = r.get("window")
            out["sites"].setdefault(c, {})[d_] = row
    return out


MAPAL_LOC = {"M18": "Maki Soho", "MakiNori": "Maki Nori", "M19": "Maki Shoreditch", "M17": "Maki Lakeside", "O2": "Maki O2 Arena"}  # Southampton is not on Mapal yet
MAPAL_SHEET = "1JgM5881gtBvjYeb_AgfQVuAi4hlJqqSWwbTyiLGdgQU"   # Mapal Weekly Compliance Tracker
RR_SHEET = "1BU8Shqe4PajaoUfqvEFY_KVcNNzAZ-BIMq5AE-xcvkE"      # RAMEN_ROYALTY (AUTO)
RR_VENUE = {"Lakeside Shopping Centre": "M17", "Old Compton St, Soho": "M18", "Shoreditch, London": "M19", "West Quay, Southampton": "M20", "The O2 Arena, London": "O2"}


def _sheet(sheet_id, rng):
    """Service account read (same secret as the Site CC nightly). None when not available."""
    info = os.environ.get("GOOGLE_SA_JSON")
    if not info:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as gbuild
        cred = service_account.Credentials.from_service_account_info(json.loads(info), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        return gbuild("sheets", "v4", credentials=cred, cache_discovery=False).spreadsheets().values().get(spreadsheetId=sheet_id, range=rng).execute().get("values", [])
    except Exception as e:
        print("sheet read failed", sheet_id, e)
        return None


def build_compliance():
    import csv
    rows = _sheet(MAPAL_SHEET, "A:K")
    if rows is None:
        p = os.path.join(HERE, "mapal_comp.csv")
        rows = list(csv.reader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
    inv = {v: k for k, v in MAPAL_LOC.items()}
    out = {}
    for r in rows[1:]:
        r = r + [""] * (11 - len(r))
        if r[2].strip().upper() != "SITE" or r[3].strip() not in inv:
            continue
        try:
            pct = float(r[4]) if r[4] != "" else None
        except ValueError:
            pct = None
        out.setdefault(inv[r[3].strip()], {})[r[0]] = {"pct": pct, "ontime": r[8] or None, "dev": r[9] or None, "flag": r[10] or ""}
    return out


def build_signups():
    """A sign up counts at the site of the member's first FINAL bill since launch (marketing's attribution)."""
    rows = _sheet(RR_SHEET, "'DAILY VISITS'!A:M")
    if rows is None:
        p = os.path.join(HERE, "signups.json")
        return json.load(open(p)) if os.path.exists(p) else None
    h = rows[0]; ix = {k: h.index(k) for k in ("date", "venue", "member_id", "status")}
    first = {}
    for r in rows[1:]:
        r = r + [""] * (len(h) - len(r))
        d_, v, m, st = r[ix["date"]][:10], r[ix["venue"]], r[ix["member_id"]], (r[ix["status"]] or "FINAL").upper()
        if not m or st != "FINAL":
            continue
        if m not in first or d_ < first[m][0]:
            first[m] = (d_, v)
    weekly, daily = {}, {}
    for d_, v in first.values():
        c = RR_VENUE.get(v)
        if not c:
            continue
        x = dt.date.fromisoformat(d_); wk = (x - dt.timedelta(days=x.weekday())).isoformat()
        weekly.setdefault(c, {}); weekly[c][wk] = weekly[c].get(wk, 0) + 1
        daily.setdefault(c, {}); daily[c][d_] = daily[c].get(d_, 0) + 1
    return {"src": "RAMEN_ROYALTY (AUTO), DAILY VISITS, first bill site", "pulled": TODAY.isoformat(), "weekly": weekly, "daily": daily}


# ------------------------------------------------------------------ Ramen Royalty voucher redemptions per site
# Trifft does not record the site a voucher is used at. Same method as Ramen_Royalty_Vouchers_Repeat_Visits_by_Site_2026-10-05.xlsx:
# each Klaviyo 'redeemed' event (COUPON EVENTS) is matched to a FINAL member bill (DAILY VISITS) placed 10 min before to 5 min after.
# Firm = the voucher's Klaviyo profile is tied to one member (learnt by elimination across that profile's redemptions, a member
# can only belong to one profile) and that member has a bill in the window. Best guess = otherwise the nearest unclaimed bill.
# KobasTest coupons excluded. Maki Nori is not on Ramen Royalty. Each site/day value is [vouchers, of which £5 welcome, of which firm].
V_BEFORE, V_AFTER = 10, 5


def _london_offset_min(day):
    """BST (UTC+1) from last Sun of March to last Sun of October 01:00 UTC."""
    y = int(day[:4])
    def last_sun(m):
        x = dt.date(y, m, 31)
        return x - dt.timedelta(days=(x.weekday() + 1) % 7)
    return 60 if last_sun(3).isoformat() <= day < last_sun(10).isoformat() else 0


def build_vouchers():
    import bisect
    ce = _sheet(RR_SHEET, "'COUPON EVENTS'!A:I")  # I = member_id (Klaviyo external_id, filled hourly by rrcmFill)
    dv = _sheet(RR_SHEET, "'DAILY VISITS'!A:M")
    if ce is None or dv is None:
        p = os.path.join(HERE, "vouchers.json")
        return json.load(open(p)) if os.path.exists(p) else None
    h = dv[0]; ix = {k: h.index(k) for k in ("date", "time_london", "venue", "member_id", "status")}
    bills = []
    for r in dv[1:]:
        r = r + [""] * (len(h) - len(r))
        day, tm, m = r[ix["date"]][:10], r[ix["time_london"]][:5], r[ix["member_id"]]
        if not m or not tm or (r[ix["status"]] or "FINAL").upper() != "FINAL":
            continue
        try:
            t = dt.datetime.fromisoformat(day + "T" + tm).replace(tzinfo=dt.timezone.utc).timestamp() / 60 - _london_offset_min(day)
        except ValueError:
            continue
        bills.append((t, m, r[ix["venue"]]))
    bills.sort()
    ts = [b[0] for b in bills]
    h = ce[0]; jx = {k: h.index(k) for k in ("event", "occurred_at", "coupon_name", "klaviyo_profile_id", "member_id") if k in h}
    reds, known = [], {}
    for r in ce[1:]:
        r = r + [""] * (len(h) - len(r))
        if r[jx["event"]] != "redeemed" or "kobastest" in r[jx["coupon_name"]].lower():
            continue
        try:
            t = dt.datetime.fromisoformat(r[jx["occurred_at"]].replace("Z", "+00:00")).timestamp() / 60
        except ValueError:
            continue
        i = bisect.bisect_left(ts, t - V_BEFORE)
        cands = []
        while i < len(bills) and bills[i][0] <= t + V_AFTER:
            cands.append(bills[i]); i += 1
        reds.append({"t": t, "p": r[jx["klaviyo_profile_id"]], "n": r[jx["coupon_name"]], "c": cands})
        mid = r[jx["member_id"]] if "member_id" in jx else ""
        if mid and mid != "none":
            known[r[jx["klaviyo_profile_id"]]] = mid
    # known profile -> member links first (COUPON EVENTS member_id), then learn the rest by elimination
    by_p = collections.defaultdict(list)
    for x in reds:
        by_p[x["p"]].append(x)
    link, owner = dict(known), {}
    for p_, m in known.items():
        owner.setdefault(m, p_)
    for _ in range(20):
        changed = False
        for p_, rs in by_p.items():
            if p_ in link:
                continue
            S = None
            for x in rs:
                ms = {b[1] for b in x["c"] if b[1] not in owner}
                if not ms:
                    continue
                if len(ms) == 1:
                    S = ms; break
                S = ms if S is None else (S & ms)
                if not S:
                    S = None; break
            if S and len(S) == 1:
                m = next(iter(S)); link[p_] = m; owner[m] = p_; changed = True
        if not changed:
            break
    inv = RR_VENUE
    daily, weekly, unmatched = {}, {}, 0
    for x in reds:
        near = lambda L: min(L, key=lambda b: abs(b[0] - x["t"]))
        b, firm = None, 0
        if x["p"] in link:
            L = [b_ for b_ in x["c"] if b_[1] == link[x["p"]]]
            if L:
                b, firm = near(L), 1
        if b is None:
            L = [b_ for b_ in x["c"] if b_[1] not in owner]
            if L:
                b = near(L)
        if b is None:
            unmatched += 1
            continue
        c = inv.get(b[2])
        if not c:
            continue
        utc = dt.datetime.fromtimestamp(x["t"] * 60, dt.timezone.utc)
        day = (utc + dt.timedelta(minutes=_london_offset_min(utc.date().isoformat()))).date()
        wk = (day - dt.timedelta(days=day.weekday())).isoformat()
        w5 = 1 if "£5 ramen" in x["n"].lower() else 0
        for M, k in ((daily, day.isoformat()), (weekly, wk)):
            o = M.setdefault(c, {}).setdefault(k, [0, 0, 0])
            o[0] += 1; o[1] += w5; o[2] += firm
    return {"src": "RAMEN_ROYALTY (AUTO), COUPON EVENTS matched to DAILY VISITS member bills", "pulled": TODAY.isoformat(),
            "unmatched": unmatched, "total": len(reds), "daily": daily, "weekly": weekly}


# ------------------------------------------------------------------ Deliveroo daily ops
# data/deliveroo_daily.json in makiramen/ops (written by the Site CC nightly, pull_deliveroo_daily.py, from the Deliveroo Daily Master
# sheet). Keyed by day then site code: [orders, prep min, AOD min, missing items %, cancellations, cancel %, rejections, prep red (1/0)].
# Area Room codes map to the sheet codes (The O2 is MAF3 on Deliveroo). Only the last 21 days travel into the page.
DROO_CODES = {"M17": "M17", "M18": "M18", "M19": "M19", "M20": "M20", "O2": "MAF3"}
DROO_FILE = os.environ.get("DROO_DAILY", os.path.join(HERE, "deliveroo_daily.json"))


def build_droo_daily():
    if not os.path.exists(DROO_FILE):
        return None
    src = json.load(open(DROO_FILE))
    lo = (TODAY - dt.timedelta(21)).isoformat()
    days = {}
    for day, sites in src.get("d", {}).items():
        if day < lo:
            continue
        row = {}
        for code, sheet_code in DROO_CODES.items():
            if sheet_code in sites:
                row[code] = sites[sheet_code]
        if row:
            days[day] = row
    weeks = {}
    for wc, sites in src.get("w", {}).items():
        row = {code: sites[sc] for code, sc in DROO_CODES.items() if sc in sites}
        if row:
            weeks[wc] = row
    return {"to": src.get("to"), "pulled": src.get("pulled"), "src": src.get("src"), "k": src.get("k"), "wk": src.get("wk"),
            "d": dict(sorted(days.items())), "w": dict(sorted(weeks.items()))}


def build():
    payload = {
        "built": dt.datetime.now(UK).strftime("%d/%m/%Y %H:%M"),
        "today": TODAY.isoformat(),
        "periods": PERIODS,
        "sites_meta": SITES,
        "targets": TARGETS,
        "sites": build_sites(),
        "b2b": build_b2b(),
        "daily": build_daily(),
        "signups": build_signups(),
        "vouchers": build_vouchers(),
        "compliance": build_compliance(),
        "clean": json.load(open(os.path.join(HERE, "cleanliness.json"))) if os.path.exists(os.path.join(HERE, "cleanliness.json")) else None,
        "droo_daily": build_droo_daily(),
    }
    raw = re.sub(r"\s*[\u2013\u2014]\s*", ", ", json.dumps(payload, separators=(",", ":"), default=str, ensure_ascii=False)).encode()
    # Per person logins (users.json, kept local, never pushed): the data is encrypted once with a random key,
    # and that key is wrapped separately for each person with a key derived from their own password.
    users = CONFIG.get("users")
    if not users:
        sys.exit("No logins: set the AREA_ROOM_CONFIG secret (or area_room_config.json / users.json on the Mac)")
    km, iv = os.urandom(64), os.urandom(16)
    ct = Cipher(algorithms.AES(km[:32]), modes.CTR(iv)).encryptor().update(raw)
    tag = hmac.new(km[32:], iv + ct, "sha256").digest()
    wrap = {}
    for name, pw in users.items():
        s_, i_ = os.urandom(16), os.urandom(16)
        ku = hashlib.pbkdf2_hmac("sha256", pw.strip().lower().encode(), s_, ITER, 64)
        wk = Cipher(algorithms.AES(ku[:32]), modes.CTR(i_)).encryptor().update(km)
        wrap[name] = {"s": base64.b64encode(s_).decode(), "i": base64.b64encode(i_).decode(), "k": base64.b64encode(wk).decode(),
                      "t": base64.b64encode(hmac.new(ku[32:], i_ + wk, "sha256").digest()).decode()}
    blob = {"n": ITER, "i": base64.b64encode(iv).decode(), "c": base64.b64encode(ct).decode(), "t": base64.b64encode(tag).decode(), "u": wrap}
    tpl = open(os.path.join(HERE, "gate_template.html"), encoding="utf-8").read()
    logo = base64.b64encode(open(os.path.join(HERE, "maki-logo1.png"), "rb").read()).decode()
    html = tpl.replace("__PURECRYPTO__", open(os.path.join(HERE, "purecrypto.js"), encoding="utf-8").read()).replace("__PAYLOAD__", json.dumps(blob)).replace("__LOGURL__", LOG_URL).replace("__LOGO__", logo)
    # marker the scheduler and the guard read: build day (UK) and the AM CC daily day it carries
    html = html.replace("<!doctype html>", "<!doctype html>\n<!-- area-room-built: %s daily:%s reviews:%s -->" % (TODAY.isoformat(), (payload["daily"]["dates"] or ["none"])[0], payload["daily"].get("reviews_latest", "none")), 1)
    out = os.environ.get("AREA_ROOM_OUT", os.path.join(HERE, "area_room.html"))
    open(out, "w", encoding="utf-8").write(html)
    if "--debug" in sys.argv:
        json.dump(payload, open(os.path.join(HERE, "_payload_debug.json"), "w"), indent=1, default=str)
    print("built", out, len(html), "bytes")


if __name__ == "__main__":
    build()
