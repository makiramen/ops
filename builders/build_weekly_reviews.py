#!/usr/bin/env python3
"""
build_weekly_reviews.py  --  Maki & Ramen AM Control Centre, Pipe 5 (reviews), v2.

WHY THIS EXISTS
    The per-site "Maki N -" star tabs in the Google Reviews workbook are corrupt and
    hand-maintained (frozen tabs, a 12.30 average, sites reading 158 reviews in a week
    that really had 47). They must NOT be used. The DAILY feed (Pipe 8b) is healthy but
    its `reviews[]` array is a DISPLAY LIST -- positives are capped at 12 per site per
    file and comment-less reviews are omitted -- so it must NOT be used for counts either.

    The single source of truth is the workbook's own `Raw Data` tab (gid 284143046),
    which holds full lifetime history per location.

WEEK-DATE MATCHING (the thing that must never regress)
    Every review is stamped with the date it was RECEIVED. A weekly slice contains
    exactly the reviews received Monday..Sunday of that week. Nothing else -- not a
    rolling 7-day window, not the daily file's `window.n`/`window.avg`.

USAGE
    1. Run the extractor (browser, docs.google.com tab -- the container cannot reach
       Google): builders/extract_reviews_rawdata.js  -> maki_reviews_agg_<date>.json
    2. python3 build_weekly_reviews.py --agg maki_reviews_agg_<date>.json \
           --live <dir of live *_wc_*.json> --out <dir> [--weeks 2026-08-10 ...]
    3. Deploy the changed files; verify by SHA against the live copies.
"""
import argparse, json, os, sys, datetime

SKIP_CODES = {"IKI2"}          # no source rows in the workbook -- never invent a number

# build_site_json.py appends this line while building, i.e. BEFORE this script
# patches the real review numbers in. Left alone it stayed on every site --
# wrong on the 18 that do have a week rating. Keep the two strings identical.
REVIEWS_GAP = "Reviews \u2014 no week rating in source"
SOURCE_TMPL = (
    "Google Reviews workbook 1aFGfbGr... 'Raw Data' tab (gid 284143046), full-history rows "
    "deduped on reviewId, filtered by review RECEIVED date to {frm}..{to} (Mon-Sun). "
    "Per-site star tabs NOT used (corrupt). Daily Pipe 8b feed NOT used for counts "
    "(its reviews[] caps positives at 12/site and drops comment-less reviews). "
    "negative_reviews = rating<=3 with a non-empty comment; `negatives` counts ALL "
    "rating<=3 including those with no comment. url null (not in source). "
    "Cumulative venue rating not in this source (null). Built {built}."
)

def week_end(monday):
    d = datetime.date.fromisoformat(monday) + datetime.timedelta(days=6)
    return d.isoformat()

def zero_block():
    return {"n": 0, "avg": None, "bd": {"5":0,"4":0,"3":0,"2":0,"1":0}, "neg": 0, "list": []}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agg", required=True)
    ap.add_argument("--live", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--weeks", nargs="*")
    ap.add_argument("--built", default=datetime.date.today().isoformat())
    a = ap.parse_args()

    agg = json.load(open(a.agg, encoding="utf-8"))
    weeks_data = agg["weeks"]
    first_seen = agg["meta"].get("firstSeen", {})
    weeks = a.weeks or sorted(weeks_data)
    os.makedirs(a.out, exist_ok=True)

    changed, untouched, report = 0, 0, []
    for wk in weeks:
        if wk not in weeks_data:
            print("SKIP (not in agg):", wk); continue
        wend = week_end(wk)
        src = SOURCE_TMPL.format(frm=wk, to=wend, built=a.built)
        sites_agg = weeks_data[wk]["sites"]

        for name in sorted(os.listdir(a.live)):
            if not name.endswith("_wc_%s.json" % wk) or name.startswith("manifest_"):
                continue
            raw = open(os.path.join(a.live, name), encoding="utf-8").read()
            doc = json.loads(raw)
            # reproduce this file's exact serialisation, whichever of the two it uses
            trailing_nl = raw.endswith("\n")
            ascii_only  = not any(ord(c) > 127 for c in raw)
            assert json.dumps(doc, ensure_ascii=ascii_only, indent=2) + ("\n" if trailing_nl else "") == raw, \
                   "serialisation round-trip failed for %s -- do NOT write it" % name

            touched = []
            for code, site in doc.get("sites", {}).items():
                if code in SKIP_CODES:
                    continue
                rv = site.get("reviews")
                if rv is None:
                    continue
                blk = sites_agg.get(code)
                if blk is None:
                    fs = first_seen.get(code)
                    if not fs or fs > wend:
                        continue                      # not connected yet -- leave null
                    blk = zero_block()                # connected, genuinely no reviews
                rv["week_avg_rating"]  = blk["avg"]
                rv["new_reviews"]      = blk["n"]
                rv["star_breakdown"]   = blk["bd"]
                rv["negatives"]        = blk["neg"]
                rv["negative_reviews"] = blk["list"]
                rv["source"]           = src
                # Reconcile the gap line with what was actually patched in.
                # A site that ends up with a real week rating loses it; a site
                # left null KEEPS it -- IKI2 (SKIP_CODES, no rows in the
                # workbook ever), a site whose first review postdates the week,
                # and a site with no Google label yet (M21) all stay null and
                # all keep a truthful gap. Never 0.
                _gaps = site.get("gaps")
                if isinstance(_gaps, list):
                    if rv.get("week_avg_rating") is not None:
                        site["gaps"] = [g for g in _gaps if g != REVIEWS_GAP]
                    elif REVIEWS_GAP not in _gaps:
                        _gaps.append(REVIEWS_GAP)
                touched.append(code)

            new = json.dumps(doc, ensure_ascii=ascii_only, indent=2) + ("\n" if trailing_nl else "")
            if new == raw:
                untouched += 1
                continue
            open(os.path.join(a.out, name), "w", encoding="utf-8", newline="").write(new)
            changed += 1
            report.append((wk, name, len(touched)))

    print("files written:", changed, " unchanged:", untouched)
    return report

if __name__ == "__main__":
    main()
