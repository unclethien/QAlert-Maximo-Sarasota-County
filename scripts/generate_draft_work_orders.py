#!/usr/bin/env python3
"""Generate the planner's draft work orders for the pilot SRs that have none yet.

Maximo shows team recommendations and similar work orders on a work order, not on a service
request. Most pilot SRs are still waiting for review, with no work order, so this writes one draft
for each: status WAPPR, linked to its SR, with the SR's text and classification and no team, job
plan or crew yet. That is the record a planner opens before deciding who goes, and the one the AI
is meant to help with.

A duplicate report gets no draft. Several residents reporting one problem should end up on one
work order: the one their cluster's first report already has, or that report's draft. Grouping
them is what the AI is asked to suggest. The pilot files are read, never changed.

Usage (from the repository root, after generate_pilot_dataset.py):
    python3 scripts/generate_draft_work_orders.py
"""

import csv
from datetime import datetime, timedelta

import pilot_catalog as cat
from generate_pilot_dataset import (AS_OF, DATA, MAXIMO_WORKLOG_COLUMNS, STRUCTURED_SR_COLUMNS, STRUCTURED_WO_COLUMNS,
                                    WO_ADDRESS_COLUMNS, crew_for, maximo_date, write_csv)

OUT = DATA / "maximo" / "drafts"
WO_START = cat.DRAFT_WO_START  # after the pilot's WO2910001-WO2910041, below nothing else
OPEN = ("NEW", "QUEUED", "PENDING")


def read(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


DUPLICATE = "Possible duplicate"


def needs_draft(sr, answer, has_wo):
    """Open County Utilities work with no work order yet, unless it repeats another report."""
    return (sr["STATUS"] in OPEN and not has_wo and bool(answer["EXPECTED_PERSONGROUP"])
            and answer["EXPECTED_ALERT"] != DUPLICATE)


def build():
    srs = read(DATA / "maximo" / "sr.csv")
    answers = {a["TICKETID"]: a for a in read(DATA / "answer-key.csv")}
    with_wo = {w["ORIGRECORDID"] for w in read(DATA / "maximo" / "wo.csv") if w["ORIGRECORDID"]}
    field = [dict(id=pid, first=first, last=last, title=title, discipline=discipline)
             for pid, first, last, title, discipline in cat.FIELD_STAFF]
    drafts = []
    for sr in sorted(srs, key=lambda r: r["TICKETID"]):
        if not needs_draft(sr, answers[sr["TICKETID"]], sr["TICKETID"] in with_wo):
            continue
        filed, _, place = sr["DESCRIPTION"].partition(", ")
        planner = crew_for(cat.REQUEST_TYPES[filed]["discipline"], field)[2]
        # The planner opens the draft within the hour, and always before the dataset's as-of time.
        created = datetime.fromisoformat(sr["REPORTDATE"]) + timedelta(minutes=30 + int(sr["TICKETID"][-3:]) * 7 % 30)
        created = min(created, AS_OF)
        drafts.append({
            "WONUM": f"WO{WO_START + len(drafts)}", "PARENT": "", "STATUS": "WAPPR", "STATUSDATE": maximo_date(created),
            "WORKTYPE": "CM", "DESCRIPTION": f"{place}:  {filed.upper()}" if place else filed.upper(),
            "DESCRIPTION_LONGDESCRIPTION": sr["DESCRIPTION_LONGDESCRIPTION"],
            "ORIGRECORDID": sr["TICKETID"], "ORIGRECORDCLASS": "SR", "REPORTEDBY": planner["id"],
            "REPORTDATE": maximo_date(created),
            # The classification the request arrived with; the team is what the AI should recommend.
            "CLASSSTRUCTUREID": sr["CLASSSTRUCTUREID"], "JPNUM": "", "PERSONGROUP": "", "OWNERGROUP": "",
            "SUPERVISOR": "", "LEAD": "", "FAILURECODE": "", "PROBLEMCODE": "", "SCHEDSTART": "", "SCHEDFINISH": "",
            "ACTSTART": "", "ACTFINISH": "",
            # The draft is for the place the request names, so it takes the SR's service address.
            **{c: sr[c] for c in WO_ADDRESS_COLUMNS},
            "SITEID": cat.SITEID, "ORGID": cat.ORGID,
        })
    return drafts


def main():
    drafts = build()
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "wo.csv", STRUCTURED_WO_COLUMNS, drafts)
    # Header-only, so the loader reads every dataset the same way.
    write_csv(OUT / "sr.csv", STRUCTURED_SR_COLUMNS, [])
    write_csv(OUT / "worklog.csv", MAXIMO_WORKLOG_COLUMNS, [])
    print(f"Draft work orders: {len(drafts)}")


if __name__ == "__main__":
    main()
