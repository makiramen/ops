#!/usr/bin/env python3
"""
bake_broth.py : write one broth snapshot per ISO week into the AM Control Centre's
data folder, plus an index the week picker reads.

  python3 bake_broth.py --out /path/to/ops/data/broth

Weeks run oldest first and share one case_history.json, so the two-strike
escalation accumulates across weeks exactly as it will in the live weekly run.
Output matches the AM dashboard's existing convention: <thing>_wc_YYYY-MM-DD.json
plus an index listing the weeks newest first.
"""
import argparse, datetime, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def all_days():
    days = None
    for line in open(os.path.join(HERE, "live_matrix.txt"), encoding="utf-8"):
        if line.startswith("DAYS:"):
            days = line.split(":", 1)[1].strip().split(",")
            break
    return days

def monday(d):
    dt = datetime.date.fromisoformat(d)
    return (dt - datetime.timedelta(days=dt.weekday())).isoformat()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="target data/broth directory")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    days = all_days()
    weeks = {}
    for d in days:
        weeks.setdefault(monday(d), []).append(d)

    hist = os.path.join(a.out, "case_history.json")
    if os.path.exists(hist):
        os.remove(hist)

    index = []
    for mon in sorted(weeks):                      # oldest first, so streaks build
        ds = sorted(weeks[mon])
        out = os.path.join(a.out, "broth_wc_%s.json" % mon)
        r = subprocess.run([sys.executable, os.path.join(HERE, "build_live.py"),
                            "--days", ",".join(ds), "--out", out],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-800:], r.stderr[-800:]); sys.exit("failed on %s" % mon)
        snap = json.load(open(out))
        snap["week"] = {"monday": mon, "days": ds, "partial": len(ds) < 7}
        json.dump(snap, open(out, "w"), separators=(",", ":"))
        sun = (datetime.date.fromisoformat(mon) + datetime.timedelta(days=6)).isoformat()
        index.append({"monday": mon, "sunday": sun,
                      "label": "Week of %s to %s" % (mon, sun),
                      "file": "broth_wc_%s.json" % mon,
                      "days": len(ds), "partial": len(ds) < 7,
                      "p1": sum(1 for c in snap["cases"] if c["priority"] == "P1"),
                      "tonkotsu_in": snap["estate"]["pork"]["in_pct"],
                      "chicken_in": snap["estate"]["chicken"]["in_pct"]})
        print("%s  %d days  P1 %d  tonkotsu %.1f%%  chicken %.1f%%"
              % (mon, len(ds), index[-1]["p1"], index[-1]["tonkotsu_in"], index[-1]["chicken_in"]))

    index.sort(key=lambda w: w["monday"], reverse=True)     # newest first, AM convention
    json.dump({"generated_at": datetime.date.today().isoformat(),
               "note": "Broth score by week for the AM Control Centre picker. Newest first. "
                       "The daily bake rewrites the current week in place and prepends a new "
                       "week each Monday.",
               "latest": index[0]["monday"] if index else None,
               "weeks": index},
              open(os.path.join(a.out, "index.json"), "w"), indent=1)
    print("\nwrote %d week file(s) + index.json to %s" % (len(index), a.out))

if __name__ == "__main__":
    main()
