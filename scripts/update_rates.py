#!/usr/bin/env python3
"""
Rebuilds data/rates.json, which is the file Rate Desk reads.

Two modes, and you can run both together.

  manual   Reads data/manual.json. You edit that file, commit it, and the page
           shows the new numbers within a minute. On by default.

  fetch    Pulls from a website automatically. OFF by default, and it should
           stay off until somebody in PFC has read the terms of the site you
           intend to point it at. CCIL, for one, states on its own pages that
           it does not authorise commercial use of its website data without
           written permission. An automated job that hits a site every hour is
           exactly the kind of use those terms are written about.

Run locally:   python3 scripts/update_rates.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, "data", "manual.json")
OUTPUT = os.path.join(ROOT, "data", "rates.json")

# Keys the page understands. Anything else is carried through untouched.
KEYS = ["REPO", "SDF", "MSF", "GSEC10Y", "AAA10Y", "CPI", "USDINR", "BRENT", "US10Y"]

# Turn a fetcher on only after you have cleared the source's terms.
ENABLED_FETCHERS = []          # e.g. ["my_source"] once you have written and cleared one

IST = timezone(timedelta(hours=5, minutes=30))


def read_manual():
    """Values you maintain by hand in data/manual.json."""
    if not os.path.exists(MANUAL):
        return {}
    with open(MANUAL, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if k in KEYS and v not in (None, "")}


# ---------------------------------------------------------------------------
# Automatic sources
# ---------------------------------------------------------------------------
# Each fetcher returns a dict of KEYS -> number, or {} if it cannot get them.
# Write one per source. Keep them small, and make every one fail quietly: a
# broken scraper must never blank out the page, it must simply contribute
# nothing and let the manual values stand.
#
# Before you add one, answer three questions in the commit message:
#   1. Does the site's terms of use permit automated access?
#   2. Is the number published, or is it behind a sign-in?
#   3. What happens to the page the day the site changes its HTML?
#
# def fetch_my_source():
#     import urllib.request
#     req = urllib.request.Request(URL, headers={"User-Agent": "rate-desk"})
#     with urllib.request.urlopen(req, timeout=20) as resp:
#         payload = json.loads(resp.read().decode("utf-8"))
#     return {"GSEC10Y": float(payload["yield"])}

FETCHERS = {
    # "my_source": fetch_my_source,
}


def run_fetchers():
    got, used = {}, []
    for name in ENABLED_FETCHERS:
        fn = FETCHERS.get(name)
        if not fn:
            print("skip: no fetcher named %s" % name, file=sys.stderr)
            continue
        try:
            vals = fn() or {}
            clean = {k: v for k, v in vals.items() if k in KEYS and v not in (None, "")}
            if clean:
                got.update(clean)
                used.append(name)
                print("ok: %s supplied %s" % (name, ", ".join(sorted(clean))))
            else:
                print("warn: %s returned nothing usable" % name, file=sys.stderr)
        except Exception as exc:                      # never let one source break the run
            print("warn: %s failed — %s" % (name, exc), file=sys.stderr)
    return got, used


def main():
    out = {}
    out.update(read_manual())                          # manual first
    fetched, used = run_fetchers()
    out.update(fetched)                                # automatic wins where present

    if not any(k in out for k in KEYS):
        print("error: no values at all — refusing to publish an empty feed", file=sys.stderr)
        return 1

    out["UPDATED"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    out["SOURCE"] = " + ".join(used) if used else "manual"

    # Do not commit an identical file; it only creates noise in the history.
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, "r", encoding="utf-8") as fh:
                old = json.load(fh)
            if {k: v for k, v in old.items() if k != "UPDATED"} == \
               {k: v for k, v in out.items() if k != "UPDATED"}:
                print("no change in the numbers; leaving the file alone")
                return 0
        except Exception:
            pass

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote %s (%s)" % (OUTPUT, out["SOURCE"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
