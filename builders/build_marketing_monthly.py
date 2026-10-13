#!/usr/bin/env python3
"""build_marketing_monthly.py  --  data/marketing_monthly.json for the Marketing Hub (13/10/2026).

Feeds the Hub's Monthly tab (covers and sales by calendar month, estate and per site, vs the
previous month) and the Summary tab's footfall story (weekly covers back to May 2026).

SOURCES (both already in this repo, both already refreshed by existing pipes)
  data/daily/daily_YYYY-MM-DD.json   Pipe 8 cash-up, one file per trading day from 27/07/2026.
                                     Per site: covers, sales.actual, sales.sit_in, sales.delivery.
  data/all_sites_wc_YYYY-MM-DD.json  AM weekly refresh, one file per week from w/c 04/05/2026.
                                     Per site: kpis.covers.actual, kpis.sales.actual (sales from June).

RULES
  * A calendar day is DAILY-sourced when its daily file exists; otherwise WEEKLY-PRORATA: the week's
    site totals are spread evenly over the 7 days (week / 7 per day). A month's `basis` says which
    mix it got, and `days_daily` / `days_prorata` count them, so the page can label estimates.
  * Sales before June 2026 are unknown (the weekly files carry 0): emitted as null, never 0.
  * Nothing here decides which sites are "live"; a site simply has data on a day or it does not.
    `sites_with_data` per month is the count, so an opening (M21 21/08) or a closure shows itself.
  * Today is never built; the daily pipe only ships completed days (D = yesterday).

Run from the repo root (daily_cloud_run.py calls it after the cash-up build, failure-tolerant):
    python3 builders/build_marketing_monthly.py --repo .
"""
import argparse, calendar, datetime, glob, json, os, sys

def log(*a): print(*a, file=sys.stderr)

def load_sites_meta(repo):
    meta = {}
    p = os.path.join(repo, "site_cc", "sites.json")
    try:
        s = json.load(open(p))["sites"]
        for code, v in s.items():
            meta[code] = {"name": v.get("name") or code, "label": v.get("label") or code,
                          "cluster": v.get("cluster") or "", "venue": v.get("loyalty_venue") or v.get("name") or code}
    except Exception as e:
        log("sites.json unreadable, falling back to codes:", e)
    return meta

def read_daily(repo):
    """{iso: {code: [covers, sales, sit_in, delivery]}}"""
    out = {}
    for f in sorted(glob.glob(os.path.join(repo, "data", "daily", "daily_????-??-??.json"))):
        try: d = json.load(open(f))
        except Exception as e: log("skip", f, e); continue
        iso = d.get("date") or os.path.basename(f)[6:16]
        row = {}
        for code, s in (d.get("sites") or {}).items():
            sales = (s.get("sales") or {})
            cov = s.get("covers")
            act = sales.get("actual")
            if cov is None and act is None: continue
            row[code] = [cov or 0, act, sales.get("sit_in"), sales.get("delivery")]
        if row: out[iso] = row
    return out

def read_weekly(repo):
    """{monday_iso: {code: [covers, sales|None]}}"""
    out = {}
    for f in sorted(glob.glob(os.path.join(repo, "data", "all_sites_wc_????-??-??.json"))):
        try: d = json.load(open(f))
        except Exception as e: log("skip", f, e); continue
        wc = (d.get("week") or {}).get("commencing") or os.path.basename(f)[13:23]
        row = {}
        for code, s in (d.get("sites") or {}).items():
            k = s.get("kpis") or {}
            cov = (k.get("covers") or {}).get("actual")
            sal = (k.get("sales") or {}).get("actual")
            if cov is None and sal is None: continue
            row[code] = [cov or 0, (sal if sal else None)]   # weekly 0 sales = unknown, not zero
        if row: out[wc] = row
    return out

def month_iter(first, last):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        yield y, m
        m += 1
        if m == 13: y, m = y + 1, 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="data/marketing_monthly.json")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    meta = load_sites_meta(repo)
    daily = read_daily(repo)
    weekly = read_weekly(repo)
    if not daily and not weekly:
        log("no source data at all"); return 2

    # ---- per-day, per-site series: daily file wins, else weekly pro-rata ----
    day_rows = {}   # iso -> {code: {"c": covers, "s": sales|None, "basis": "daily"|"prorata"}}
    for wc, row in weekly.items():
        mon = datetime.date.fromisoformat(wc)
        for i in range(7):
            iso = (mon + datetime.timedelta(i)).isoformat()
            r = day_rows.setdefault(iso, {})
            for code, (cov, sal) in row.items():
                r[code] = {"c": cov / 7.0, "s": (sal / 7.0 if sal is not None else None), "basis": "prorata"}
    for iso, row in daily.items():
        r = day_rows.setdefault(iso, {})
        r.clear()   # a daily file is the whole truth for that day
        for code, (cov, act, sit, dlv) in row.items():
            r[code] = {"c": cov, "s": act, "sit": sit, "dlv": dlv, "basis": "daily"}
    if not day_rows: log("nothing to aggregate"); return 2
    all_days = sorted(day_rows)
    first, last = datetime.date.fromisoformat(all_days[0]), datetime.date.fromisoformat(all_days[-1])
    today_uk = datetime.datetime.now(datetime.timezone.utc).date()
    # never let pro-rata weekly rows extend past the last real day of data
    last = min(last, today_uk - datetime.timedelta(1))

    # ---- months ----
    months = []
    for y, m in month_iter(first, last):
        dim = calendar.monthrange(y, m)[1]
        sites = {}
        tot_c = 0.0; tot_s = 0.0; any_sales = False; sit = 0.0; dlv = 0.0; any_split = False
        days_daily = 0; days_prorata = 0; days_data = 0
        for d in range(1, dim + 1):
            dt = datetime.date(y, m, d)
            if dt > last: break
            r = day_rows.get(dt.isoformat())
            if not r: continue
            days_data += 1
            bases = {v["basis"] for v in r.values()}
            if "daily" in bases: days_daily += 1
            else: days_prorata += 1
            for code, v in r.items():
                s = sites.setdefault(code, {"covers": 0.0, "sales": 0.0, "sales_known": False, "days": 0})
                s["covers"] += v["c"]; s["days"] += 1
                tot_c += v["c"]
                if v["s"] is not None:
                    s["sales"] += v["s"]; s["sales_known"] = True; tot_s += v["s"]; any_sales = True
                if v.get("sit") is not None or v.get("dlv") is not None:
                    sit += v.get("sit") or 0; dlv += v.get("dlv") or 0; any_split = True
        if days_data == 0: continue
        for code, s in sites.items():
            s["covers"] = int(round(s["covers"]))
            s["sales"] = round(s["sales"], 2) if s["sales_known"] else None
            del s["sales_known"]
        basis = "daily" if days_prorata == 0 else ("weekly-prorata" if days_daily == 0 else "mixed")
        complete = (days_data == dim) and (datetime.date(y, m, dim) <= last)
        months.append({
            "m": f"{y:04d}-{m:02d}", "label": datetime.date(y, m, 1).strftime("%b %Y"),
            "days_in_month": dim, "days_data": days_data, "days_daily": days_daily, "days_prorata": days_prorata,
            "complete": complete, "basis": basis,
            "through": min(datetime.date(y, m, dim), last).isoformat(),
            "covers": int(round(tot_c)), "sales": (round(tot_s, 2) if any_sales else None),
            # the sit-in / delivery split exists only on daily rows; a mixed month would understate it
            "sit_in": (round(sit, 2) if any_split and days_prorata == 0 else None),
            "delivery": (round(dlv, 2) if any_split and days_prorata == 0 else None),
            "sites_with_data": len(sites), "sites": sites,
        })

    # ---- daily totals (daily-sourced only) for like-for-like MTD and projection ----
    daily_out = []
    for iso in sorted(daily):
        if datetime.date.fromisoformat(iso) > last: continue
        row = daily[iso]
        c = sum(v[0] or 0 for v in row.values()); s = sum(v[1] or 0 for v in row.values())
        daily_out.append({"d": iso, "covers": int(c), "sales": round(s, 2),
                          "sites": {k: [v[0] or 0, round(v[1] or 0, 2)] for k, v in row.items()}})

    # ---- weekly estate series for the footfall story (weekly files, then daily-built weeks) ----
    weekly_out = []
    for wc in sorted(weekly):
        row = weekly[wc]
        c = sum(v[0] for v in row.values()); s = sum((v[1] or 0) for v in row.values())
        known = any(v[1] is not None for v in row.values())
        weekly_out.append({"wc": wc, "covers": int(c), "sales": (round(s, 2) if known else None), "sites": len(row),
                           "per_site": {k: [v[0], v[1]] for k, v in row.items()}})
    # weeks after the last weekly file, built from daily rows (a week in progress shows as partial)
    last_wc = datetime.date.fromisoformat(max(weekly)) if weekly else None
    mon = (last_wc + datetime.timedelta(7)) if last_wc else (first - datetime.timedelta(first.weekday()))
    while mon <= last:
        days = [(mon + datetime.timedelta(i)).isoformat() for i in range(7)]
        got = [d for d in days if d in daily and datetime.date.fromisoformat(d) <= last]
        if not got: break
        c = sum(sum(v[0] or 0 for v in daily[d].values()) for d in got)
        s = sum(sum(v[1] or 0 for v in daily[d].values()) for d in got)
        weekly_out.append({"wc": mon.isoformat(), "covers": int(c), "sales": round(s, 2), "sites": len(daily[got[-1]]),
                           "partial": (len(got) < 7), "days": len(got)})
        mon += datetime.timedelta(7)

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "through": last.isoformat(),
        "sources": {"daily": "data/daily (Pipe 8 cash-up, from %s)" % (min(daily) if daily else "n/a"),
                    "weekly": "data/all_sites_wc_* (AM weekly refresh, from w/c %s)" % (min(weekly) if weekly else "n/a"),
                    "note": "Sales before June 2026 unknown (null). Days without a daily file use the week total / 7."},
        "sites": meta,
        "months": months,
        "daily": daily_out,
        "weekly": weekly_out,
    }
    p = os.path.join(repo, a.out)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w"), separators=(",", ":"))
    log(f"wrote {a.out}: {len(months)} months, {len(daily_out)} daily, {len(weekly_out)} weekly, through {last}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
