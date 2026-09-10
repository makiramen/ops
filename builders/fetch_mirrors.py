#!/usr/bin/env python3
"""fetch_mirrors.py v2 (10/09/2026) , feed the daily pipe, and NEVER hand it a stale source.

Cash-up : Drive v3 files.export of the cash-up MIRROR, twice, must be byte-identical.
Reviews : Sheets API v4 values.get on the MASTER tracker, 'Raw Data'!A:L, twice.
          Falls back to the reviews MIRROR export if the master cannot be read (not shared with
          the service account yet, Sheets API not enabled, any error at all). The fallback is
          announced loudly on stderr and recorded in <out>/reviews_source.txt.

  python3 builders/fetch_mirrors.py --out /tmp/mirrors
      -> cashup_1.csv cashup_2.csv reviews_1.csv reviews_2.csv reviews_source.txt

Auth: GOOGLE_SA_JSON = the service-account key JSON text. Scopes drive.readonly +
spreadsheets.readonly.

!! WHY THE REVIEWS ROUTE CHANGED, 10/09/2026
A formula MIRROR only recalculates when something OPENS it. Drive files.export then serves the
last computed CSV at HTTP 200 , well formed, plausible row count, no error anywhere. The reviews
mirror exported BYTE-IDENTICALLY at 19:47Z 09/09 and 08:17Z 10/09, both times with ZERO rows for
09/09, while the master tracker held all 57 the whole time. The pipe shipped a day of reviews as
an empty column and nothing in the chain could tell. A live Sheets API read of a real tab cannot
do that. See project_reviews_mirror_stale_1009.

!! THE FRESHNESS GATE
Whatever the route, the newest date in each source must be >= D-1, where D is the day being built
(default: yesterday, UK clock). A source frozen further back than that exits 5 and fails the job.
D-1 rather than D on purpose: "D not filed yet" is a legitimate morning state that the build step
handles with its own exit 11, but a source that has not moved for two days is always a fault.

Exit codes: 2 auth | 3 fetch | 4 two pulls never matched | 5 SOURCE STALE | 6 header unexpected.
"""
import argparse, csv, datetime, hashlib, io, json, os, sys, time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

UK = ZoneInfo("Europe/London")

CASHUP_MIRROR  = "1CxrxXJ66vKdDTNvcxfQExDcGWfoVB3_Ed4AHO6_4Gl0"   # "Auto Cash Up MIRROR , cloud pipe (do not edit)"
REVIEWS_MIRROR = "1KG2Q5YM8etf614xMpSpeQv3SF2iLdf5SLc978vH3YHY"   # "Google Reviews MIRROR , cloud pipe (do not edit)"
REVIEWS_MASTER = "1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I"   # "Google Reviews Maki & Ramen" , the real tracker
REVIEWS_RANGE  = "'Raw Data'!A:L"                                  # A:L is exactly what the mirror carries
REVIEWS_WINDOW = 14                                                # days kept, to match the mirror's own window

SCOPES = ["https://www.googleapis.com/auth/drive.readonly",
          "https://www.googleapis.com/auth/spreadsheets.readonly"]


def log(*a): print(*a, file=sys.stderr)


def token():
    raw = os.environ.get("GOOGLE_SA_JSON")
    if not raw: log("GOOGLE_SA_JSON is not set"); sys.exit(2)
    creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def export(tok, fid):
    """Drive v3 CSV export. Returns the FIRST TAB only , fine for a mirror, useless for the master."""
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{fid}/export", params={"mimeType": "text/csv"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=120)
    if r.status_code != 200: raise RuntimeError(f"export {fid} -> HTTP {r.status_code}: {r.text[:300]}")
    b = r.content
    if b.lstrip()[:15].lower().startswith(b"<!doctype") or b.lstrip()[:5].lower() == b"<html":
        raise RuntimeError(f"export {fid} returned HTML, not CSV (wrong id fails at 200)")
    if len(b) < 2048: raise RuntimeError(f"export {fid} suspiciously small ({len(b)} B)")
    return b


def sheet_csv(tok, fid, rng, window_days=None, today=None):
    """Sheets API v4 values.get -> the same CSV shape the mirror export produces.

    FORMATTED_VALUE keeps Date as the dd/mm/yyyy TEXT every downstream parser expects. Rows come
    back ragged (trailing empties dropped), so pad every row to the widest one.

    !! WINDOW THE MASTER. The master holds FULL LIFETIME history per location (Bath St alone is
    ~2,845 rows) while the mirror carries a rolling ~14 days. Handing merge_reviews_mirror.py the
    whole history would re-upsert tens of thousands of rows into reviews_full.json and blow up
    Reviews Intelligence. Trim to the same window the mirror keeps."""
    resp = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{fid}/values/{quote(rng, safe='')}",
                        params={"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE",
                                "dateTimeRenderOption": "FORMATTED_STRING"},
                        headers={"Authorization": f"Bearer {tok}"}, timeout=180)
    if resp.status_code != 200: raise RuntimeError(f"values.get {fid} -> HTTP {resp.status_code}: {resp.text[:300]}")
    vals = resp.json().get("values", [])
    if len(vals) < 21: raise RuntimeError(f"values.get {fid} returned {len(vals)} rows , too few to trust")
    w = max(len(v) for v in vals)
    rows = [[str(x) for x in v] + [""] * (w - len(v)) for v in vals]
    hdr = [h.strip() for h in rows[0]]
    if "reviewId" not in hdr or "Date" not in hdr:
        raise RuntimeError(f"master header unexpected: {hdr[:8]}")
    if window_days:
        ict = hdr.index("createTime") if "createTime" in hdr else None
        idt = hdr.index("Date")
        floor = (today or datetime.date.today()) - datetime.timedelta(days=window_days - 1)
        kept = [rows[0]]
        for row in rows[1:]:
            d = None
            if ict is not None and len(row) > ict:
                try: d = datetime.date.fromisoformat(row[ict].strip()[:10])
                except Exception: d = None
            if d is None and len(row) > idt:
                try:
                    dd, mm, yy = row[idt].strip().split("/")[:3]
                    d = datetime.date(int(yy), int(mm), int(dd))
                except Exception: d = None
            if d and d >= floor: kept.append(row)
        if len(kept) < 21:
            raise RuntimeError(f"master gave only {len(kept)-1} rows inside the {window_days}-day window")
        rows = kept
    buf = io.StringIO(newline="")
    out = csv.writer(buf, lineterminator="\r\n")
    for row in rows: out.writerow(row)
    return buf.getvalue().encode("utf-8")


def twice(fn, name, gap):
    """Two identical reads or die. Kept for BOTH routes: it is cheap, and it is the only thing that
    would have caught a mirror mid-recalculation."""
    for attempt in range(3):
        b1 = fn(); time.sleep(gap); b2 = fn()
        if b1 == b2: return b1
        log(f"{name}: pulls differ (attempt {attempt+1}) {len(b1)} vs {len(b2)} B , source is recalculating, retrying")
        time.sleep(gap)
    log(f"{name}: never got two identical pulls"); sys.exit(4)


def newest_date(b, name):
    """Newest calendar date in the CSV, read from the 'Date' column (dd/mm/yyyy), with createTime
    (ISO) as a second opinion for the reviews shape."""
    rows = list(csv.reader(io.StringIO(b.decode("utf-8-sig"))))
    if not rows: log(f"{name}: no rows at all"); sys.exit(6)
    hdr = [h.strip() for h in rows[0]]
    if "Date" not in hdr: log(f"{name}: header has no 'Date' column: {hdr[:8]}"); sys.exit(6)
    idt = hdr.index("Date")
    ict = hdr.index("createTime") if "createTime" in hdr else None
    best = None
    for r in rows[1:]:
        cand = None
        if len(r) > idt:
            s = r[idt].strip()
            if len(s) >= 8 and s[:2].isdigit():
                try:
                    d, m, y = s.split("/")[:3]
                    cand = datetime.date(int(y), int(m), int(d))
                except Exception: cand = None
        if cand is None and ict is not None and len(r) > ict:
            s = r[ict].strip()[:10]
            try: cand = datetime.date.fromisoformat(s)
            except Exception: cand = None
        if cand and (best is None or cand > best): best = cand
    return best


def gate(b, name, D, route):
    """A source that has not moved since before D-1 cannot possibly carry D. Fail, never build a zero."""
    newest = newest_date(b, name)
    floor = D - datetime.timedelta(days=1)
    log(f"{name}: {len(b)} B sha {hashlib.sha256(b).hexdigest()[:16]} newest {newest} (route {route}, building {D})")
    if newest is None or newest < floor:
        log(f"!! {name.upper()} SOURCE IS STALE: newest row is {newest}, building {D}, floor {floor}.")
        log(f"!!   A formula sheet only recalculates when something opens it and then exports the frozen")
        log(f"!!   snapshot at HTTP 200. Open the source in a browser, or move this feed off the mirror.")
        log(f"!!   Refusing to build a day off a stale source. See project_reviews_mirror_stale_1009.")
        sys.exit(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--gap", type=float, default=20)
    ap.add_argument("--day", help="the day being built, YYYY-MM-DD (default: yesterday, UK)")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

    D = datetime.date.fromisoformat(a.day) if a.day else datetime.datetime.now(UK).date() - datetime.timedelta(days=1)
    tok = token()

    cb = twice(lambda: export(tok, CASHUP_MIRROR), "cashup", a.gap)

    route = "master:sheets-api"
    try:
        today_uk = datetime.datetime.now(UK).date()
        rb = twice(lambda: sheet_csv(tok, REVIEWS_MASTER, REVIEWS_RANGE, REVIEWS_WINDOW, today_uk), "reviews", 2)
    except SystemExit: raise
    except Exception as e:
        log(f"!! REVIEWS MASTER READ FAILED: {e}")
        log( "!!   Falling back to the reviews MIRROR, which CAN be a day frozen. To fix permanently,")
        log(f"!!   share {REVIEWS_MASTER} with the service account as Viewer and enable the Sheets API.")
        route = "mirror:drive-export"
        rb = twice(lambda: export(tok, REVIEWS_MIRROR), "reviews", a.gap)

    for name, b in (("cashup", cb), ("reviews", rb)):
        for i in (1, 2): open(os.path.join(a.out, f"{name}_{i}.csv"), "wb").write(b)
    open(os.path.join(a.out, "reviews_source.txt"), "w").write(route + "\n")

    gate(cb, "cashup", D, "mirror:drive-export")
    gate(rb, "reviews", D, route)
    print("ok " + route)


if __name__ == "__main__":
    main()
