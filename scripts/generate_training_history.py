#!/usr/bin/env python3
"""Generate the synthetic training history for MAS AI field value recommendations.

Writes past, closed SRs with their follow-up work orders and work logs to data/maximo/history/,
in the same columns as the pilot files. Maximo's AI learns classification and team from these
records; the 65 pilot SRs stay the test set. Output is deterministic and does not touch the pilot
files or the pilot generator's random stream.

Usage (from the repository root):
    python3 scripts/generate_training_history.py
"""

import random
from datetime import datetime, timedelta

import history_catalog as hc
import pilot_catalog as cat
from generate_pilot_dataset import (DATA, MAXIMO_SR_COLUMNS, MAXIMO_WO_COLUMNS, MAXIMO_WORKLOG_COLUMNS, TZ,
                                    crew_for, long_description, maximo_date, write_csv)

OUT = DATA / "maximo" / "history"
CREW_TYPES = [t for t, rt in cat.REQUEST_TYPES.items() if rt["persongroup"]]


def street_points():
    """A first house number and a base coordinate for every history street, each from its own seed."""
    points = []
    for street, city in hc.STREETS:
        r = random.Random(f"{hc.HISTORY_SEED}:{street}")
        box = cat.CITIES[city]
        points.append(dict(street=street, city=city, first=r.randrange(100, 8000, 2),
                           lat=r.uniform(*box["lat"]), lon=r.uniform(*box["lon"])))
    return points


def location(rng, points):
    p = rng.choice(points)
    house = rng.randrange(12)
    number = str(p["first"] + 6 * house)
    return dict(line=f"{number} {p['street']}, {p['city']}", short=f"{number} {p['street']}", num=number,
                street=p["street"], city=p["city"],
                lat=round(p["lat"] + 0.0003 * house, 6), lon=round(p["lon"] + 0.0002 * house, 6))


def resident(rng):
    first, last = rng.choice(hc.FIRST_NAMES), rng.choice(hc.LAST_NAMES)
    name = f"{first} {last}"
    email = f"{first[0]}{last}{rng.randint(10, 99)}@{rng.choice(['example.com', 'example.net'])}".lower()
    # The fictional 941-555-01XX range is used up by the pilot, so history residents give only an email.
    return dict(name=name.upper() if rng.random() < 0.35 else name, email=email.replace("-", ""), phone="")


def request_text(rng, true_type):
    parts = [rng.choice(hc.SYMPTOMS[true_type]).rstrip(".") + "."]
    if rng.random() < 0.6:
        parts.append(rng.choice(hc.DETAILS))
    if rng.random() < 0.5:
        parts.append(rng.choice(hc.TIME_CUES))
    return " ".join(parts)


def filed_type(rng, true_type):
    if true_type == "Drainage / Flooding":
        return rng.choice(hc.STORMWATER_FILED_AS)
    if rng.random() < hc.MISFILE_SHARE:
        return rng.choice(hc.CONFUSABLE[true_type])
    return true_type


def build():
    """Records are numbered round by round (the k-th request of every type, then the next k), and
    each draws from its own seed. Raising PER_CLASS therefore only appends records: every ID
    already loaded into Maximo keeps exactly the same content."""
    points = street_points()
    field = [dict(id=pid, first=first, last=last, title=title, discipline=discipline)
             for pid, first, last, title, discipline in cat.FIELD_STAFF]
    water_leads = [f for f in field if f["discipline"] == "water" and f["title"].startswith("Crew Lead")]
    start = datetime.fromisoformat(hc.HISTORY_START).replace(tzinfo=TZ)
    # Reports stop two days before the end, so dispatch, finish and close dates stay inside the history.
    days = (datetime.fromisoformat(hc.HISTORY_END).replace(tzinfo=TZ) - start).days - 1
    types = list(cat.REQUEST_TYPES)
    crew_types = [t for t in types if t in CREW_TYPES]

    srs, wo_rows, logs = [], [], []

    def add_log(at, record, cls, author, desc, text, logtype="CLIENTNOTE"):
        logs.append({
            "WORKLOGID": str(hc.WORKLOG_START + len(logs)), "RECORDKEY": record, "CLASS": cls, "LOGTYPE": logtype,
            "CREATEBY": author, "CREATEDATE": maximo_date(at), "CLIENTVIEWABLE": "1", "DESCRIPTION": desc,
            "DESCRIPTION_LONGDESCRIPTION": text, "SITEID": cat.SITEID, "ORGID": cat.ORGID,
        })

    for k in range(hc.PER_CLASS):
        for t_index, true_type in enumerate(types):
            rng = random.Random(f"{hc.HISTORY_SEED}:{true_type}:{k}")
            rt = cat.REQUEST_TYPES[true_type]
            i = k * len(types) + t_index
            sr_id = f"SR{hc.SR_START + i}"
            reported = start + timedelta(days=rng.randrange(days), hours=rng.randint(7, 19), minutes=rng.randrange(60))
            filed, loc = filed_type(rng, true_type), location(rng, points)
            ld = long_description(resident(rng), loc, request_text(rng, true_type), None)
            sup, lead, planner = crew_for(rt["discipline"], field)
            if true_type in crew_types:
                dispatched = reported + timedelta(hours=rng.randint(1, 20), minutes=rng.randrange(60))
                finished = dispatched + timedelta(hours=rng.randint(1, 4), minutes=rng.randrange(60))
                sr_status, sr_status_date = "CLOSED", finished + timedelta(hours=1)
                if rt["discipline"] == "water":
                    lead = rng.choice(water_leads)
                short, closings = hc.CREW_WORK[true_type]
                wonum = f"WO{hc.WO_START + k * len(crew_types) + crew_types.index(true_type)}"
                desc = f"{loc['short']}:  {short}"
                wo_rows.append({
                    "WONUM": wonum, "PARENT": "", "STATUS": "CLOSE",
                    "STATUSDATE": maximo_date(finished + timedelta(days=1)),
                    "WORKTYPE": "CM" if rng.random() < 0.6 else "CS", "DESCRIPTION": desc,
                    "DESCRIPTION_LONGDESCRIPTION": ld, "ORIGRECORDID": sr_id, "ORIGRECORDCLASS": "SR",
                    "REPORTEDBY": cat.INTEGRATION_ACCOUNT["id"], "REPORTDATE": maximo_date(reported),
                    "CLASSSTRUCTUREID": rt["classid"], "JPNUM": rt["jpnum"], "PERSONGROUP": rt["persongroup"],
                    "OWNERGROUP": rt["persongroup"], "SUPERVISOR": sup["id"], "LEAD": lead["id"],
                    "FAILURECODE": rt["failure"], "PROBLEMCODE": rt["problem"], "SCHEDSTART": "", "SCHEDFINISH": "",
                    "ACTSTART": maximo_date(dispatched), "ACTFINISH": maximo_date(finished),
                    "SITEID": cat.SITEID, "ORGID": cat.ORGID,
                })
                add_log(dispatched, wonum, "WORKORDER", lead["id"], desc, "Arrived on site.")
                add_log(finished, wonum, "WORKORDER", lead["id"], desc, rng.choice(closings))
            else:
                logtype, note = hc.NO_CREW_CLOSING[true_type]
                sr_status = "CLOSED" if logtype == "RESOLUTION" else "RESOLVED"
                sr_status_date = reported + timedelta(hours=rng.randint(2, 30))
                add_log(sr_status_date - timedelta(minutes=5), sr_id, "SR", planner["id"], "", note, logtype)
            srs.append({
                "TICKETID": sr_id, "CLASS": "SR", "DESCRIPTION": f"{filed}, {loc['short']}",
                "DESCRIPTION_LONGDESCRIPTION": ld, "STATUS": sr_status, "STATUSDATE": maximo_date(sr_status_date),
                "REPORTEDBY": cat.INTEGRATION_ACCOUNT["id"], "REPORTEDNAME": cat.INTEGRATION_ACCOUNT["name"],
                "REPORTEDPHONE": "", "REPORTEDEMAIL": cat.INTEGRATION_ACCOUNT["email"], "REPORTDATE": maximo_date(reported),
                "AFFECTEDPERSON": cat.INTEGRATION_ACCOUNT["id"], "AFFECTEDNAME": cat.INTEGRATION_ACCOUNT["name"],
                "AFFECTEDEMAIL": cat.INTEGRATION_ACCOUNT["email"], "EXTERNALSYSTEM": "QAlert",
                "EXTERNALSYSTEM_TICKETID": str(hc.REQUEST_START + i),
                # The planner corrected the classification at review, so it is the true type's.
                "COMMODITYGROUP": rt["cgroup"], "COMMODITY": rt["commodity"], "CLASSSTRUCTUREID": rt["classid"],
                "OWNERGROUP": "", "SITEID": cat.SITEID, "ORGID": cat.ORGID,
                "CREATEDBY": cat.INTEGRATION_ACCOUNT["id"], "CREATIONDATE": maximo_date(reported),
            })
    return srs, wo_rows, logs


def main():
    srs, wos, logs = build()
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "sr.csv", MAXIMO_SR_COLUMNS, srs)
    write_csv(OUT / "wo.csv", MAXIMO_WO_COLUMNS, wos)
    write_csv(OUT / "worklog.csv", MAXIMO_WORKLOG_COLUMNS, logs)
    print(f"History SRs: {len(srs)}  WOs: {len(wos)}  work logs: {len(logs)}")


if __name__ == "__main__":
    main()
