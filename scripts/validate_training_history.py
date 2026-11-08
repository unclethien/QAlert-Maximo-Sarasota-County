#!/usr/bin/env python3
"""Validate the training history: balance, dates, links, and separation from the pilot test set.

Usage (from the repository root):
    python3 scripts/validate_training_history.py
Exits 1 if any check fails.
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import history_catalog as hc
import pilot_catalog as cat

DATA = Path(__file__).resolve().parent.parent / "data"
PILOT, HISTORY = DATA / "maximo", DATA / "maximo" / "history"
CUSTOMER = re.compile(r"<div>Customer: (.*?)</div>")
REQUEST_TEXT = re.compile(r"</div><div>([^<]*)</div>$")

errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


def read(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def main():
    files = {}
    for name in ("sr", "wo", "worklog"):
        pilot_header, pilot_rows = read(PILOT / f"{name}.csv")
        header, rows = read(HISTORY / f"{name}.csv")
        check(header == pilot_header, f"{name}.csv: history columns differ from the pilot's")
        files[name] = (rows, pilot_rows)
    (srs, pilot_srs), (wos, pilot_wos), (logs, pilot_logs) = files["sr"], files["wo"], files["worklog"]
    _, addresses = read(DATA / "reference" / "address-points.csv")

    # Balance: every classification has the same number of requests.
    per_class = Counter(sr["CLASSSTRUCTUREID"] for sr in srs)
    check(set(per_class) == set(cat.CLASSIFICATIONS), f"classifications covered: {sorted(per_class)}")
    for classid, n in per_class.items():
        check(n == hc.PER_CLASS, f"classification {classid}: {n} SRs, expected {hc.PER_CLASS}")

    # Dates: all history is reported before the pilot window, so a REPORTDATE filter splits the two.
    for row in srs + wos + logs:
        for column in ("REPORTDATE", "STATUSDATE", "CREATIONDATE", "ACTSTART", "ACTFINISH", "CREATEDATE"):
            day = (row.get(column) or "")[:10]
            if day:
                check(hc.HISTORY_START <= day <= hc.HISTORY_END,
                      f"{row.get('TICKETID') or row.get('WONUM') or row['WORKLOGID']}: {column} {day} outside history")
    pilot_first = min(sr["REPORTDATE"][:10] for sr in pilot_srs)
    check(hc.HISTORY_END < pilot_first, f"history ends {hc.HISTORY_END}, pilot starts {pilot_first}")

    # No ID collides with the pilot.
    for key, rows, pilot_rows in (("TICKETID", srs, pilot_srs), ("EXTERNALSYSTEM_TICKETID", srs, pilot_srs),
                                  ("WONUM", wos, pilot_wos), ("WORKLOGID", logs, pilot_logs)):
        ids = [r[key] for r in rows]
        check(len(ids) == len(set(ids)), f"duplicate {key} in history")
        overlap = set(ids) & {r[key] for r in pilot_rows}
        check(not overlap, f"{key} shared with the pilot: {sorted(overlap)[:5]}")

    # Nothing the model learns from repeats a pilot street, resident or sentence.
    pilot_streets = {a["STREETNAME"] for a in addresses}
    # Not even a first word in common, so a search for one pilot street never finds history.
    pilot_words = {w.lower() for text in [*pilot_streets, *(r["DESCRIPTION"] for r in pilot_srs + pilot_wos)]
                   for w in re.findall(r"[A-Za-z]+", text)}
    shared = [s for s, _ in hc.STREETS if s.split()[0].lower() in pilot_words]
    check(not shared, f"history streets share a name with pilot records: {shared}")
    pilot_texts = [s["text"].lower() for s in cat.SCENARIOS]
    pilot_customers = {m.group(1).lower() for sr in pilot_srs for m in [CUSTOMER.search(sr["DESCRIPTION_LONGDESCRIPTION"])] if m}
    for sr in srs:
        ld = sr["DESCRIPTION_LONGDESCRIPTION"]
        text = REQUEST_TEXT.search(ld)
        check(text is not None, f"{sr['TICKETID']}: no request text in the long description")
        if text:
            said = text.group(1).lower()
            check(not any(p in said or said in p for p in pilot_texts), f"{sr['TICKETID']}: text repeats a pilot request")
        customer = CUSTOMER.search(ld)
        check(customer is not None and customer.group(1).lower() not in pilot_customers,
              f"{sr['TICKETID']}: customer missing or shared with the pilot")
        check(not any(street in ld or street in sr["DESCRIPTION"] for street in pilot_streets),
              f"{sr['TICKETID']}: mentions a pilot street")

    # Links and statuses.
    sr_by_id = {sr["TICKETID"]: sr for sr in srs}
    type_by_class = {rt["classid"]: name for name, rt in cat.REQUEST_TYPES.items()}
    wo_origins = Counter(wo["ORIGRECORDID"] for wo in wos)
    for wo in wos:
        sr = sr_by_id.get(wo["ORIGRECORDID"])
        check(sr is not None and wo["ORIGRECORDCLASS"] == "SR", f"{wo['WONUM']}: origin {wo['ORIGRECORDID']} is not a history SR")
        if sr:
            rt = cat.REQUEST_TYPES[type_by_class[sr["CLASSSTRUCTUREID"]]]
            check(wo["CLASSSTRUCTUREID"] == sr["CLASSSTRUCTUREID"], f"{wo['WONUM']}: classification differs from its SR")
            check(wo["PERSONGROUP"] == rt["persongroup"] and wo["JPNUM"] == rt["jpnum"],
                  f"{wo['WONUM']}: team or job plan does not match {type_by_class[sr['CLASSSTRUCTUREID']]}")
        check(wo["STATUS"] == "CLOSE" and wo["ACTFINISH"], f"{wo['WONUM']}: history WOs are closed and finished")
        check(wo["WORKTYPE"] in cat.WORK_TYPES, f"{wo['WONUM']}: unknown work type {wo['WORKTYPE']!r}")
    check(all(n == 1 for n in wo_origins.values()), "an SR has more than one history WO")
    closing_logs = {(log["RECORDKEY"], log["LOGTYPE"]) for log in logs if log["CLASS"] == "SR"}
    for sr in srs:
        rtype = type_by_class[sr["CLASSSTRUCTUREID"]]
        if cat.REQUEST_TYPES[rtype]["persongroup"]:
            check(sr["STATUS"] == "CLOSED" and wo_origins[sr["TICKETID"]] == 1, f"{sr['TICKETID']}: crew work needs one WO and CLOSED")
        else:
            logtype, _ = hc.NO_CREW_CLOSING[rtype]
            check(sr["TICKETID"] not in wo_origins and (sr["TICKETID"], logtype) in closing_logs,
                  f"{sr['TICKETID']}: {rtype} closes with a {logtype} note and no WO")
            check(sr["STATUS"] == ("CLOSED" if logtype == "RESOLUTION" else "RESOLVED"), f"{sr['TICKETID']}: wrong status")
    for log in logs:
        check(log["LOGTYPE"] in cat.LOG_TYPES, f"{log['WORKLOGID']}: unknown log type")
        check(log["RECORDKEY"] in (sr_by_id if log["CLASS"] == "SR" else {wo["WONUM"] for wo in wos}),
              f"{log['WORKLOGID']}: parent {log['RECORDKEY']} not in the history")

    # Some requests were filed under the wrong type, and every stormwater request was.
    filed_wrong = Counter()
    for sr in srs:
        filed = sr["DESCRIPTION"].split(",")[0]
        check(filed in cat.REQUEST_TYPES, f"{sr['TICKETID']}: description does not start with a request type")
        if filed in cat.REQUEST_TYPES and cat.REQUEST_TYPES[filed]["classid"] != sr["CLASSSTRUCTUREID"]:
            filed_wrong[sr["CLASSSTRUCTUREID"]] += 1
    check(filed_wrong["9401"] == hc.PER_CLASS, "every stormwater request is filed under a Utilities type")
    other = sum(n for c, n in filed_wrong.items() if c != "9401")
    share = other / (len(srs) - hc.PER_CLASS)
    check(0.05 <= share <= 0.25, f"misfiled share {share:.0%} outside 5-25%")

    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for e in errors[:40]:
            print(f" - {e}")
        sys.exit(1)
    print(f"OK: history checks passed ({len(srs)} SRs, {len(wos)} WOs, {len(logs)} work logs, "
          f"{share:.0%} misfiled outside stormwater)")


if __name__ == "__main__":
    main()
