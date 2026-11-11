#!/usr/bin/env python3
"""Validate the draft work orders: one per open pilot SR with no work order, and nothing decided yet.

Usage (from the repository root):
    python3 scripts/validate_draft_work_orders.py
Exits 1 if any check fails.
"""

import csv
import sys
from datetime import datetime

import generate_draft_work_orders as drafts_gen
import id_map
import pilot_catalog as cat
from generate_pilot_dataset import AS_OF, DATA

errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


def read(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def main():
    base = DATA / "maximo"
    wo_header, pilot_wos = read(base / "wo.csv")
    _, srs = read(base / "sr.csv")
    _, answers = read(DATA / "answer-key.csv")
    header, drafts = read(base / "drafts" / "wo.csv")
    _, history_wos = read(base / "history" / "wo.csv")
    _, people = read(base / "person.csv")
    for name in ("sr", "worklog"):
        pilot_header, _ = read(base / f"{name}.csv")
        draft_header, rows = read(base / "drafts" / f"{name}.csv")
        check(draft_header == pilot_header and not rows, f"drafts/{name}.csv must be header-only")
    check(header == wo_header, "drafts/wo.csv columns differ from the pilot's")

    sr_by_id = {sr["TICKETID"]: sr for sr in srs}
    answer = {a["TICKETID"]: a for a in answers}
    with_wo = {w["ORIGRECORDID"] for w in pilot_wos if w["ORIGRECORDID"]}
    # Worked out here, not with the generator's rule, so a broken rule cannot pass its own check.
    expected = {t for t, sr in sr_by_id.items()
                if sr["STATUS"] in ("NEW", "QUEUED", "PENDING") and t not in with_wo
                and answer[t]["EXPECTED_PERSONGROUP"] and answer[t]["EXPECTED_ALERT"] != "Possible duplicate"}
    origins = [d["ORIGRECORDID"] for d in drafts]
    check(len(origins) == len(set(origins)), "an SR has more than one draft")
    check(set(origins) == expected, f"drafts missing for {sorted(expected - set(origins))}, "
                                    f"unexpected for {sorted(set(origins) - expected)}")

    taken = {w["WONUM"] for w in pilot_wos + history_wos}
    numbers = [d["WONUM"] for d in drafts]
    check(len(numbers) == len(set(numbers)), "two drafts share a WONUM")
    planners = {p["PERSONID"] for p in people}
    for d in drafts:
        tag, sr = d["WONUM"], sr_by_id.get(d["ORIGRECORDID"])
        check(tag not in taken and id_map.kind_of(tag, "new") == "draft",
              f"{tag}: number outside WO{cat.DRAFT_WO_START}+ or already used")
        check(d["STATUS"] == "WAPPR" and d["ORIGRECORDCLASS"] == "SR" and d["WORKTYPE"] == "CM",
              f"{tag}: a draft is a WAPPR corrective work order that comes from an SR")
        check(not any(d[c] for c in ("PARENT", "PERSONGROUP", "OWNERGROUP", "JPNUM", "SUPERVISOR", "LEAD", "FAILURECODE",
                                     "PROBLEMCODE", "SCHEDSTART", "SCHEDFINISH", "ACTSTART", "ACTFINISH")),
              f"{tag}: a draft has no parent, team, job plan, crew, codes or dates yet")
        check(d["REPORTEDBY"] in planners, f"{tag}: REPORTEDBY {d['REPORTEDBY']} is not a person in the dataset")
        if sr:
            check(d["CLASSSTRUCTUREID"] == sr["CLASSSTRUCTUREID"], f"{tag}: classification differs from its SR")
            check(d["DESCRIPTION_LONGDESCRIPTION"] == sr["DESCRIPTION_LONGDESCRIPTION"], f"{tag}: text differs from its SR")
            created = datetime.fromisoformat(d["REPORTDATE"])
            check(datetime.fromisoformat(sr["REPORTDATE"]) <= created <= AS_OF,
                  f"{tag}: created before its SR or after the as-of time")
            check((sr["SITEID"], sr["ORGID"]) == (d["SITEID"], d["ORGID"]), f"{tag}: site or org differs from its SR")

    # Every related-work SR has a work order to look from. A duplicate has none of its own: its
    # cluster's first report has the one work order the whole cluster is grouped onto.
    has_wo = with_wo | set(origins)
    for t, a in answer.items():
        if a["EXPECTED_ALERT"] in ("Related past work", "Related planned work"):
            check(t in has_wo, f"{t}: related-work SR with no work order to run similarity on")
        if a["EXPECTED_ALERT"] == drafts_gen.DUPLICATE:
            check(t not in has_wo, f"{t}: a duplicate report must not get a work order of its own")
            firsts = [r for r in a["RELATED_RECORDS"].split(";")
                      if r.startswith("SR") and answer[r]["EXPECTED_ALERT"] != drafts_gen.DUPLICATE]
            check(len(firsts) == 1 and firsts[0] in has_wo,
                  f"{t}: its cluster's first report {firsts} has no work order to group onto")

    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for e in errors[:40]:
            print(f" - {e}")
        sys.exit(1)
    print(f"OK: draft checks passed ({len(drafts)} drafts)")


if __name__ == "__main__":
    main()
