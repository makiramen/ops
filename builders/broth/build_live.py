#!/usr/bin/env python3
"""
Build broth.json.

MODEL (Michael, 27 Aug 26, corrected):
  Site spec, measured AFTER the restaurant adds water:
      chicken   5.0 to 7.0
      tonkotsu  6.0 to 7.0
  Sites are scored against THAT window and nothing else.

  The factory is shown at the top as its own reference line, NOT as a comparator.
  Factory column F is read after ice at the factory; sites dilute again on site,
  so the two numbers are not on the same scale and must not be differenced.

Sites   <- live_matrix.txt    (Mapal public API, Chicken/Tonkotsu Broth Check)
Factory <- factory_matrix.txt (deanops batching form Sheet, column F)
"""
import json, os, statistics, sys
from regions import REGIONS, resolve

SPEC = {"chicken": (4.0, 5.0), "pork": (6.0, 7.0)}     # site spec, after water
#   chicken corrected 4.0-5.0 by Michael 27 Aug 26 (he first said 5-7, then 4-5)
MAPAL_FLOOR = {"chicken": 4.0, "pork": 6.0}            # what Mapal actually flags today
W_SPEC, W_DISC, W_FLAT = 0.60, 0.20, 0.20
RAG = (90, 70)
FACTORY = "AA Factory1 Limited"
KINDS = ("pork", "chicken")            # tonkotsu leads, Michael 27 Aug 26
WINDOW_DAYS = 7                        # weekly run, Michael 27 Aug 26
# CLI: --days 2026-08-17,...,2026-08-23  bakes exactly those days (used by bake_broth.py
#      to emit one file per ISO week).   --out PATH  writes the snapshot elsewhere.
_ARG_DAYS = None
_OUT = "broth.json"
_a = sys.argv[1:]
for _i, _v in enumerate(_a):
    if _v == "--days" and _i + 1 < len(_a): _ARG_DAYS = set(_a[_i + 1].split(","))
    if _v == "--out" and _i + 1 < len(_a):  _OUT = _a[_i + 1]
if _ARG_DAYS: WINDOW_DAYS = None
MIN_N_LONG = 10                        # rules that need a longer base than a week gives
FLATLINE_LOOKBACK = 14                 # flatline is about BEHAVIOUR over time, so it always
                                       # looks back a fortnight even on a weekly run. On 7 days
                                       # a genuinely stable site looks identical to one that is
                                       # not measuring, and that produced 3 false alarms.
EXCLUDE = {"Maki Property Ltd"}        # not a kitchen we score, Michael 27 Aug 26

def read_matrix(path, window=None):
    kv, days = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("SOURCE"): continue
        if line.startswith("DEV:"): break
        k, v = line.split(":", 1)
        if k == "DAYS": days = v.split(",")
        else: kv[k] = v.split(",")
    if _ARG_DAYS and days and window is None:
        keepix = [i for i, d in enumerate(days) if d in _ARG_DAYS]
        days = [days[i] for i in keepix]
        kv = {k: [v[i] for i in keepix] for k, v in kv.items()}
        return days, kv
    w = WINDOW_DAYS if window is None else window
    if days and window is not None and _ARG_DAYS:
        # The flatline look-back must END AT THE END OF THE WEEK BEING BAKED, not at the end of
        # the matrix file. It used to be the file's tail, so simply appending a day silently
        # restated the flatline cases of every older week (03/09/26: w/c 24/08 moved 19 P1 to 18
        # for no reason but the file growing two columns). Anchoring it to the week makes a baked
        # week reproducible forever, which is what lets the cloud run freeze older weeks.
        end = max(_ARG_DAYS)
        keepix = [i for i, d in enumerate(days) if d <= end]
        days = [days[i] for i in keepix]
        kv = {k: [v[i] for i in keepix] for k, v in kv.items()}
    if days and w and len(days) > w:
        keep = len(days) - w
        days = days[keep:]
        kv = {k: v[keep:] for k, v in kv.items()}
    return days, kv

# ---------------------------------------------------------------- factory (reference only)
fdays, fkv = read_matrix("factory_matrix.txt")
factory, cells = {}, []
for kind in KINDS:
    nums = []
    for d, v, n in zip(fdays, fkv[kind], fkv[kind + "N"]):
        v, n = v.strip(), int(n) if n.strip() else 0
        if not v and n == 0: continue          # no production that day
        val = float(v)
        nums.append(val)
        cells.append({"scope": "factory", "loc": FACTORY, "kind": kind, "d": d,
                      "v": val, "n": n, "miss": 0, "batches": n})
    mean = statistics.mean(nums); sd = statistics.pstdev(nums)
    cv = sd / mean if mean else 0
    # No factory spec exists, so the factory is scored on how tightly it holds its
    # OWN line: coefficient of variation. 2% or better is 100, 8% or worse is 0.
    cons = round(100 * max(0.0, min(1.0, (0.08 - cv) / 0.06)), 1)
    factory[kind] = {"mean": round(mean, 2), "min": min(nums), "max": max(nums),
                     "sd": round(sd, 3), "cv_pct": round(100 * cv, 2),
                     "consistency": cons,
                     "rag": "g" if cons >= 85 else "a" if cons >= 65 else "r",
                     "days": len(nums),
                     "batches": sum(int(x) for x in fkv[kind + "N"] if x.strip()),
                     "spread": round(max(nums) - min(nums), 2)}

# ---------------------------------------------------------------- sites
sdays, skv = read_matrix("live_matrix.txt")
_ldays, _lkv = read_matrix("live_matrix.txt", FLATLINE_LOOKBACK)
long_series = {}
for _k, _v in _lkv.items():
    _loc, _kind = _k.split("~")
    if _loc in EXCLUDE: continue
    long_series[(_loc, _kind)] = [float(x) for x in _v if x.strip()]

series = {}
for key, vals in skv.items():
    loc, kind = key.split("~")
    if loc in EXCLUDE: continue
    lo, hi = SPEC[kind]
    series[(loc, kind)] = []
    for d, v in zip(sdays, vals):
        v = v.strip()
        val = float(v) if v else None
        series[(loc, kind)].append(val)
        band = None if val is None else ("under" if val < lo else "over" if val > hi else "in")
        cells.append({"scope": "site", "loc": loc, "kind": kind, "d": d, "v": val,
                      "n": 1, "miss": 0 if val is not None else 1, "band": band})

devs = []
for l in open("live_matrix.txt", encoding="utf-8").read().split("DEV:")[1].strip().split("\n"):
    if not l.strip(): continue
    loc, kind, d, v, state = l.split("|")
    if loc in EXCLUDE: continue
    devs.append({"loc": loc, "kind": kind, "d": d, "v": None if v == "MISS" else float(v),
                 "state": "Closed" if state == "closed" else "Open", "open": state == "open",
                 "fix": "no reading registered" if v == "MISS" else "below the Mapal floor"})
devs.sort(key=lambda x: x["d"], reverse=True)

scores = []
for (loc, kind), vals in sorted(series.items()):
    nums = [v for v in vals if v is not None]
    if not nums: continue
    lo, hi = SPEC[kind]
    under = sum(1 for v in nums if v < lo)
    over  = sum(1 for v in nums if v > hi)
    inn   = len(nums) - under - over
    spec  = inn / len(nums)
    disc  = len(nums) / len(vals)
    distinct = len(set(nums))
    flat = 0.0 if distinct <= 1 else min(1.0, (distinct - 1) / 3.0)
    sc = round(100 * (W_SPEC * spec + W_DISC * disc + W_FLAT * flat), 1)
    mean = statistics.mean(nums)
    meta = resolve(loc)
    scores.append({"scope": "site", "loc": loc, "kind": kind, "score": sc,
        "code": meta["code"], "site": meta["site"], "region": meta["region"],
        "unconfirmed": meta["unconfirmed"],
        "rag": "g" if sc >= RAG[0] else "a" if sc >= RAG[1] else "r",
        "mean": round(mean, 2), "spec_lo": lo, "spec_hi": hi,
        "verdict": "under" if mean < lo else "over" if mean > hi else "in",
        "in_spec_pct": round(100 * spec, 1),
        "under": under, "over": over, "in": inn,
        "readings": len(nums), "checks": len(vals), "missed": len(vals) - len(nums),
        "discipline": round(100 * disc, 1), "distinct": distinct,
        # flatline uses FLATLINE_LOOKBACK, the same basis as the flag rule, so the
        # KPI and the case list can never disagree
        "flatline": len(set(long_series.get((loc, kind), nums))) <= 1
                    and len(long_series.get((loc, kind), nums)) >= 10,
        "open_dev": sum(1 for x in devs if x["loc"] == loc and x["kind"] == kind and x["open"]),
        "days": len(vals)})

# ---------------------------------------------------------------- inconsistency engine
# A league table ranks everyone, including the 20 sites doing nothing wrong.
# This flags only what actually stands out. Michael, 27 Aug 26.
SEV = {"high": 3, "med": 2, "low": 1}
flags = []

def add(sev, kind, loc, ftype, headline, detail):
    m = resolve(loc)
    flags.append({"sev": sev, "rank": SEV[sev], "kind": kind, "loc": loc,
                  "code": m["code"], "site": m["site"], "region": m["region"],
                  "type": ftype, "headline": headline, "detail": detail})

for kind in KINDS:
    lo, hi = SPEC[kind]
    rows = [r for r in scores if r["kind"] == kind]
    means = [r["mean"] for r in rows]
    gmean = statistics.mean(means)
    gsd = statistics.pstdev(means) or 1e-9
    sds = []
    for r in rows:
        nums = [v for v in series[(r["loc"], kind)] if v is not None]
        sds.append(statistics.pstdev(nums))
    med_sd = statistics.median(sds)

    for r, own_sd in zip(rows, sds):
        loc = r["loc"]
        nums = [v for v in series[(loc, kind)] if v is not None]
        n = len(nums)

        # 1. out of spec
        if r["under"] or r["over"]:
            out = r["under"] + r["over"]
            share = 100 * out / n
            sev = "high" if share >= 25 else "med"
            way = "under" if r["under"] >= r["over"] else "over"
            add(sev, kind, loc, "Out of spec",
                f"{out} of {n} readings {way} the {lo} to {hi} window",
                f"mean {r['mean']}, {r['under']} under, {r['over']} over")

        # 2. outlier against the rest of the estate
        z = (r["mean"] - gmean) / gsd
        if abs(z) >= 1.5:
            add("high" if abs(z) >= 2 else "med", kind, loc, "Outlier vs estate",
                f"mean {r['mean']} against an estate average of {round(gmean,2)}",
                f"{abs(round(z,1))} standard deviations {'above' if z>0 else 'below'} the group")

        # 3. flatline, judged over FLATLINE_LOOKBACK days not the scoring window
        ln = long_series.get((loc, kind), nums)
        if len(set(ln)) <= 1 and len(ln) >= 10:
            add("high", kind, loc, "Flatline",
                f"exactly {ln[0]} on every one of {len(ln)} readings over {FLATLINE_LOOKBACK} days",
                "no variation at all over a fortnight, so the meter is probably not being used")

        # 4. (rounding is tracked estate-wide below, not per site: whole numbers
        #     turned out to be the NORM, so flagging each one is noise not signal)
        r["whole_only"] = all(float(v).is_integer() for v in nums)

        # 5. volatile: swinging far more than the estate norm
        if n >= MIN_N_LONG and med_sd > 0 and own_sd >= 2.5 * med_sd and own_sd >= 0.35:
            add("med", kind, loc, "Volatile",
                f"day to day spread of {round(own_sd,2)} against an estate norm of {round(med_sd,2)}",
                f"range {min(nums)} to {max(nums)} inside a single fortnight")

        # 6. step change between the two halves of the window
        h = n // 2
        if n >= MIN_N_LONG and h >= 3:
            a1, a2 = statistics.mean(nums[:h]), statistics.mean(nums[-h:])
            if abs(a2 - a1) >= 0.5:
                add("med", kind, loc, "Step change",
                    f"moved from {round(a1,2)} to {round(a2,2)} across the fortnight",
                    "not noise, the level itself has shifted")

        # 7. missed checks
        if r["missed"]:
            add("med" if r["missed"] >= 2 else "low", kind, loc, "Missed checks",
                f"{r['missed']} of {r['checks']} checks with no reading",
                "the check was scheduled and nothing was entered")

flags.sort(key=lambda f: (-f["rank"], f["region"], f["loc"]))

whole_lines = [r for r in scores if r.get("whole_only")]
resolution = {"whole_only": len(whole_lines), "lines": len(scores),
    "pct": round(100 * len(whole_lines) / len(scores), 1),
    "note": ("Most of the estate only ever records whole numbers. A refractometer reads "
             "to one decimal, so a whole number is a rounded number. On a window only "
             "1.0 or 2.0 wide, rounding to the nearest whole unit is a big fraction of "
             "the tolerance and it hides small drifts entirely. Sites already reporting "
             "decimals prove the meters can do it.")}

# ---------------------------------------------------------------- remedial cases
# Flags are symptoms. A site+broth with four flags is ONE problem, not four jobs.
# Collapse to a case, prescribe the response, name the owner, set a priority, and
# be willing to say "no action". Michael, 27 Aug 26: "we need remedial responses".
OWNER = {"scotland": "Penny (DEC Scotland & Newcastle)",
         "midlands": "Artur Mroczkowski (DEC North England & Midlands)",
         "south":    'Srawut "O" Chairipu (DEC South England)',
         "franchise":"Matthew Jenner (BDM, via the franchisee)",
         "unmapped": "unassigned"}

def prescribe(kind, types, r, lo, hi):
    """Return (headline, response, evidence) for the dominant problem."""
    over  = r["over"] > r["under"]
    share = 100 * (r["under"] + r["over"]) / max(1, r["readings"])
    if "Flatline" in types:
        return ("Not measuring",
            "Unannounced visit. Watch the check being taken, then take it yourself on the "
            "same pot and compare. If the refractometer is missing, broken or uncalibrated, "
            "replace it before anything else. Do not treat this as a broth problem until a "
            "real reading exists.",
            "one DEC-witnessed reading, plus 5 consecutive days of varying readings after")
    if "Out of spec" in types and share >= 25:
        if over:
            return ("Consistently too strong",
                f"Method check at the pass. Watch one batch made start to finish: what vessel "
                f"is the water measured with, and is the ratio the current spec? Too strong "
                f"almost always means under-watering a concentrate. Re-read with the chef "
                f"present and agree the ratio in writing before you leave.",
                f"7 consecutive readings inside {lo} to {hi}")
        return ("Consistently too weak",
            f"Method check at the pass, then a service check. Too weak is either over-watering "
            f"at make-up or topping the pot up during service. Watch both. If they are topping "
            f"up, that is a par and prep-quantity problem, not a recipe problem.",
            f"7 consecutive readings inside {lo} to {hi}")
    if "Step change" in types:
        return ("Level has moved",
            "Ask the Head Chef what changed in the last fortnight: new delivery batch, new "
            "starter, different jug, staff change, new opening routine. The level shifted, so "
            "something specific changed. Find it before it drifts out of the window.",
            "the new level holds inside the window for 7 days, or is corrected back")
    if "Volatile" in types:
        return ("Unstable batch to batch",
            "Different people are getting different answers on the same broth. Re-brief the "
            "whole section together rather than one chef, and check they are all reading the "
            "meter the same way.",
            "day to day spread back in line with the estate norm")
    if "Outlier vs estate" in types:
        edge = "bottom" if r["mean"] <= (lo + hi) / 2 else "top"
        return (f"Sitting on the {edge} edge",
            f"Technically inside {lo} to {hi} but parked against the {edge} of it and well "
            f"away from where the rest of the estate sits. There is no margin left, so one "
            f"ordinary bad day puts it out. Check the ratio and move it toward the middle of "
            f"the window rather than waiting for it to fail.",
            f"mean moved toward {round((lo+hi)/2,1)} and holding")
    if "Out of spec" in types:
        return ("Occasional miss",
            "No visit. Mention it on the next scheduled call and watch the next run. One or "
            "two readings out is a shift, not a system.", "next run shows it gone")
    if "Missed checks" in types:
        return ("Check not completed",
            "Compliance nudge only. Once the Mapal comparer is set correctly this raises "
            "itself as a deviation with an owner attached.", "no missed checks next run")
    return ("Review", "Look at it on the next run.", "next run")

cases = []
for r in scores:
    mine = [f for f in flags if f["loc"] == r["loc"] and f["kind"] == r["kind"]]
    if not mine: continue
    types = {f["type"] for f in mine}
    hi_n  = sum(1 for f in mine if f["sev"] == "high")
    med_n = sum(1 for f in mine if f["sev"] == "med")
    lo_, hi_ = SPEC[r["kind"]]
    head, resp, ev = prescribe(r["kind"], types, r, lo_, hi_)
    if hi_n:                        priority, when = "P1", "this week"
    elif med_n >= 2:                priority, when = "P1", "this week"
    elif med_n == 1:                priority, when = "P2", "this month"
    else:                           priority, when = "P3", "watch only, no action"
    if types == {"Missed checks"}:  priority, when = "P3", "watch only, no action"
    cases.append({"loc": r["loc"], "code": r["code"], "site": r["site"],
        "region": r["region"], "kind": r["kind"], "priority": priority, "when": when,
        "headline": head, "response": resp, "evidence": ev,
        "owner": OWNER.get(r["region"], "unassigned"),
        "mean": r["mean"], "in_spec_pct": r["in_spec_pct"],
        "under": r["under"], "over": r["over"], "missed": r["missed"],
        "flags": sorted(types), "flag_count": len(mine)})
# Two strikes and it goes to the EC. Michael, 27 Aug 26. State lives in
# case_history.json beside this script so each run knows what was open last time.
EC = "Matt Polak (Executive Chef)"
HIST = os.path.join(os.path.dirname(_OUT) or ".", "case_history.json")
try:
    hist = json.load(open(HIST))
except Exception:
    hist = {}
seen_now = set()
for c in cases:
    key = c["loc"] + "~" + c["kind"]
    seen_now.add(key)
    prev = hist.get(key, {})
    # only a P1 or P2 carries a streak; a watch-only case does not accumulate
    c["runs_open"] = (prev.get("runs_open", 0) + 1) if c["priority"] in ("P1", "P2") else 1
    c["first_seen"] = prev.get("first_seen", sdays[-1])
    if c["runs_open"] >= 2 and c["priority"] == "P1":
        c["escalated"] = True
        c["owner_original"] = c["owner"]
        c["owner"] = EC + " (escalated from " + c["owner"].split(" (")[0] + ")"
        c["escalation_note"] = ("open for %d consecutive runs, escalated to the Executive Chef"
                                % c["runs_open"])
    else:
        c["escalated"] = False
hist = {k: v for k, v in hist.items() if k in seen_now}
for c in cases:
    hist[c["loc"] + "~" + c["kind"]] = {"runs_open": c["runs_open"],
                                        "first_seen": c["first_seen"],
                                        "priority": c["priority"], "last_run": sdays[-1]}
json.dump(hist, open(HIST, "w"), indent=1)

prio_rank = {"P1": 0, "P2": 1, "P3": 2}
cases.sort(key=lambda c: (prio_rank[c["priority"]], not c.get("escalated"), c["region"], c["code"] or "zz"))

estate = {}
for kind in KINDS:
    rs = [r for r in scores if r["kind"] == kind]
    tot = sum(r["readings"] for r in rs)
    estate[kind] = {"spec": list(SPEC[kind]),
        "readings": tot,
        "in_pct": round(100 * sum(r["in"] for r in rs) / tot, 1),
        "under_pct": round(100 * sum(r["under"] for r in rs) / tot, 1),
        "over_pct": round(100 * sum(r["over"] for r in rs) / tot, 1),
        "mean": round(statistics.mean([r["mean"] for r in rs]), 2),
        "sites_under": sum(1 for r in rs if r["verdict"] == "under"),
        "sites_over": sum(1 for r in rs if r["verdict"] == "over"),
        "sites_in": sum(1 for r in rs if r["verdict"] == "in"),
        "sites": len(rs)}

# How much of the real spec is Mapal currently blind to?
blind = {"under_missed": 0, "over_missed": 0, "flagged": 0, "out_of_spec": 0}
for c in cells:
    if c["scope"] != "site" or c.get("v") is None: continue
    k, v = c["kind"], c["v"]
    lo, hi = SPEC[k]
    if v < lo:
        blind["out_of_spec"] += 1
        if v >= MAPAL_FLOOR[k]: blind["under_missed"] += 1
        else: blind["flagged"] += 1
    elif v > hi:
        blind["out_of_spec"] += 1
        blind["over_missed"] += 1          # Mapal has no upper limit at all
blind["missed"] = blind["under_missed"] + blind["over_missed"]
blind["missed_pct"] = round(100 * blind["missed"] / blind["out_of_spec"], 1) if blind["out_of_spec"] else 0

# regional rollup: the EC function is owned by region, so the league is read by region
regions = {}
for key, meta in REGIONS.items():
    rs = [r for r in scores if r["region"] == key]
    if not rs: continue
    sites = sorted({r["loc"] for r in rs})
    row = {"key": key, "label": meta["label"], "dec": meta["dec"], "am": meta["am"],
           "order": meta["order"], "sites": len(sites), "lines": len(rs),
           "off_spec_sites": len({r["loc"] for r in rs if r["verdict"] != "in"})}
    for kind in KINDS:
        ks = [r for r in rs if r["kind"] == kind]
        tot = sum(r["readings"] for r in ks)
        row[kind] = None if not tot else {
            "in_pct": round(100 * sum(r["in"] for r in ks) / tot, 1),
            "under": sum(r["under"] for r in ks), "over": sum(r["over"] for r in ks),
            "mean": round(statistics.mean([r["mean"] for r in ks]), 2),
            "sites_off": sum(1 for r in ks if r["verdict"] != "in"), "sites": len(ks)}
    tot_all = sum(r["readings"] for r in rs)
    row["in_pct"] = round(100 * sum(r["in"] for r in rs) / tot_all, 1) if tot_all else None
    regions[key] = row

# Estate-wide actions: things that are nobody's site problem and everybody's problem
estate_actions = [
    {"id": "mapal-comparer", "priority": "P1", "owner": "Michael / Ross",
     "title": "Set the Mapal comparer to the real windows",
     "why": ("Mapal catches %d of %d out-of-spec readings and misses %d. It has no upper "
             "limit configured at all, and over-strength is now essentially the whole "
             "problem." % (blind["flagged"], blind["out_of_spec"], blind["missed"])),
     "do": ("Change the Chicken Broth Check comparer to %s-%s and the Tonkotsu Broth Check "
            "to %s-%s. Every one of those misses then raises itself as a deviation at the "
            "point of failure, on the chef's screen, with a corrective action required."
            % (SPEC["chicken"][0], SPEC["chicken"][1], SPEC["pork"][0], SPEC["pork"][1])),
     "effect": "turns this whole page from a fortnightly report into a live control"},
    {"id": "decimals", "priority": "P2", "owner": "Michael / Ross",
     "title": "Require one decimal place on both broth checks",
     "why": ("%d of %d site lines (%s%%) only ever record whole numbers, on windows just "
             "1.0 wide. A site writing 5 on a 4 to 5 chicken window is sitting exactly on "
             "the ceiling, and small drifts are invisible."
             % (resolution["whole_only"], resolution["lines"], resolution["pct"])),
     "do": "Set the answer option to one decimal, and say so in the task text.",
     "effect": "makes the window usable and the drift detectable"},
    {"id": "factory-spec", "priority": "P2", "owner": "Ross",
     "title": "Set a factory target band",
     "why": ("The factory has no spec, so it can only be scored on steadiness. It could "
             "slide from 8.30 to 7.60 over a month, smoothly, and keep scoring in the 90s."),
     "do": "Give a min and max for factory tonkotsu and chicken after ice.",
     "effect": "the factory panel scores against a target instead of just measuring steadiness"},
]


snap = {"range": {"start": sdays[0], "end": sdays[-1]},
    "mapal_blind": blind,
    "regions": regions,
    "model": "site_spec_window",
    "window_days": WINDOW_DAYS or len(sdays),
    "days": sdays,
    "dormant_rules": ([] if len(sdays) >= MIN_N_LONG else
        ["Step change", "Volatile"]),
    "dormant_note": ("Step change and Volatile need at least %d readings to mean anything "
                     "and a %d day window does not give that, so they stay quiet on a weekly "
                     "run. Flatline always looks back %d days regardless, because on a week a "
                     "genuinely steady site is indistinguishable from one that is not "
                     "measuring." % (MIN_N_LONG, len(sdays), FLATLINE_LOOKBACK)),
    "escalation": {"rule": "a P1 still open on the next run goes to the Executive Chef",
                   "to": "Matt Polak (Executive Chef)"},
    "spec": {k: list(v) for k, v in SPEC.items()},
    "spec_note": "site spec, measured after the restaurant adds water",
    "mapal_floor": MAPAL_FLOOR,
    "mapal_gap_note": ("Mapal currently only flags chicken below 4.0 and tonkotsu below 6.0, "
                       "and flags nothing high. So it misses every chicken reading between 4.0 "
                       "and 5.0, and every reading above 7.0, both of which are out of spec."),
    "factory": {"loc": FACTORY, "by_kind": factory,
        "source": "Refractometer Reading (Responses) sheet, column F, auto-fed by the deanops batching form",
        "scored_on": ("consistency only. No factory spec has been set, so the factory is "
                      "judged on how tightly it holds its own line batch to batch, not "
                      "against a target."),
        "note": ("Reference line only. This is the reading after ice AT THE FACTORY. Sites add "
                 "more water before they measure, so these numbers are not on the same scale as "
                 "the site readings below and must not be compared to them. What matters here is "
                 "that the factory holds its own line batch to batch.")},
    "estate": estate,
    "weights": {"in_spec": W_SPEC, "discipline": W_DISC, "consistency": W_FLAT},
    "rag": {"green": RAG[0], "amber": RAG[1]},
    "cells": cells, "deviations": devs, "scores": scores, "flags": flags,
    "resolution": resolution, "cases": cases,
    "estate_actions": estate_actions}
os.makedirs(os.path.dirname(_OUT) or ".", exist_ok=True)
json.dump(snap, open(_OUT, "w"), separators=(",", ":"))

print("FACTORY (reference only, after ice, pre site dilution)")
for k in KINDS:
    f = factory[k]
    print(f"  {k:8s} {f['mean']:5.2f}  consistency {f['consistency']:5.1f} ({f['rag']})  "
          f"cv {f['cv_pct']}%  range {f['min']} to {f['max']}  sd {f['sd']}  "
          f"{f['batches']} batches / {f['days']} days")
print("SITE SPEC (after water)")
for k in KINDS:
    print(f"  {k:8s} {SPEC[k][0]} to {SPEC[k][1]}")
print("\nESTATE vs SITE SPEC")
for k, e in estate.items():
    print(f"  {k:8s} spec {e['spec'][0]} to {e['spec'][1]}  |  in {e['in_pct']}%  "
          f"under {e['under_pct']}%  over {e['over_pct']}%  |  sites: {e['sites_in']} in, "
          f"{e['sites_under']} under, {e['sites_over']} over (of {e['sites']})")
print("\nMAPAL BLIND SPOT")
print(f"  {blind['out_of_spec']} readings are outside the real spec.")
print(f"  Mapal flags {blind['flagged']}. It misses {blind['missed']} ({blind['missed_pct']}%): "
      f"{blind['under_missed']} weak-but-above-its-floor, {blind['over_missed']} over the ceiling it does not have.")
print("\nWORST 14")
for r in sorted(scores, key=lambda r: r["score"])[:14]:
    print(f"  {r['score']:5.1f} {r['rag']}  {r['loc']:24s} {r['kind']:8s} mean {r['mean']:5.2f} "
          f"[{r['verdict']:5s}]  in {r['in_spec_pct']:5.1f}%  under {r['under']} over {r['over']}"
          f"{'  FLATLINE' if r['flatline'] else ''}")

print("\nBY REGION")
for r in sorted(regions.values(), key=lambda x: x["order"]):
    c, k = r.get("chicken"), r.get("pork")
    print(f"  {r['label']:26s} DEC {r['dec']:22s} {r['sites']} sites | "
          f"chicken {(str(c['in_pct'])+'%') if c else '-':>6s} (mean {c['mean'] if c else '-'}, "
          f"{c['sites_off'] if c else 0} off) | "
          f"tonkotsu {(str(k['in_pct'])+'%') if k else '-':>6s} (mean {k['mean'] if k else '-'}, "
          f"{k['sites_off'] if k else 0} off)")

print("\nINCONSISTENCIES:", len(flags), "flags")
from collections import Counter
for t, c in Counter([f["type"] for f in flags]).most_common():
    print(f"  {c:3d}  {t}")
print(f"\nRESOLUTION: {resolution['whole_only']} of {resolution['lines']} site lines "
      f"({resolution['pct']}%) only ever record whole numbers")
print("\nHIGH SEVERITY")
for f in flags:
    if f["sev"] == "high":
        print(f"  {(f['code'] or '?'):5s} {f['site'][:22]:22s} {f['kind']:8s} {f['type']:18s} {f['headline']}")

print("\nREMEDIAL CASES")
from collections import Counter
for pr, c in sorted(Counter([c["priority"] for c in cases]).items()):
    print(f"  {pr}: {c}")
print()
for c in cases:
    if c["priority"] == "P1":
        print(f"  {c['priority']} {(c['code'] or '?'):5s} {c['site'][:20]:20s} {c['kind']:8s} "
              f"{c['headline']:26s} -> {c['owner'].split(' (')[0]}")
