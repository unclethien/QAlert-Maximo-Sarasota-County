#!/usr/bin/env python3
"""Validate the generated pilot dataset: links between files, scenario coverage, and synthetic-data safety.

Usage (from the repository root):
    python3 scripts/validate_pilot_dataset.py
Exits 1 if any check fails.
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PHONE = re.compile(r"^941-555-01\d\d$")
EMAIL = re.compile(r"^[a-z0-9.]+@example\.(com|org|net)$")
ENTERED_BY = re.compile(r"<div>Entered by: (\w+)</div>")
LD_PHONES = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
LD_EMAILS = re.compile(r"[\w.+-]+@[\w.-]+")

EXPECTED_ALERTS = {
    "Missing or incorrect information": 24,
    "Possible duplicate": 7,
    "Related past work": 5,
    "Related planned work": 4,
    "None": 20,
}
# Provisional channel mix: most requests come from residents through 311Connect (app or web),
# about one in five from Contact Center staff (phone or email). Values are QAlert origin labels.
STAFF_ORIGIN = "Control Panel"
EXPECTED_CHANNELS = {
    "311Connect mobile app": 30,
    "311 web portal": 18,
    "phone call to 311": 9,
    "email to the Contact Center": 3,
}
EXPECTED_USE_CASES = {
    "Missing-Information Detection": 24,
    "Duplicate Identification": 15,
    "Historical / Planned Work Context": 9,
    "Control (no issue)": 12,
}

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def read_csv(name):
    with (DATA / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main():
    srs = read_csv("maximo/sr.csv")
    wos = read_csv("maximo/wo.csv")
    logs = read_csv("maximo/worklog.csv")
    persons = read_csv("maximo/person.csv")
    points = read_csv("reference/address-points.csv")
    answers = read_csv("answer-key.csv")
    requests = read_json("qalert/requests.json")
    activity = read_json("qalert/activity.json")
    employees = read_json("qalert/employees.json")
    types = read_json("qalert/types.json")

    sr_ids = {r["TICKETID"] for r in srs}
    wo_ids = {r["WONUM"] for r in wos}
    request_by_id = {r["id"]: r for r in requests}
    employee_by_id = {e["id"]: e for e in employees}
    person_ids = {p["PERSONID"] for p in persons}
    type_ids = {t["id"] for t in types}
    known_addresses = {(p["STREETNO"], p["STREETNAME"].upper(), p["CITY"]) for p in points}

    # Links between files.
    check(len(sr_ids) == len(srs) == 60, f"expected 60 unique SRs, found {len(srs)}")
    for sr in srs:
        rid = int(sr["EXTERNALSYSTEM_TICKETID"])
        check(rid in request_by_id, f"{sr['TICKETID']}: QAlert request {rid} missing")
        match = ENTERED_BY.search(sr["DESCRIPTION_LONGDESCRIPTION"])
        req = request_by_id.get(rid)
        if req and req["origin"] == STAFF_ORIGIN:
            check(match is not None, f"{sr['TICKETID']}: staff-entered SR has no 'Entered by' line")
            check(req["intakeMethod"] in ("Phone", "Email"), f"{sr['TICKETID']}: staff-entered request needs an intakeMethod")
            if match:
                emp = match.group(1)
                check(emp in employee_by_id, f"{sr['TICKETID']}: employee {emp} missing from employees.json")
                check(req["employeeId"] == emp, f"{sr['TICKETID']}: Entered by differs from QAlert employeeId")
        elif req:
            check(match is None, f"{sr['TICKETID']}: resident-submitted SR must not have an 'Entered by' line")
            check(req["employeeId"] is None and req["intakeMethod"] is None,
                  f"{sr['TICKETID']}: resident-submitted request must not carry an employee or intake method")
        check(sr["REPORTEDBY"] == "MWQSCINT", f"{sr['TICKETID']}: reporter is not the integration account")
    for wo in wos:
        if wo["ORIGRECORDID"]:
            check(wo["ORIGRECORDID"] in sr_ids, f"{wo['WONUM']}: origin {wo['ORIGRECORDID']} missing")
        for field in ("SUPERVISOR", "LEAD", "REPORTEDBY"):
            check(wo[field] in person_ids, f"{wo['WONUM']}: {field} {wo[field]} is not a Maximo person")
    for log in logs:
        target = sr_ids if log["CLASS"] == "SR" else wo_ids
        check(log["RECORDKEY"] in target, f"work log {log['WORKLOGID']}: record {log['RECORDKEY']} missing")
        check(log["CREATEBY"] in person_ids, f"work log {log['WORKLOGID']}: author {log['CREATEBY']} is not a Maximo person")
    for a in activity:
        check(a["requestId"] in request_by_id, f"activity {a['id']}: request {a['requestId']} missing")
    created = {a["requestId"] for a in activity if a["codeDesc"] == "Created"}
    check(created == set(request_by_id), "every QAlert request needs exactly one Created activity")
    usernames = {e["username"] for e in employees}
    for a in activity:
        if a["codeDesc"] == "Created":
            staff_entered = request_by_id[a["requestId"]]["origin"] == STAFF_ORIGIN
            check((a["routeId"] in usernames) if staff_entered else a["routeId"] == "",
                  f"activity {a['id']}: creator {a['routeId']!r} does not match the request origin")
    for r in requests:
        check(r["typeId"] in type_ids, f"request {r['id']}: unknown type {r['typeId']}")

    # Answer key coverage.
    check({a["TICKETID"] for a in answers} == sr_ids, "answer key must cover every SR exactly once")
    request_by_ticket = {sr["TICKETID"]: request_by_id[int(sr["EXTERNALSYSTEM_TICKETID"])] for sr in srs}
    for a in answers:
        req = request_by_ticket[a["TICKETID"]]
        check(a["QALERT_ORIGIN"] == req["origin"], f"{a['TICKETID']}: QALERT_ORIGIN differs from the QAlert request")
        check(bool(a["ENTERED_BY_EMPLOYEE_ID"]) == (req["origin"] == STAFF_ORIGIN),
              f"{a['TICKETID']}: only staff-entered requests have an entered-by employee")
        emp = employee_by_id.get(a["ENTERED_BY_EMPLOYEE_ID"])
        if emp:
            expected = "Entered-by employee" if emp["active"] else "Department supervisor"
        elif req["phone"] or req["email"]:
            expected = "Resident"
            check((a["FOLLOW_UP_CONTACT_PHONE"], a["FOLLOW_UP_CONTACT_EMAIL"]) == (req["phone"], req["email"]),
                  f"{a['TICKETID']}: resident contact differs from the QAlert request")
        else:
            expected = "Owning group supervisor"
            check(a["FOLLOW_UP_CONTACT_PHONE"] in {p["PRIMARYPHONE"] for p in persons},
                  f"{a['TICKETID']}: supervisor contact is not a Maximo person")
        check(a["FOLLOW_UP_CONTACT_TYPE"] == expected,
              f"{a['TICKETID']}: follow-up contact {a['FOLLOW_UP_CONTACT_TYPE']!r}, expected {expected!r}")
        for ref in filter(None, a["RELATED_RECORDS"].split(";")):
            check(ref in sr_ids or ref in wo_ids, f"{a['TICKETID']}: related record {ref} missing")
        emp = employee_by_id.get(a["ENTERED_BY_EMPLOYEE_ID"])
        if emp:
            check((a["ENTERED_BY_IN_MAXIMO"] == "Y") == (emp["id"] in person_ids),
                  f"{a['TICKETID']}: ENTERED_BY_IN_MAXIMO disagrees with person.csv")
            check((a["ENTERED_BY_ACTIVE"] == "Y") == emp["active"], f"{a['TICKETID']}: ENTERED_BY_ACTIVE disagrees")
        if a["EXPECTED_ALERT"] == "Missing or incorrect information":
            check(bool(a["SUGGESTED_CLARIFICATION_QUESTION"]), f"{a['TICKETID']}: flagged SR needs a clarification question")
    channels = Counter(a["SUBMITTED_VIA"] for a in answers)
    check(channels == Counter(EXPECTED_CHANNELS), f"channel counts {dict(channels)} differ from {EXPECTED_CHANNELS}")
    alerts = Counter(a["EXPECTED_ALERT"] for a in answers)
    use_cases = Counter(a["USE_CASE"] for a in answers)
    check(alerts == Counter(EXPECTED_ALERTS), f"alert counts {dict(alerts)} differ from {EXPECTED_ALERTS}")
    check(use_cases == Counter(EXPECTED_USE_CASES), f"use case counts {dict(use_cases)} differ from {EXPECTED_USE_CASES}")

    # Location scenarios agree with the GIS stand-in.
    scenario_by_ticket = {a["TICKETID"]: a["SCENARIO"] for a in answers}
    for sr in srs:
        req = request_by_id[int(sr["EXTERNALSYSTEM_TICKETID"])]
        in_gis = (req["streetNum"], req["streetName"], req["cityName"]) in known_addresses
        scenario = scenario_by_ticket[sr["TICKETID"]]
        if scenario in ("Missing location", "Invalid location"):
            check(not in_gis, f"{sr['TICKETID']}: {scenario} SR unexpectedly matches an address point")
        else:
            check(in_gis, f"{sr['TICKETID']}: address {req['streetNum']} {req['streetName']} is not in address-points.csv")

    # The mapping gap and inactive staff are both represented.
    unmapped = [e for e in employees if e["id"] not in person_ids]
    check(len(unmapped) >= 1, "at least one QAlert employee must be missing from Maximo PERSON")
    used_unmapped = {a["ENTERED_BY_EMPLOYEE_ID"] for a in answers} & {e["id"] for e in unmapped}
    check(len(used_unmapped) >= 1, "at least one SR must be entered by an unmapped employee")
    check(any(a["ENTERED_BY_ACTIVE"] == "N" for a in answers), "at least one SR must be entered by an inactive employee")
    check(any(a["FOLLOW_UP_CONTACT_TYPE"] == "Owning group supervisor" for a in answers),
          "at least one resident request must be anonymous")

    # Synthetic-data safety: every phone and email uses the reserved fictional ranges.
    phones, emails = [], []
    for e in employees:
        phones.append(e["phone"]); emails.append(e["email"])
    for p in persons:
        if p["PRIMARYPHONE"]:
            phones.append(p["PRIMARYPHONE"])
        emails.append(p["PRIMARYEMAIL"])
    for r in requests:
        if r["phone"]:
            phones.append(r["phone"])
        if r["email"]:
            emails.append(r["email"])
    for sr in srs:
        phones += LD_PHONES.findall(sr["DESCRIPTION_LONGDESCRIPTION"])
        emails += [e for e in LD_EMAILS.findall(sr["DESCRIPTION_LONGDESCRIPTION"]) if "google.com" not in e]
        emails.append(sr["REPORTEDEMAIL"])
    for a in answers:
        phones += filter(None, (a["ENTERED_BY_PHONE"], a["FOLLOW_UP_CONTACT_PHONE"]))
        emails += filter(None, (a["ENTERED_BY_EMAIL"], a["FOLLOW_UP_CONTACT_EMAIL"]))
    for p in phones:
        check(bool(PHONE.match(p)), f"phone {p} is outside 941-555-0100..0199")
    for e in emails:
        check(bool(EMAIL.match(e.lower())), f"email {e} is not on a reserved example domain")

    print(f"SRs {len(srs)}, WOs {len(wos)}, work logs {len(logs)}, QAlert requests {len(requests)}, "
          f"activity {len(activity)}, employees {len(employees)} ({len(unmapped)} not in Maximo)")
    print("Use cases:", dict(sorted(use_cases.items())))
    print("Channels:", dict(sorted(channels.items())))
    print("Expected alerts:", dict(sorted(alerts.items())))
    if failures:
        print(f"\nFAILED: {len(failures)} problem(s)")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("\nOK: all checks passed")


if __name__ == "__main__":
    main()
