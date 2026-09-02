#!/usr/bin/env python3
"""fetch_mirrors.py — pull the two Drive MIRROR docs as CSV, twice each, with NO browser and NO Claude.

Auth: a Google service account (env GOOGLE_SA_JSON = the key file's JSON text) that the two mirror
docs are shared with as Viewer. Export endpoint: Drive v3 files.export (text/csv = first tab).

  python3 builders/fetch_mirrors.py --out /tmp/mirrors      -> cashup_1.csv cashup_2.csv reviews_1.csv reviews_2.csv

Guards (loud, non-zero exit): auth failure, HTTP != 200, a body that is HTML (a wrong id fails at 200
with a 'Page not found' page), a body under 2 KB, or two pulls that still differ after 3 attempts.
"""
import argparse, json, os, sys, time, hashlib
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

MIRRORS = {
    "cashup":  "1CxrxXJ66vKdDTNvcxfQExDcGWfoVB3_Ed4AHO6_4Gl0",   # "Auto Cash Up MIRROR — cloud pipe (do not edit)"
    "reviews": "1KG2Q5YM8etf614xMpSpeQv3SF2iLdf5SLc978vH3YHY",   # "Google Reviews MIRROR — cloud pipe (do not edit)"
}

def log(*a): print(*a, file=sys.stderr)

def token():
    raw = os.environ.get("GOOGLE_SA_JSON")
    if not raw: log("GOOGLE_SA_JSON is not set"); sys.exit(2)
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(Request())
    return creds.token

def export(tok, fid):
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{fid}/export", params={"mimeType": "text/csv"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=120)
    if r.status_code != 200: log(f"export {fid} -> HTTP {r.status_code}: {r.text[:300]}"); sys.exit(3)
    b = r.content
    if b.lstrip()[:15].lower().startswith(b"<!doctype") or b.lstrip()[:5].lower() == b"<html": log(f"export {fid} returned HTML, not CSV"); sys.exit(3)
    if len(b) < 2048: log(f"export {fid} suspiciously small ({len(b)} B)"); sys.exit(3)
    return b

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--gap", type=float, default=20)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    tok = token()
    for name, fid in MIRRORS.items():
        pulls = []
        for attempt in range(3):
            b1 = export(tok, fid); time.sleep(a.gap); b2 = export(tok, fid)
            if b1 == b2: pulls = [b1, b2]; break
            log(f"{name}: pulls differ (attempt {attempt+1}) {len(b1)} vs {len(b2)} B — the mirror is recalculating, retrying")
            time.sleep(a.gap)
        if not pulls: log(f"{name}: never got two identical pulls"); sys.exit(4)
        for i, b in enumerate(pulls, 1): open(os.path.join(a.out, f"{name}_{i}.csv"), "wb").write(b)
        log(f"{name}: {len(pulls[0])} B sha {hashlib.sha256(pulls[0]).hexdigest()[:16]} (two identical pulls)")
    print("ok")

if __name__ == "__main__":
    main()
