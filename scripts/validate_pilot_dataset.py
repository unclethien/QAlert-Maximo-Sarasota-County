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

import id_map
import pilot_catalog as cat

DATA = Path(__file__).resolve().parent.parent / "data"
PHONE = re.compile(r"^941-555-01\d\d$")
EMAIL = re.compile(r"^[a-z0-9.]+@example\.(com|org|net)$")
ENTERED_BY = re.compile(r"<div>Entered by: (\w+)</div>")
LD_PHONES = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
LD_EMAILS = re.compile(r"[\w.+-]+@[\w.-]+")

NOT_COUNTY = "Possibly not County responsibility"
EXPECTED_SRS = 65
EXPECTED_ALERTS = {
    "Missing or incorrect information": 22,
    NOT_COUNTY: 6,
    "Possible duplicate": 7,
    "Related past work": 5,
    "Related planned work": 4,
    "None": 21,
}
# Provisional channel mix: most requests come from residents through 311Connect (app or web),
# about one in five from Contact Center staff (phone or email). Values are QAlert origin labels.
STAFF_ORIGIN = "Control Panel"
EXPECTED_CHANNELS = {
    "311Connect mobile app": 32,
    "311 web portal": 19,
    "phone call to 311": 11,
    "email to the Contact Center": 3,
}
EXPECTED_USE_CASES = {
    "Missing-Information Detection": 28,
    "Duplicate Identification": 16,
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


def check_structured_fields(srs, wos, request_by_id, employee_by_id, persons, points):
    """The SR's structured fields carry what QAlert holds, by the mapping proposed to the County."""
    active_people = {p["PERSONID"] for p in persons if p["STATUS"] == "ACTIVE"}
    point_by_code = {p["ADDRESS_ID"]: p for p in points}
    known = {(p["STREETNO"], p["STREETNAME"].upper(), p["CITY"]) for p in points}
    codes = set(cat.SOURCE_CODES.values())
    for sr in srs:
        t = sr["TICKETID"]
        req = request_by_id.get(int(sr["EXTERNALSYSTEM_TICKETID"]))
        check(id_map.kind_of(t, "new") == "sr", f"{t}: SR number outside SR{cat.SR_START}+")
        check(id_map.kind_of(sr["EXTERNALSYSTEM_TICKETID"], "new") == "request",
              f"{t}: QAlert request {sr['EXTERNALSYSTEM_TICKETID']} outside {cat.REQUEST_START}+")
        if not req:
            continue
        check(sr["SOURCE"] in codes and sr["SOURCE"] == cat.SOURCE_CODES.get(req["intakeMethod"] or req["origin"]),
              f"{t}: SOURCE {sr['SOURCE']!r} does not match QAlert origin {req['origin']!r} / {req['intakeMethod']!r}")
        check(sr["REPORTEDPRIORITY"] == str(req["priorityToDisplay"]),
              f"{t}: REPORTEDPRIORITY {sr['REPORTEDPRIORITY']!r} differs from QAlert priority {req['priorityToDisplay']}")

        # Reporter: whoever entered the request; the resident is the affected contact.
        emp = employee_by_id.get(req["employeeId"])
        person = emp["id"] if emp and emp["id"] in active_people else ""
        if req["intakeMethod"]:
            reporter = (emp["phone"], emp["email"]) if emp else ("", "")
        else:
            reporter = (req["phone"], req["email"])
        check(sr["REPORTEDBY"] == sr["AFFECTEDPERSON"] == person,
              f"{t}: REPORTEDBY and AFFECTEDPERSON must be {person or 'blank'!r} (an active Maximo person entered it)")
        check((sr["REPORTEDPHONE"], sr["REPORTEDEMAIL"]) == reporter, f"{t}: reported contact is not who entered it")
        check((sr["AFFECTEDPHONE"], sr["AFFECTEDEMAIL"]) == (req["phone"], req["email"]),
              f"{t}: affected contact differs from the QAlert resident")

        # Service address: as written in QAlert, with the address point's code only when it matches one.
        address = (req["streetNum"], req["streetName"], req["cityName"])
        check((sr["STADDRNUMBER"], sr["STADDRSTREET"].upper(), sr["CITY"]) == address,
              f"{t}: service address differs from the QAlert location")
        check(sr["STREETADDRESS"] == " ".join(filter(None, (sr["STADDRNUMBER"], sr["STADDRSTREET"]))),
              f"{t}: STREETADDRESS is not the number and street")
        check((sr["STATEPROVINCE"], sr["COUNTRY"]) == (("FL", "US") if sr["CITY"] else ("", "")),
              f"{t}: state and country are set exactly when there is a city")
        point = point_by_code.get(sr["SADDRESSCODE"])
        if sr["SADDRESSCODE"]:
            check(point is not None and (point["STREETNO"], point["STREETNAME"], point["CITY"], point["ZIP"],
                                         point["LATITUDE"], point["LONGITUDE"])
                  == (sr["STADDRNUMBER"], sr["STADDRSTREET"], sr["CITY"], sr["POSTALCODE"], sr["LATITUDEY"], sr["LONGITUDEX"]),
                  f"{t}: address {sr['SADDRESSCODE']} fields differ from the address point")
        else:
            check(address not in known, f"{t}: an address that matches an address point must carry its code")
            check(sr["POSTALCODE"] == "", f"{t}: only a matched address has a ZIP")
        if req["streetName"]:
            check(sr["LATITUDEY"] != "" and (float(sr["LATITUDEY"]), float(sr["LONGITUDEX"])) == (req["latitude"], req["longitude"]),
                  f"{t}: coordinates differ from where QAlert placed the request")
        else:
            check(sr["LATITUDEY"] == sr["LONGITUDEX"] == "", f"{t}: a request with no street has no coordinates")
    sr_by_id = {sr["TICKETID"]: sr for sr in srs}
    for wo in wos:
        check(id_map.kind_of(wo["WONUM"], "new") == "wo", f"{wo['WONUM']}: WO number outside WO{cat.WO_START}+")
        check_wo_address(wo, sr_by_id.get(wo["ORIGRECORDID"]), points)


WO_ADDRESS_COLUMNS = ("STADDRNUMBER", "STADDRSTREET", "STREETADDRESS", "CITY", "STATEPROVINCE", "POSTALCODE",
                      "COUNTRY", "LATITUDEY", "LONGITUDEX")


def check_wo_address(wo, sr, points):
    """A WO's service address is its SR's. With no SR, it is an address point, or for street-wide
    work a point among the street's address points, with no number or ZIP."""
    w = wo["WONUM"]
    if sr:
        check(all(wo[c] == sr[c] for c in WO_ADDRESS_COLUMNS), f"{w}: service address differs from its SR's")
        return
    street = [p for p in points if (p["STREETNAME"], p["CITY"]) == (wo["STADDRSTREET"], wo["CITY"])]
    check(bool(street) and wo["LATITUDEY"] != "", f"{w}: past or planned work must sit on a known street")
    if not street or wo["LATITUDEY"] == "":
        return
    check(wo["STREETADDRESS"] == " ".join(filter(None, (wo["STADDRNUMBER"], wo["STADDRSTREET"])))
          and (wo["STATEPROVINCE"], wo["COUNTRY"]) == ("FL", "US"), f"{w}: street address, state or country is wrong")
    if wo["STADDRNUMBER"]:
        check(any((p["STREETNO"], p["ZIP"], p["LATITUDE"], p["LONGITUDE"])
                  == (wo["STADDRNUMBER"], wo["POSTALCODE"], wo["LATITUDEY"], wo["LONGITUDEX"]) for p in street),
              f"{w}: address differs from its address point")
    else:
        lat, lon = float(wo["LATITUDEY"]), float(wo["LONGITUDEX"])
        lats, lons = [float(p["LATITUDE"]) for p in street], [float(p["LONGITUDE"]) for p in street]
        check(wo["POSTALCODE"] == "" and min(lats) <= lat <= max(lats) and min(lons) <= lon <= max(lons),
              f"{w}: street-wide work must sit among its street's address points, with no ZIP")


def main():
    srs = read_csv("maximo/sr.csv")
    wos = read_csv("maximo/wo.csv")
    logs = read_csv("maximo/worklog.csv")
    persons = read_csv("maximo/person.csv")
    points = read_csv("reference/address-points.csv")
    rules = read_csv("reference/required-information.csv")
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
    unattributed = []
    check(len(sr_ids) == len(srs) == EXPECTED_SRS, f"expected {EXPECTED_SRS} unique SRs, found {len(srs)}")
    for sr in srs:
        rid = int(sr["EXTERNALSYSTEM_TICKETID"])
        check(rid in request_by_id, f"{sr['TICKETID']}: QAlert request {rid} missing")
        match = ENTERED_BY.search(sr["DESCRIPTION_LONGDESCRIPTION"])
        req = request_by_id.get(rid)
        if req and req["origin"] == STAFF_ORIGIN:
            # A staff-entered request either names its employee in both systems or in neither.
            if req["employeeId"] is None:
                unattributed.append(sr["TICKETID"])
                check(match is None, f"{sr['TICKETID']}: unattributed SR must not have an 'Entered by' line")
            else:
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
            req = request_by_id[a["requestId"]]
            staff_named = req["origin"] == STAFF_ORIGIN and req["employeeId"] is not None
            check((a["routeId"] in usernames) if staff_named else a["routeId"] == "",
                  f"activity {a['id']}: creator {a['routeId']!r} does not match the request origin")
    for r in requests:
        check(r["typeId"] in type_ids, f"request {r['id']}: unknown type {r['typeId']}")

    # Answer key coverage.
    check({a["TICKETID"] for a in answers} == sr_ids, "answer key must cover every SR exactly once")
    request_by_ticket = {sr["TICKETID"]: request_by_id[int(sr["EXTERNALSYSTEM_TICKETID"])] for sr in srs}
    for a in answers:
        req = request_by_ticket[a["TICKETID"]]
        check(a["QALERT_ORIGIN"] == req["origin"], f"{a['TICKETID']}: QALERT_ORIGIN differs from the QAlert request")
        check(bool(a["ENTERED_BY_EMPLOYEE_ID"]) == (req["origin"] == STAFF_ORIGIN and req["employeeId"] is not None),
              f"{a['TICKETID']}: only attributed staff-entered requests have an entered-by employee")
        emp = employee_by_id.get(a["ENTERED_BY_EMPLOYEE_ID"])
        if emp:
            expected = "Entered-by employee" if emp["active"] else "Department supervisor"
        elif req["origin"] == STAFF_ORIGIN:
            expected = "Contact Center"
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
        if a["EXPECTED_ALERT"] in ("Missing or incorrect information", NOT_COUNTY):
            check(bool(a["SUGGESTED_CLARIFICATION_QUESTION"]), f"{a['TICKETID']}: flagged SR needs a clarification question")
        if a["EXPECTED_ALERT"] == NOT_COUNTY:
            check("refer the customer to" in a["EXPECTED_RECOMMENDATION"],
                  f"{a['TICKETID']}: a possibly non-County request must say who to refer the customer to")
    channels = Counter(a["SUBMITTED_VIA"] for a in answers)
    check(channels == Counter(EXPECTED_CHANNELS), f"channel counts {dict(channels)} differ from {EXPECTED_CHANNELS}")
    alerts = Counter(a["EXPECTED_ALERT"] for a in answers)
    use_cases = Counter(a["USE_CASE"] for a in answers)
    check(alerts == Counter(EXPECTED_ALERTS), f"alert counts {dict(alerts)} differ from {EXPECTED_ALERTS}")
    check(use_cases == Counter(EXPECTED_USE_CASES), f"use case counts {dict(use_cases)} differ from {EXPECTED_USE_CASES}")

    # Records match the shapes of the County's Maximo samples.
    check(len(unattributed) == 1, f"expected exactly one unattributed staff-entered SR, found {unattributed}")
    class_ids = set(cat.CLASSIFICATIONS)
    sr_statuses = Counter(sr["STATUS"] for sr in srs)
    check(set(sr_statuses) <= set(cat.SR_STATUSES), f"unexpected SR statuses {sorted(set(sr_statuses) - set(cat.SR_STATUSES))}")
    for status in ("NEW", "INPRG", "PENDING"):
        check(sr_statuses[status] >= 1, f"at least one SR must be {status}")
    sr_logged = {log["RECORDKEY"] for log in logs if log["CLASS"] == "SR"}
    for sr in srs:
        check(sr["OWNERGROUP"] == "", f"{sr['TICKETID']}: SRs carry no team; OWNERGROUP must be blank")
        check(sr["CLASSSTRUCTUREID"] in class_ids, f"{sr['TICKETID']}: unknown classification {sr['CLASSSTRUCTUREID']!r}")
        if sr["STATUS"] == "NEW":
            check(sr["TICKETID"] not in sr_logged, f"{sr['TICKETID']}: a NEW SR has not been reviewed, so it has no work log")
    work_types = Counter(wo["WORKTYPE"] for wo in wos)
    check(set(work_types) <= set(cat.WORK_TYPES), f"unexpected work types {sorted(set(work_types) - set(cat.WORK_TYPES))}")
    check(work_types["IN"] >= 1, "at least one WO must be an inspection (IN)")
    sr_status_by_id = {sr["TICKETID"]: sr["STATUS"] for sr in srs}
    for wo in wos:
        tag = wo["WONUM"]
        check(wo["STATUS"] in cat.WO_STATUSES, f"{tag}: unexpected status {wo['STATUS']!r}")
        check(wo["PERSONGROUP"] in cat.PERSON_GROUPS, f"{tag}: unknown person group {wo['PERSONGROUP']!r}")
        check(wo["OWNERGROUP"] == wo["PERSONGROUP"], f"{tag}: OWNERGROUP should match PERSONGROUP")
        check(wo["CLASSSTRUCTUREID"] in class_ids, f"{tag}: unknown classification {wo['CLASSSTRUCTUREID']!r}")
        if wo["WORKTYPE"] == "CP":
            check(wo["JPNUM"] == "" and wo["FAILURECODE"] == "" and wo["PROBLEMCODE"] == "",
                  f"{tag}: planned capital work has no job plan or failure codes")
        else:
            plan = cat.JOB_PLANS.get(wo["JPNUM"])
            check(plan is not None, f"{tag}: unknown job plan {wo['JPNUM']!r}")
            if plan:
                check(wo["PERSONGROUP"] == plan[1], f"{tag}: person group differs from job plan {wo['JPNUM']}")
            check(wo["FAILURECODE"] in cat.FAILURE_CODES, f"{tag}: unknown failure code {wo['FAILURECODE']!r}")
            check(wo["PROBLEMCODE"] in cat.PROBLEM_CODES, f"{tag}: unknown problem code {wo['PROBLEMCODE']!r}")
        check(bool(wo["ACTFINISH"]) == (wo["STATUS"] in ("COMP", "CLOSE", "CAN") and wo["WORKTYPE"] != "CP"),
              f"{tag}: ACTFINISH must be set exactly when field work finished")
        if wo["ORIGRECORDID"] and wo["STATUS"] == "INPRG":
            check(sr_status_by_id.get(wo["ORIGRECORDID"]) == "INPRG", f"{tag}: origin SR should be INPRG while the WO is")
    for sr in srs:
        if sr["DESCRIPTION"].split(",")[0] in ("Low Water Pressure", "Curb Stop"):
            check(sr["COMMODITY"] == "WATER_PIPE", f"{sr['TICKETID']}: Low Water Pressure and Curb Stop use WATER_PIPE")
    # The expected classification differs from the SR's own only where the request was misclassified.
    sr_class = {sr["TICKETID"]: sr["CLASSSTRUCTUREID"] for sr in srs}
    for a in answers:
        expected, misclassified = a["EXPECTED_CLASSSTRUCTUREID"], "Suggested reclassification:" in a["EXPECTED_RECOMMENDATION"]
        check(expected in cat.CLASSIFICATIONS, f"{a['TICKETID']}: unknown expected classification {expected!r}")
        check((expected != sr_class.get(a["TICKETID"])) == misclassified,
              f"{a['TICKETID']}: expected classification must differ from the SR's exactly when it is misclassified")
    for a in answers:
        group = a["EXPECTED_PERSONGROUP"]
        check(group == "" or group in cat.PERSON_GROUPS, f"{a['TICKETID']}: unknown expected team {group!r}")
        if not group:
            check("Drainage / Flooding" in a["EXPECTED_RECOMMENDATION"] or a["EXPECTED_ALERT"] == NOT_COUNTY,
                  f"{a['TICKETID']}: only non-Utilities or non-County requests have no expected team")

    # Work log types, and requests closed by a note instead of a work order (the County's
    # misrouted pattern: a RESOLUTION note on the SR, no WO).
    log_types = Counter(log["LOGTYPE"] for log in logs)
    check(set(log_types) <= set(cat.LOG_TYPES), f"unexpected work log types {sorted(set(log_types) - set(cat.LOG_TYPES))}")
    with_wo = {wo["ORIGRECORDID"] for wo in wos if wo["ORIGRECORDID"]}
    resolution_srs = {log["RECORDKEY"] for log in logs if log["LOGTYPE"] == "RESOLUTION"}
    for log in logs:
        if log["LOGTYPE"] == "RESOLUTION":
            check(log["CLASS"] == "SR" and log["RECORDKEY"] not in with_wo
                  and sr_status_by_id.get(log["RECORDKEY"]) in ("RESOLVED", "CLOSED"),
                  f"work log {log['WORKLOGID']}: a RESOLUTION note closes an SR that has no work order")
    check(any(a["SCENARIO"] == "Incorrect classification" and a["TICKETID"] in resolution_srs for a in answers),
          "at least one misclassified SR must be closed by a RESOLUTION note, with no work order")
    check(any(a["EXPECTED_ALERT"] == NOT_COUNTY and a["TICKETID"] not in with_wo
              and sr_status_by_id[a["TICKETID"]] in ("RESOLVED", "CLOSED") for a in answers),
          "at least one non-County SR must be resolved by a note, with no work order")

    # Required information: one rule per County request type, and every missing-information SR
    # names the rules it breaks.
    rule_by_id = {r["RULE_ID"]: r for r in rules}
    check(len(rule_by_id) == len(rules), "required-information rule ids must be unique")
    for rtype in cat.REQUEST_TYPES:
        if rtype != "Drainage / Flooding":
            count = sum(r["REQUEST_TYPE"] == rtype for r in rules)
            check(count == 1, f"request type {rtype!r} needs exactly one required-information rule, has {count}")
    submitted_type = {sr["TICKETID"]: sr["DESCRIPTION"].split(",")[0] for sr in srs}
    for a in answers:
        gaps = [g for g in a["REQUIRED_INFO_GAP"].split(";") if g]
        check(bool(gaps) == (a["SCENARIO"] in cat.REQUIRED_INFO_SCENARIOS),
              f"{a['TICKETID']}: REQUIRED_INFO_GAP is set exactly for missing-information scenarios")
        for g in gaps:
            rule = rule_by_id.get(g)
            check(rule is not None and rule["REQUEST_TYPE"] in ("ALL", submitted_type[a["TICKETID"]]),
                  f"{a['TICKETID']}: rule {g!r} does not exist or does not apply to its request type")

    # Location scenarios agree with the GIS stand-in, and so does who supplies the water.
    answer_by_ticket = {a["TICKETID"]: a for a in answers}
    utility_by_address = {(p["STREETNO"], p["STREETNAME"].upper(), p["CITY"]): p["UTILITY"] for p in points}
    city_utility_srs = []
    for sr in srs:
        req = request_by_id[int(sr["EXTERNALSYSTEM_TICKETID"])]
        address = (req["streetNum"], req["streetName"], req["cityName"])
        in_gis = address in known_addresses
        a = answer_by_ticket[sr["TICKETID"]]
        scenario = a["SCENARIO"]
        if scenario in ("Missing location", "Invalid location"):
            check(not in_gis, f"{sr['TICKETID']}: {scenario} SR unexpectedly matches an address point")
        else:
            check(in_gis, f"{sr['TICKETID']}: address {req['streetNum']} {req['streetName']} is not in address-points.csv")
        utility = utility_by_address.get(address, cat.COUNTY_UTILITY)
        for city_utility in set(cat.CITY_UTILITY_STREETS.values()):
            if f"refer the customer to {city_utility}" in a["EXPECTED_RECOMMENDATION"]:
                check(utility == city_utility, f"{sr['TICKETID']}: referred to {city_utility}, but GIS says {utility}")
        if utility != cat.COUNTY_UTILITY:
            city_utility_srs.append(sr["TICKETID"])
            check(a["EXPECTED_ALERT"] == NOT_COUNTY and utility in a["EXPECTED_RECOMMENDATION"]
                  and a["EXPECTED_PERSONGROUP"] == "",
                  f"{sr['TICKETID']}: an address {utility} serves must be flagged and referred, with no County team")
    check(len(city_utility_srs) >= 1, "at least one SR must be at an address another utility serves")

    # A look-alike at the same address as an earlier request whose work order was finished
    # before it came in: separate work, not a duplicate.
    sr_by_id = {sr["TICKETID"]: sr for sr in srs}
    wo_by_id = {wo["WONUM"]: wo for wo in wos}
    same_address = 0
    for a in answers:
        refs = [r for r in a["RELATED_RECORDS"].split(";") if r]
        if not a["SCENARIO"].startswith("Look-alike") or not any(r in wo_by_id for r in refs):
            continue
        earlier = next(sr_by_id[r] for r in refs if r in sr_by_id)
        wo = next(wo_by_id[r] for r in refs if r in wo_by_id)
        here = sr_by_id[a["TICKETID"]]
        same_address += 1
        check(here["DESCRIPTION"].split(", ", 1)[1:] == earlier["DESCRIPTION"].split(", ", 1)[1:],
              f"{a['TICKETID']}: a look-alike with a related work order must be at the earlier SR's address")
        check(wo["ORIGRECORDID"] == earlier["TICKETID"] and wo["ACTFINISH"] and wo["ACTFINISH"] < here["REPORTDATE"],
              f"{a['TICKETID']}: the earlier work order must be finished before the look-alike was reported")
    check(same_address >= 1, "at least one look-alike must be at the same address as finished work")

    # The mapping gap and inactive staff are both represented.
    unmapped = [e for e in employees if e["id"] not in person_ids]
    check(len(unmapped) >= 1, "at least one QAlert employee must be missing from Maximo PERSON")
    used_unmapped = {a["ENTERED_BY_EMPLOYEE_ID"] for a in answers} & {e["id"] for e in unmapped}
    check(len(used_unmapped) >= 1, "at least one SR must be entered by an unmapped employee")
    check(any(a["ENTERED_BY_ACTIVE"] == "N" for a in answers), "at least one SR must be entered by an inactive employee")
    check(any(a["FOLLOW_UP_CONTACT_TYPE"] == "Owning group supervisor" for a in answers),
          "at least one resident request must be anonymous")

    check_structured_fields(srs, wos, request_by_id, employee_by_id, persons, points)
    for log in logs:
        check(id_map.kind_of(log["WORKLOGID"], "new") == "worklog",
              f"work log {log['WORKLOGID']}: outside {cat.WORKLOG_START}+")

    # Maximo field lengths: PERSON.TITLE and PERSON.DEPARTMENT hold 30 characters.
    for p in persons:
        for col in ("TITLE", "DEPARTMENT"):
            check(len(p[col]) <= 30, f"person {p['PERSONID']}: {col} longer than Maximo's 30 characters")

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
        phones += filter(None, (sr["REPORTEDPHONE"], sr["AFFECTEDPHONE"]))
        emails += filter(None, (sr["REPORTEDEMAIL"], sr["AFFECTEDEMAIL"]))
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
