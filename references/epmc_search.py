#!/usr/bin/env python3
"""Europe PMC search + JATS full-text harvester (stdlib only, no API key).

Verified 2026-08-30 on Windows/Git-Bash + Python 3.13.

Subcommands
  search   -- run a Europe PMC query, print a result table (PMCID / year / journal / OA)
  fetch    -- download full-text JATS XML for one or more PMCIDs
  harvest  -- search, then auto-download every OA full text found

Query syntax notes (empirically verified, do NOT guess):
  HAS_FT:Y              works  -> restrict to records with full text
  OPEN_ACCESS:Y         works  -> restrict to open access
  JOURNAL:"..."         works
  FULL_TEXT:"..."       BROKEN -> always returns hitCount 0 on this API version

Examples
  python epmc_search.py search 'HAS_FT:Y AND OPEN_ACCESS:Y AND "intra-arterial" AND "stroke"' -n 20
  python epmc_search.py search 'JOURNAL:"Stem Cell Reports" AND OPEN_ACCESS:Y' -n 10
  python epmc_search.py fetch PMC7147186 PMC11373674 -o xml/
  python epmc_search.py harvest 'HAS_FT:Y AND OPEN_ACCESS:Y AND "chronic stroke" AND "neural stem" ' -n 20 -o out/
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = {"User-Agent": "Mozilla/5.0 (compatible; epmc-harvester/1.0)"}
# Europe PMC asks for polite use; 0.4s keeps us well clear of rate limits.
DELAY = 0.4


def http_get(url, timeout=40, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - surface whatever the network did
            last = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last


def search(query, n=20, offset=0):
    url = "%s/search?query=%s&format=json&pageSize=%d&resultType=core" % (
        BASE, urllib.parse.quote(query), min(n, 1000))
    if offset:
        url += "&cursorMark=%s" % urllib.parse.quote(str(offset))
    d = json.loads(http_get(url).decode("utf-8", "ignore"))
    return d.get("hitCount", 0), d.get("resultList", {}).get("result", [])


def print_table(rows, total):
    print("hitCount: %s   showing: %d\n" % (total, len(rows)))
    print("| # | PMCID | Year | OA | FT | Journal | Title |")
    print("|---|-------|------|----|----|---------|-------|")
    for i, r in enumerate(rows, 1):
        pmcid = r.get("pmcid") or "-"
        year = r.get("pubYear") or (r.get("firstPublicationDate") or "")[:4] or "-"
        oa = r.get("isOpenAccess") or "-"
        ft = r.get("hasTextMinedTerms") or r.get("inEPMC") or "-"
        jr = (r.get("journalTitle") or r.get("bookOrReportDetails", {}).get("publisher") or "-")
        ti = (r.get("title") or "").replace("|", "/")
        print("| %d | %s | %s | %s | %s | %s | %s |" % (
            i, pmcid, year, oa, ft, jr[:26], ti[:70]))
    print()
    ok = [r.get("pmcid") for r in rows
          if r.get("pmcid") and r.get("isOpenAccess") == "Y" and r.get("inEPMC") == "Y"]
    if ok:
        print("Downloadable full text (%d):" % len(ok))
        print("  " + " ".join(ok))
        print()
        print("Next step:")
        print("  python %s fetch %s -o xml/" % (os.path.basename(__file__), " ".join(ok)))


def fetch(pmcids, outdir="."):
    os.makedirs(outdir, exist_ok=True)
    got, failed = [], []
    for p in pmcids:
        p = p.strip()
        if not p:
            continue
        dest = os.path.join(outdir, p + ".xml")
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            got.append(p)
            print("  skip (exists): %s" % p)
            continue
        try:
            data = http_get("%s/%s/fullTextXML" % (BASE, p))
        except Exception as e:  # noqa: BLE001
            print("  FAIL %s (%s)" % (p, str(e)[:50]))
            failed.append(p)
            time.sleep(DELAY)
            continue
        # A real hit is >=10 KB of JATS markup. Europe PMC emits TWO valid shapes:
        #   b'\n<!DOCTYPE article PUBLIC "-//NLM//DTD JATS...'   (with DTD)
        #   b'<?xml version="1.0" encoding="UTF-8"?><article...' (XML decl, no DTD)
        # Detect the <article> element, NOT the doctype -- matching only the
        # doctype silently discards ~40% of valid full texts. Verified 2026-08-30:
        # PMC12559856 (162 KB) and PMC12617542 (291 KB) were being thrown away.
        # 0-byte or 16-byte bodies ("error") mean embargo / abstract-only deposit.
        head = data[:4096].lstrip().lower()
        if len(data) < 10000 or b"<article" not in head:
            print("  EMPTY %s (%d bytes) -> not available, do not retry" % (p, len(data)))
            failed.append(p)
        else:
            with open(dest, "wb") as f:
                f.write(data)
            got.append(p)
            print("  OK %s (%d bytes) -> %s" % (p, len(data), dest))
        time.sleep(DELAY)
    print("\nretrieved=%d  failed=%d" % (len(got), len(failed)))
    if failed:
        print("not available: " + " ".join(failed))
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="run a Europe PMC query")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=20)

    f = sub.add_parser("fetch", help="download JATS XML for PMCIDs")
    f.add_argument("pmcids", nargs="+")
    f.add_argument("-o", "--outdir", default=".")

    h = sub.add_parser("harvest", help="search then download all OA full text")
    h.add_argument("query")
    h.add_argument("-n", type=int, default=20)
    h.add_argument("-o", "--outdir", default="xml")

    a = ap.parse_args()

    if a.cmd == "search":
        total, rows = search(a.query, a.n)
        print_table(rows, total)
    elif a.cmd == "fetch":
        fetch(a.pmcids, a.outdir)
    elif a.cmd == "harvest":
        total, rows = search(a.query, a.n)
        print_table(rows, total)
        ok = [r.get("pmcid") for r in rows
              if r.get("pmcid") and r.get("isOpenAccess") == "Y" and r.get("inEPMC") == "Y"]
        if ok:
            print("=== harvesting %d ===" % len(ok))
            fetch(ok, a.outdir)


if __name__ == "__main__":
    main()
