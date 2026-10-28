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

MAXIMO_SR_COLUMNS = [
    "TICKETID", "CLASS", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "STATUS", "STATUSDATE",
    "REPORTEDBY", "REPORTEDNAME", "REPORTEDPHONE", "REPORTEDEMAIL", "REPORTDATE",
    "AFFECTEDPERSON", "AFFECTEDNAME", "AFFECTEDEMAIL", "EXTERNALSYSTEM", "EXTERNALSYSTEM_TICKETID",
    "COMMODITYGROUP", "COMMODITY", "OWNERGROUP", "SITEID", "ORGID", "CREATEDBY", "CREATIONDATE",
]
MAXIMO_WO_COLUMNS = [
    "WONUM", "PARENT", "STATUS", "STATUSDATE", "WORKTYPE", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION",
    "ORIGRECORDID", "ORIGRECORDCLASS", "REPORTEDBY", "REPORTDATE", "OWNERGROUP", "SUPERVISOR", "LEAD",
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
ADDRESS_COLUMNS = ["ADDRESS_ID", "STREETNO", "STREETNAME", "CITY", "STATE", "ZIP", "LATITUDE", "LONGITUDE", "PARCEL_ID"]
ANSWER_KEY_COLUMNS = [
    "TICKETID", "QALERT_REQUEST_ID", "USE_CASE", "SCENARIO", "EXPECTED_ALERT", "ISSUE_SUMMARY",
    "MISSING_INFORMATION", "ENTERED_BY_EMPLOYEE_ID", "ENTERED_BY_NAME", "ENTERED_BY_DEPARTMENT",
    "ENTERED_BY_PHONE", "ENTERED_BY_EMAIL", "ENTERED_BY_ACTIVE", "ENTERED_BY_IN_MAXIMO",
    "SUGGESTED_CLARIFICATION_QUESTION", "RELATED_RECORDS", "EXPECTED_RECOMMENDATION",
]

SR_REVIEW_NOTES = [
    "Reviewed SR. Need more information before dispatch. Called customer, no answer, left voicemail.",
    "Reviewed SR. Not enough detail to dispatch. Sent back to the contact center to clarify.",
    "Reviewed. Holding for clarification from the customer.",
    "Called customer twice, no answer. Will try again tomorrow.",
    "Reviewed SR. Unclear what is being requested. Need callback from whoever took the call.",
]


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
                         PARCEL_ID=str(r.randrange(10 ** 9, 10 ** 10)))
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
                    num=p["STREETNO"], street=street, city=city, lat=p["LATITUDE"], lon=p["LONGITUDE"])
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


def pick_entered_by(rng, scenario, staff_by_id, active_staff):
    if scenario.get("entered_by"):
        return staff_by_id[scenario["entered_by"]]
    return rng.choice(active_staff)


def make_resident(rng, name_pairs, phones):
    first, last = name_pairs.pop()
    name = f"{first} {last}"
    if rng.random() < 0.35:
        name = name.upper()
    email = "" if rng.random() < 0.15 else f"{first[0]}{last}{rng.randint(10, 99)}@{rng.choice(['example.com', 'example.net'])}".lower()
    return dict(name=name, email=email, phone=phones.take())


def long_description(resident, loc, text, employee_id):
    customer = f"<div>Customer: {html_text(resident['name'])} {resident['email']} {resident['phone']}</div>"
    if loc["lat"]:
        address = (f"<div>Address: {html_text(loc['line'])}, FL <a target=\"_blank\" "
                   f"href=\"https://www.google.com/maps/search/{loc['lat']},{loc['lon']}\">Map</a></div>")
    else:
        address = f"<div>Address: {html_text(loc['line'])}, FL</div>"
    return f"{customer}{address}<div>{html_text(text)}</div><div>Entered by: {employee_id}</div>"


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
    active_staff = [s for s in staff if s["active"]]
    water_leads = [f for f in field if f["discipline"] == "water" and f["title"].startswith("Crew Lead")]

    streets = collect_streets()
    points, centroids, address_rows = build_address_points(streets)

    name_pairs = [(f, l) for f in cat.RESIDENT_FIRST for l in cat.RESIDENT_LAST]
    rng.shuffle(name_pairs)

    times = assign_times(rng)
    scenarios = sorted(cat.SCENARIOS, key=lambda s: (times[s["key"]], s["key"]))

    srs, requests, activity, wos, logs, answers = [], [], [], [], [], []
    sr_by_key, wo_by_key, residents = {}, {}, {}
    pending_logs = []  # (datetime, record key, class, author, description, text)

    # Historical and planned work orders, kept for ID assignment after sorting.
    work_orders = []
    for street, city, house, rtype, months_ago, short, notes in cat.HISTORICAL_WOS:
        _, _, _, discipline, _, _, ownergroup, _ = cat.REQUEST_TYPES[rtype]
        sup, lead, _ = crew_for(discipline, field)
        if discipline == "water":
            lead = water_leads[(months_ago + len(street)) % len(water_leads)]
        start = AS_OF - timedelta(days=30 * months_ago + rng.randint(0, 20), hours=rng.randint(0, 6))
        start = start.replace(hour=rng.randint(7, 14), minute=rng.randrange(60))
        addr = f"{points[(street, house)]['STREETNO']} {street}" if house is not None else street
        work_orders.append(dict(kind="historical", street=street, house=house, date=start, rtype=rtype,
                                desc=f"{addr}:  {short}", ld=f"<div>{html_text(addr)}, {city}, FL</div><div>{html_text(short.capitalize())}</div>",
                                worktype="CM", status="CLOSE", ownergroup=ownergroup, sup=sup, lead=lead,
                                actstart=start, actfinish=start + timedelta(hours=rng.randint(2, 5)), notes=notes,
                                closing="Work complete. Site restored and cleaned up."))
    for street, city, rtype, status, start, finish, desc, scope, notes in cat.PLANNED_WOS:
        _, _, _, discipline, _, _, ownergroup, _ = cat.REQUEST_TYPES[rtype]
        sup, _, planner = crew_for(discipline, field)
        sched_start = datetime.strptime(start, "%Y-%m-%d").replace(hour=7, tzinfo=TZ)
        sched_finish = datetime.strptime(finish, "%Y-%m-%d").replace(hour=16, tzinfo=TZ)
        created = min(sched_start, AS_OF) - timedelta(days=rng.randint(20, 45))
        work_orders.append(dict(kind="planned", street=street, house=None, date=created, rtype=rtype,
                                desc=desc, ld=f"<div>{html_text(scope)}</div>", worktype="CP", status=status,
                                ownergroup=ownergroup, sup=sup, lead=planner, schedstart=sched_start,
                                schedfinish=sched_finish, actstart=sched_start if status == "INPRG" else None,
                                notes=notes, author=planner))

    # Service requests, QAlert requests, follow-up work orders.
    for s in scenarios:
        key, rtype = s["key"], s["type"]
        type_id, dept_id, priority, discipline, cgroup, commodity, ownergroup, route = cat.REQUEST_TYPES[rtype]
        reported = times[key]
        created_in_qalert = reported - timedelta(minutes=rng.randint(2, 9))
        employee = pick_entered_by(rng, s, staff_by_id, active_staff)
        if s.get("resident", "").startswith("same_as:"):
            resident = residents[s["resident"].split(":", 1)[1]]
        else:
            resident = make_resident(rng, name_pairs, phones)
        residents[key] = resident
        loc = resolve_address(s["addr"], points, centroids)
        description = f"{rtype}, {loc['short']}" if loc["short"] else rtype
        ld = long_description(resident, loc, s["text"], employee["id"])
        sup, lead, planner = crew_for(discipline, field)

        wo_spec = s.get("wo")
        if wo_spec:
            dispatched = reported + timedelta(hours=rng.randint(1, 20), minutes=rng.randrange(60))
            finished = dispatched + timedelta(hours=rng.randint(1, 4), minutes=rng.randrange(60))
            sr_status = "CLOSED" if wo_spec["status"] in ("CLOSE", "CAN") else "RESOLVED"
            sr_status_date = finished + timedelta(hours=1)
        else:
            sr_status, sr_status_date = "QUEUED", reported
        qalert_status = QALERT_STATUS["closed"] if sr_status in ("CLOSED", "RESOLVED") else QALERT_STATUS["open"]

        sr = dict(key=key, reported=reported, row={
            "CLASS": "SR", "DESCRIPTION": description, "DESCRIPTION_LONGDESCRIPTION": ld,
            "STATUS": sr_status, "STATUSDATE": maximo_date(sr_status_date),
            "REPORTEDBY": cat.INTEGRATION_ACCOUNT["id"], "REPORTEDNAME": cat.INTEGRATION_ACCOUNT["name"],
            "REPORTEDPHONE": "", "REPORTEDEMAIL": cat.INTEGRATION_ACCOUNT["email"], "REPORTDATE": maximo_date(reported),
            "AFFECTEDPERSON": cat.INTEGRATION_ACCOUNT["id"], "AFFECTEDNAME": cat.INTEGRATION_ACCOUNT["name"],
            "AFFECTEDEMAIL": cat.INTEGRATION_ACCOUNT["email"], "EXTERNALSYSTEM": "QAlert",
            "COMMODITYGROUP": cgroup, "COMMODITY": commodity, "OWNERGROUP": ownergroup,
            "SITEID": cat.SITEID, "ORGID": cat.ORGID, "CREATEDBY": cat.INTEGRATION_ACCOUNT["id"],
            "CREATIONDATE": maximo_date(reported),
        })
        srs.append(sr)
        sr_by_key[key] = sr

        last_action = sr_status_date if qalert_status == QALERT_STATUS["closed"] else created_in_qalert + timedelta(minutes=1)
        requests.append(dict(key=key, created=created_in_qalert, row={
            "status": qalert_status, "createDate": qalert_date(created_in_qalert),
            "createDateUnix": int(created_in_qalert.timestamp()), "lastAction": qalert_date(last_action),
            "lastActionUnix": int(last_action.timestamp()), "typeId": type_id, "typeName": rtype,
            "priorityToDisplay": priority, "hasLinks": False, "comments": s["text"],
            "streetNum": loc["num"], "streetName": loc["street"].upper(), "crossName": "",
            "cityName": loc["city"], "latitude": loc["lat"], "longitude": loc["lon"],
            "origin": "Control Panel", "name": resident["name"], "email": resident["email"],
            "phone": resident["phone"], "intakeMethod": s.get("intake", "Phone"), "employeeId": employee["id"],
        }))
        activity.append(dict(key=key, at=created_in_qalert, codeDesc="Created", routeId=employee["username"]))
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
                                    worktype=wo_spec["worktype"], status=wo_spec["status"], ownergroup=ownergroup,
                                    sup=sup, lead=wo_lead, actstart=dispatched, actfinish=finished,
                                    statusdate=sr_status_date, notes=wo_spec["logs"]))
        for note in s.get("notes", []):
            pending_logs.append((reported + timedelta(hours=3), ("SR", key), planner["id"], "", note))

        if s["group"] == "missing" and "notes" not in s:
            note = SR_REVIEW_NOTES[ord(key[-1]) % len(SR_REVIEW_NOTES)]
            if wo_spec:
                note = "Reviewed SR and dispatched to field crew."
            pending_logs.append((reported + timedelta(hours=1, minutes=rng.randrange(50)), ("SR", key), planner["id"], "", note))
        elif s["group"] == "control" and not wo_spec:
            pending_logs.append((reported + timedelta(hours=2), ("SR", key), planner["id"], "", "Reviewed. Complete request, assigned to crew queue."))
        elif s.get("cluster") and key.endswith("1"):
            pending_logs.append((reported + timedelta(minutes=40), ("SR", key), planner["id"], "", "Priority call. Assigned to on-call crew."))

        s["_employee"], s["_loc"] = employee, loc

    # Assign IDs in chronological order.
    for i, sr in enumerate(sorted(srs, key=lambda r: (r["reported"], r["key"]))):
        sr["id"] = f"SR{800001 + i}"
    for i, req in enumerate(sorted(requests, key=lambda r: (r["created"], r["key"]))):
        req["id"] = 700001 + i
    request_id_by_key = {r["key"]: r["id"] for r in requests}
    for sr in srs:
        sr["row"]["TICKETID"] = sr["id"]
        sr["row"]["EXTERNALSYSTEM_TICKETID"] = str(request_id_by_key[sr["key"]])
    work_orders.sort(key=lambda w: (w["date"], w["desc"]))
    for i, wo in enumerate(work_orders):
        wo["id"] = f"WO{2900001 + i}"
        if wo["kind"] == "followup":
            wo_by_key[wo["key"]] = wo

    # Work order rows and their logs.
    for wo in work_orders:
        is_followup = wo["kind"] == "followup"
        statusdate = wo.get("statusdate") or wo.get("actfinish") or wo["date"]
        wos.append({
            "WONUM": wo["id"], "PARENT": "", "STATUS": wo["status"], "STATUSDATE": maximo_date(statusdate),
            "WORKTYPE": wo["worktype"], "DESCRIPTION": wo["desc"], "DESCRIPTION_LONGDESCRIPTION": wo["ld"],
            "ORIGRECORDID": sr_by_key[wo["key"]]["id"] if is_followup else "",
            "ORIGRECORDCLASS": "SR" if is_followup else "",
            "REPORTEDBY": cat.INTEGRATION_ACCOUNT["id"] if is_followup else wo["sup"]["id"],
            "REPORTDATE": maximo_date(wo["date"]), "OWNERGROUP": wo["ownergroup"],
            "SUPERVISOR": wo["sup"]["id"], "LEAD": wo["lead"]["id"],
            "SCHEDSTART": maximo_date(wo["schedstart"]) if wo.get("schedstart") else "",
            "SCHEDFINISH": maximo_date(wo["schedfinish"]) if wo.get("schedfinish") else "",
            "ACTSTART": maximo_date(wo["actstart"]) if wo.get("actstart") else "",
            "ACTFINISH": maximo_date(wo["actfinish"]) if wo.get("actfinish") and wo["kind"] != "planned" else "",
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
    for i, (at, (cls, record), author, desc, text) in enumerate(pending_logs):
        record_id = sr_by_key[record]["id"] if cls == "SR" else record
        logs.append({
            "WORKLOGID": str(3000001 + i), "RECORDKEY": record_id, "CLASS": cls, "LOGTYPE": "CLIENTNOTE",
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

def contact_sentence(emp):
    sentence = (f"Contact {emp['firstName']} {emp['lastName']} ({emp['department']}, {emp['phone']}, "
                f"{emp['email']}), who entered the request in QAlert as employee {emp['id']}")
    if not emp["in_maximo"]:
        sentence += "; this employee has no Maximo person record, so the contact details come from QAlert"
    if not emp["active"]:
        sentence = (f"The request was entered by {emp['firstName']} {emp['lastName']} (employee {emp['id']}), "
                    f"who is no longer active; send the question to the {emp['department']} supervisor instead")
    return sentence + "."


def answer_row(s, sr_by_key, wo_by_key, request_id_by_key, work_orders, times):
    key, emp, group = s["key"], s["_employee"], s["group"]
    sr_id = sr_by_key[key]["id"]
    related, alert, recommendation = [], "None", ""
    use_case = {"missing": cat.USE_CASE_MISSING, "duplicate": cat.USE_CASE_DUPLICATE,
                "lookalike": cat.USE_CASE_DUPLICATE, "historical": cat.USE_CASE_CONTEXT,
                "planned": cat.USE_CASE_CONTEXT, "control": cat.USE_CASE_CONTROL}[group]

    if group == "missing":
        alert = "Missing or incorrect information"
        recommendation = f"Flag before dispatch: {s['issue']} {contact_sentence(emp)} Ask: \"{s['question']}\""
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
            recommendation = (f"Likely duplicate of {sr_by_key[primary]['id']} ({s['issue']} Reported {hours} hours later "
                              f"at the same or a neighboring address.) Link to the primary SR instead of dispatching again.")
            if primary in wo_by_key:
                related.append(wo_by_key[primary]["id"])
                recommendation += f" Work order {wo_by_key[primary]['id']} already covers it."
    elif group == "lookalike":
        other = sr_by_key[s["related"]]["id"]
        related.append(other)
        recommendation = f"Similar to {other} but not a duplicate: {s['reason']}. Treat as a new request."
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
        "MISSING_INFORMATION": s.get("missing", ""), "ENTERED_BY_EMPLOYEE_ID": emp["id"],
        "ENTERED_BY_NAME": f"{emp['firstName']} {emp['lastName']}", "ENTERED_BY_DEPARTMENT": emp["department"],
        "ENTERED_BY_PHONE": emp["phone"], "ENTERED_BY_EMAIL": emp["email"],
        "ENTERED_BY_ACTIVE": "Y" if emp["active"] else "N", "ENTERED_BY_IN_MAXIMO": "Y" if emp["in_maximo"] else "N",
        "SUGGESTED_CLARIFICATION_QUESTION": s.get("question", ""), "RELATED_RECORDS": ";".join(related),
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
                "DEPARTMENT": "Enterprise Information Technology", "TITLE": "Integration service account", "STATUS": "ACTIVE"}]
    for f in d["field"]:
        persons.append({"PERSONID": f["id"], "DISPLAYNAME": f"{f['first']} {f['last']}", "FIRSTNAME": f["first"],
                        "LASTNAME": f["last"], "PRIMARYEMAIL": f["email"], "PRIMARYPHONE": f["phone"],
                        "DEPARTMENT": "Public Utilities", "TITLE": f["title"], "STATUS": "ACTIVE"})
    for s in d["staff"]:
        if s["in_maximo"]:
            persons.append({"PERSONID": s["id"], "DISPLAYNAME": f"{s['firstName']} {s['lastName']}",
                            "FIRSTNAME": s["firstName"], "LASTNAME": s["lastName"], "PRIMARYEMAIL": s["email"],
                            "PRIMARYPHONE": s["phone"], "DEPARTMENT": s["department"], "TITLE": "Customer Service Representative",
                            "STATUS": "ACTIVE" if s["active"] else "INACTIVE"})
    persons.sort(key=lambda p: p["PERSONID"])

    write_csv(DATA / "maximo" / "sr.csv", MAXIMO_SR_COLUMNS, d["srs"])
    write_csv(DATA / "maximo" / "wo.csv", MAXIMO_WO_COLUMNS, d["wos"])
    write_csv(DATA / "maximo" / "worklog.csv", MAXIMO_WORKLOG_COLUMNS, d["logs"])
    write_csv(DATA / "maximo" / "person.csv", MAXIMO_PERSON_COLUMNS, persons)
    write_csv(DATA / "reference" / "address-points.csv", ADDRESS_COLUMNS, d["address_rows"])
    write_csv(DATA / "answer-key.csv", ANSWER_KEY_COLUMNS, d["answers"])

    write_json(DATA / "qalert" / "requests.json", d["requests"])
    write_json(DATA / "qalert" / "activity.json", d["activity"])
    write_json(DATA / "qalert" / "employees.json", [
        {k: s[k] for k in ("id", "username", "firstName", "lastName", "email", "phone", "department", "active")}
        for s in d["staff"]])
    write_json(DATA / "qalert" / "types.json", [
        {"id": t[0], "name": name, "parent": 0, "dept": t[1], "isPrivate": False, "priorityValue": t[2]}
        for name, t in sorted(cat.REQUEST_TYPES.items(), key=lambda kv: kv[1][0])])
    write_json(DATA / "qalert" / "departments.json", [{"id": i, "name": n} for i, n in cat.DEPARTMENTS])

    print(f"SRs: {len(d['srs'])}  WOs: {len(d['wos'])}  work logs: {len(d['logs'])}  "
          f"QAlert requests: {len(d['requests'])}  activity: {len(d['activity'])}  "
          f"address points: {len(d['address_rows'])}  persons: {len(persons)}")


if __name__ == "__main__":
    main()
