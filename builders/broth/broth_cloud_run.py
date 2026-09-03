#!/usr/bin/env python3
"""broth_cloud_run.py — the broth pipe end to end in one deterministic step.

  fetch (done separately) -> extend the matrices -> bake every week -> ship only the weeks the
  new data actually touches -> merge the index -> commit -> push.

Why this exists: until 03/09/2026 only the FIRST stage of the broth pipe was automated. The Mapal
broker Apps Script refreshed its Sheet every morning, but turning that Sheet into
data/broth/*.json and pushing it only ever happened when a human did it by hand, so the tab
silently aged. A pipe is only as automated as its last stage.

  python3 builders/broth/broth_cloud_run.py --repo . --sources /tmp/broth_src \
          --report data/broth/run_report.json

Exit codes
  0   shipped, or nothing to ship
  2   bad inputs / missing files
  3   a guard tripped (gap in days, matrix shape, index would lose a week)
  4   the bake itself failed
  20  built and committed but NOT pushed (no GH_TOKEN, or the push failed)

TWO RULES THIS FILE EXISTS TO ENFORCE
1. THE BROKER SHEET IS A ROLLING 8 DAY WINDOW. Days inside that window are REBUILT from the Sheet
   every run, so a late entry is picked up. Days before it are frozen: the committed matrix is the
   only record of them and is never rewritten.
2. REBAKING HISTORY REWRITES HISTORY. build_live.py judges flatline on the last FLATLINE_LOOKBACK
   days of the WHOLE matrix file, not the week being baked, so growing the file silently restates
   the flatline cases of every older week. Every week is therefore rebaked (the two-strike streak
   in case_history.json needs the full sequence) but ONLY weeks the window actually touches are
   shipped, and the index keeps the published numbers for the rest.
"""
import argparse, csv, datetime, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ("chicken", "pork")


def log(*a): print(*a, file=sys.stderr)


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def monday(d):
    dt = datetime.date.fromisoformat(d)
    return (dt - datetime.timedelta(days=dt.weekday())).isoformat()


def read_matrix_days(path):
    for line in open(path, encoding="utf-8"):
        if line.startswith("DAYS:"):
            return line.split(":", 1)[1].strip().split(",")
    sys.exit("no DAYS: line in %s" % path)


def norm_text(s):
    """Mapal writes NON-BREAKING SPACES into some location names ("Maki\\xa0O2\\xa0Arena"). Left
    alone they fork a second series for a site that already exists. Found live 03/09/2026."""
    return " ".join((s or "").replace("\u00a0", " ").split())


def norm_date(s):
    """Two shapes, because the same column arrives differently depending on the route:
    dd/mm/yyyy from a text cell (with a 0025 / 0026 year typo the form introduced), and
    yyyy-mm-dd from a real date cell that openpyxl handed back as a date object."""
    s = (s or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if not m:
        return None
    dd, mm, yy = m.groups()
    if yy.startswith("00"):
        yy = "20" + yy[2:]
    return "%s-%02d-%02d" % (yy, int(mm), int(dd))


def mean_half_up(xs):
    # match the hand-built matrices: round half UP, not python's banker's rounding
    return float("%.2f" % (sum(xs) / len(xs) + 1e-9))


def load_cells(path, R):
    """(loc, kind, day) -> value string ('' = the check was missed), plus the days seen."""
    cells, days, locs = {}, set(), set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("scope") or "site").strip() != "site":
                continue
            loc = norm_text(r.get("location"))
            kind = norm_text(r.get("kind")).lower()
            day = norm_date(r.get("business_day"))
            if not loc or kind not in KINDS or not day:
                continue
            if re.search(r"factory", loc, re.I):
                continue
            cells[(loc, kind, day)] = (r.get("value") or "").strip()
            days.add(day)
            locs.add(loc)
    R["source_days"] = sorted(days)
    R["source_locations"] = len(locs)
    return cells, sorted(days), locs


def load_factory(path, keep):
    agg = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = norm_date(r.get("Date"))
            if d not in keep:
                continue
            p = (r.get("Product Name") or "").strip().lower()
            kind = "pork" if "tonkotsu" in p else ("chicken" if "chicken" in p else None)
            if not kind:
                continue
            try:
                agg.setdefault((d, kind), []).append(float((r.get("Reading After Adding Ice") or "").strip()))
            except ValueError:
                continue
    return agg


def extend_sites(path, cells, window, R):
    lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    old_days = lines[0].split(":", 1)[1].split(",")
    devi = lines.index("DEV:")

    series = {}
    for ln in lines[1:devi]:
        key, vals = ln.split(":", 1)
        loc, kind = key.split("~")
        v = vals.split(",")
        if len(v) != len(old_days):
            sys.exit("%s has %d columns, expected %d" % (key, len(v), len(old_days)))
        series[(loc, kind)] = dict(zip(old_days, v))

    days = sorted(set(old_days) | set(window))
    gaps = [days[i] for i in range(1, len(days))
            if datetime.date.fromisoformat(days[i]) - datetime.date.fromisoformat(days[i - 1])
            != datetime.timedelta(days=1)]
    if gaps:
        R["warnings"].append("the day list is not contiguous, first break at " + gaps[0])

    fresh = sorted({(l, k) for (l, k, d) in cells} - set(series))
    if fresh:
        # a new site must never appear silently: name it in the report and in the log
        R["warnings"].append("NEW series in the broker feed, added to the matrix: "
                             + ", ".join("%s %s" % (l, k) for l, k in fresh))
        log("NEW series:", fresh)
    for k in fresh:
        series[k] = {}

    out = ["DAYS:" + ",".join(days)]
    for (loc, kind) in sorted(series):
        row = []
        for d in days:
            if d in window:
                row.append(cells.get((loc, kind, d), ""))      # the window is authoritative
            else:
                row.append(series[(loc, kind)].get(d, ""))     # frozen history
        out.append("%s~%s:%s" % (loc, kind, ",".join(row)))
    out.append("DEV:")
    out += [l for l in lines[devi + 1:] if l.strip()]
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    R["sites_series"] = len(series)
    return days


def extend_dev(path, devs_csv, window, R):
    """Mapal's deviations endpoint returns a null location on this route, so these rows are usually
    unusable. Append only the ones that DO name a location. Never drop a committed line."""
    txt = open(path, encoding="utf-8").read().rstrip("\n")
    head, _, tail = txt.partition("DEV:")
    have = {l for l in tail.strip().split("\n") if l.strip()}
    keys = {tuple(l.split("|")[:3]) for l in have}
    added = 0
    if os.path.exists(devs_csv):
        with open(devs_csv, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                loc = norm_text(r.get("location"))
                kind = norm_text(r.get("kind")).lower()
                d = norm_date(r.get("date")) or ""
                if not loc or kind not in KINDS or d not in window or (loc, kind, d) in keys:
                    continue
                state = "open" if (r.get("open_closed") or "").strip() == "open" else "closed"
                have.add("|".join([loc, kind, d, "MISS", state]))
                keys.add((loc, kind, d))
                added += 1
    R["deviations_added"] = added
    open(path, "w", encoding="utf-8").write(head + "DEV:\n" + "\n".join(sorted(have)) + "\n")


def extend_factory(path, agg, days, window, R):
    lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    src = lines[0]
    old_days = lines[1].split(":", 1)[1].split(",")
    old = {}
    for ln in lines[2:]:
        key, vals = ln.split(":", 1)
        old[key] = dict(zip(old_days, vals.split(",")))

    out = [src, "DAYS:" + ",".join(days)]
    for kind in ("pork", "chicken"):
        vals, counts = [], []
        for d in days:
            if d in window:
                xs = agg.get((d, kind), [])
                vals.append("" if not xs else ("%g" % mean_half_up(xs)))
                counts.append(str(len(xs)))
            else:
                vals.append(old.get(kind, {}).get(d, ""))
                counts.append(old.get(kind + "N", {}).get(d, "0"))
        out.append("%s:%s" % (kind, ",".join(vals)))
        out.append("%sN:%s" % (kind, ",".join(counts)))
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    R["factory_readings_in_window"] = sum(len(v) for v in agg.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--sources", required=True, help="dir written by fetch_broth_sources.py")
    ap.add_argument("--report", help="repo-relative path for the run report, shipped with the commit")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    data = os.path.join(repo, "data", "broth")
    today = datetime.date.today().isoformat()
    R = {"run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "today": today, "warnings": [], "shipped": [], "result": None}

    cells_csv = os.path.join(a.sources, "broth_cells.csv")
    fac_csv = os.path.join(a.sources, "refractometer.csv")
    for p in (cells_csv, fac_csv):
        if not os.path.exists(p):
            log("missing source %s" % p); return 2

    cells, src_days, _ = load_cells(cells_csv, R)
    if not src_days:
        log("the broker feed carried no site cells at all"); return 2

    # RULE 1: the window is every source day that is already OVER. Today is still being filed, so
    # it never enters the matrix; tomorrow's run picks it up complete.
    window = [d for d in src_days if d < today]
    R["window"] = [window[0], window[-1]] if window else None
    if not window:
        R["result"] = "the broker feed holds nothing but today, nothing to bake"
        print(json.dumps(R)); return 0

    live_m = os.path.join(HERE, "live_matrix.txt")
    fac_m = os.path.join(HERE, "factory_matrix.txt")
    before = read_matrix_days(live_m)
    R["matrix_before"] = [before[0], before[-1]]

    # GUARD: A PARSE REGRESSION MUST NEVER BLANK A DAY THAT ALREADY HAS DATA. The window is
    # rewritten wholesale from the feed, so if the feed suddenly parses to nothing (a renamed
    # column, a date cell that changed type) the matrix would quietly lose real readings and the
    # tab would render zeros. Compare like for like before writing a byte.
    wset = set(window)
    head0 = open(live_m, encoding="utf-8").read().split("DEV:")[0].rstrip("\n").split("\n")
    d0 = head0[0].split(":", 1)[1].split(",")
    ix = [i for i, d in enumerate(d0) if d in wset]
    had = 0
    for ln in head0[1:]:
        v = ln.split(":", 1)[1].split(",")
        had += sum(1 for i in ix if v[i].strip())
    got = sum(1 for (l, k, d), v in cells.items() if d in wset and v.strip())
    R["window_values"] = {"committed": had, "feed": got}
    if had and got < had * 0.8:
        log("the feed carries %d site values for %s to %s where the committed matrix has %d "
            "— refusing to blank days" % (got, window[0], window[-1], had))
        return 3

    fac_agg = load_factory(fac_csv, wset)
    if not fac_agg:
        log("the refractometer sheet produced no readings at all for %s to %s — refusing to blank "
            "the factory line (check the Date column type and the Product Name header)"
            % (window[0], window[-1]))
        return 3

    days = extend_sites(live_m, cells, wset, R)
    extend_dev(live_m, os.path.join(a.sources, "broth_deviations.csv"), wset, R)
    extend_factory(fac_m, fac_agg, days, wset, R)
    if read_matrix_days(fac_m) != days:
        log("factory DAYS does not match sites DAYS after extending"); return 3
    R["matrix_after"] = [days[0], days[-1]]

    # ---------------- BAKE (every week, oldest first, so the two-strike streak is right) --------
    out = tempfile.mkdtemp(prefix="brothbake")
    r = run([sys.executable, os.path.join(HERE, "bake_broth.py"), "--out", out], cwd=HERE)
    if r.returncode != 0:
        log(r.stdout[-1500:]); log(r.stderr[-1500:]); return 4
    R["bake_log"] = [l for l in r.stdout.strip().split("\n") if l.strip()]

    new_index = json.load(open(os.path.join(out, "index.json")))
    try:
        old_index = json.load(open(os.path.join(data, "index.json")))
    except Exception:
        old_index = {"weeks": []}
    published = {w["monday"]: w for w in old_index.get("weeks", [])}

    # RULE 2: only weeks the window touches may move. Everything older keeps what it published.
    floor = monday(window[0])
    ship, weeks, final = [], [], {}
    for w in new_index["weeks"]:                          # newest first
        mon = w["monday"]
        src = os.path.join(out, w["file"])
        dst = os.path.join(data, w["file"])
        if mon >= floor:                                  # inside the window: the bake wins
            if (not os.path.exists(dst)) or open(src, "rb").read() != open(dst, "rb").read():
                shutil.copyfile(src, dst)
                ship.append(os.path.relpath(dst, repo))
                weeks.append(w)
            final[mon] = w
        elif os.path.exists(dst):                         # older week, already published: freeze it
            final[mon] = published.get(mon, w)
        else:                                             # older week we have never shipped at all
            shutil.copyfile(src, dst)
            ship.append(os.path.relpath(dst, repo))
            weeks.append(w)
            final[mon] = w
    for mon, w in published.items():                      # never lose a week the index already had
        if mon not in final and os.path.exists(os.path.join(data, w["file"])):
            final[mon] = w
    merged = sorted(final.values(), key=lambda w: w["monday"], reverse=True)
    for w in merged:
        if not os.path.exists(os.path.join(data, w["file"])):
            log("index would point at a missing file: %s" % w["file"]); return 3

    idx = {"generated_at": today,
           "note": ("Broth score by week for the AM Control Centre picker. Newest first. "
                    "Rebuilt every morning by .github/workflows/broth-tab.yml: the current week is "
                    "rewritten in place, a new week is prepended each Monday, and weeks older than "
                    "the Mapal 8 day window are never restated."),
           "latest": merged[0]["monday"] if merged else None,
           "weeks": merged}
    idx_path = os.path.join(data, "index.json")
    new_bytes = json.dumps(idx, indent=1).encode()
    if not os.path.exists(idx_path) or open(idx_path, "rb").read() != new_bytes:
        open(idx_path, "wb").write(new_bytes)
        ship.append(os.path.relpath(idx_path, repo))

    R["weeks_rebuilt"] = [w["monday"] for w in weeks]
    R["latest_day"] = days[-1]
    R["headline"] = ({"week": weeks[0]["monday"], "days": weeks[0]["days"], "p1": weeks[0]["p1"],
                      "tonkotsu_in": weeks[0]["tonkotsu_in"], "chicken_in": weeks[0]["chicken_in"]}
                     if weeks else None)
    shutil.rmtree(out, ignore_errors=True)

    for m in (live_m, fac_m):
        rel = os.path.relpath(m, repo)
        if run(["git", "diff", "--quiet", "--", rel], cwd=repo).returncode != 0:
            ship.append(rel)

    data_ship = list(ship)
    if a.report:
        # The report ships on EVERY run, changed or not. It is the heartbeat: without it there is
        # no way to tell "ran and found nothing new" from "has not run for four days", which is
        # exactly the failure this whole workflow exists to stop.
        R["result"] = ("no data change: live already carries " + days[-1]) if not data_ship \
                      else "shipping %d file(s)" % len(data_ship)
        rp = os.path.join(repo, a.report)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        json.dump(R, open(rp, "w"), indent=1)
        ship.append(a.report)
    if not ship:
        R["result"] = "no data change and no report path: nothing to commit"
        print(json.dumps(R)); return 0

    # ---------------- COMMIT + PUSH ----------------
    run(["git", "config", "user.name", "maki-nori"], cwd=repo)
    run(["git", "config", "user.email", "michael@makiramen.com"], cwd=repo)
    run(["git", "add", "--"] + ship, cwd=repo)
    h = R["headline"]
    head = ("Broth tab: w/c %s to %s (%d day%s, tonkotsu %.1f%% in spec, chicken %.1f%%, %d P1)"
            % (h["week"], days[-1], h["days"], "" if h["days"] == 1 else "s",
               h["tonkotsu_in"], h["chicken_in"], h["p1"])) if h else \
           ("Broth tab run %sZ: nothing changed — live is current to %s"
            % (R["run_at"][11:16], days[-1]))
    body = ["Scheduled run (broth_cloud_run.py). Files: " + ", ".join(ship),
            "Matrix %s to %s. Weeks rebuilt: %s. Older weeks were deliberately not restated."
            % (days[0], days[-1], ", ".join(R["weeks_rebuilt"]) or "none")]
    body += ["⚠️ " + w for w in R["warnings"]]
    body += ["", "Co-Authored-By: Claude <noreply@anthropic.com>"]
    run(["git", "commit", "-q", "-m", head, "-m", "\n".join(body)], cwd=repo)
    R["commit"] = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    R["commit_title"] = head
    if a.no_push:
        R["result"] = "built and committed locally, --no-push"; print(json.dumps(R)); return 20
    tok = os.environ.get("GH_TOKEN")
    if not tok:
        R["result"] = "built and committed locally but NO GH_TOKEN — not pushed"; print(json.dumps(R)); return 20
    env = dict(os.environ); env["GIT_TERMINAL_PROMPT"] = "0"
    url = "https://x-access-token:%s@github.com/makiramen/ops.git" % tok
    pr = run(["git", "push", url, "HEAD:main"], cwd=repo, env=env)
    if pr.returncode != 0:
        msg = (pr.stderr + pr.stdout).replace(tok, "***")
        if "fetch first" in msg or "non-fast-forward" in msg or "rejected" in msg:
            run(["git", "fetch", url, "main"], cwd=repo, env=env)
            if run(["git", "rebase", "FETCH_HEAD"], cwd=repo, env=env).returncode == 0:
                pr = run(["git", "push", url, "HEAD:main"], cwd=repo, env=env)
                R["commit"] = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
                msg = (pr.stderr + pr.stdout).replace(tok, "***")
            else:
                run(["git", "rebase", "--abort"], cwd=repo)
        if pr.returncode != 0:
            R["result"] = "PUSH FAILED: " + msg[-600:]; print(json.dumps(R)); return 20
    remote = run(["git", "ls-remote", url, "refs/heads/main"], cwd=repo, env=env).stdout.split()
    R["pushed"] = bool(remote) and remote[0] == R["commit"]
    R["result"] = ("SHIPPED " + R["commit"][:7]) if R["pushed"] else \
                  "push returned ok but remote HEAD != our commit — CHECK"
    print(json.dumps(R))
    return 0


if __name__ == "__main__":
    sys.exit(main())
