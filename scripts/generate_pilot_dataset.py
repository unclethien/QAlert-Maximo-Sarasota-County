#!/usr/bin/env python3
"""Generate the synthetic Sarasota MAS AI Pilot sample dataset.

Writes linked Maximo CSVs, mock QAlert JSON, a GIS address stand-in, and an answer key
under data/. Output is deterministic: rerunning produces identical files.

Usage (from the repository root):
    python3 scripts/generate_pilot_dataset.py
"""

import csv
import html
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pilot_catalog as cat

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ = ZoneInfo("America/New_York")
WINDOW_START = datetime(2026, 8, 1, tzinfo=TZ)
WINDOW_DAYS = 87  # through 2026-10-27
AS_OF = datetime(2026, 10, 27, 17, 0, tzinfo=TZ)

# QAlert activity codes are illustrative; the real code table is not public.
ACTIVITY_CODES = {"Created": 1, "Assigned": 4, "Closed": 15}
QALERT_STATUS = {"open": 0, "closed": 1, "in_progress": 3}

# The text-only SR shape of today's QAlert feed. The training history keeps it.
MAXIMO_SR_COLUMNS = [
    "TICKETID", "CLASS", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "STATUS", "STATUSDATE",
    "REPORTEDBY", "REPORTEDNAME", "REPORTEDPHONE", "REPORTEDEMAIL", "REPORTDATE",
    "AFFECTEDPERSON", "AFFECTEDNAME", "AFFECTEDEMAIL", "EXTERNALSYSTEM", "EXTERNALSYSTEM_TICKETID",
    "COMMODITYGROUP", "COMMODITY", "CLASSSTRUCTUREID", "OWNERGROUP", "SITEID", "ORGID", "CREATEDBY", "CREATIONDATE",
]
# The service address Maximo keeps on an SR (its TKSERVICEADDRESS child).
SR_ADDRESS_COLUMNS = [
    "SADDRESSCODE", "STADDRNUMBER", "STADDRSTREET", "STREETADDRESS", "CITY", "STATEPROVINCE", "POSTALCODE",
    "COUNTRY", "LATITUDEY", "LONGITUDEX",
]
# The pilot's SR shape: what QAlert knows goes into Maximo fields, not only into the text.
# REPORTEDNAME and AFFECTEDNAME are gone because Maximo does not store a free-text name.
STRUCTURED_SR_COLUMNS = [
    "TICKETID", "CLASS", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "STATUS", "STATUSDATE",
    "SOURCE", "REPORTEDPRIORITY", "REPORTEDBY", "REPORTEDPHONE", "REPORTEDEMAIL", "REPORTDATE",
    "AFFECTEDPERSON", "AFFECTEDPHONE", "AFFECTEDEMAIL", "EXTERNALSYSTEM", "EXTERNALSYSTEM_TICKETID",
    "COMMODITYGROUP", "COMMODITY", "CLASSSTRUCTUREID", "OWNERGROUP", *SR_ADDRESS_COLUMNS,
    "SITEID", "ORGID", "CREATEDBY", "CREATIONDATE",
]
MAXIMO_WO_COLUMNS = [
    "WONUM", "PARENT", "STATUS", "STATUSDATE", "WORKTYPE", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION",
    "ORIGRECORDID", "ORIGRECORDCLASS", "REPORTEDBY", "REPORTDATE", "CLASSSTRUCTUREID", "JPNUM",
    "PERSONGROUP", "OWNERGROUP", "SUPERVISOR", "LEAD", "FAILURECODE", "PROBLEMCODE",
    "SCHEDSTART", "SCHEDFINISH", "ACTSTART", "ACTFINISH", "SITEID", "ORGID",
]
MAXIMO_WORKLOG_COLUMNS = [
    "WORKLOGID", "RECORDKEY", "CLASS", "LOGTYPE", "CREATEBY", "CREATEDATE", "CLIENTVIEWABLE",
    "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "SITEID", "ORGID",
]
MAXIMO_PERSON_COLUMNS = [
    "PERSONID", "DISPLAYNAME", "FIRSTNAME", "LASTNAME", "PRIMARYEMAIL", "PRIMARYPHONE",
    "DEPARTMENT", "TITLE", "STATUS",
]
ADDRESS_COLUMNS = ["ADDRESS_ID", "STREETNO", "STREETNAME", "CITY", "STATE", "ZIP", "LATITUDE", "LONGITUDE",
                   "PARCEL_ID", "UTILITY"]
REQUIRED_INFO_COLUMNS = ["RULE_ID", "REQUEST_TYPE", "REQUIRED_INFORMATION"]
ANSWER_KEY_COLUMNS = [
    "TICKETID", "QALERT_REQUEST_ID", "USE_CASE", "SCENARIO", "EXPECTED_ALERT", "ISSUE_SUMMARY",
    "MISSING_INFORMATION", "REQUIRED_INFO_GAP", "QALERT_ORIGIN", "SUBMITTED_VIA", "ENTERED_BY_EMPLOYEE_ID", "ENTERED_BY_NAME",
    "ENTERED_BY_DEPARTMENT", "ENTERED_BY_PHONE", "ENTERED_BY_EMAIL", "ENTERED_BY_ACTIVE", "ENTERED_BY_IN_MAXIMO",
    "FOLLOW_UP_CONTACT_TYPE", "FOLLOW_UP_CONTACT_NAME", "FOLLOW_UP_CONTACT_PHONE", "FOLLOW_UP_CONTACT_EMAIL",
    "SUGGESTED_CLARIFICATION_QUESTION", "EXPECTED_CLASSSTRUCTUREID", "EXPECTED_PERSONGROUP", "RELATED_RECORDS", "EXPECTED_RECOMMENDATION",
]

# Planner notes on held SRs, by who entered the request.
SR_REVIEW_NOTES = {
    "resident": [
        "Reviewed SR. Need more information before dispatch. Called customer, no answer, left voicemail.",
        "Reviewed. Holding for clarification from the customer.",
        "Called customer twice, no answer. Will try again tomorrow.",
        "Reviewed SR. Unclear what is being requested. Asked the customer for more detail through 311Connect.",
    ],
    "staff": [
        "Reviewed SR. Not enough detail to dispatch. Sent back to the contact center to clarify.",
        "Reviewed SR. Unclear what is being requested. Need callback from whoever took the call.",
    ],
}


# ---- formatting helpers --------------------------------------------------------------------

def maximo_date(dt):
    return dt.isoformat(timespec="seconds")


def qalert_date(dt):
    return f"{dt.month}/{dt.day}/{dt.year} {dt.strftime('%I:%M %p').lstrip('0')}"


def html_text(text):
    return html.escape(text, quote=True).replace("&#x27;", "&#39;")


class Phones:
    """Hands out unique numbers from the 555-0100..0199 range reserved for fiction."""

    def __init__(self):
        self.next = 100

    def take(self):
        if self.next > 199:
            raise RuntimeError("Ran out of fictional 941-555-01XX numbers")
        number = f"941-555-0{self.next}"
        self.next += 1
        return number


# ---- reference data ------------------------------------------------------------------------

def build_people(phones):
    staff = []
    for emp_id, user, first, last, dept, active, in_maximo in cat.QALERT_STAFF:
        staff.append(dict(id=emp_id, username=user, firstName=first, lastName=last,
                          email=f"{first}.{last}@example.org".lower(), phone=phones.take(),
                          department=dept, active=active, in_maximo=in_maximo))
    field = []
    for pid, first, last, title, discipline in cat.FIELD_STAFF:
        field.append(dict(id=pid, first=first, last=last, title=title, discipline=discipline,
                          email=f"{first}.{last}@example.org".lower(), phone=phones.take()))
    return staff, field


def collect_streets():
    streets = set(cat.EXTRA_STREETS)
    for s in cat.SCENARIOS:
        form = s["addr"]
        if form[0] in ("valid", "street_only", "bad_number"):
            streets.add((form[1], form[2]))
        elif form[0] == "typo":
            streets.add((form[2], form[3]))
    for street, city, *_ in cat.HISTORICAL_WOS:
        streets.add((street, city))
    for street, city, *_ in cat.PLANNED_WOS:
        streets.add((street, city))
    return sorted(streets)


def build_address_points(streets):
    """Four neighboring address points per street; centroid used for street-only locations."""
    points, centroids, rows = {}, {}, []
    for street, city in streets:
        r = random.Random(f"{cat.SEED}:{street}")
        box = cat.CITIES[city]
        lat0, lon0 = r.uniform(*box["lat"]), r.uniform(*box["lon"])
        zip_code = r.choice(box["zips"])
        first_number = r.randrange(100, 8000, 2)
        centroids[street] = (round(lat0 + 0.00045, 6), round(lon0 + 0.0003, 6))
        for i in range(4):
            point = dict(ADDRESS_ID=f"AP{len(rows) + 1:05d}", STREETNO=str(first_number + 6 * i),
                         STREETNAME=street, CITY=city, STATE="FL", ZIP=zip_code,
                         LATITUDE=round(lat0 + 0.0003 * i, 6), LONGITUDE=round(lon0 + 0.0002 * i, 6),
                         PARCEL_ID=str(r.randrange(10 ** 9, 10 ** 10)),
                         UTILITY=cat.CITY_UTILITY_STREETS.get((street, city), cat.COUNTY_UTILITY))
            points[(street, i)] = point
            rows.append(point)
    return points, centroids, rows


def resolve_address(form, points, centroids):
    """Return the location as written on the SR and as stored in QAlert."""
    kind = form[0]
    if kind == "valid":
        _, street, city, house = form
        p = points[(street, house)]
        return dict(line=f"{p['STREETNO']} {street}, {city}", short=f"{p['STREETNO']} {street}",
                    num=p["STREETNO"], street=street, city=city, lat=p["LATITUDE"], lon=p["LONGITUDE"],
                    code=p["ADDRESS_ID"], zip=p["ZIP"])
    if kind == "street_only":
        _, street, city = form
        lat, lon = centroids[street]
        return dict(line=f"{street}, {city}", short=street, num="", street=street, city=city, lat=lat, lon=lon)
    if kind == "none":
        return dict(line=form[1], short="", num="", street="", city=form[1], lat=0.0, lon=0.0)
    if kind == "bad_number":
        _, street, city, number = form
        lat, lon = centroids[street]
        return dict(line=f"{number} {street}, {city}", short=f"{number} {street}", num=str(number),
                    street=street, city=city, lat=lat, lon=lon)
    if kind == "typo":
        _, shown, street, city, house = form
        p = points[(street, house)]
        return dict(line=f"{p['STREETNO']} {shown}, {city}", short=f"{p['STREETNO']} {shown}",
                    num=p["STREETNO"], street=shown, city=city, lat=p["LATITUDE"], lon=p["LONGITUDE"])
    if kind == "out_of_county":
        _, street, city, number, lat, lon = form
        return dict(line=f"{number} {street}, {city}", short=f"{number} {street}", num=str(number),
                    street=street, city=city, lat=lat, lon=lon)
    raise ValueError(f"Unknown address form {kind}")


# ---- build -----------------------------------------------------------------------------------

def assign_times(rng):
    """Resolve each scenario's report time; relative times are resolved after absolute ones."""
    times = {}
    for s in cat.SCENARIOS:
        when = s.get("when")
        if when and when[0] == "at":
            times[s["key"]] = datetime.strptime(when[1], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        elif not when:
            day = rng.randrange(WINDOW_DAYS)
            times[s["key"]] = WINDOW_START + timedelta(days=day, hours=rng.randint(7, 17), minutes=rng.randrange(60))
    for s in cat.SCENARIOS:
        when = s.get("when")
        if when and when[0] == "after":
            times[s["key"]] = times[when[1]] + timedelta(hours=when[2], minutes=rng.randrange(5, 50))
    return times


def make_resident(rng, name_pairs, phones, channel):
    """A resident and the contact details QAlert holds for them.

    App users sign in with an email, so app requests always carry one; the web portal and the
    Contact Center may collect a phone, an email, or both.
    """
    first, last = name_pairs.pop()
    name = f"{first} {last}"
    if rng.random() < 0.35:
        name = name.upper()
    email = f"{first[0]}{last}{rng.randint(10, 99)}@{rng.choice(['example.com', 'example.net'])}".lower()
    has_email = channel == "app" or rng.random() >= 0.15
    has_phone = rng.random() < {"app": 0.7, "web": 0.6}.get(channel, 1.0) or not has_email
    return dict(name=name, email=email if has_email else "", phone=phones.take() if has_phone else "")


def long_description(resident, loc, text, employee_id):
    contact = " ".join(filter(None, (html_text(resident["name"]), resident["email"], resident["phone"])))
    customer = f"<div>Customer: {contact}</div>"
    if loc["lat"]:
        address = (f"<div>Address: {html_text(loc['line'])}, FL <a target=\"_blank\" "
                   f"href=\"https://www.google.com/maps/search/{loc['lat']},{loc['lon']}\">Map</a></div>")
    else:
        address = f"<div>Address: {html_text(loc['line'])}, FL</div>"
    entered_by = f"<div>Entered by: {employee_id}</div>" if employee_id else ""
    return f"{customer}{address}<div>{html_text(text)}</div>{entered_by}"


def maximo_sr_fields(origin, intake, rtype, loc, resident, employee):
    """The Maximo SR fields for what QAlert holds about a request.

    This is the field mapping proposed to the County (docs/qalert-integration-proposal.md):
    - SOURCE: the QAlert origin, or the intake method for staff-entered requests.
    - REPORTEDPRIORITY: the request type's QAlert priority, on Maximo's 1-4 scale.
    - Reporter: whoever entered the request. A resident reports their own request. A Contact
      Center employee is REPORTEDBY only with an active Maximo person record (Maximo then also
      sets AFFECTEDPERSON to that person); otherwise their QAlert phone and email are the reported
      contact. The resident is always the affected contact.
    - Service address: a matched address point sends its code and every field, because Maximo
      stores only the code when the code is sent alone. Anything else keeps what was written,
      so a missing or invalid address stays missing or invalid.
    """
    staff = intake is not None
    person = employee and employee["in_maximo"] and employee["active"]
    reporter = employee if staff else resident
    fields = {
        "SOURCE": cat.SOURCE_CODES[intake or origin],
        "REPORTEDPRIORITY": str(cat.REQUEST_TYPES[rtype]["priority"]),
        "REPORTEDBY": employee["id"] if person else "",
        "REPORTEDPHONE": reporter["phone"] if reporter else "",
        "REPORTEDEMAIL": reporter["email"] if reporter else "",
        "AFFECTEDPERSON": employee["id"] if person else "",
        "AFFECTEDPHONE": resident["phone"], "AFFECTEDEMAIL": resident["email"],
    }
    street_address = " ".join(filter(None, (loc["num"], loc["street"])))
    fields.update({
        "SADDRESSCODE": loc.get("code", ""), "STADDRNUMBER": loc["num"], "STADDRSTREET": loc["street"],
        "STREETADDRESS": street_address, "CITY": loc["city"],
        "STATEPROVINCE": "FL" if loc["city"] else "", "POSTALCODE": loc.get("zip", ""),
        "COUNTRY": "US" if loc["city"] else "",
        "LATITUDEY": str(loc["lat"]) if loc["lat"] else "", "LONGITUDEX": str(loc["lon"]) if loc["lat"] else "",
    })
    return fields


def crew_for(discipline, field):
    """Supervisor, lead, and planner for a request discipline."""
    by = {f["discipline"]: [] for f in field}
    for f in field:
        by[f["discipline"]].append(f)
    if discipline == "wastewater":
        return by["wastewater"][0], by["wastewater"][1], by["planner_wastewater"][0]
    lead = by["meter"][0] if discipline == "meter" else by["water"][1]
    return by["water"][0], lead, by["planner_water"][0]


def build():
    rng = random.Random(cat.SEED)
    phones = Phones()
    staff, field = build_people(phones)
    staff_by_id = {s["id"]: s for s in staff}
    water_leads = [f for f in field if f["discipline"] == "water" and f["title"].startswith("Crew Lead")]

    streets = collect_streets()
    points, centroids, address_rows = build_address_points(streets)

    name_pairs = [(f, l) for f in cat.RESIDENT_FIRST for l in cat.RESIDENT_LAST]
    rng.shuffle(name_pairs)

    times = assign_times(rng)
    scenarios = sorted(cat.SCENARIOS, key=lambda s: (times[s["key"]], s["key"]))

    srs, requests, activity, wos, logs, answers = [], [], [], [], [], []
    sr_by_key, wo_by_key, residents = {}, {}, {}
    pending_logs = []  # (datetime, (class, record key), author, description, text[, log type; CLIENTNOTE if absent])

    # Historical and planned work orders, kept for ID assignment after sorting.
    work_orders = []
    for street, city, house, rtype, months_ago, short, notes in cat.HISTORICAL_WOS:
        discipline = cat.REQUEST_TYPES[rtype]["discipline"]
        sup, lead, _ = crew_for(discipline, field)
        if discipline == "water":
            lead = water_leads[(months_ago + len(street)) % len(water_leads)]
        start = AS_OF - timedelta(days=30 * months_ago + rng.randint(0, 20), hours=rng.randint(0, 6))
        start = start.replace(hour=rng.randint(7, 14), minute=rng.randrange(60))
        addr = f"{points[(street, house)]['STREETNO']} {street}" if house is not None else street
        work_orders.append(dict(kind="historical", street=street, house=house, date=start, rtype=rtype,
                                desc=f"{addr}:  {short}", ld=f"<div>{html_text(addr)}, {city}, FL</div><div>{html_text(short.capitalize())}</div>",
                                worktype="IN" if "INSPECTION" in short else "CM", status="CLOSE", sup=sup, lead=lead,
                                actstart=start, actfinish=start + timedelta(hours=rng.randint(2, 5)), notes=notes,
                                closing="Work complete. Site restored and cleaned up."))
    for street, city, rtype, status, start, finish, desc, scope, notes in cat.PLANNED_WOS:
        sup, _, planner = crew_for(cat.REQUEST_TYPES[rtype]["discipline"], field)
        sched_start = datetime.strptime(start, "%Y-%m-%d").replace(hour=7, tzinfo=TZ)
        sched_finish = datetime.strptime(finish, "%Y-%m-%d").replace(hour=16, tzinfo=TZ)
        created = min(sched_start, AS_OF) - timedelta(days=rng.randint(20, 45))
        work_orders.append(dict(kind="planned", street=street, house=None, date=created, rtype=rtype,
                                desc=desc, ld=f"<div>{html_text(scope)}</div>", worktype="CP", status=status,
                                sup=sup, lead=planner, schedstart=sched_start,
                                schedfinish=sched_finish, actstart=sched_start if status == "INPRG" else None,
                                notes=notes, author=planner))

    # Service requests, QAlert requests, follow-up work orders.
    for s in scenarios:
        key, rtype = s["key"], s["type"]
        rt = cat.REQUEST_TYPES[rtype]
        discipline, route = rt["discipline"], rt["route"]
        reported = times[key]
        created_in_qalert = reported - timedelta(minutes=rng.randint(2, 9))
        origins, intake, staff_entered, _ = cat.CHANNELS[s["channel"]]
        origin = origins[sum(map(ord, key)) % len(origins)]
        employee = staff_by_id[s["entered_by"]] if staff_entered and not s.get("unattributed") else None
        if s.get("resident", "").startswith("same_as:"):
            resident = residents[s["resident"].split(":", 1)[1]]
        elif s.get("anonymous"):
            resident = dict(name="Anonymous", email="", phone="")
        else:
            resident = make_resident(rng, name_pairs, phones, s["channel"])
        residents[key] = resident
        loc = resolve_address(s["addr"], points, centroids)
        description = f"{rtype}, {loc['short']}" if loc["short"] else rtype
        ld = long_description(resident, loc, s["text"], employee and employee["id"])
        sup, lead, planner = crew_for(discipline, field)

        wo_spec, resolved = s.get("wo"), s.get("resolved")
        if wo_spec:
            dispatched = reported + timedelta(hours=rng.randint(1, 20), minutes=rng.randrange(60))
            finished = dispatched + timedelta(hours=rng.randint(1, 4), minutes=rng.randrange(60))
            if wo_spec["status"] == "INPRG":
                sr_status, sr_status_date = "INPRG", dispatched
            else:
                sr_status = "CLOSED" if wo_spec["status"] in ("CLOSE", "CAN") else "RESOLVED"
                sr_status_date = finished + timedelta(hours=1)
        elif resolved:  # closed by a planner's note, with no work order
            sr_status, sr_status_date = resolved["status"], reported + timedelta(hours=resolved["hours"])
            pending_logs.append((sr_status_date - timedelta(minutes=5), ("SR", key), planner["id"], "",
                                 resolved["note"], resolved["logtype"]))
        else:
            sr_status, sr_status_date = s.get("sr_status", "QUEUED"), reported
        if sr_status in ("CLOSED", "RESOLVED"):
            qalert_status = QALERT_STATUS["closed"]
        elif sr_status == "INPRG":
            qalert_status = QALERT_STATUS["in_progress"]
        else:
            qalert_status = QALERT_STATUS["open"]

        sr = dict(key=key, reported=reported, row={
            "CLASS": "SR", "DESCRIPTION": description, "DESCRIPTION_LONGDESCRIPTION": ld,
            "STATUS": sr_status, "STATUSDATE": maximo_date(sr_status_date), "REPORTDATE": maximo_date(reported),
            **maximo_sr_fields(origin, intake, rtype, loc, resident, employee), "EXTERNALSYSTEM": "QAlert",
            "COMMODITYGROUP": rt["cgroup"], "COMMODITY": rt["commodity"], "CLASSSTRUCTUREID": rt["classid"],
            "OWNERGROUP": "",
            "SITEID": cat.SITEID, "ORGID": cat.ORGID, "CREATEDBY": cat.INTEGRATION_ACCOUNT["id"],
            "CREATIONDATE": maximo_date(reported),
        })
        srs.append(sr)
        sr_by_key[key] = sr

        last_action = sr_status_date if qalert_status != QALERT_STATUS["open"] else created_in_qalert + timedelta(minutes=1)
        requests.append(dict(key=key, created=created_in_qalert, row={
            "status": qalert_status, "createDate": qalert_date(created_in_qalert),
            "createDateUnix": int(created_in_qalert.timestamp()), "lastAction": qalert_date(last_action),
            "lastActionUnix": int(last_action.timestamp()), "typeId": rt["type_id"], "typeName": rtype,
            "priorityToDisplay": rt["priority"], "hasLinks": False, "comments": s["text"],
            "streetNum": loc["num"], "streetName": loc["street"].upper(), "crossName": "",
            "cityName": loc["city"], "latitude": loc["lat"], "longitude": loc["lon"],
            "origin": origin, "name": resident["name"], "email": resident["email"],
            "phone": resident["phone"], "intakeMethod": intake, "employeeId": employee["id"] if employee else None,
        }))
        # Resident-submitted requests have no staff creator.
        activity.append(dict(key=key, at=created_in_qalert, codeDesc="Created",
                             routeId=employee["username"] if employee else ""))
        activity.append(dict(key=key, at=created_in_qalert + timedelta(minutes=1), codeDesc="Assigned", routeId=route))
        if qalert_status == QALERT_STATUS["closed"]:
            activity.append(dict(key=key, at=sr_status_date, codeDesc="Closed", routeId=route))

        if wo_spec:
            wo_lead = lead
            if discipline == "water":
                wo_lead = water_leads[ord(key[-1]) % len(water_leads)]
            short_addr = loc["short"] or loc["city"]
            work_orders.append(dict(kind="followup", key=key, street=loc["street"], house=None, date=reported,
                                    rtype=rtype, desc=f"{short_addr}:  {wo_spec['short']}", ld=ld,
                                    worktype=wo_spec["worktype"], status=wo_spec["status"],
                                    sup=sup, lead=wo_lead, actstart=dispatched, actfinish=finished,
                                    statusdate=sr_status_date, notes=wo_spec["logs"]))
        for note in s.get("notes", []):
            pending_logs.append((reported + timedelta(hours=3), ("SR", key), planner["id"], "", note, "CLIENTNOTE"))

        # A request from another utility's area is still waiting for its first review.
        if s["group"] in ("missing", "responsibility") and "notes" not in s and not resolved and not s.get("other_utility"):
            notes = SR_REVIEW_NOTES["staff" if staff_entered else "resident"]
            note = notes[ord(key[-1]) % len(notes)]
            if wo_spec:
                note = "Reviewed SR and dispatched to field crew."
            pending_logs.append((reported + timedelta(hours=1, minutes=rng.randrange(50)), ("SR", key), planner["id"], "",
                                 note, "CLIENTNOTE"))
        elif s["group"] == "control" and not wo_spec:
            pending_logs.append((reported + timedelta(hours=2), ("SR", key), planner["id"], "",
                                 "Reviewed. Complete request, assigned to crew queue.", "CLIENTNOTE"))
        elif s.get("cluster") and key.endswith("1"):
            pending_logs.append((reported + timedelta(minutes=40), ("SR", key), planner["id"], "",
                                 "Priority call. Assigned to on-call crew.", "CLIENTNOTE"))

        s.update(_employee=employee, _loc=loc, _origin=origin, _resident=resident, _supervisor=sup)

    # Assign IDs in chronological order.
    for i, sr in enumerate(sorted(srs, key=lambda r: (r["reported"], r["key"]))):
        sr["id"] = f"SR{cat.SR_START + i}"
    for i, req in enumerate(sorted(requests, key=lambda r: (r["created"], r["key"]))):
        req["id"] = cat.REQUEST_START + i
    request_id_by_key = {r["key"]: r["id"] for r in requests}
    for sr in srs:
        sr["row"]["TICKETID"] = sr["id"]
        sr["row"]["EXTERNALSYSTEM_TICKETID"] = str(request_id_by_key[sr["key"]])
    work_orders.sort(key=lambda w: (w["date"], w["desc"]))
    for i, wo in enumerate(work_orders):
        wo["id"] = f"WO{cat.WO_START + i}"
        if wo["kind"] == "followup":
            wo_by_key[wo["key"]] = wo

    # Work order rows and their logs.
    for wo in work_orders:
        is_followup = wo["kind"] == "followup"
        statusdate = wo.get("statusdate") or wo.get("actfinish") or wo["date"]
        # The WO keeps the classification and team it was actually given, even when the request was
        # misclassified: that record is what shows the AI how routing went.
        rt = cat.REQUEST_TYPES[wo["rtype"]]
        corrective = wo["kind"] != "planned"
        finished = wo.get("actfinish") and wo["kind"] != "planned" and wo["status"] != "INPRG"
        wos.append({
            "WONUM": wo["id"], "PARENT": "", "STATUS": wo["status"], "STATUSDATE": maximo_date(statusdate),
            "WORKTYPE": wo["worktype"], "DESCRIPTION": wo["desc"], "DESCRIPTION_LONGDESCRIPTION": wo["ld"],
            "ORIGRECORDID": sr_by_key[wo["key"]]["id"] if is_followup else "",
            "ORIGRECORDCLASS": "SR" if is_followup else "",
            "REPORTEDBY": cat.INTEGRATION_ACCOUNT["id"] if is_followup else wo["sup"]["id"],
            "REPORTDATE": maximo_date(wo["date"]), "CLASSSTRUCTUREID": rt["classid"],
            "JPNUM": rt["jpnum"] if corrective else "", "PERSONGROUP": rt["persongroup"],
            "OWNERGROUP": rt["persongroup"], "SUPERVISOR": wo["sup"]["id"], "LEAD": wo["lead"]["id"],
            "FAILURECODE": rt["failure"] if corrective else "", "PROBLEMCODE": rt["problem"] if corrective else "",
            "SCHEDSTART": maximo_date(wo["schedstart"]) if wo.get("schedstart") else "",
            "SCHEDFINISH": maximo_date(wo["schedfinish"]) if wo.get("schedfinish") else "",
            "ACTSTART": maximo_date(wo["actstart"]) if wo.get("actstart") else "",
            "ACTFINISH": maximo_date(wo["actfinish"]) if finished else "",
            "SITEID": cat.SITEID, "ORGID": cat.ORGID,
        })
        author = wo.get("author") or wo["lead"]
        if wo["kind"] == "planned":
            for i, note in enumerate(wo["notes"]):
                pending_logs.append((wo["date"] + timedelta(days=3 + 5 * i), ("WORKORDER", wo["id"]), author["id"], wo["desc"], note))
            continue
        pending_logs.append((wo["actstart"], ("WORKORDER", wo["id"]), author["id"], wo["desc"], "Arrived on site."))
        span = (wo["actfinish"] - wo["actstart"]) / (len(wo["notes"]) + 1)
        for i, note in enumerate(wo["notes"]):
            pending_logs.append((wo["actstart"] + span * (i + 1), ("WORKORDER", wo["id"]), author["id"], wo["desc"], note))
        if wo.get("closing"):
            pending_logs.append((wo["actfinish"], ("WORKORDER", wo["id"]), author["id"], wo["desc"], wo["closing"]))

    pending_logs.sort(key=lambda p: (p[0], p[1][1]))
    for i, (at, (cls, record), author, desc, text, *logtype) in enumerate(pending_logs):
        record_id = sr_by_key[record]["id"] if cls == "SR" else record
        logs.append({
            "WORKLOGID": str(cat.WORKLOG_START + i), "RECORDKEY": record_id, "CLASS": cls,
            "LOGTYPE": logtype[0] if logtype else "CLIENTNOTE",
            "CREATEBY": author, "CREATEDATE": maximo_date(at), "CLIENTVIEWABLE": "1",
            "DESCRIPTION": desc, "DESCRIPTION_LONGDESCRIPTION": text, "SITEID": cat.SITEID, "ORGID": cat.ORGID,
        })

    # QAlert activity rows.
    activity.sort(key=lambda a: (a["at"], request_id_by_key[a["key"]], ACTIVITY_CODES[a["codeDesc"]]))
    activity_rows = [dict(id=i + 1, requestId=request_id_by_key[a["key"]], displayDate=qalert_date(a["at"]),
                          code=ACTIVITY_CODES[a["codeDesc"]], codeDesc=a["codeDesc"], routeId=a["routeId"])
                     for i, a in enumerate(activity)]

    # Answer key.
    for s in scenarios:
        answers.append(answer_row(s, sr_by_key, wo_by_key, request_id_by_key, work_orders, times))

    request_rows = []
    for req in sorted(requests, key=lambda r: r["id"]):
        request_rows.append({"id": req["id"], **req["row"]})

    return dict(staff=staff, field=field, address_rows=address_rows,
                srs=sorted((sr["row"] for sr in srs), key=lambda r: r["TICKETID"]),
                wos=wos, logs=logs, requests=request_rows, activity=activity_rows, answers=answers)


# ---- answer key ----------------------------------------------------------------------------

def follow_up(s):
    """Who to ask when a request needs clarification: (type, name, phone, email, sentence).

    Residents who submitted through the app or web portal are asked directly. Phone and email
    requests go back to the Contact Center employee who entered them, or to that employee's
    supervisor once they are inactive. A staff-entered request that records no employee goes back
    to the Contact Center as a team. Anonymous requests go to the owning group's supervisor.
    """
    emp, res, sup = s["_employee"], s["_resident"], s["_supervisor"]
    via = cat.CHANNELS[s["channel"]][3]
    if s.get("unattributed"):
        return ("Contact Center", "Contact Center", "", "",
                f"The request came in as a {via}, but neither the SR nor QAlert records who entered it; "
                f"send the question to the Contact Center to find the call.")
    if emp and not emp["active"]:
        name = f"{emp['department']} supervisor"
        return ("Department supervisor", name, "", "",
                f"The request was entered by {emp['firstName']} {emp['lastName']} (employee {emp['id']}), "
                f"who is no longer active; send the question to the {name} instead.")
    if emp:
        sentence = (f"Contact {emp['firstName']} {emp['lastName']} ({emp['department']}, {emp['phone']}, "
                    f"{emp['email']}), who took the {via} and entered it in QAlert as employee {emp['id']}")
        if not emp["in_maximo"]:
            sentence += "; this employee has no Maximo person record, so the contact details come from QAlert"
        return ("Entered-by employee", f"{emp['firstName']} {emp['lastName']}", emp["phone"], emp["email"], sentence + ".")
    if res["phone"] or res["email"]:
        reach = " or ".join(filter(None, (res["phone"], res["email"])))
        return ("Resident", res["name"], res["phone"], res["email"],
                f"The resident submitted this through the {via}; contact {res['name']} directly ({reach}).")
    name = f"{sup['first']} {sup['last']}"
    return ("Owning group supervisor", name, sup["phone"], sup["email"],
            f"The request was submitted anonymously through the {via} with no phone or email, so send the "
            f"question to {name} ({sup['title']}, {sup['phone']}, {sup['email']}).")


def required_info_gaps(s):
    """The required-information rules a request breaks: its own `gaps`, or its scenario's default."""
    defaults = s.get("gaps") or cat.REQUIRED_INFO_SCENARIOS.get(s["scenario"], ())
    type_rule = next((rid for rid, rtype, _ in cat.REQUIRED_INFORMATION if rtype == s["type"]), None)
    return [type_rule if rule == "TYPE" else rule for rule in defaults]


def answer_row(s, sr_by_key, wo_by_key, request_id_by_key, work_orders, times):
    key, emp, group = s["key"], s["_employee"], s["group"]
    contact_type, contact_name, contact_phone, contact_email, contact_sentence = follow_up(s)
    sr_id = sr_by_key[key]["id"]
    related, alert, recommendation = [], "None", ""
    use_case = {"missing": cat.USE_CASE_MISSING, "responsibility": cat.USE_CASE_MISSING,
                "duplicate": cat.USE_CASE_DUPLICATE, "lookalike": cat.USE_CASE_DUPLICATE,
                "historical": cat.USE_CASE_CONTEXT, "planned": cat.USE_CASE_CONTEXT,
                "control": cat.USE_CASE_CONTROL}[group]

    if group == "responsibility":
        alert = "Possibly not County responsibility"
        recommendation = (f"Check responsibility before dispatch: {s['issue']} {contact_sentence} "
                          f"Ask: \"{s['question']}\" If confirmed, refer the customer to {s['refer_to']}.")
    elif group == "missing":
        alert = "Missing or incorrect information"
        recommendation = f"Flag before dispatch: {s['issue']} {contact_sentence} Ask: \"{s['question']}\""
        if s.get("true_type"):
            recommendation += f" Suggested reclassification: {s['true_type']}."
        if key in wo_by_key:
            recommendation += f" A crew was already sent ({wo_by_key[key]['id']}); clarification first could have avoided this trip."
            related.append(wo_by_key[key]["id"])
    elif group == "duplicate":
        members = sorted((k for k in sr_by_key if k.startswith(f"D{s['cluster']}")), key=lambda k: times[k])
        primary = members[0]
        if key == primary:
            others = [sr_by_key[k]["id"] for k in members[1:]]
            related += others
            recommendation = (f"Primary report. Later requests {', '.join(others)} describe the same problem at the "
                              f"same location and should be linked to this SR.")
        else:
            related.append(sr_by_key[primary]["id"])
            alert = "Possible duplicate"
            hours = round((times[key] - times[primary]).total_seconds() / 3600)
            recommendation = (f"Likely duplicate of {sr_by_key[primary]['id']} ({s['issue']} Reported {hours} hour{'s' if hours != 1 else ''} later "
                              f"at the same or a neighboring address.) Link to the primary SR instead of dispatching again.")
            if primary in wo_by_key:
                related.append(wo_by_key[primary]["id"])
                recommendation += f" Work order {wo_by_key[primary]['id']} already covers it."
    elif group == "lookalike":
        other = sr_by_key[s["related"]]["id"]
        related.append(other)
        recommendation = f"Similar to {other} but not a duplicate: {s['reason']}. Treat as a new request."
        if s.get("same_address"):
            earlier = wo_by_key[s["related"]]
            related.append(earlier["id"])
            recommendation += (f" Give the crew work order {earlier['id']} (completed "
                               f"{earlier['actfinish'].date().isoformat()}) as context.")
    elif group in ("historical", "planned"):
        street = s["_loc"]["street"]
        kind = "historical" if group == "historical" else "planned"
        matches = [w for w in work_orders if w["kind"] == kind and w["street"] == street]
        related += [w["id"] for w in matches]
        alert = "Related past work" if kind == "historical" else "Related planned work"
        refs = "; ".join(f"{w['id']} ({w['desc'].strip()}, {w['date'].date().isoformat()})" for w in matches)
        if kind == "historical":
            recommendation = f"Surface prior work at this location: {refs}. {s['issue']} {s['advice']}"
        else:
            refs = "; ".join(f"{w['id']} ({w['desc']}, scheduled {w['schedstart'].date().isoformat()} to {w['schedfinish'].date().isoformat()}, status {w['status']})" for w in matches)
            recommendation = f"Surface planned work on this street: {refs}. {s['issue']} {s['advice']}"
    else:
        recommendation = "No issue detected. The request is complete and correctly classified; route normally."

    return {
        "TICKETID": sr_id, "QALERT_REQUEST_ID": str(request_id_by_key[key]), "USE_CASE": use_case,
        "SCENARIO": s["scenario"], "EXPECTED_ALERT": alert, "ISSUE_SUMMARY": s.get("issue", "Complete request."),
        "MISSING_INFORMATION": s.get("missing", ""), "REQUIRED_INFO_GAP": ";".join(required_info_gaps(s)),
        "QALERT_ORIGIN": s["_origin"],
        "SUBMITTED_VIA": cat.CHANNELS[s["channel"]][3],
        "ENTERED_BY_EMPLOYEE_ID": emp["id"] if emp else "",
        "ENTERED_BY_NAME": f"{emp['firstName']} {emp['lastName']}" if emp else "",
        "ENTERED_BY_DEPARTMENT": emp["department"] if emp else "",
        "ENTERED_BY_PHONE": emp["phone"] if emp else "", "ENTERED_BY_EMAIL": emp["email"] if emp else "",
        "ENTERED_BY_ACTIVE": ("Y" if emp["active"] else "N") if emp else "",
        "ENTERED_BY_IN_MAXIMO": ("Y" if emp["in_maximo"] else "N") if emp else "",
        "FOLLOW_UP_CONTACT_TYPE": contact_type, "FOLLOW_UP_CONTACT_NAME": contact_name,
        "FOLLOW_UP_CONTACT_PHONE": contact_phone, "FOLLOW_UP_CONTACT_EMAIL": contact_email,
        "SUGGESTED_CLARIFICATION_QUESTION": s.get("question", ""),
        # The classification of what the request really is, so a misclassified SR expects its corrected class.
        "EXPECTED_CLASSSTRUCTUREID": cat.REQUEST_TYPES[s.get("true_type") or s["type"]]["classid"],
        # Another utility's customer gets no County team.
        "EXPECTED_PERSONGROUP": "" if s.get("other_utility") else cat.REQUEST_TYPES[s.get("true_type") or s["type"]]["persongroup"],
        "RELATED_RECORDS": ";".join(related),
        "EXPECTED_RECOMMENDATION": recommendation,
    }


# ---- output --------------------------------------------------------------------------------

def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    d = build()
    persons = [{"PERSONID": cat.INTEGRATION_ACCOUNT["id"], "DISPLAYNAME": cat.INTEGRATION_ACCOUNT["name"],
                "FIRSTNAME": "", "LASTNAME": "", "PRIMARYEMAIL": cat.INTEGRATION_ACCOUNT["email"], "PRIMARYPHONE": "",
                "DEPARTMENT": "Information Technology", "TITLE": "Integration service account", "STATUS": "ACTIVE"}]
    for f in d["field"]:
        persons.append({"PERSONID": f["id"], "DISPLAYNAME": f"{f['first']} {f['last']}", "FIRSTNAME": f["first"],
                        "LASTNAME": f["last"], "PRIMARYEMAIL": f["email"], "PRIMARYPHONE": f["phone"],
                        "DEPARTMENT": "Public Utilities", "TITLE": f["title"], "STATUS": "ACTIVE"})
    for s in d["staff"]:
        if s["in_maximo"]:
            persons.append({"PERSONID": s["id"], "DISPLAYNAME": f"{s['firstName']} {s['lastName']}",
                            "FIRSTNAME": s["firstName"], "LASTNAME": s["lastName"], "PRIMARYEMAIL": s["email"],
                            "PRIMARYPHONE": s["phone"],
                            "DEPARTMENT": cat.MAXIMO_DEPARTMENT.get(s["department"], s["department"]),
                            "TITLE": "Customer Service Rep",
                            "STATUS": "ACTIVE" if s["active"] else "INACTIVE"})
    persons.sort(key=lambda p: p["PERSONID"])

    write_csv(DATA / "maximo" / "sr.csv", STRUCTURED_SR_COLUMNS, d["srs"])
    write_csv(DATA / "maximo" / "wo.csv", MAXIMO_WO_COLUMNS, d["wos"])
    write_csv(DATA / "maximo" / "worklog.csv", MAXIMO_WORKLOG_COLUMNS, d["logs"])
    write_csv(DATA / "maximo" / "person.csv", MAXIMO_PERSON_COLUMNS, persons)
    write_csv(DATA / "reference" / "address-points.csv", ADDRESS_COLUMNS, d["address_rows"])
    write_csv(DATA / "reference" / "required-information.csv", REQUIRED_INFO_COLUMNS,
              [dict(zip(REQUIRED_INFO_COLUMNS, rule)) for rule in cat.REQUIRED_INFORMATION])
    write_csv(DATA / "answer-key.csv", ANSWER_KEY_COLUMNS, d["answers"])

    write_json(DATA / "qalert" / "requests.json", d["requests"])
    write_json(DATA / "qalert" / "activity.json", d["activity"])
    write_json(DATA / "qalert" / "employees.json", [
        {k: s[k] for k in ("id", "username", "firstName", "lastName", "email", "phone", "department", "active")}
        for s in d["staff"]])
    write_json(DATA / "qalert" / "types.json", [
        {"id": t["type_id"], "name": name, "parent": 0, "dept": t["dept"], "isPrivate": False, "priorityValue": t["priority"]}
        for name, t in sorted(cat.REQUEST_TYPES.items(), key=lambda kv: kv[1]["type_id"])])
    write_json(DATA / "qalert" / "departments.json", [{"id": i, "name": n} for i, n in cat.DEPARTMENTS])

    print(f"SRs: {len(d['srs'])}  WOs: {len(d['wos'])}  work logs: {len(d['logs'])}  "
          f"QAlert requests: {len(d['requests'])}  activity: {len(d['activity'])}  "
          f"address points: {len(d['address_rows'])}  persons: {len(persons)}")


if __name__ == "__main__":
    main()
