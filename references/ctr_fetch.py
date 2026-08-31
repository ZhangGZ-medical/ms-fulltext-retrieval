#!/usr/bin/env python3
"""Clinical-trial registry fetcher — the data source that beats the paper.

Why this exists
---------------
Trial registries legally must post results for every pre-specified endpoint
(FDAAA 801 / WHO ICTRP). Journals do not: **negative trials are often never
published**. A registry result set is therefore frequently the *only* place a
failed endpoint is documented — and it is free, authoritative and instant.

Verified 2026-08-30 on ACTIsSIMA (NCT02448641, SanBio SB623, chronic stroke,
N=163, completed 2018-12-05). No paper exists for the stroke Phase 2b result,
but the registry posted it on 2020-04-17:

    SB623 2.5M   7/55  = 12.7% responders
    SB623 5.0M   9/56  = 16.1% responders
    Sham control 7/52  = 13.5% responders   <- low dose BELOW sham

Usage
    python ctr_fetch.py NCT02448641
    python ctr_fetch.py NCT02448641 --all          # include secondary endpoints
    python ctr_fetch.py NCT02448641 --json out.json # save raw payload

Other registries: ChiCTR (chictr.org.cn), ICTRP (who.int/clinical-trials-registry-platform),
EU CTIS, jRCT. Same principle, different scrapers.
"""
import argparse
import json
import sys
import urllib.request

BASE = "https://clinicaltrials.gov/api/v2/studies"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ctr-fetch/1.0)"}


def api(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def short_id(work_id):
    return (work_id or "").split("/")[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nct_id")
    ap.add_argument("--all", action="store_true", help="include secondary endpoints")
    ap.add_argument("--json", dest="json_out", help="save raw JSON payload")
    a = ap.parse_args()

    url = "%s/%s?fields=protocolSection,hasResults,resultsSection" % (BASE, a.nct_id)
    d = api(url)

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)

    p = d.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    design = p.get("designModule", {})

    print("=" * 78)
    print("NCT ID :", ident.get("nctId"))
    print("Title  :", (ident.get("briefTitle") or "")[:100])
    print("Status :", status.get("overallStatus"),
          "| Completed:", (status.get("completionDateStruct") or {}).get("date"))
    print("Phase  :", design.get("phases"),
          "| Enrollment:", (design.get("enrollmentInfo") or {}).get("count"))
    print("Results posted:", d.get("hasResults"),
          "| first:", (status.get("resultsFirstPostDateStruct") or {}).get("date"))

    rs = d.get("resultsSection") or {}
    if not rs:
        print("\nNo results posted on the registry.")
        print("-> If status is COMPLETED but hasResults is False, that is itself a")
        print("   signal: treat the trial as an unpublished result and check")
        print("   conference abstracts / sponsor press releases.")
        return

    oms = (rs.get("outcomeMeasuresModule") or {}).get("outcomeMeasures") or []
    ae = rs.get("adverseEventsModule") or {}
    print("Endpoints on file: %d | Serious AE terms: %d"
          % (len(oms), len(ae.get("seriousEvents") or [])))

    for o in oms:
        if o.get("type") != "PRIMARY" and not a.all:
            continue
        print("\n" + "-" * 78)
        print("[%s] %s" % (o.get("type"), (o.get("title") or "")[:110]))
        print("  Time frame :", (o.get("timeFrame") or "")[:70])
        print("  Unit       :", o.get("unitOfMeasure"))

        gtitle = {g.get("id"): (g.get("title") or g.get("id"))
                  for g in (o.get("groups") or [])}
        denom = {}
        for dn in (o.get("denoms") or [])[:1]:
            for c in (dn.get("counts") or []):
                denom[c.get("groupId")] = c.get("value")

        if gtitle:
            print("  Groups     :")
            for gid, t in gtitle.items():
                print("     %-8s %s   (n=%s)" % (gid, t[:56], denom.get(gid, "?")))

        for cl in (o.get("classes") or []):
            cname = cl.get("title") or "(value)"
            cells = []
            for cat in (cl.get("categories") or []):
                for m in (cat.get("measurements") or []):
                    gid = m.get("groupId")
                    val = m.get("value")
                    pct = ""
                    try:
                        if denom.get(gid) and float(denom[gid]) > 0:
                            pct = " (%.1f%%)" % (100.0 * float(val) / float(denom[gid]))
                    except (TypeError, ValueError):
                        pass
                    cells.append("%s=%s%s" % (gid, val, pct))
                if not (cl.get("categories") or []):
                    break
            if cells:
                print("  %-14s %s" % (cname[:14], "  |  ".join(cells)))

        for cl in (o.get("classes") or []):
            for an in (cl.get("analyses") or []):
                if an.get("pValue") or an.get("paramValue"):
                    print("  Analysis   : %s=%s p=%s  %s" % (
                        an.get("paramType", ""), an.get("paramValue", ""),
                        an.get("pValue", ""), (an.get("description") or "")[:60]))

    print("\n" + "=" * 78)
    print("Interpretation checklist:")
    print(" 1. Compare the ACTIVE arms against the CONTROL arm, never against zero.")
    print(" 2. Check whether the control arm's own response rate is high — a large")
    print("    sham response invalidates any single-arm 'improvement' claim.")
    print(" 3. If the trial completed years ago and no paper exists, treat the")
    print("    registry as the definitive record, and say so explicitly when citing.")
    print(" 4. Registry results are citable as a primary source: cite the NCT ID.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
