#!/usr/bin/env python3
"""
build_delivery_total.py : TOTAL delivery sales (all platforms, Deliverect incl. HungryPanda) into the weekly files.

Michael, 28/10/2026: the weekly pull must carry the total delivery sales figure the site modal tile shows
("Deliveroo Sales (wk) . dailies"), i.e. the Deliverect delivery lines of the Kobas "Daily Headline Revenue
Report (All Venues)" that auto-pulls into Matt's "Script Raw Data" sheet (1LCn9m8U41eckBOPrXGmkwmB2JkGeA2t0gGhEFK_3nH8,
per-venue tabs, column "Delivery", gross incl. VAT) between 05:00 and 06:00 UK. The Auto Cash Up dailies
(data/daily/daily_<day>.json, key sales.delivery) hold exactly those values (verified 28/10/2026, 26 days x 20 sites,
0 differences), so this builder reads the dailies and never needs a Google credential.

Writes kpis.delivery_total into data/<SITE>_wc_<monday>.json and data/all_sites_wc_<monday>.json (MERGE: no other key
is touched). Idempotent: exit 0 and no write when nothing changed.

    delivery_total = {
      "sales": 3240.1,            # sum of daily delivery GBP, gross incl. VAT, all platforms
      "days": 7,                  # days with a delivery figure
      "target": 2700.0,           # sum of the daily Delivery Target over the days that have one
      "target_days": 7,
      "var_pct": 20.0,            # sales vs target
      "orders": 78,               # Deliveroo orders only (Deliveroo Daily Master), null when no storefront
      "prev": 2995.4,             # previous week's sales on the same basis (from that week's dailies)
      "wow_abs": 244.7, "wow_pct": 8.2,
      "source": "...", "basis": "..."
    }

Usage:
    python3 builders/build_delivery_total.py --repo . --week 2026-10-19 [--week 2026-10-12 ...]
    python3 builders/build_delivery_total.py --repo . --auto      # current ISO week and the previous one
"""
import argparse, datetime as dt, glob, json, os, sys

SOURCE = ("Kobas Daily Headline Revenue Report (All Venues) -> Script Raw Data sheet, Delivery column "
          "(Deliverect lines, all platforms incl. HungryPanda, gross incl. VAT), via the Auto Cash Up dailies")
BASIS = "sum of daily delivery GBP Mon-Sun; orders = Deliveroo Daily Master (Deliveroo only)"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def week_days(monday):
    d0 = dt.date.fromisoformat(monday)
    return [(d0 + dt.timedelta(days=i)).isoformat() for i in range(7)]


def week_agg(repo, monday, roo):
    """Per site: delivery sales, target, days; orders from deliveroo_daily."""
    out = {}
    iO = roo["k"].index("orders") if roo and "orders" in roo.get("k", []) else -1
    for day in week_days(monday):
        p = os.path.join(repo, "data", "daily", f"daily_{day}.json")
        if os.path.exists(p):
            for code, x in (load(p).get("sites") or {}).items():
                s = (x or {}).get("sales") or {}
                a = out.setdefault(code, {"sales": 0.0, "days": 0, "target": 0.0, "target_days": 0, "orders": 0, "order_days": 0})
                v = s.get("delivery")
                if isinstance(v, (int, float)):
                    a["sales"] += float(v); a["days"] += 1
                t = s.get("target_delivery")
                if isinstance(t, (int, float)) and t > 0:
                    a["target"] += float(t); a["target_days"] += 1
        dd = (roo or {}).get("d", {}).get(day) or {}
        for code, q in dd.items():
            if iO >= 0 and isinstance(q, list) and len(q) > iO and isinstance(q[iO], (int, float)):
                a = out.setdefault(code, {"sales": 0.0, "days": 0, "target": 0.0, "target_days": 0, "orders": 0, "order_days": 0})
                a["orders"] += int(q[iO]); a["order_days"] += 1
    return out


def block(a, prev):
    if not a or (a["days"] == 0 and a["order_days"] == 0):
        return None
    sales = round(a["sales"], 2) if a["days"] else None
    target = round(a["target"], 2) if a["target_days"] else None
    orders = a["orders"] if a["order_days"] else None
    # no orders all week and GBP 0 delivered and no target = no storefront (Maki Nori), not a real GBP 0 week
    if orders is None and (sales is None or abs(sales) < 0.005) and target is None:
        return None
    b = {"sales": sales, "days": a["days"], "target": target, "target_days": a["target_days"],
         "var_pct": round((sales / target - 1) * 100, 2) if (sales is not None and target) else None,
         "orders": orders, "order_days": a["order_days"]}
    pv = prev.get("sales") if prev else None
    b["prev"] = pv
    if sales is not None and isinstance(pv, (int, float)) and pv:
        b["wow_abs"] = round(sales - pv, 2); b["wow_pct"] = round((sales / pv - 1) * 100, 2)
    else:
        b["wow_abs"] = None; b["wow_pct"] = None
    b["source"] = SOURCE; b["basis"] = BASIS
    return b


def dump(obj, p):
    # match the file's own serialisation: indent 2; keep its ascii-escaping and trailing-newline choice
    # (build_site_json.py writes ascii-escaped, no newline; the notes ingest writes raw UTF-8 + newline)
    raw = open(p, "rb").read()
    ascii_only = all(b < 128 for b in raw)
    nl = raw.endswith(b"\n")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=ascii_only)
        if nl:
            f.write("\n")


def patch_week(repo, monday, roo, write=True):
    cur = week_agg(repo, monday, roo)
    prev_monday = (dt.date.fromisoformat(monday) - dt.timedelta(days=7)).isoformat()
    prev = week_agg(repo, prev_monday, roo)
    prev_blocks = {c: block(a, {}) for c, a in prev.items()}
    changed, summary = [], {}
    files = sorted(glob.glob(os.path.join(repo, "data", f"*_wc_{monday}.json")))
    files = [f for f in files if not os.path.basename(f).startswith("manifest_")]
    if not files:
        print(f"{monday}: no weekly files yet, skipped"); return []
    for p in files:
        j = load(p)
        sites = j.get("sites")
        if not isinstance(sites, dict):
            continue
        touched = False
        for code, s in sites.items():
            k = s.setdefault("kpis", {})
            b = block(cur.get(code), prev_blocks.get(code))
            if b is None:
                if "delivery_total" in k:
                    del k["delivery_total"]; touched = True
                continue
            if k.get("delivery_total") != b:
                k["delivery_total"] = b; touched = True
            summary[code] = b
        if touched:
            changed.append(p)
            if write:
                dump(j, p)
    fleet = sum(b["sales"] or 0 for b in summary.values())
    print(f"{monday}: {len(summary)} sites with a delivery_total, fleet GBP {fleet:,.2f}, "
          f"{len(changed)} file(s) {'written' if write else 'would change'}")
    for code in sorted(summary):
        b = summary[code]
        print(f"  {code:9s} GBP {b['sales'] or 0:9,.2f} ({b['days']}/7) tgt {b['target'] or 0:9,.2f} "
              f"var {b['var_pct'] if b['var_pct'] is not None else '-':>7} orders {b['orders'] if b['orders'] is not None else 'n/a':>4} "
              f"prev {b['prev'] if b['prev'] is not None else '-':>9} wow {b['wow_pct'] if b['wow_pct'] is not None else '-'}")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--week", action="append", default=[], help="Monday ISO date, repeatable")
    ap.add_argument("--auto", action="store_true", help="current week (UK) and the previous one")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    weeks = list(a.week)
    if a.auto:
        today = dt.datetime.utcnow().date()  # the run is 09:30 UK, the date is the same either side of the clock change
        mon = today - dt.timedelta(days=today.weekday())
        weeks += [mon.isoformat(), (mon - dt.timedelta(days=7)).isoformat()]
    if not weeks:
        ap.error("--week or --auto")
    roo_p = os.path.join(a.repo, "data", "deliveroo_daily.json")
    roo = load(roo_p) if os.path.exists(roo_p) else None
    changed = []
    for w in dict.fromkeys(weeks):
        changed += patch_week(a.repo, w, roo, write=not a.dry_run)
    print("CHANGED " + " ".join(os.path.relpath(p, a.repo) for p in changed) if changed else "CHANGED none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
