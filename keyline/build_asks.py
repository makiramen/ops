#!/usr/bin/env python3
"""
Rolling store of what Keyline asked each site to order, and the part file the page reads.

The daily cycle is: pull -> decide -> ask -> CLOSE. This script owns the memory between the ask and the close.
render.py dumps one file per run (asks-YYYY-MM-DD.json). This script keeps the last KEEP ask days in
asks-store.json and renders them into part_asks.html, which the engine reads as window.KEYLINE_ASKS.

  python3 build_asks.py prepare              before the build: part_asks.html = every day UP TO YESTERDAY
  python3 build_asks.py commit 2026-09-15    after the render: fold todays asks into the store

Order matters. prepare must run before the cat, so the page closes yesterday. commit must run after render.py,
so today is remembered for tomorrow. Committing before the build would make the page try to close asks that
were issued sixty seconds earlier, and every one of them would read as not ordered.
"""
import json, os, sys, datetime

STORE = 'asks-store.json'
PART  = 'part_asks.html'
KEEP  = 7


def load():
    if not os.path.exists(STORE):
        return {"days": {}}
    with open(STORE) as f:
        return json.load(f)


def prune(store):
    days = sorted(store["days"].keys(), reverse=True)[:KEEP]
    store["days"] = {d: store["days"][d] for d in days}
    return store


def write_part(store, note=""):
    asks = []
    for d in sorted(store["days"].keys()):
        asks.extend(store["days"][d])
    meta = {
        "source": "keyline-run" if asks else "none",
        "days": sorted(store["days"].keys()),
        "nAsks": len(asks),
        "builtAt": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "note": note or "What each site was asked to order, per run. Read by the closure step in part_e.",
    }
    body = json.dumps({"meta": meta, "asks": asks}, separators=(', ', ': '))
    with open(PART, 'w') as f:
        f.write("<script>\nwindow.KEYLINE_ASKS = " + body + ";\n</script>\n")
    return meta


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'prepare'
    store = prune(load())

    if cmd == 'prepare':
        today = datetime.date.today().isoformat()
        # never hand the page an ask issued today: it has not had a chance to be ordered yet
        store["days"] = {d: v for d, v in store["days"].items() if d < today}
        meta = write_part(store)
        print("prepare:", meta["nAsks"], "asks across", meta["days"] or "no days yet")
        return

    if cmd == 'commit':
        day = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
        src = 'asks-%s.json' % day
        if not os.path.exists(src):
            print("commit: nothing to commit,", src, "not found")
            return
        with open(src) as f:
            rows = json.load(f)
        store["days"][day] = rows
        store = prune(store)
        with open(STORE, 'w') as f:
            json.dump(store, f, separators=(', ', ': '), indent=0)
        meta = write_part(store)
        print("commit:", day, len(rows), "asks stored; store now holds", meta["days"])
        return

    print(__doc__)


if __name__ == '__main__':
    main()
