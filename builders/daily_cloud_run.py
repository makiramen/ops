#!/usr/bin/env python3
"""daily_cloud_run.py — THE DAILY PIPE, END TO END, IN ONE DETERMINISTIC STEP (02/09/2026).

Runs inside a clone of github.com/makiramen/ops. Everything the scheduled task used to do across
five agent steps (guard, slice, build cash-up, build reviews, merge the reviews mirror, rebuild
Reviews Intelligence, index checks, content diff, commit, push) happens here, so a scheduled
session has exactly three jobs: pull the two Drive mirrors (twice each), run this, relay the report.

  python3 builders/daily_cloud_run.py --repo . \
      --cashup  /tmp/cashup_1.csv  /tmp/cashup_2.csv \
      --reviews /tmp/reviews_1.csv /tmp/reviews_2.csv \
      [--day YYYY-MM-DD] [--no-push] [--allow-single-pull]

Exit codes (the report JSON on stdout always says why):
  0  shipped, or nothing to ship        10 mirror pulls not byte-identical (re-pull and re-run)
  11 cash-up mirror unhealthy (short / stale / dark)   12 reviews mirror dark
  13 index would lose history           20 built + committed but NOT pushed (no GH_TOKEN / push failed)
  2  builder failed

Rules of the house baked in (standing_rules.md):
  * D = YESTERDAY (Europe/London). Never build today.
  * SALES COMPLETE != DAY BUILDABLE: every live venue present, no blank Actual, fleet avg spend
    £20-26 AND every site inside its own band (£15-40 ramen, £30-50 Nori). If D is not buildable
    we STILL back-fill D-2/D-1 (splits and reviews land late) and say so; we never ship a D file.
  * Cash-up and reviews for the same day ship in the SAME commit. Reviews are built for D-2, D-1, D.
  * A rebuild that differs only in _generated_at / rows_scanned / built_at / pulledAt is not a deploy.
  * Both indexes must be a strict superset of live. index.html is never touched.
  * Every drop is loud; a dark feed never renders as zero.
"""
import argparse, csv, datetime, hashlib, io, json, os, re, subprocess, sys, collections
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
CASHUP_EXPECTED_MIN = 20     # live sites from 21/08/2026
NORI = {"MakiNori"}

def log(*a): print(*a, file=sys.stderr)
def sha(b): return hashlib.sha256(b).hexdigest()
def run(cmd, cwd=None, check=True, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        log("CMD FAILED:", " ".join(cmd), "\n", r.stdout[-2000:], r.stderr[-4000:])
        raise SystemExit(2)
    return r

def money(s):
    s = (s or "").strip().replace("£", "").replace(",", "").replace(" ", "")
    if not s or s.startswith("#"): return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try: v = float(s)
    except ValueError: return None
    return -v if neg else v

def dmy(iso):  # 2026-08-31 -> 31/08/2026
    y, m, d = iso.split("-"); return f"{d}/{m}/{y}"

def identical(paths, allow_single):
    bs = [open(p, "rb").read() for p in paths]
    if len(bs) == 1:
        if not allow_single: log("only one pull given and --allow-single-pull not set"); raise SystemExit(10)
        return bs[0]
    if bs[0] != bs[1]:
        log(f"PULLS DIFFER: {len(bs[0])} B {sha(bs[0])[:12]} vs {len(bs[1])} B {sha(bs[1])[:12]} — re-pull"); raise SystemExit(10)
    return bs[0]

def strip_volatile(o):
    if isinstance(o, dict):
        return {k: strip_volatile(v) for k, v in o.items()
                if k not in ("_generated_at", "generated_at", "built_at", "rows_scanned", "pulledAt", "source_pulled_at", "generated", "meta")}
    if isinstance(o, list): return [strip_volatile(x) for x in o]
    return o

def changed_vs_head(repo, relpath):
    """True if the file's non-volatile content differs from HEAD (or is new)."""
    p = os.path.join(repo, relpath)
    if not os.path.exists(p): return False
    r = subprocess.run(["git", "show", f"HEAD:{relpath}"], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0: return True
    try:
        return strip_volatile(json.loads(r.stdout)) != strip_volatile(json.load(open(p, encoding="utf-8")))
    except Exception:
        return open(p, "rb").read() != r.stdout.encode("utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--cashup", nargs="+", required=True)
    ap.add_argument("--reviews", nargs="+", required=True); ap.add_argument("--day")
    ap.add_argument("--no-push", action="store_true"); ap.add_argument("--allow-single-pull", action="store_true")
    ap.add_argument("--report", help="repo-relative path to write the run report to and ship with the commit (a heartbeat with content)")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo); B = os.path.join(repo, "builders"); DD = os.path.join(repo, "data", "daily")
    tmp = "/tmp/daily_cloud_run"; os.makedirs(tmp, exist_ok=True)
    sys.path.insert(0, B)
    import pull_daily_cashup as PC  # VENUE_TO_CODE, VENUE_IGNORE

    today_uk = datetime.datetime.now(UK).date()
    D = datetime.date.fromisoformat(a.day) if a.day else today_uk - datetime.timedelta(days=1)
    if D >= today_uk: log("refusing to build today or the future"); raise SystemExit(2)
    D1, D2 = D - datetime.timedelta(days=1), D - datetime.timedelta(days=2)
    R = {"day": D.isoformat(), "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "warnings": [], "cashup": {}, "reviews": {}, "intel": {}, "shipped": [], "commit": None, "pushed": False}

    # ---------------- CASH-UP MIRROR GUARD ----------------
    cb = identical(a.cashup, a.allow_single_pull)
    rows = list(csv.reader(io.StringIO(cb.decode("utf-8-sig"))))
    hdr = [h.strip() for h in rows[0]]
    if "Venue" not in hdr or "Date" not in hdr:
        log("cash-up mirror header unexpected:", hdr[:6]); raise SystemExit(11)
    iv, idt = hdr.index("Venue"), hdr.index("Date")
    iact = next(i for i, h in enumerate(hdr) if h == "Actual (£)")
    icov = next((i for i, h in enumerate(hdr) if h.lower().startswith("no. of customers") or h.lower() == "covers"), None)
    by_date = collections.defaultdict(dict)
    for r in rows[1:]:
        if len(r) <= max(iv, idt, iact): continue
        venue = r[iv].strip(); dt = r[idt].strip()
        if not venue or not dt or venue in PC.VENUE_IGNORE: continue
        by_date[dt][venue] = r
    if not by_date: log("cash-up mirror carries no rows"); raise SystemExit(11)
    counts = {d: len(v) for d, v in by_date.items()}
    R["cashup"]["mirror_sha"] = sha(cb)[:16]; R["cashup"]["mirror_dates"] = len(counts)
    live_venues = set(PC.VENUE_TO_CODE)

    def buildable(dt):
        """Return (ok, why, fleet_avg_spend, per_site_flags) for a dd/mm/yyyy date."""
        vr = by_date.get(dt, {})
        missing = sorted(live_venues - set(vr))
        if missing: return False, f"venues missing on {dt}: {missing}", None, []
        blank = [v for v in live_venues if (money(vr[v][iact]) or 0) <= 0]
        if blank: return False, f"zero/blank Actual on {dt}: {sorted(blank)}", None, []
        sales = {v: money(vr[v][iact]) for v in live_venues}
        covers = {v: money(vr[v][icov]) if icov is not None else None for v in live_venues}
        if icov is not None:
            blankc = [v for v in live_venues if not covers[v]]
            if blankc: return False, f"covers blank on {dt}: {sorted(blankc)}", None, []
            fleet = sum(sales.values()) / sum(covers.values())
            flags = []
            for v in live_venues:
                sp = sales[v] / covers[v]; code = PC.VENUE_TO_CODE[v]
                lo, hi = (30, 50) if code in NORI else (15, 40)
                if not (lo <= sp <= hi): flags.append(f"{code} £{sp:.2f}/head (band £{lo}-{hi})")
            if not (20 <= fleet <= 26): return False, f"fleet avg spend £{fleet:.2f} outside £20-26 on {dt} (covers still filling?)", fleet, flags
            if flags: return False, "per-site spend outside band on " + dt + ": " + "; ".join(flags), fleet, flags
            return True, "ok", fleet, flags
        return True, "ok (no covers column found)", None, []

    ok, why, fleet_sp, flags = buildable(dmy(D.isoformat()))
    R["cashup"]["D_buildable"] = ok; R["cashup"]["D_gate"] = why
    if fleet_sp: R["cashup"]["D_fleet_avg_spend"] = round(fleet_sp, 2)
    build_dates = [D2, D1] + ([D] if ok else [])
    for dd in (D2, D1):
        o2, w2, _, _ = buildable(dmy(dd.isoformat()))
        if not o2: R["warnings"].append(f"{dd.isoformat()} not buildable in this mirror ({w2}) — left as live")
    build_dates = [dd for dd in build_dates if buildable(dmy(dd.isoformat()))[0]]
    if not build_dates:
        log("nothing buildable in the cash-up mirror:", why)
        R["cashup"]["result"] = "nothing buildable"; print(json.dumps(R)); raise SystemExit(11)
    keep_dmy = {dmy(dd.isoformat()) for dd in build_dates}
    slice_path = os.path.join(tmp, f"daily_cashup_{D}.csv")
    with open(slice_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(rows[0])
        for r in rows[1:]:
            if len(r) > idt and r[idt].strip() in keep_dmy: w.writerow(r)
    live_index = json.load(open(os.path.join(DD, "daily_index.json")))
    live_ridx = json.load(open(os.path.join(DD, "daily_reviews_index.json")))
    ik = "dates" if "dates" in live_index else "days"
    r = run([sys.executable, "pull_daily_cashup.py", "--csv", slice_path, "--out", DD], cwd=B)
    R["cashup"]["builder_log"] = [l for l in r.stderr.splitlines() + r.stdout.splitlines() if "WARN" in l or "FATAL" in l][:20]
    R["cashup"]["built"] = [dd.isoformat() for dd in build_dates]

    # ---------------- REVIEWS MIRROR ----------------
    rb = identical(a.reviews, a.allow_single_pull)
    rrows = list(csv.reader(io.StringIO(rb.decode("utf-8-sig"))))
    rh = [h.strip() for h in rrows[0]]
    try: iid, ia, ir, ic, isite, idate = (rh.index(x) for x in ("reviewId", "author_name", "rating", "comment", "Site", "Date"))
    except ValueError: log("reviews mirror header unexpected:", rh); raise SystemExit(12)
    per_date = collections.Counter(r[idate].strip() for r in rrows[1:] if len(r) > idate and r[idate].strip())
    R["reviews"]["mirror_sha"] = sha(rb)[:16]; R["reviews"]["rows"] = len(rrows) - 1
    R["reviews"]["rows_D"] = per_date.get(dmy(D.isoformat()), 0); R["reviews"]["rows_D1"] = per_date.get(dmy(D1.isoformat()), 0)
    if len(rrows) < 21 or (R["reviews"]["rows_D"] == 0 and R["reviews"]["rows_D1"] == 0):
        R["warnings"].append(f"REVIEWS FEED LOOKS DARK: {len(rrows)-1} rows, {R['reviews']['rows_D']} on D, {R['reviews']['rows_D1']} on D-1 — ingestion at source has not run; not building reviews")
        reviews_ok = False
    else:
        reviews_ok = True
        psv = os.path.join(tmp, f"daily_reviews_{D}.psv")
        with open(psv, "w", encoding="utf-8") as fh:
            for r in rrows[1:]:
                if len(r) <= max(iid, ia, ir, ic, isite, idate) or not r[idate].strip(): continue
                fh.write("|".join(re.sub(r"\s+", " ", r[i]).strip() for i in (iid, ia, ir, ic, isite, idate)) + "\n")
        R["reviews"]["built"] = []
        for dd in build_dates:
            r = run([sys.executable, "pull_daily_reviews.py", "--psv", psv, "--date", dd.isoformat(), "--outdir", DD, "--window", "7", "--validate"], cwd=B)
            m = re.search(r"day \S+: (\d+) reviews, (\d+) negative", r.stdout + r.stderr)
            wm = re.search(r"window \S+\.\.\S+: (\d+) reviews, (\d+) negative", r.stdout + r.stderr)
            R["reviews"]["built"].append({"day": dd.isoformat(), "n": int(m.group(1)) if m else None, "neg": int(m.group(2)) if m else None,
                                          "window_n": int(wm.group(1)) if wm else None, "window_neg": int(wm.group(2)) if wm else None})
            for l in (r.stdout + r.stderr).splitlines():
                if "WARN" in l and "Leith" not in l and "IKI2" not in l: R["warnings"].append(dd.isoformat() + " " + l.strip())
        # Reviews Intelligence: merge the mirror into the rolling full pull and rebuild
        mpath = os.path.join(tmp, "reviews_mirror.csv"); open(mpath, "wb").write(rb)
        full = os.path.join(repo, "data", "reviews_full.json")
        r = run([sys.executable, "merge_reviews_mirror.py", "--base", full, "--mirror", mpath, "--out", full, "--today", today_uk.isoformat()], cwd=B, check=False)
        if r.returncode != 0:
            R["warnings"].append("reviews mirror merge refused: " + r.stderr.strip().splitlines()[-1][:300])
            run(["git", "checkout", "--", "data/reviews_full.json"], cwd=repo, check=False)
        else:
            R["intel"]["merge"] = json.loads(r.stdout.strip().splitlines()[-1])
            r = run([sys.executable, "build_reviews_intel.py", "--full", full, "--taxonomy", "reviews_taxonomy.json", "--live-dir", "../data",
                     "--llm", "../data/reviews_llm_labels.json", "--annotations", "../data/reviews_annotations.json",
                     "--out", "../data/reviews_intel.json", "--needs-review", os.path.join(tmp, "reviews_needs_review.json"),
                     "--summary", "../data/reviews_summary.json"], cwd=B)
            intel = json.load(open(os.path.join(repo, "data", "reviews_intel.json")))
            wk = (D - datetime.timedelta(days=D.weekday())).isoformat()
            w = [x for x in intel["reviews"] if x["week"] == wk]
            R["intel"]["week_in_progress"] = {"week": wk, "reviews": len(w), "negatives": sum(1 for x in w if x["stars"] <= 3),
                                              "avg": round(sum(x["stars"] for x in w) / len(w), 2) if w else None,
                                              "days": sorted({x["date"] for x in w})}
            summ = json.load(open(os.path.join(repo, "data", "reviews_summary.json")))
            R["intel"]["badge_week"] = summ["week"]; R["intel"]["badge_reviews"] = summ["reviews"]

    # ---------------- INDEX + CONTENT CHECKS ----------------
    new_index = json.load(open(os.path.join(DD, "daily_index.json"))); new_ridx = json.load(open(os.path.join(DD, "daily_reviews_index.json")))
    if not set(live_index[ik]) <= set(new_index[ik]) or not set(live_ridx["days"]) <= set(new_ridx["days"]):
        log("INDEX WOULD LOSE HISTORY — aborting"); run(["git", "checkout", "--", "data/daily"], cwd=repo, check=False); raise SystemExit(13)
    R["index"] = {"cashup_latest": new_index["latest"], "cashup_days": len(new_index[ik]), "reviews_latest": new_ridx["latest"], "reviews_days": len(new_ridx["days"])}
    st = run(["git", "status", "--porcelain", "--", "data", "reviews.html"], cwd=repo).stdout.splitlines()
    cand = [l[3:].strip() for l in st if l.strip()]
    ship = []
    for rel in cand:
        if rel.startswith("data/_raw"): continue
        if rel.endswith(".json") and not changed_vs_head(repo, rel):
            run(["git", "checkout", "--", rel], cwd=repo, check=False); continue
        ship.append(rel)
    # the reviews_full base is only worth shipping if something was added or changed
    if "data/reviews_full.json" in ship and R["intel"].get("merge") and R["intel"]["merge"]["added"] == 0 and R["intel"]["merge"]["changed"] == 0:
        run(["git", "checkout", "--", "data/reviews_full.json"], cwd=repo, check=False); ship.remove("data/reviews_full.json")
        for rel in ("data/reviews_intel.json", "data/reviews_summary.json"):
            if rel in ship and not changed_vs_head(repo, rel):
                run(["git", "checkout", "--", rel], cwd=repo, check=False); ship.remove(rel)
    R["shipped"] = ship
    # headline numbers for the message
    if D.isoformat() in R["cashup"]["built"]:
        dj = json.load(open(os.path.join(DD, f"daily_{D}.json"))); t = dj["totals"]
        R["cashup"]["D_totals"] = {"sales": t["sales"], "target": t["target"], "vs_target_pct": round((t["sales"] / t["target"] - 1) * 100, 1) if t.get("target") else None,
                                   "covers": t["covers"], "avg_spend": t.get("avg_spend"), "wage_pct": t.get("wage_pct"),
                                   "sites": f"{dj['sites_reported']}/{dj['sites_expected']}", "splits": f"{dj['foh_boh_reported']}/{dj['sites_reported']}"}
        R["cashup"]["D_gaps"] = dj.get("gaps", {})
        worst = sorted(((c, s["sales"].get("vs_target_pct")) for c, s in dj["sites"].items() if s["sales"].get("vs_target_pct") is not None), key=lambda x: x[1])
        R["cashup"]["D_worst"] = worst[:3]; R["cashup"]["D_best"] = worst[-3:][::-1]
        R["cashup"]["D_wage_over_25"] = sorted([(c, s["labour"]["wage_pct"]) for c, s in dj["sites"].items() if (s["labour"].get("wage_pct") or 0) > 25], key=lambda x: -x[1])
    if not ship:
        R["result"] = "nothing changed — live is current"
    if a.report:
        rp = os.path.join(repo, a.report)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        json.dump(R, open(rp, "w"), indent=1)
        ship.append(a.report)
    if not ship:
        print(json.dumps(R)); return 0

    # ---------------- COMMIT + PUSH ----------------
    run(["git", "config", "user.name", "maki-nori"], cwd=repo); run(["git", "config", "user.email", "michael@makiramen.com"], cwd=repo)
    run(["git", "add", "--"] + ship, cwd=repo)
    tt = R["cashup"].get("D_totals")
    data_ship = [x for x in ship if x != a.report]
    if not data_ship:
        head = f"Daily tab run {R['run_at'][11:16]}Z: {R.get('result', 'no data change')} ({D} {'buildable' if R['cashup'].get('D_buildable') else 'not filed yet'})"
    else:
        head = (f"Daily tab: {D.strftime('%a %d/%m')} cash-up + reviews ({tt['sites']} sites, £{tt['sales']:,.2f}, {tt['covers']:,} covers, wage {tt['wage_pct']}%)"
            if tt else f"Daily tab: back-fill {', '.join(R['cashup']['built'])} ({D} not filed yet)")
    wip = R["intel"].get("week_in_progress")
    body = ["Cloud-native scheduled run (daily_cloud_run.py). Files: " + ", ".join(ship)]
    if wip: body.append(f"Reviews Intelligence week in progress w/c {wip['week']}: {wip['reviews']} reviews, {wip['negatives']} negative, {wip['avg']}★ over {len(wip['days'])} day(s)")
    body += ["", "Co-Authored-By: Claude <noreply@anthropic.com>"]
    run(["git", "commit", "-q", "-m", head, "-m", "\n".join(body)], cwd=repo)
    R["commit"] = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip(); R["commit_title"] = head
    if a.no_push:
        R["result"] = "built and committed locally, --no-push"; print(json.dumps(R)); return 20
    tok = os.environ.get("GH_TOKEN")
    if not tok:
        R["result"] = "built and committed locally but NO GH_TOKEN in the environment — not pushed"; print(json.dumps(R)); return 20
    env = dict(os.environ); env["GIT_TERMINAL_PROMPT"] = "0"
    url = f"https://x-access-token:{tok}@github.com/makiramen/ops.git"
    pr = subprocess.run(["git", "push", url, "HEAD:main"], cwd=repo, capture_output=True, text=True, env=env)
    if pr.returncode != 0:
        msg = (pr.stderr + pr.stdout).replace(tok, "***")
        if "fetch first" in msg or "non-fast-forward" in msg or "rejected" in msg:
            # someone shipped meanwhile: rebase our data commit on top and retry once
            subprocess.run(["git", "fetch", url, "main"], cwd=repo, capture_output=True, text=True, env=env)
            rb_ = subprocess.run(["git", "rebase", "FETCH_HEAD"], cwd=repo, capture_output=True, text=True, env=env)
            if rb_.returncode == 0:
                pr = subprocess.run(["git", "push", url, "HEAD:main"], cwd=repo, capture_output=True, text=True, env=env)
                R["commit"] = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
                msg = (pr.stderr + pr.stdout).replace(tok, "***")
            else:
                subprocess.run(["git", "rebase", "--abort"], cwd=repo, capture_output=True)
        if pr.returncode != 0:
            R["result"] = "PUSH FAILED: " + msg[-600:]; print(json.dumps(R)); return 20
    remote = subprocess.run(["git", "ls-remote", url, "refs/heads/main"], cwd=repo, capture_output=True, text=True, env=env).stdout.split()
    R["pushed"] = bool(remote) and remote[0] == R["commit"]
    R["remote_head"] = remote[0] if remote else None
    R["result"] = "SHIPPED " + R["commit"][:7] if R["pushed"] else "push returned ok but remote HEAD != our commit — CHECK"
    print(json.dumps(R)); return 0

if __name__ == "__main__":
    sys.exit(main())
