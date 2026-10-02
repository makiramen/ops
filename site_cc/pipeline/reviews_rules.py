"""Review rules, vendored from am_rebuild/builders/build_reviews_intel.py (AM CC Reviews Intelligence) so the Site CC labels new reviews the same way.
Keyword rules only; the AM CC Claude pass is not run here. Re-copy if the AM CC rules change."""
import re
CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+|\s+(?=\b(?:but|however|although|though|except|unfortunately)\b)", re.I)
TRANSLATED = re.compile(r"\(Translated by Google\)\s*(.*?)\s*\(Original\)\s*(.*)", re.S)

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

