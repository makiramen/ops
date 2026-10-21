#!/usr/bin/env python3
"""Franchise Deliveroo RAG: MAF1 / MAF2 / MAF3 rows for the AM Control Centre Deliveroo tab.

Source: Brogan's weekly "Maki & Ramen - CSV RAG REPORT" (Drive folder 1c0srl6ZMuCgs81nlhV6wmkk0-_SfoSOi),
the same file the corporate Deliveroo ops overlay reads. Trading week = the `Date Hour Week` column.

Storefront -> code (Michael, 21/10/2026):
  Maki & Ramen - Glasgow     -> MAF1 (West End, Byres Road)
  Maki & Ramen - High Street -> MAF2
  Maki & Ramen - The O2      -> MAF3

Usage: build_deliveroo_franchise.py RAG.csv [RAG.csv ...]   (merges into data/deliveroo_franchise.json)
Blanks stay null (missing), never zero.
"""
import csv, json, os, sys

STORE_MAP = {
    "Maki & Ramen - Glasgow":     ("MAF1", "West End (Glasgow)"),
    "Maki & Ramen - High Street": ("MAF2", "High Street"),
    "Maki & Ramen - The O2":      ("MAF3", "The O2 (London)"),
}
COLS = {
    "open_hours_pct":      "Open Hours % of Scheduled (net of Vacation Mode)",
    "busy_mode_pct":       "Core Busy Mode - %",
    "rejection_pct":       "B10 Order % - Rejection",
    "avg_prep_min":        "Avg Estimated Prep Time Mins",
    "rider_wait_5min_pct": "Prct Rider Wait Time Greater Than 5mins",
    "inaccuracy_pct":      "B10 Order %  - Order Inaccuracy",
    "rating":              "Avg Order Rating (0-5 stars)",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "deliveroo_franchise.json")


def num(v):
    v = (v or "").strip().rstrip("%").strip()
    return None if v == "" else float(v)


def main(paths):
    out = {"weeks": {}}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            out = json.load(f)
    for p in paths:
        with open(p, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = (row.get("Restaurant Name") or "").strip()
                if name not in STORE_MAP:
                    continue
                code, label = STORE_MAP[name]
                wk = row["Date Hour Week"].strip()
                rec = {"code": code, "name": label, "storefront": name,
                       "source": "Deliveroo CSV RAG REPORT (franchise)"}
                for k, col in COLS.items():
                    rec[k] = num(row.get(col))
                rows = [r for r in out["weeks"].get(wk, []) if r["code"] != code]
                rows.append(rec)
                rows.sort(key=lambda r: r["code"])
                out["weeks"][wk] = rows
    out["weeks"] = dict(sorted(out["weeks"].items(), reverse=True))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print({wk: [r["code"] for r in rows] for wk, rows in out["weeks"].items()})


if __name__ == "__main__":
    main(sys.argv[1:])
