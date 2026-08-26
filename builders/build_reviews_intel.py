#!/usr/bin/env python3
"""build_reviews_intel.py — Reviews Intelligence (Pipe 5c) STEP 2, container/Mac-side.

Turns the flat full-text pull (extract_reviews_fulltext.js -> maki_reviews_full_<date>.json) into
data/reviews_intel.json: one classified record per review plus roster, weekly KPI cross-refs,
annotations and a loud list of everything the rules could NOT classify (the Claude pass input).

  python3 build_reviews_intel.py \
      --full  data/_raw/maki_reviews_full_2026-08-25.json \
      --taxonomy builders/reviews_taxonomy.json \
      --live-dir data/_live_weeks          # all_sites_wc_*.json (roster + KPIs)
      --llm   data/reviews_llm_labels.json  # optional, output of the Claude pass (keyed by review id)
      --annotations data/reviews_annotations.json   # optional, Claude-written commentary per period/scope
      --out   data/reviews_intel.json \
      --needs-review data/_raw/reviews_needs_review_<date>.json

Rules of the house (see standing_rules.md):
  * Every drop is LOUD. Nothing is skipped silently; counts of everything not classified are in meta.
  * Count the sites you need BY NAME (roster), never the rows you got.
  * A review with no text is 'unclassifiable' and stays in the star counts only. Never guessed.
  * IKI2 and M21 have no rows in the source: they appear in the roster with reviews_connected=false.
  * Periods: week = Mon..Sun by RECEIVED date; month/quarter = calendar, by received date.
  * Simple counts (Michael 25/08): one review can carry several issues; each counts once.
"""
import argparse, json, re, sys, os, glob, datetime, collections
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")

REGIONS = {
    "Scotland & Newcastle":    {"id": "scotland", "head": "Ka Ho",        "dam": "Óisín Patrick Darragh"},
    "North England & Midlands":{"id": "north",    "head": "Inka Cheung",  "dam": "Amy Tang"},
    "South England":           {"id": "south",    "head": "Ziang Lin",    "dam": "Kaitlin Docherty"},
}
AM_ALIAS = {"Lincoln": "Ziang Lin", "Lincoln Z.": "Ziang Lin", "Lincoln (Ziang)": "Ziang Lin"}
DISPLAY = {"M1": "Nicolson", "M3": "Fountainbridge", "M6": "Bath Street", "M7": "SJQ Edinburgh",
           "M8": "Renfield", "M9": "Manchester", "M10": "Leeds", "M11": "Leicester", "M12": "Newcastle",
           "M13": "Aberdeen", "M14": "Meadowhall", "M15": "Metrocentre", "M16": "Nottingham",
           "M17": "Lakeside", "M18": "Soho", "M19": "Shoreditch", "M20": "Southampton",
           "M21": "Maki 21", "MakiNori": "Maki Nori", "IKI2": "Ikigai Ramen"}
NOT_IN_SOURCE = {"IKI2": "Ikigai is not wired into the Google Reviews workbook (never has been)."}
# M21 dropped from NOT_IN_SOURCE 25/08/2026: it now HAS a label at source,
# `Maki Birmingham` (first rows 20/08), mapped to M21 with Michael's approval.

CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+|\s+(?=\b(?:but|however|although|though|except|unfortunately)\b)", re.I)
TRANSLATED = re.compile(r"\(Translated by Google\)\s*(.*?)\s*\(Original\)\s*(.*)", re.S)

def log(*a):
    print(*a, file=sys.stderr)

def compile_tax(tax):
    cats = {}
    for ck, c in tax["categories"].items():
        subs = {}
        for sk, s in c["subs"].items():
            subs[sk] = {"label": s["label"], "rx": [re.compile(p, re.I) for p in s["patterns"]],
                        "ov": [re.compile(p, re.I) for p in s.get("overrides", [])]}
        cats[ck] = {"label": c["label"], "owner": c["owner"], "colour": c.get("colour"), "subs": subs}
    praise = {k: {"label": v["label"], "rx": [re.compile(p, re.I) for p in v["patterns"]]} for k, v in tax["praise"].items()}
    dishes = [(name, [re.compile(p, re.I) for p in pats]) for name, pats in tax["dishes"].items()]
    staff_rx = [re.compile(p) for p in tax["staff_name_patterns"]]
    stop = set(x.lower() for x in tax["staff_name_stoplist"])
    cue = re.compile(tax["complaint_cues"], re.I)
    return cats, praise, dishes, staff_rx, stop, cue

def norm_text(t):
    """Returns (text_for_classification, lang_flag, original_if_translated)."""
    if not t:
        return "", "none", None
    m = TRANSLATED.search(t)
    if m:
        return m.group(1).strip(), "translated_by_google", m.group(2).strip()
    # crude script check: >30% non-ASCII letters => needs translation
    letters = [ch for ch in t if ch.isalpha()]
    if letters:
        non = sum(1 for ch in letters if ord(ch) > 0x24F)  # beyond Latin Extended
        if non / len(letters) > 0.3:
            return t, "needs_translation", None
    return t, "en", None

def clauses_of(text):
    parts = [p.strip() for p in CLAUSE_SPLIT.split(text) if p and p.strip()]
    return parts or [text]

def classify(rec, C):
    cats, praise, dishes, staff_rx, stop, cue = C
    text, lang, original = norm_text(rec["t"])
    out = {"lang": lang}
    if original is not None:
        out["original"] = original
    if not text:
        out.update(issues=[], praise=[], dishes=[], staff=[], complaint_clauses=[], unclassifiable=True)
        return out
    stars = rec["s"]
    cls = clauses_of(text)
    negative = stars <= 3
    issues, issue_hits = [], {}
    praise_hits = set()
    complaint_clauses = []
    for cl in cls:
        is_complaint = negative or bool(cue.search(cl))
        if is_complaint:
            complaint_clauses.append(cl)
            for ck, c in cats.items():
                for sk, s in c["subs"].items():
                    if any(rx.search(cl) for rx in s["rx"]):
                        if not negative and any(rx.search(cl) for rx in s["ov"]):
                            continue  # praise phrased with complaint words on a 4-5* review
                        key = (ck, sk)
                        if key not in issue_hits:
                            issue_hits[key] = cl[:160]
        if not negative or not is_complaint:
            for pk, p in praise.items():
                if any(rx.search(cl) for rx in p["rx"]):
                    praise_hits.add(pk)
    # For a negative review, praise can still exist in clauses without a cue; but we do NOT count
    # 'food' praise on a <=3* review whose issues are all food (mixed signals). Keep it simple: keep praise
    # only for clauses without a complaint cue (handled above by is_complaint => negative always complaint).
    # So negatives get NO praise from rules (the Claude pass can add it). Deliberate.
    issues = [{"cat": ck, "sub": sk, "evidence": ev} for (ck, sk), ev in issue_hits.items()]
    # dishes: sentiment from where they appear
    dish_hits = {}
    for name, rxs in dishes:
        for cl in cls:
            if any(rx.search(cl) for rx in rxs):
                sent = "neg" if (negative or cue.search(cl)) else "pos"
                # a dish named in a negative review's clause = complaint context; in a positive review's
                # complaint clause = 'but' context; otherwise praise
                prev = dish_hits.get(name)
                if prev is None or (prev == "pos" and sent == "neg"):
                    dish_hits[name] = sent
    # collapse generic 'Ramen (unspecified)' if a specific ramen is named
    if any(k.endswith("ramen") and k != "Ramen (unspecified)" for k in dish_hits):
        dish_hits.pop("Ramen (unspecified)", None)
    if "Broth (unspecified)" in dish_hits and any(k.endswith("ramen") for k in dish_hits):
        dish_hits.pop("Broth (unspecified)", None)
    # staff names
    staff = {}
    for rx in staff_rx:
        for m in rx.finditer(text):
            name = m.group(1).strip()
            for part in re.split(r"\s+(?:and|&)\s+", name):
                part = part.strip()
                if not part or part.lower() in stop or len(part) < 3:
                    continue
                if part.lower() in ("us", "me", "our", "the", "a", "an"):
                    continue
                # sentiment = the clause the name sits in
                cl = next((c for c in cls if part in c), text)
                sent = "neg" if (negative or cue.search(cl)) and re.search(r"rude|unhelpful|dismissive|slow|inattentive|unfriendly|abrupt|arrogant|ignored|attitude", cl, re.I) else ("pos" if not negative else "neutral")
                # canonical key: "Harvey P" -> "Harvey" (a trailing initial is the same person at the same site)
                canon = re.sub(r"\s+[A-Z]\.?$", "", part)
                staff[canon] = sent
    out.update(
        issues=issues,
        praise=sorted(praise_hits),
        dishes=[{"name": k, "sent": v} for k, v in dish_hits.items()],
        staff=[{"name": k, "sent": v} for k, v in staff.items()],
        complaint_clauses=complaint_clauses if not negative else [],
        unclassifiable=False,
    )
    return out

def period_keys(d):
    dt = datetime.date.fromisoformat(d)
    mon = dt - datetime.timedelta(days=dt.weekday())
    q = (dt.month - 1) // 3 + 1
    return mon.isoformat(), f"{dt.year}-{dt.month:02d}", f"{dt.year}-Q{q}"

def uk_time(ct):
    if not ct:
        return None, None
    try:
        t = datetime.datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone(UK)
        return t.strftime("%a"), t.hour
    except Exception:
        return None, None

def load_live(live_dir):
    roster, kpis = {}, {}
    files = sorted(glob.glob(os.path.join(live_dir, "all_sites_wc_*.json")))
    if not files:
        log("WARNING: no all_sites_wc_*.json in", live_dir, "— roster and KPI cross-refs will be EMPTY")
    for f in files:
        d = json.load(open(f))
        wk = d.get("week", {}).get("commencing") or os.path.basename(f)[13:23]
        if isinstance(d.get("week"), dict):
            wk = d["week"].get("commencing") or d["week"].get("from") or wk
        for code, s in d["sites"].items():
            k = s["kpis"]
            kpis.setdefault(wk, {})[code] = {
                "sales": k["sales"].get("actual"), "target": k["sales"].get("target"), "var_pct": k["sales"].get("var_pct"),
                "covers": k["covers"].get("actual"), "sph": k["sph"].get("actual"),
                "wage_pct": k["wage_pct"].get("actual"), "food_pct": k["food_pct"].get("actual"),
                "labour_hours": k["labour_hours"].get("actual"),
                "eff_score": (s.get("efficiency_score") or {}).get("score"),
                "eff_rag": (s.get("efficiency_score") or {}).get("rag"),
                "red_light": (s.get("red_light") or {}).get("status"),
                "wk_rating_published": (s.get("reviews") or {}).get("week_avg_rating"),
                "wk_reviews_published": (s.get("reviews") or {}).get("new_reviews"),
            }
            roster[code] = {"code": code, "name": DISPLAY.get(code, s["name"]), "site_label": s["name"],
                            "gm": s.get("gm"), "am": AM_ALIAS.get(s.get("am"), s.get("am")), "region": s["cluster"]}
    for code, r in roster.items():
        reg = REGIONS.get(r["region"], {})
        r["region_id"] = reg.get("id"); r["head"] = reg.get("head"); r["dam"] = reg.get("dam")
    return roster, kpis

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True); ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--live-dir", required=True); ap.add_argument("--llm"); ap.add_argument("--annotations")
    ap.add_argument("--out", required=True); ap.add_argument("--needs-review", required=True)
    ap.add_argument("--summary", help="small JSON the Control Centre shell reads for the tab badge (last complete week)")
    a = ap.parse_args()

    full = json.load(open(a.full)); tax = json.load(open(a.taxonomy))
    C = compile_tax(tax)
    roster, kpis = load_live(a.live_dir)
    llm = json.load(open(a.llm)) if a.llm and os.path.exists(a.llm) else {}
    ann = json.load(open(a.annotations)) if a.annotations and os.path.exists(a.annotations) else {}
    if a.llm and not os.path.exists(a.llm): log("WARNING: --llm file not found, rules only:", a.llm)
    if a.annotations and not os.path.exists(a.annotations): log("WARNING: --annotations file not found:", a.annotations)

    # roster sanity: every source site must be in the roster; every roster site accounted for
    src_sites = set(full["meta"]["perSite"].keys())
    missing_roster = src_sites - set(roster)
    if missing_roster:
        log("🔴 SOURCE SITES NOT IN ROSTER — resolve before shipping:", sorted(missing_roster)); sys.exit(2)
    not_connected = {c: NOT_IN_SOURCE.get(c, "no rows in source and no ruling on file — CHECK") for c in roster if c not in src_sites}
    for c, why in not_connected.items():
        log(f"NOTE: {c} has no reviews in source: {why}")
        roster[c]["reviews_connected"] = False; roster[c]["not_connected_reason"] = why
    for c in src_sites: roster[c]["reviews_connected"] = True

    reviews, needs = [], []
    stats = collections.Counter()
    llm_used = 0
    for r in full["reviews"]:
        cl = classify(r, C)
        rid = r["id"]
        src = "rules"
        if rid in llm:
            L = llm[rid]; src = "llm"; llm_used += 1
            if "issues" in L: cl["issues"] = [{"cat": i[0], "sub": i[1], "evidence": (i[2] if len(i) > 2 else None)} for i in L["issues"]]
            if "praise" in L: cl["praise"] = L["praise"]
            if "staff" in L:
                seen_names = {}
                for sx in L["staff"]:
                    nm = re.sub(r"\s+[A-Z]\.?$", "", str(sx.get("name", "")).strip())
                    if nm and nm.lower() not in C[4]:
                        seen_names[nm] = sx.get("sent", "pos")
                cl["staff"] = [{"name": k, "sent": v} for k, v in seen_names.items()]
            if "dishes" in L:
                have = {d["name"] for d in cl["dishes"]}
                cl["dishes"] += [d for d in L["dishes"] if d["name"] not in have]
            if L.get("translation"): cl["translation"] = L["translation"]; cl["lang"] = L.get("lang", cl["lang"])
            if L.get("note"): cl["note"] = L["note"]
            if L.get("summary"): cl["summary"] = L["summary"]
        # validate taxonomy keys loudly
        for i in cl["issues"]:
            if i["cat"] not in C[0] or i["sub"] not in C[0][i["cat"]]["subs"]:
                log(f"🔴 review {rid}: unknown taxonomy key {i['cat']}/{i['sub']} — dropped from output"); stats["bad_llm_keys"] += 1
        cl["issues"] = [i for i in cl["issues"] if i["cat"] in C[0] and i["sub"] in C[0][i["cat"]]["subs"]]
        wk, mo, q = period_keys(r["d"])
        dow, hour = uk_time(r.get("ct"))
        rec = {"id": rid, "site": r["c"], "stars": r["s"], "date": r["d"], "week": wk, "month": mo, "quarter": q,
               "dow": dow, "hour": hour, "author": r.get("a"), "text": r["t"], "src": src, **cl}
        reviews.append(rec)
        stats["total"] += 1
        if r["s"] <= 3: stats["negative"] += 1
        if not r["t"]: stats["no_text"] += 1
        else:
            stats["with_text"] += 1
            reason = None
            if r["s"] <= 3 and not cl["issues"]: reason = "negative_no_issue_matched"
            elif r["s"] >= 4 and cl.get("complaint_clauses") and not cl["issues"]: reason = "positive_with_complaint_cue_no_issue"
            elif cl["lang"] == "needs_translation": reason = "needs_translation"
            elif r["s"] >= 4 and not cl["praise"] and not cl["issues"]: reason = "positive_no_theme"
            if reason:
                stats["needs_review_" + reason] += 1
                if src != "llm":
                    needs.append({"id": rid, "site": r["c"], "stars": r["s"], "date": r["d"], "reason": reason, "text": r["t"]})
    meta = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source_file": os.path.basename(a.full), "source_pulled_at": full["meta"]["pulledAt"],
        "source_rows": full["meta"]["rows"], "source_dupes_dropped": full["meta"]["dup"],
        "source_dropped_labels": full["meta"]["dropped"], "source_unmapped": full["meta"]["unmapped"],
        "taxonomy_version": tax["version"], "llm_labels_applied": llm_used,
        "counts": dict(stats), "not_connected": not_connected,
        "periods": {"week": "Mon-Sun by received date", "month": "calendar month by received date", "quarter": "calendar quarter by received date"},
        "time_note": "dow/hour are the RECEIVED time in Europe/London (Google createTime). There is no visit date in the source.",
        "weighting": "simple counts; a review can carry several issues, each counted once",
    }
    taxonomy_out = {ck: {"label": c["label"], "owner": c["owner"], "colour": c["colour"],
                         "subs": {sk: s["label"] for sk, s in c["subs"].items()}} for ck, c in C[0].items()}
    praise_out = {k: v["label"] for k, v in C[1].items()}
    out = {"schema_version": "1.0", "meta": meta, "taxonomy": taxonomy_out, "praise_themes": praise_out,
           "regions": REGIONS, "roster": roster, "kpis": kpis, "annotations": ann, "reviews": reviews}
    json.dump(out, open(a.out, "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"generated": meta["built_at"], "n": len(needs), "items": needs}, open(a.needs_review, "w"), ensure_ascii=False, indent=1)
    if a.summary:
        pulled = full["meta"]["pulledAt"][:10]
        weeks = sorted({r["week"] for r in reviews})
        complete = [w for w in weeks if (datetime.date.fromisoformat(w) + datetime.timedelta(days=6)).isoformat() < pulled]
        wk = complete[-1] if complete else weeks[-1]
        wr = [r for r in reviews if r["week"] == wk]
        per = {}
        for r in wr:
            p = per.setdefault(r["site"], {"n": 0, "sum": 0, "neg": 0, "issues": 0, "hyg": 0})
            p["n"] += 1; p["sum"] += r["stars"]; p["neg"] += r["stars"] <= 3; p["issues"] += len(r["issues"])
            p["hyg"] += any(i["sub"] == "hygiene_foreign" for i in r["issues"])
        sites = {}
        for s_, p in per.items():
            avg = p["sum"] / p["n"]; negp = p["neg"] / p["n"] * 100; rate = p["issues"] / p["n"] * 100
            rag = "na" if p["n"] < 5 else ("red" if (avg < 4.5 or negp > 8 or rate > 20) else "amber" if (avg < 4.7 or negp > 4 or rate > 10) else "green")
            sites[s_] = {"n": p["n"], "avg": round(avg, 2), "neg": p["neg"], "issues": p["issues"], "rag": rag, "food_safety": p["hyg"]}
        summ = {"week": wk, "built_at": meta["built_at"], "source_pulled_at": full["meta"]["pulledAt"],
                "reviews": len(wr), "avg": round(sum(r["stars"] for r in wr) / len(wr), 2) if wr else None,
                "negatives": sum(1 for r in wr if r["stars"] <= 3), "issues": sum(len(r["issues"]) for r in wr),
                "red_sites": sum(1 for v in sites.values() if v["rag"] == "red"), "amber_sites": sum(1 for v in sites.values() if v["rag"] == "amber"),
                "food_safety_mentions": sum(v["food_safety"] for v in sites.values()), "sites": sites}
        json.dump(summ, open(a.summary, "w"), ensure_ascii=False, indent=1)
        log("SUMMARY", a.summary, "week", wk, "reviews", summ["reviews"], "red", summ["red_sites"])
    log("BUILT", a.out, "reviews", len(reviews), "| stats", dict(stats), "| llm labels", llm_used, "| needs review", len(needs))

if __name__ == "__main__":
    main()
