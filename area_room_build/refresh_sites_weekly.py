"""Adds AM CC weeks newer than the sites_weekly.json seed, straight from the repo data (data/all_sites_wc_<monday>.json),
in the same shape the Area Room reads. Seed weeks are never changed. The O2 (MAF3, franchise) is not in the AM CC site
files, so its Deliveroo open hours and rider wait come from data/deliveroo_daily.json weekly rows."""
import glob, json, os, re

CODES = ["M17", "M18", "M19", "M20", "MakiNori"]


def _g(o, *path):
    for k in path:
        if not isinstance(o, dict):
            return None
        o = o.get(k)
    return o


def site_row(s):
    k, dl = s.get("kpis") or {}, s.get("deliveroo") or {}
    return {
        "gm": s.get("gm"), "sales": _g(k, "sales", "actual"), "sales_t": _g(k, "sales", "target"), "covers": _g(k, "covers", "actual"),
        "wage": _g(k, "wage_pct", "actual"), "food": _g(k, "food_pct", "actual"),
        "rev": _g(s, "reviews", "new_reviews"), "rev_avg": _g(s, "reviews", "week_avg_rating"), "neg": _g(s, "reviews", "negatives"),
        "d_rating": dl.get("rating"), "d_open": dl.get("open_hours_pct"), "d_prep": dl.get("avg_prep_min"), "d_inacc": dl.get("inaccuracy_pct"),
        "d_rider": dl.get("rider_wait_5min_pct"), "d_sales": dl.get("sales"), "d_orders": dl.get("orders"),
        "eff": _g(s, "efficiency_score", "score"), "red": _g(s, "red_light", "status"), "maint": _g(s, "maintenance", "outstanding_count") or 0,
    }


def add_new_weeks(sw, data_dir):
    droo = {}
    p = os.path.join(data_dir, "deliveroo_daily.json")
    if os.path.exists(p):
        droo = json.load(open(p)).get("w", {})
    for f in sorted(glob.glob(os.path.join(data_dir, "all_sites_wc_*.json"))):
        wk = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f)).group(1)
        if wk in sw or wk < "2026-09-07":
            continue
        try:
            sites = json.load(open(f))["sites"]
        except Exception as e:
            print("skip", f, e)
            continue
        row = {c: site_row(sites[c]) for c in CODES if c in sites}
        o2 = (droo.get(wk) or {}).get("MAF3")
        if o2:
            row["O2"] = {"d_open": o2[1], "d_prep": None, "d_rider": o2[0], "d_inacc": None, "d_rating": None}
        if row:
            sw[wk] = row
            print("sites_weekly: added w/c", wk)
    return sw
