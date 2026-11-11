"""Reference data and scenario catalog for the synthetic Sarasota MAS AI Pilot dataset.

Every person, street, phone number, and email here is invented. Street names are
fictitious; cities and ZIP codes are real Sarasota County places. Nothing is copied
from the real pilot workbook.
"""

SEED = 20261030
SITEID, ORGID = "SRQSITE", "SRQ"

# Pilot ID ranges. The pilot loaded before the SRs carried structured fields used SR800001,
# request 700001, WO2900001, work log 3000001 and draft WO2950001; those records stay in TechZone,
# closed, as the "before" copies. The work logs move too, because the loader's manifest keys them
# by WORKLOGID. scripts/id_map.py maps each old ID to its new one.
SR_START, REQUEST_START, WO_START, WORKLOG_START = 810001, 710001, 2910001, 3010001
DRAFT_WO_START = 2915001

# The integration service account that the current QAlert -> Maximo feed stamps on every SR.
INTEGRATION_ACCOUNT = {
    "id": "MWQSCINT",
    "name": "QAlert Integration",
    "email": "mxqscint@example.com",
}

# How a request reaches QAlert. Sarasota County's 311 has four ways in: the 311Connect
# mobile app, the 311 web portal, a phone call to the Contact Center, and email to the
# Contact Center. Residents submit app and web requests themselves; Contact Center staff
# type phone and email requests into the QAlert Control Panel.
# The QAlert `origin` labels are PROVISIONAL: "Control Panel" and "QAlert Mobile iOS" appear
# in public QAlert client code; "QAlert Mobile Android" and "Web Portal" are assumed.
# channel: (QAlert origin labels, QAlert intakeMethod, entered by staff, plain-language label)
CHANNELS = {
    "app": (("QAlert Mobile iOS", "QAlert Mobile Android"), None, False, "311Connect mobile app"),
    "web": (("Web Portal",), None, False, "311 web portal"),
    "phone": (("Control Panel",), "Phone", True, "phone call to 311"),
    "email": (("Control Panel",), "Email", True, "email to the Contact Center"),
}

# Maximo TICKET.SOURCE for each way in: the QAlert origin, or for staff-entered requests (origin
# "Control Panel") the intake method. SOURCE has no domain, so these codes are a convention the
# County would adopt (docs/qalert-integration-proposal.md).
SOURCE_CODES = {"QAlert Mobile iOS": "APP-IOS", "QAlert Mobile Android": "APP-ANDROID", "Web Portal": "WEB",
                "Phone": "PHONE", "Email": "EMAIL"}

# QAlert staff who enter phone and email requests.
# (employee id, username, first, last, department, active, has Maximo PERSON record)
QALERT_STAFF = [
    ("0820417", "mreyes", "Maria", "Reyes", "Contact Center", True, True),
    ("0820533", "dokafor", "Daniel", "Okafor", "Contact Center", True, False),
    ("0821106", "lchen", "Linda", "Chen", "Contact Center", True, True),
    ("0821942", "jbrooks", "Jordan", "Brooks", "Contact Center", True, False),
    ("0822318", "apatel", "Anita", "Patel", "Contact Center", True, True),
    ("0822775", "rmorales", "Ricardo", "Morales", "Contact Center", True, False),
    ("0823051", "kwhitfield", "Karen", "Whitfield", "Contact Center", False, True),
    ("0823690", "tbaxter", "Tyler", "Baxter", "Contact Center", True, True),
    ("0824012", "egarcia", "Elena", "Garcia", "Contact Center", True, True),
    ("0815877", "hlawson", "Heather", "Lawson", "Public Utilities Customer Service", True, True),
    ("0816249", "bfoster", "Brian", "Foster", "Public Utilities Customer Service", True, False),
    ("0816630", "ckim", "Christine", "Kim", "Public Utilities Customer Service", True, True),
    ("0817104", "pwalsh", "Patrick", "Walsh", "Public Utilities Customer Service", False, False),
    ("0817588", "nhughes", "Nina", "Hughes", "Public Utilities Customer Service", True, True),
    ("0818023", "gdiaz", "Gabriel", "Diaz", "Public Works Customer Service", True, False),
]

# Maximo PERSON.TITLE and PERSON.DEPARTMENT hold 30 characters, so a QAlert department that is
# longer gets a shorter Maximo name.
MAXIMO_DEPARTMENT = {"Public Utilities Customer Service": "Utilities Customer Service"}

# Maximo-only field staff. (person id, first, last, title, discipline)
FIELD_STAFF = [
    ("0830144", "Raymond", "Castillo", "Supervisor - Water", "water"),
    ("0830581", "Denise", "Holloway", "Supervisor - Wastewater", "wastewater"),
    ("0831027", "Marcus", "Bell", "Crew Lead - Water", "water"),
    ("0831460", "Owen", "Price", "Crew Lead - Water", "water"),
    ("0831893", "Felix", "Romero", "Crew Lead - Wastewater", "wastewater"),
    ("0833015", "Sandra", "Ortiz", "Crew Lead - Meter Services", "meter"),
    ("0832236", "Tanya", "Greer", "Utility Planner - Water", "planner_water"),
    ("0832671", "Victor", "Lindqvist", "Utility Planner - Wastewater", "planner_wastewater"),
]

# Fictional resident name pools. Combined pairs are sampled without replacement.
RESIDENT_FIRST = [
    "Alicia", "Benjamin", "Carla", "Desmond", "Evelyn", "Franklin", "Gloria", "Harold",
    "Irene", "Jerome", "Kendra", "Leonard", "Monica", "Nathaniel", "Olivia", "Preston",
    "Rosalind", "Samuel", "Theresa", "Vincent", "Wanda", "Xavier", "Yolanda", "Zachary",
    "Bridget", "Curtis", "Delia", "Emmett", "Fiona", "Grady",
]
RESIDENT_LAST = [
    "Abernathy", "Bellamy", "Calderon", "Dunleavy", "Ellsworth", "Fairbanks", "Galloway",
    "Hargrove", "Ingram", "Jessup", "Kowalczyk", "Lindgren", "Mercado", "Northcutt",
    "Oyelaran", "Pemberton", "Quintero", "Rasmussen", "Sheffield", "Thibodeaux", "Upchurch",
    "Valdivia", "Whitacre", "Yancey", "Zimmerman", "Ashworth", "Brannigan", "Castellanos",
    "Delacroix", "Esposito",
]

# Real Sarasota County places with approximate bounding boxes. "Bradenton" is outside the
# county and is used only for the out-of-service-area scenario.
CITIES = {
    "Sarasota": {"zips": ["34231", "34232", "34233", "34238", "34241"], "lat": (27.24, 27.36), "lon": (-82.55, -82.42)},
    "Nokomis": {"zips": ["34275"], "lat": (27.11, 27.16), "lon": (-82.47, -82.42)},
    "Venice": {"zips": ["34285", "34292", "34293"], "lat": (27.05, 27.11), "lon": (-82.45, -82.38)},
    "Osprey": {"zips": ["34229"], "lat": (27.18, 27.21), "lon": (-82.50, -82.46)},
    "North Port": {"zips": ["34286", "34287", "34288"], "lat": (27.03, 27.09), "lon": (-82.25, -82.15)},
    "Englewood": {"zips": ["34223"], "lat": (26.94, 26.99), "lon": (-82.37, -82.32)},
}

DEPARTMENTS = [
    (1, "Public Utilities - Water"),
    (2, "Public Utilities - Wastewater"),
    (3, "Public Utilities - Reclaimed Water"),
    (4, "Public Works - Stormwater"),
    (5, "Contact Center"),
]

# Maximo configuration values. In Sarasota, the team that does the work (PERSONGROUP, with
# SUPERVISOR and LEAD) is set on the work order, by applying a job plan. Service requests carry no
# team. The boolean marks a code seen in the County's sample records; everything else is our own
# illustrative value. Code meanings marked "inferred" are read from the code name, not confirmed.
# person group: (description, real)
PERSON_GROUPS = {
    "WTRPIPE": ("Water distribution pipe crew", True),
    "SANCLINSP": ("Sanitary collection and inspection crew (meaning inferred)", True),
    "LSCENT": ("Lift station crew (meaning inferred)", True),
    "WTRMETER": ("Meter services crew", False),
    "RECLAIM": ("Reclaimed water crew", False),
}
# job plan: (description, person group, real)
JOB_PLANS = {
    "LEAK": ("Water leak investigation and repair", "WTRPIPE", True),
    "PRESSURE": ("Low pressure investigation", "WTRPIPE", True),
    "NOWATER": ("No water investigation", "WTRPIPE", False),
    "METER": ("Meter repair or change-out", "WTRMETER", False),
    "SAN INSP": ("Sanitary sewer inspection", "SANCLINSP", True),
    "FORCEMAIN": ("Force main break response", "SANCLINSP", False),
    "LSALARM": ("Lift station alarm response", "LSCENT", False),
    "RECLAIM": ("Reclaimed water repair", "RECLAIM", False),
}
# failure code: (description, real)
FAILURE_CODES = {
    "SERVLINE": ("Water service line", True),
    "WTRMAIN": ("Water main", False),
    "METER": ("Water meter and box", False),
    "SERVICELATERAL": ("Sewer service lateral", True),
    "FORCEMAIN": ("Wastewater force main", False),
    "LIFTSTN": ("Lift station", False),
    "RECLAIM": ("Reclaimed water line", False),
}
# problem code: (description, real)
PROBLEM_CODES = {
    "LEAKBROKEN": ("Leak or broken pipe", True),
    "LOWPRESSURE": ("Low pressure", True),
    "CURBSTOP": ("Curb stop problem", True),
    "CUSTCOMPLAINT": ("Customer complaint", True),
    "NOWATER": ("No water", False),
    "METERFAIL": ("Meter damaged or not registering", False),
    "ODOR": ("Odor", False),
    "ALARM": ("Station alarm", False),
}
# Classification IDs are synthetic: the County's numeric IDs only mean something on their
# own instance. CLASSSTRUCTUREID: (classification, description)
CLASSIFICATIONS = {
    "9101": ("WATER-LEAK", "Utilities \\ Water \\ Line leak"),
    "9102": ("WATER-MAIN", "Utilities \\ Water \\ Main break"),
    "9103": ("WATER-PRESS", "Utilities \\ Water \\ Low pressure"),
    "9104": ("WATER-NOWTR", "Utilities \\ Water \\ No water"),
    "9105": ("WATER-METER", "Utilities \\ Water \\ Meter"),
    "9106": ("WATER-CURB", "Utilities \\ Water \\ Curb stop"),
    "9107": ("WATER-BACKFLOW", "Utilities \\ Water \\ Backflow device"),
    "9201": ("WW-SEWER", "Utilities \\ Wastewater \\ Sewer issue"),
    "9202": ("WW-ODOR", "Utilities \\ Wastewater \\ Sewer odor"),
    "9203": ("WW-LIFT", "Utilities \\ Wastewater \\ Lift station"),
    "9204": ("WW-FMAIN", "Utilities \\ Wastewater \\ Force main"),
    "9301": ("RECL-LINE", "Utilities \\ Reclaimed \\ Reclaimed water"),
    "9401": ("STORM-FLOOD", "Public Works \\ Stormwater \\ Drainage and flooding"),
}
SR_STATUSES = ("NEW", "QUEUED", "INPRG", "PENDING", "RESOLVED", "CLOSED")
WO_STATUSES = ("WCONT", "SCHED", "INPRG", "COMP", "CLOSE", "CAN")
WORK_TYPES = ("CM", "CS", "IN", "CP")  # CP (planned capital work) is our assumption
# Work log types. The County's samples use CLIENTNOTE for notes and RESOLUTION for the note that
# closes a misrouted request without a work order.
LOG_TYPES = ("CLIENTNOTE", "RESOLUTION")

# Who supplies water at an address. The mailing city does not decide it: Venice and North Port
# addresses can be served by the County or by the city's own utility. ILLUSTRATIVE: the real
# service-area boundaries come from County GIS. Streets not listed are County-served.
COUNTY_UTILITY = "Sarasota County Utilities"
CITY_UTILITY_STREETS = {
    ("Zinnia Crest Ln", "North Port"): "City of North Port Utilities",
    ("Zoysia Meadow Ct", "Venice"): "City of Venice Utilities",
}


def _request_type(type_id, dept, priority, discipline, cgroup, commodity, jpnum, failure, problem, classid, route):
    return dict(type_id=type_id, dept=dept, priority=priority, discipline=discipline, cgroup=cgroup,
                commodity=commodity, jpnum=jpnum, persongroup=JOB_PLANS[jpnum][1] if jpnum else "",
                failure=failure, problem=problem, classid=classid, route=route)


# QAlert request types mapped to Maximo classification and the job plan a planner would apply.
# Drainage / Flooding is a Public Works type and is used only as the true type of a
# misclassified request, so it has no Utilities job plan or team. Backflow Device Issue is a
# County request type with the County's BACKFLOW commodity; backflow devices belong to the
# property owner, so it has no job plan or team either.
REQUEST_TYPES = {
    "Water Line Leak": _request_type(101, 1, 2, "water", "POTABLE", "WATER_PIPE", "LEAK", "SERVLINE", "LEAKBROKEN", "9101", "PUWater"),
    "Water Main Break": _request_type(102, 1, 1, "water", "POTABLE", "WATER_PIPE", "LEAK", "WTRMAIN", "LEAKBROKEN", "9102", "PUWater"),
    "Low Water Pressure": _request_type(103, 1, 3, "water", "POTABLE", "WATER_PIPE", "PRESSURE", "SERVLINE", "LOWPRESSURE", "9103", "PUWater"),
    "No Water": _request_type(104, 1, 1, "water", "POTABLE", "WATER_SERV", "NOWATER", "SERVLINE", "NOWATER", "9104", "PUWater"),
    "Water Meter Issue": _request_type(105, 1, 3, "meter", "POTABLE", "WATER_SERV", "METER", "METER", "METERFAIL", "9105", "PUWater"),
    "Curb Stop": _request_type(106, 1, 3, "water", "POTABLE", "WATER_PIPE", "LEAK", "SERVLINE", "CURBSTOP", "9106", "PUWater"),
    "Backflow Device Issue": _request_type(107, 1, 3, "water", "POTABLE", "BACKFLOW", "", "", "", "9107", "PUWater"),
    "Sewer Issue": _request_type(201, 2, 2, "wastewater", "WASTEWATER", "COLLECTION", "SAN INSP", "SERVICELATERAL", "CUSTCOMPLAINT", "9201", "PUWastewater"),
    "Sewer Odor": _request_type(202, 2, 3, "wastewater", "WASTEWATER", "COLLECTION", "SAN INSP", "SERVICELATERAL", "ODOR", "9202", "PUWastewater"),
    "Lift Station Alarm": _request_type(203, 2, 1, "wastewater", "WASTEWATER", "LIFTSTATION", "LSALARM", "LIFTSTN", "ALARM", "9203", "PUWastewater"),
    "Force Main Break": _request_type(204, 2, 1, "wastewater", "WASTEWATER", "FORCEMAIN", "FORCEMAIN", "FORCEMAIN", "LEAKBROKEN", "9204", "PUWastewater"),
    "Reclaimed Water Issue": _request_type(301, 3, 3, "water", "RECLAIMED", "RECLAIM_PIPE", "RECLAIM", "RECLAIM", "LEAKBROKEN", "9301", "PUReclaimed"),
    "Drainage / Flooding": _request_type(401, 4, 2, "stormwater", "", "", "", "", "", "9401", "PWStormwater"),
}

# Streets used only by background work orders, plus the correctly spelled street behind the
# misspelled-address scenario. They give the GIS stand-in realistic noise.
EXTRA_STREETS = [
    ("Sandpiper Glen Way", "Sarasota"),
    ("Brackenridge Ln", "Sarasota"),
    ("Copperleaf Dr", "Venice"),
    ("Dunmore Key Way", "Nokomis"),
    ("Embersand Ct", "North Port"),
    ("Featherstone Rd", "Osprey"),
    ("Gannet Ridge Ave", "Englewood"),
    ("Hollowpine Cir", "Sarasota"),
    ("Ironwood Shoals Dr", "Venice"),
    ("Jessamine Bay Rd", "Sarasota"),
    ("Kingfisher Lantern Ln", "North Port"),
    ("Lindenhurst Ave", "Nokomis"),
]

# Information a request needs before a crew is sent: rules for every request type, then one rule
# per type. Our own proposal for the County to confirm; the answer key's REQUIRED_INFO_GAP names
# the rules each missing-information request breaks. (rule id, request type or "ALL", requirement)
REQUIRED_INFORMATION = [
    ("ADDR", "ALL", "A street address with a house number, or a cross street or landmark a crew can find"),
    ("ADDR-VALID", "ALL", "An address that exists in the County address file and lies in Sarasota County"),
    ("ONE-ISSUE", "ALL", "One problem per request; a second problem needs its own request"),
    ("LEAK-WHERE", "Water Line Leak", "Where the water is (yard, road, meter box) and whether it runs continuously"),
    ("MAIN-WHERE", "Water Main Break", "Where the water comes up in the road and how much is flowing"),
    ("PRESS-SCOPE", "Low Water Pressure", "Whether the whole house or one fixture is affected, and since when"),
    ("NOWATER-SCOPE", "No Water", "Whether neighbors are out too, and whether the meter has a lock or notice"),
    ("METER-PROBLEM", "Water Meter Issue", "What the meter problem is: leak, damage, blank display, reading or bill"),
    ("CURB-PROBLEM", "Curb Stop", "What is wrong with the curb stop: leaking, stuck or broken"),
    ("BACKFLOW-WHERE", "Backflow Device Issue", "Where the device is and what it is doing: leaking, spraying or noisy"),
    ("SEWER-SYMPTOM", "Sewer Issue", "The symptom (backup, overflow, odor) and whether it is inside or outside the house"),
    ("ODOR-SOURCE", "Sewer Odor", "Where the odor comes from: a manhole, a cleanout or inside the house"),
    ("LS-ID", "Lift Station Alarm", "The lift station name or number, or the street it is on"),
    ("FMAIN-WHERE", "Force Main Break", "Where the pipe is broken and whether sewage is flowing"),
    ("RECL-PROBLEM", "Reclaimed Water Issue", "What the reclaimed water problem is: no pressure, leak or water quality"),
]
# Scenarios whose requests break a required-information rule, and the rule each breaks by default.
# "TYPE" means the rule for the request type as submitted. A scenario can override with `gaps`.
REQUIRED_INFO_SCENARIOS = {
    "Missing location": ("ADDR",),
    "Invalid location": ("ADDR-VALID",),
    "Insufficient problem detail": ("TYPE",),
    "Unclear request": ("TYPE",),
    "Multiple issues in one request": ("ONE-ISSUE",),
}

USE_CASE_MISSING = "Missing-Information Detection"
USE_CASE_DUPLICATE = "Duplicate Identification"
USE_CASE_CONTEXT = "Historical / Planned Work Context"
USE_CASE_CONTROL = "Control (no issue)"

# Service request scenarios. Address forms:
#   ("valid", street, city, house_index)       house_index 0-3 selects a GIS address point
#   ("street_only", street, city)              street known, no house number
#   ("none", city)                             no usable address
#   ("bad_number", street, city, number)       house number not in the GIS file
#   ("typo", shown_street, real_street, city, house_index)
#   ("out_of_county", street, city, number, lat, lon)
# Timing: ("after", other_key, hours) or ("at", "YYYY-MM-DD HH:MM"); default is random in window.
# channel: a CHANNELS key. Staff channels name the employee in entered_by. anonymous=True is a
# web request submitted with no phone or email. unattributed=True is a staff-entered request
# that records no employee anywhere (no "Entered by" line, no QAlert employeeId), like the
# County's staff-written samples.
# SR status: a scenario with a WO follows the WO (INPRG, RESOLVED, CLOSED); otherwise QUEUED,
# unless sr_status sets PENDING (held for the requester) or NEW (not reviewed yet). `resolved`
# closes an SR without a WO, through one SR work log, as in the County's misrouted and
# non-County samples: dict(status, hours after the report, logtype, note).
# group "responsibility": the request may not be the County's job. `refer_to` names who to send
# the customer to once confirmed; `other_utility` marks an address another utility serves.
# A look-alike with same_address=True is at the address of an earlier SR whose WO was already
# completed: a new problem, not a duplicate of an open one.
# New scenarios are reported on 2026-10-27, after every earlier one, so adding them leaves the
# IDs, names and phone numbers of existing records unchanged.
SCENARIOS = [
    # ---- Missing-Information Detection -------------------------------------------------
    dict(key="M01", group="missing", scenario="Missing location", type="Water Main Break",
         addr=("street_only", "Halyard Reach Rd", "Nokomis"),
         text="Caller was driving by and says water is bubbling up out of the road and running down the gutter. Thinks it is a main break. Did not know the house number, said it is somewhere on Halyard Reach.",
         issue="No house number or cross street, so the crew cannot find the break.",
         missing="House number or nearest cross street on Halyard Reach Rd.",
         question="Can you call the customer back and get the nearest house number or cross street where the water is coming up?",
         wo=dict(worktype="CM", short="POSS MAIN BREAK", status="COMP",
                 logs=["Drove Halyard Reach end to end looking for a main break. Did not find any water in the road. No leak found."]),
         channel="phone", entered_by="0820533"),
    dict(key="M02", group="missing", scenario="Missing location", type="Sewer Odor",
         addr=("none", "Venice"),
         text="Strong sewer smell near the bus stop by the shopping plaza, has been there 3 days. Caller would not give an address.",
         issue="No street address; only a vague landmark.",
         missing="Which shopping plaza and bus stop, or the nearest street address.",
         question="Which shopping plaza and bus stop did the caller mean, and what is the nearest street?",
         when=("at", "2026-08-06 10:12"), channel="phone", entered_by="0823051"),
    dict(key="M03", group="missing", scenario="Missing location", type="Water Line Leak",
         addr=("street_only", "Fennimore Pines Blvd", "North Port"),
         text="Leak in the grass next to the sidewalk, water pooling. I am a landscaper working in the neighborhood and not sure of the address.",
         issue="Street only; no house number.",
         missing="House number or a nearby landmark on Fennimore Pines Blvd.",
         question="Can you give the house number or describe the closest house to the leak?",
         channel="app"),
    dict(key="M04", group="missing", scenario="Missing location", type="Lift Station Alarm",
         addr=("none", "North Port"),
         text="Alarm going off at the pump station behind our neighborhood, red light is flashing.",
         issue="No address and no lift station identified.",
         missing="Lift station name or number, or the nearest street.",
         question="Which neighborhood or street is the pump station behind?",
         gaps=("ADDR", "LS-ID"), channel="web", anonymous=True),
    dict(key="M05", group="missing", scenario="Invalid location", type="Low Water Pressure",
         addr=("bad_number", "Wrenhaven Pl", "Sarasota", 9870),
         text="Low water pressure at my house for 2 weeks, the shower barely runs.",
         issue="Address 9870 Wrenhaven Pl does not exist in the County address file.",
         missing="A verified service address.",
         question="Can you confirm your service address? 9870 Wrenhaven Pl is not in the County address file.",
         wo=dict(worktype="CS", short="LOW PRESSURE", status="CLOSE",
                 logs=["Could not locate 9870 Wrenhaven Pl, numbers on this street stop well below that. Unable to complete."]),
         channel="web"),
    dict(key="M06", group="missing", scenario="Invalid location", type="Water Meter Issue",
         addr=("typo", "Sandpiper Glenn Way", "Sandpiper Glen Way", "Sarasota", 1),
         text="Meter box lid is broken and someone could trip on it.",
         issue="Street name is misspelled (Glenn vs Glen) and does not match the County address file.",
         missing="Corrected street name.",
         question="Is the address on Sandpiper Glen Way (one n)?",
         channel="web"),
    dict(key="M07", group="missing", scenario="Invalid location", type="No Water",
         addr=("out_of_county", "Riverbluff Ln", "Bradenton", 4410, 27.4891, -82.5712),
         text="No water since this morning, my neighbors are out too.",
         issue="Address is in Bradenton (Manatee County), outside the Sarasota County service area.",
         missing="Confirmation that the property is a Sarasota County utility customer.",
         question="Is your water bill from Sarasota County? Bradenton addresses are normally served by Manatee County.",
         channel="web"),
    dict(key="M08", group="missing", scenario="Insufficient problem detail", type="Curb Stop",
         addr=("valid", "Tessaly Oaks Blvd", "Sarasota", 0),
         text="MY PLUMBER FIXED A LEAK ON THE HOUSE SIDE BUT TOLD ME THERE IS A PROBLEM WITH THE CURB STOP",
         issue="Does not say what is wrong with the curb stop or what service is needed.",
         missing="What the problem with the curb stop is (leaking, stuck, broken) and what the customer needs.",
         question="What exactly did the plumber say is wrong with the curb stop: is it leaking, stuck, or broken?",
         wo=dict(worktype="CS", short="curbstop issue", status="CLOSE",
                 logs=["Curb stop operates fine, no leak. No problem found."]),
         channel="app"),
    dict(key="M09", group="missing", scenario="Insufficient problem detail", type="Water Meter Issue",
         addr=("valid", "Aldersea Cir", "Venice", 1),
         text="Customer has a question about the meter.",
         issue="No description of the meter problem.",
         missing="What the meter question or problem is (high bill, leak, damage, reading).",
         question="What is the customer's question about the meter: high bill, leak, damage, or something else?",
         channel="phone", unattributed=True),
    dict(key="M10", group="missing", scenario="Insufficient problem detail", type="Sewer Issue",
         addr=("valid", "Orchidmere Dr", "Osprey", 0),
         text="Sewer problem at the house.",
         issue="No symptoms described (backup, odor, overflow).",
         missing="Symptoms: backup, odor, or overflow; inside or outside the house.",
         question="Is the sewer problem a backup inside the house, an overflow outside, or an odor?",
         channel="web", sr_status="PENDING"),
    dict(key="M11", group="missing", scenario="Insufficient problem detail", type="Reclaimed Water Issue",
         addr=("valid", "Calloway Marsh Ln", "Englewood", 0),
         text="Reclaimed water issue, please call.",
         issue="No description of the reclaimed water problem.",
         missing="Nature of the reclaimed water problem.",
         question="What is the reclaimed water problem: no pressure, leak, or water quality?",
         when=("at", "2026-08-12 14:40"), channel="phone", entered_by="0817104"),
    dict(key="M12", group="missing", scenario="Unclear request", type="Sewer Issue",
         addr=("valid", "Ivorybill Pass", "Sarasota", 0),
         text="GREEN BOX IN MY YARD HAS A HOLE DUG NEXT TO IT AND THE CAUTION TAPE AROUND IT IS FALLING DOWN SO IT IS NOT SAFE",
         issue="Unclear whether the green box is a County sewer asset; it may belong to another utility.",
         missing="What the green box is, and who dug the hole.",
         question="Does the green box have any label or company name on it, and do you know who dug the hole?",
         wo=dict(worktype="IN", short="GREEN BOX HOLE", status="COMP",
                 logs=["Inspected area. Green box is an electric pedestal, not ours. Referred customer to the power company."]),
         channel="app"),
    dict(key="M13", group="missing", scenario="Unclear request", type="Water Line Leak",
         addr=("valid", "Seabright Hollow Ln", "Nokomis", 1),
         text="Caller says something is wrong with the water thing by the road, it makes a noise at night.",
         issue="Does not identify the device or the problem.",
         missing="Which device is meant (meter, backflow, valve) and what the noise is.",
         question="Is the noisy device the water meter, a backflow preventer, or something else, and is there any water leaking?",
         wo=dict(worktype="CS", short="NOISE AT METER", status="COMP",
                 logs=["Noise is from the customer's backflow preventer cycling. Advised customer to call a plumber. No County issue."]),
         channel="phone", entered_by="0821942"),
    dict(key="M14", group="missing", scenario="Unclear request", type="Low Water Pressure",
         addr=("valid", "Kestrel Tide Way", "Venice", 2),
         text="Please send someone to come look at it, I already reported the same thing last year.",
         issue="'It' is never described; the request depends on an earlier call that is not referenced.",
         missing="What the problem is and the earlier request number if known.",
         question="What would you like us to look at, and do you have the request number from last year?",
         channel="web", sr_status="PENDING"),
    dict(key="M15", group="missing", scenario="Incorrect classification", type="Water Line Leak",
         true_type="Drainage / Flooding",
         addr=("valid", "Marlowe Cove Ave", "Sarasota", 0),
         text="URGENT. After a little rain the corner of my street is flooded with several inches of water and I cannot get out of my driveway to pick up my kids.",
         issue="Describes stormwater street flooding but was classified as a Water Line Leak and routed to Water.",
         missing="Correct classification: Drainage / Flooding (Public Works Stormwater).",
         question="Is there any water coming from a pipe or meter, or is this only rainwater flooding the street?",
         wo=dict(worktype="CM", short="LEAK", status="CAN",
                 logs=["Rain water only, no utility leak. This is a stormwater drainage issue. Cancel and route to Stormwater."]),
         channel="app"),
    dict(key="M16", group="missing", scenario="Incorrect classification", type="Water Main Break",
         true_type="Force Main Break",
         addr=("valid", "Quillfeather Rd", "Sarasota", 0),
         text="Caller reports water spewing from a pipe near the pump station. Says the marker post says force main.",
         issue="Description points to a wastewater force main, but it was classified as a Water Main Break.",
         missing="Correct classification: Force Main Break (Wastewater).",
         question="Can the caller confirm the marker says force main, and is there any sewage odor?",
         wo=dict(worktype="CM", short="POSS MAIN BREAK", status="COMP",
                 logs=["This is the wastewater force main, not a water main. Called wastewater on-call to respond."]),
         channel="phone", entered_by="0821106"),
    dict(key="M17", group="missing", scenario="Incorrect classification", type="Sewer Issue",
         true_type="Water Line Leak",
         addr=("valid", "Palmetto Driftwood Ct", "Venice", 0),
         text="Clear water bubbling up in the front yard near the water meter. No smell.",
         issue="Clear water near the meter with no odor suggests a water leak, not a sewer issue.",
         missing="Correct classification: Water Line Leak (Water).",
         question="Is the water clear with no odor, and is it coming up next to the meter box?",
         channel="app"),
    dict(key="M18", group="missing", scenario="Incorrect classification", type="Low Water Pressure",
         true_type="Reclaimed Water Issue",
         addr=("valid", "Bayberry Shoal Ln", "Osprey", 0),
         text="My irrigation system has no pressure, sprinklers barely come on. The house is on reclaimed water for irrigation.",
         issue="Irrigation on reclaimed water; the request belongs to Reclaimed Water, not potable Low Water Pressure.",
         missing="Correct classification: Reclaimed Water Issue.",
         question="Is the low pressure only on your irrigation (reclaimed) system, or inside the house too?",
         channel="app"),
    dict(key="M19", group="missing", scenario="Multiple issues in one request", type="Water Meter Issue",
         addr=("valid", "Pinnacle Reef Ct", "Englewood", 0),
         text="A contractor told me the water pressure is too high, about 90 psi, and also that the meter might not be working. Please check both.",
         issue="Two issues in one request: high pressure and a possibly faulty meter.",
         missing="Split into separate requests, or confirm both checks are needed.",
         question="Should the high pressure and the meter accuracy be handled as two separate requests?",
         wo=dict(worktype="CS", short="HIGH PRESSURE ISSUE", status="COMP",
                 logs=["Pressure within spec, read 78 psi at the hose bib. Meter not tested on this visit."]),
         channel="app"),
    dict(key="M20", group="missing", scenario="Multiple issues in one request", type="Sewer Issue",
         addr=("valid", "Coquina Lantern Dr", "Nokomis", 0),
         text="Manhole lid rattles loudly when cars drive over it. There is also a sewer smell coming from the storm drain across the street.",
         issue="Two issues: a noisy manhole lid (wastewater) and an odor from a storm drain (possibly stormwater).",
         missing="Separate the manhole lid issue from the storm drain odor.",
         question="Is the smell coming from the sewer manhole or from the storm drain across the street?",
         channel="web"),
    dict(key="M21", group="missing", scenario="Multiple issues in one request", type="Water Line Leak",
         addr=("valid", "Lumen Palm Ct", "Sarasota", 0),
         text="Leak at the meter. Also the County crew that worked here last month left a big hole and damaged my irrigation lines.",
         issue="Combines a new leak with a property damage complaint about earlier County work.",
         missing="Separate the leak from the damage claim; identify the earlier work.",
         question="Do you know when the earlier County work happened? The damage claim will be handled separately by risk management.",
         channel="app"),
    dict(key="M22", group="responsibility", scenario="County responsibility review", type="Sewer Issue",
         addr=("valid", "Driftmoor St", "Venice", 0),
         text="The toilet in the guest bathroom backs up when the washer drains. The other toilets are fine.",
         issue="A single-fixture backup suggests private plumbing, not a County sewer problem. This is a planner judgment.",
         missing="Whether other fixtures or neighbors are affected.",
         question="Are any other drains in your house, or any of your neighbors, having problems?",
         notes=["Advised resident this looks like a private plumbing issue. Waiting on callback."],
         refer_to="a licensed plumber", channel="web", sr_status="PENDING"),
    dict(key="M23", group="responsibility", scenario="County responsibility review", type="Water Line Leak",
         addr=("valid", "Tamberly Creek Rd", "North Port", 0),
         text="Leak under the kitchen sink, water everywhere.",
         issue="The leak is inside the home, which is the property owner's responsibility.",
         missing="Whether there is any leak on the County side of the meter.",
         question="Is the leak only inside your house, or is there water at the meter box too?",
         refer_to="a licensed plumber", channel="app"),
    dict(key="M24", group="responsibility", scenario="County responsibility review", type="Low Water Pressure",
         addr=("valid", "Silverthorn Bayou Dr", "North Port", 0),
         text="Only the upstairs shower has low pressure, the rest of the house is fine.",
         issue="Low pressure at a single fixture points to private plumbing.",
         missing="Whether pressure is low at the outside hose bib.",
         question="Is the pressure normal at your outside spigot near the meter?",
         refer_to="a licensed plumber", channel="web"),

    # ---- Duplicate Identification ------------------------------------------------------
    dict(key="DA1", group="duplicate", cluster="A", scenario="Duplicate cluster A (primary)", type="Water Main Break",
         addr=("valid", "Corvina Bay Dr", "Sarasota", 0),
         text="Water gushing out of the road in front of my house.",
         issue="First report of a main break on Corvina Bay Dr.",
         wo=dict(worktype="CM", short="MAIN BREAK", status="COMP",
                 logs=["6 in. main break at the edge of pavement. Isolated two valves, repaired with a full circle clamp.",
                       "Restored service, flushed. Road patch needed."]),
         when=("at", "2026-09-14 06:55"), channel="app"),
    dict(key="DA2", group="duplicate", cluster="A", scenario="Duplicate cluster A", type="Water Main Break",
         addr=("valid", "Corvina Bay Dr", "Sarasota", 1),
         text="Water running down the street from the corner, looks like a lot of water.",
         issue="Same break reported by a neighbor two houses down.",
         when=("after", "DA1", 2), channel="app"),
    dict(key="DA3", group="duplicate", cluster="A", scenario="Duplicate cluster A", type="Water Line Leak",
         addr=("valid", "Corvina Bay Dr", "Sarasota", 2),
         text="Road is wet and there is a hole starting to form in the pavement.",
         issue="Same break; filed under a different type (Water Line Leak).",
         when=("after", "DA1", 5), channel="email", entered_by="0815877"),
    dict(key="DB1", group="duplicate", cluster="B", scenario="Duplicate cluster B (primary)", type="Sewer Odor",
         addr=("valid", "Gulfwren Ave", "Venice", 1),
         text="Sewer smell outside the house in the evenings, worse after rain.",
         issue="First report of sewer odor on Gulfwren Ave.",
         when=("at", "2026-10-05 16:20"), channel="app"),
    dict(key="DB2", group="duplicate", cluster="B", scenario="Duplicate cluster B", type="Sewer Odor",
         addr=("valid", "Gulfwren Ave", "Venice", 1),
         text="Customer is calling about the sewer smell she reported in the app. It is still there and nobody has come out.",
         issue="Same customer calling the Contact Center about the request she already submitted in the app.",
         resident="same_as:DB1", when=("after", "DB1", 50), channel="phone", entered_by="0822318"),
    dict(key="DC1", group="duplicate", cluster="C", scenario="Duplicate cluster C (primary)", type="No Water",
         addr=("valid", "Bramblewick Ln", "Sarasota", 0),
         text="No water at all since about 6 this morning.",
         issue="First report of an outage on Bramblewick Ln.",
         wo=dict(worktype="CM", short="NO WATER", status="COMP",
                 logs=["Main break at the intersection with the side street. Repaired 4 in. main, service restored to street.",
                       "Precautionary boil water notice delivered to 14 homes."]),
         when=("at", "2026-10-21 06:40"), channel="app"),
    dict(key="DC2", group="duplicate", cluster="C", scenario="Duplicate cluster C", type="No Water",
         addr=("valid", "Bramblewick Ln", "Sarasota", 1),
         text="We have no water. Our neighbor has none either.",
         issue="Same outage, different household.",
         when=("after", "DC1", 1), channel="app"),
    dict(key="DC3", group="duplicate", cluster="C", scenario="Duplicate cluster C", type="Low Water Pressure",
         addr=("valid", "Bramblewick Ln", "Sarasota", 3),
         text="Very low pressure, just a trickle from the faucets.",
         issue="Same outage at the end of the street; filed as Low Water Pressure.",
         when=("after", "DC1", 2), channel="web"),
    dict(key="DD1", group="duplicate", cluster="D", scenario="Duplicate cluster D (primary)", type="Lift Station Alarm",
         addr=("valid", "Eldergrove Ct", "Osprey", 0),
         text="Alarm horn and red light going off at the lift station at the end of the street.",
         issue="First report of the Eldergrove Ct lift station alarm.",
         wo=dict(worktype="CM", short="LS ALARM", status="COMP",
                 logs=["High wet well alarm. Pump 2 tripped, reset breaker, pumped down. Both pumps running normal."]),
         when=("at", "2026-09-28 21:10"), channel="app"),
    dict(key="DD2", group="duplicate", cluster="D", scenario="Duplicate cluster D", type="Lift Station Alarm",
         addr=("valid", "Eldergrove Ct", "Osprey", 2),
         text="Pump station alarm is still going, very loud.",
         issue="Same alarm reported by a second resident.",
         when=("after", "DD1", 1), channel="web"),
    dict(key="DE1", group="duplicate", cluster="E", scenario="Duplicate cluster E (primary)", type="Water Line Leak",
         addr=("valid", "Thistlewood Dr", "Englewood", 1),
         text="Water leaking from the meter box, running into the street.",
         issue="First report of a meter box leak on Thistlewood Dr.",
         wo=dict(worktype="CS", short="LEAK AT METER", status="COMP",
                 logs=["Leak on meter coupling, county side. Replaced coupling gasket. No further leak."]),
         when=("at", "2026-08-25 09:05"), channel="app"),
    dict(key="DE2", group="duplicate", cluster="E", scenario="Duplicate cluster E", type="Water Line Leak",
         addr=("valid", "Thistlewood Dr", "Englewood", 1),
         text="Neighbor reporting water running from the meter at the house next door.",
         issue="Same meter leak reported by a neighbor using the same address.",
         when=("after", "DE1", 20), channel="email", entered_by="0816249"),
    dict(key="L01", group="lookalike", scenario="Look-alike (not a duplicate)", type="Water Line Leak",
         addr=("valid", "Corvina Bay Dr", "Sarasota", 3),
         text="Small leak at the meter box, slow drip, no water in the road.",
         issue="Same street as the September main break, but a separate small meter leak six weeks later.",
         related="DA1", reason="different issue (small meter leak) six weeks after the main break was repaired",
         when=("at", "2026-10-26 11:30"), channel="web", sr_status="NEW"),
    dict(key="L02", group="lookalike", scenario="Look-alike (not a duplicate)", type="No Water",
         addr=("valid", "Bramblewick Ln", "Sarasota", 2),
         text="No water. I found a lock on the meter and a door hanger about my account.",
         issue="Same street as the outage, but caused by an account lock on the meter, not the main break.",
         related="DC1", reason="no water caused by an account lock on the meter, not the main break",
         when=("at", "2026-10-27 08:15"), channel="app", sr_status="NEW"),
    dict(key="L03", group="lookalike", scenario="Look-alike (not a duplicate)", type="Lift Station Alarm",
         addr=("valid", "Foxmere Rd", "North Port", 0),
         text="Lift station alarm sounding, light on the panel is flashing.",
         issue="Same night as the Eldergrove Ct alarm, but a different lift station in a different city.",
         related="DD1", reason="different lift station in North Port, not the Osprey station",
         when=("after", "DD1", 3), channel="app"),

    # ---- Historical / Planned Work Context ---------------------------------------------
    dict(key="H01", group="historical", scenario="Related past work", type="Water Line Leak",
         addr=("valid", "Larkspur Bay Dr", "Sarasota", 0),
         text="Water leaking again in the front yard near the meter, same spot as before.",
         issue="Third leak at this address within a year.",
         advice="Recommend a full service line replacement instead of another spot repair.",
         channel="app"),
    dict(key="H02", group="historical", scenario="Related past work", type="Low Water Pressure",
         addr=("valid", "Nettlecreek Ln", "Venice", 1),
         text="Low pressure throughout the house, mostly in the mornings.",
         issue="Pressure was tested at this address five months ago and was within spec.",
         advice="Check whether the earlier finding (customer pressure reducing valve) still applies before sending a crew.",
         channel="web"),
    dict(key="H03", group="historical", scenario="Related past work", type="Sewer Issue",
         addr=("valid", "Oakhallow Cir", "Nokomis", 0),
         text="Toilets and tubs are slow to drain and gurgle. Neighbor has the same problem.",
         issue="The main line on this street was jetted for root intrusion two months ago.",
         advice="Likely recurring root intrusion; prioritize the main for lining rather than another jetting visit.",
         channel="app"),
    dict(key="H04", group="historical", scenario="Related past work", type="Water Meter Issue",
         addr=("valid", "Pebblestone Way", "North Port", 2),
         text="My bill doubled this month, I think the meter is wrong.",
         issue="Meter was replaced at this address four months ago.",
         advice="Check the new meter's reads since installation; a high bill may be a customer-side leak rather than a meter fault.",
         channel="web"),
    dict(key="H05", group="historical", scenario="Related past work", type="Curb Stop",
         addr=("valid", "Rushmere Ave", "Sarasota", 1),
         text="Curb stop will not turn off, plumber needs the water shut off to do a repair.",
         issue="The curb stop at this address was replaced 14 months ago.",
         advice="Possible warranty or installation issue with the replacement curb stop; reference the earlier work order.",
         channel="phone", entered_by="0820417"),
    dict(key="P01", group="planned", scenario="Related planned work", type="Low Water Pressure",
         addr=("valid", "Starling Cove Dr", "Sarasota", 1),
         text="Low pressure and brown water for about a week.",
         issue="A water main replacement on Starling Cove Dr is scheduled to start in November.",
         advice="Likely related to the aging main; flush and monitor, and let the project team know rather than opening separate repair work.",
         channel="app"),
    dict(key="P02", group="planned", scenario="Related planned work", type="Sewer Odor",
         addr=("valid", "Willowmarsh Rd", "Venice", 0),
         text="Sewer smell from the manhole in front of the house.",
         issue="A sewer main lining project on Willowmarsh Rd is scheduled for December.",
         advice="Odor on this segment is expected to resolve with lining; tell the customer about the project and check the manhole only if it gets worse.",
         channel="web"),
    dict(key="P03", group="planned", scenario="Related planned work", type="Water Meter Issue",
         addr=("valid", "Yarrowfield Ln", "North Port", 2),
         text="Meter display is blank and the customer cannot read it.",
         issue="This neighborhood is in the automated meter change-out scheduled for November.",
         advice="The blank meter will be replaced by the scheduled change-out; avoid a separate meter trip unless the customer has no water.",
         channel="app"),
    dict(key="P04", group="planned", scenario="Related planned work", type="Water Line Leak",
         addr=("valid", "Quayside Ct", "Englewood", 0),
         text="The road was dug up and patched last week and now water is seeping up through the patch.",
         issue="An active valve and hydrant replacement project is in progress on Quayside Ct.",
         advice="Likely related to the 10/20 excavation patch; send to the project team and contractor instead of a separate repair crew.",
         channel="app"),

    # ---- Controls ----------------------------------------------------------------------
    dict(key="C01", group="control", scenario="Complete request", type="Water Line Leak",
         addr=("valid", "Ashcombe Dr", "Sarasota", 0),
         text="Steady leak from the meter box on the County side, water running to the street since last night. I am home all day.",
         wo=dict(worktype="CS", short="LEAK AT METER", status="COMP",
                 logs=["Replaced leaking meter washer. Checked for further leaks, none."]),
         channel="app"),
    dict(key="C02", group="control", scenario="Complete request", type="Sewer Issue",
         addr=("valid", "Cindermoss Ln", "Venice", 1),
         text="Sewer cleanout cap in the front yard is overflowing with sewage. All drains in the house are backing up.",
         wo=dict(worktype="CM", short="SEWER BACKUP", status="COMP",
                 logs=["Blockage in the County main downstream of the cleanout. Jetted 300 ft, cleared. Flowing normal."]),
         channel="app"),
    dict(key="C03", group="control", scenario="Complete request", type="Water Meter Issue",
         addr=("valid", "Dovetail Pl", "Nokomis", 0),
         text="Meter box lid cracked in half, opening is exposed next to the sidewalk. Trip hazard.",
         wo=dict(worktype="CS", short="METER LID", status="COMP",
                 logs=["Replaced cracked meter box lid."]),
         channel="web"),
    dict(key="C04", group="control", scenario="Complete request", type="Water Main Break",
         addr=("valid", "Glimmerton Ave", "Sarasota", 2),
         text="Water flowing out of a crack in the street at the storm drain, about 20 ft from the hydrant. Started an hour ago.",
         wo=dict(worktype="CM", short="MAIN BREAK", status="INPRG",
                 logs=["Isolated the main and started excavation. 8 in. repair clamp on order, crew staying on site."]),
         channel="phone", entered_by="0823690"),
    dict(key="C05", group="control", scenario="Complete request", type="Low Water Pressure",
         addr=("valid", "Harrowgate Blvd", "North Port", 1),
         text="Whole house pressure dropped yesterday, including the outside spigot at the meter. Neighbors are normal.",
         wo=dict(worktype="CS", short="LOW PRESSURE", status="COMP",
                 logs=["Partially closed curb stop. Opened fully, pressure 64 psi."]),
         channel="app"),
    dict(key="C06", group="control", scenario="Complete request", type="Reclaimed Water Issue",
         addr=("valid", "Juniper Mist Ct", "Osprey", 0),
         text="Reclaimed water line is leaking at the purple valve box by the curb, water bubbling up continuously.",
         wo=dict(worktype="CM", short="RECLAIM LEAK", status="COMP",
                 logs=["Replaced cracked reclaimed service saddle at the main."]),
         channel="app"),
    dict(key="C07", group="control", scenario="Complete request", type="Sewer Odor",
         addr=("valid", "Kittering Way", "Englewood", 0),
         text="Sewer odor from the manhole in the cul-de-sac for two days, strongest in the morning. No backup in the house.",
         channel="web"),
    dict(key="C08", group="control", scenario="Complete request", type="Curb Stop",
         addr=("valid", "Mistral Point Dr", "Sarasota", 0),
         text="Curb stop is leaking from the stem when turned on. I had a plumber confirm it is on the County side.",
         channel="app"),
    dict(key="C09", group="control", scenario="Complete request", type="Water Line Leak",
         addr=("valid", "Umberleigh Rd", "Venice", 2),
         text="Water seeping from the ground between the meter and the road, the area stays wet even when it does not rain.",
         channel="email", entered_by="0824012"),
    dict(key="C10", group="control", scenario="Complete request", type="No Water",
         addr=("valid", "Verbena Key Ln", "Sarasota", 1),
         text="No water at this address only. Bill is paid, no lock on the meter, neighbors have water.",
         channel="app"),
    dict(key="C11", group="control", scenario="Complete request", type="Lift Station Alarm",
         addr=("valid", "Zephyr Palm Dr", "North Port", 0),
         text="Lift station at the corner has its red alarm light on and the horn is sounding. Station sign reads LS-114.",
         wo=dict(worktype="CM", short="LS ALARM", status="COMP",
                 logs=["Float switch stuck. Cleaned and reset. Station operating normally."]),
         channel="app"),
    dict(key="C12", group="control", scenario="Complete request", type="Water Meter Issue",
         addr=("valid", "Ashgrove Tern Ct", "Nokomis", 1),
         text="Meter is spinning with all fixtures off and no visible leak in the house. Please check the meter for accuracy.",
         channel="web"),

    # ---- Added after IBM's updated data review: the County's misrouted, non-County and
    # similar-but-not-duplicate patterns. Reported on the last day, after every earlier SR.
    dict(key="M25", group="missing", scenario="Incorrect classification", type="Sewer Issue",
         true_type="Drainage / Flooding",
         addr=("valid", "Pinnacle Reef Ct", "Englewood", 2),
         text="Caller says the sewer pipes along the street need to be cleaned out. The drains in the road are clogged with leaves and the street floods every time it rains.",
         issue="Describes clogged storm drains and street flooding, but it was filed as a Sewer Issue and routed to Wastewater.",
         missing="Correct classification: Drainage / Flooding (Public Works Stormwater).",
         question="Are the clogged drains the storm drains in the road, or a sewer manhole or cleanout?",
         resolved=dict(status="CLOSED", hours=2, logtype="RESOLUTION",
                       note="Spoke with the caller. The clogged drains are the storm drains in the road, so this is "
                            "stormwater, not sewer. Sent routing instruction to the Contact Center to reassign it to "
                            "Public Works Stormwater."),
         when=("at", "2026-10-27 08:40"), channel="phone", entered_by="0822775"),
    dict(key="N01", group="responsibility", scenario="County responsibility review", type="Backflow Device Issue",
         addr=("valid", "Dovetail Pl", "Nokomis", 2),
         text="The backflow pipes in front of our office are leaking, a lot of water is coming out of the valves. Maybe it is rusted out.",
         issue="A backflow preventer belongs to the property owner, so the repair is private, not County work.",
         missing="Whether the water comes from the backflow device or from the County side of the meter.",
         question="Is the water coming from the backflow device itself, or from the meter box at the street?",
         refer_to="a licensed plumber or backflow tester",
         resolved=dict(status="RESOLVED", hours=2, logtype="CLIENTNOTE",
                       note="Called the customer and explained that backflow devices are the property owner's "
                            "responsibility. Advised them to call a plumber."),
         when=("at", "2026-10-27 09:10"), channel="web"),
    dict(key="N02", group="responsibility", scenario="County responsibility review", type="Water Line Leak",
         addr=("valid", "Zinnia Crest Ln", "North Port", 1),
         text="Water is leaking from the meter box in front of my house and running down the street.",
         issue="The address is in the City of North Port Utilities service area, so the County does not own this meter or line.",
         missing="Which utility the customer gets a water bill from.",
         question="Is your water bill from the City of North Port? If so, the city's utility handles this leak.",
         refer_to="City of North Port Utilities", other_utility=True,
         when=("at", "2026-10-27 10:25"), channel="app"),
    dict(key="N03", group="responsibility", scenario="County responsibility review", type="No Water",
         addr=("valid", "Zoysia Meadow Ct", "Venice", 0),
         text="Caller has had no water since early this morning. The neighbors are out too.",
         issue="The address is in the City of Venice Utilities service area; the County does not supply water there.",
         missing="Which utility the customer gets a water bill from.",
         question="Does the caller pay a City of Venice water bill? If so, give them the city utility's number.",
         refer_to="City of Venice Utilities", other_utility=True,
         when=("at", "2026-10-27 11:40"), channel="phone", entered_by="0821106"),
    dict(key="L04", group="lookalike", scenario="Look-alike (not a duplicate)", type="Water Main Break",
         addr=("valid", "Bramblewick Ln", "Sarasota", 0),
         text="Water is coming up through the road again at the same spot the County dug up last week.",
         issue="Same address and problem as the October outage, but reported after that repair was completed.",
         related="DC1", same_address=True,
         reason="the main break repair at this address was completed before this report, so water coming up again "
                "is a new leak or a failed repair, not another report of the open problem",
         when=("at", "2026-10-27 12:15"), channel="app", sr_status="NEW"),
]

# Past work orders. (street, city, house_index or None, request type, months ago, short description, logs)
HISTORICAL_WOS = [
    ("Larkspur Bay Dr", "Sarasota", 0, "Water Line Leak", 8, "SERVICE LINE LEAK",
     ["Exposed 3/4 in. copper service, pinhole leak 2 ft from the meter. Repaired with compression coupling."]),
    ("Larkspur Bay Dr", "Sarasota", 0, "Water Line Leak", 3, "SERVICE LINE LEAK",
     ["Second leak on the same copper service. Repaired. Copper is thin, recommend full service replacement if it leaks again."]),
    ("Nettlecreek Ln", "Venice", 1, "Low Water Pressure", 5, "LOW PRESSURE",
     ["Pressure 62 psi at the meter, within spec. Customer's pressure reducing valve is old. Advised plumber."]),
    ("Oakhallow Cir", "Nokomis", None, "Sewer Issue", 2, "MAIN LINE STOPPAGE",
     ["Jetted 450 ft of 8 in. gravity main. Heavy root intrusion at two joints."]),
    ("Oakhallow Cir", "Nokomis", None, "Sewer Issue", 1, "CCTV INSPECTION",
     ["CCTV after jetting. Roots at joints 3 and 7. Recommend lining. Added to the rehab candidate list."]),
    ("Pebblestone Way", "North Port", 2, "Water Meter Issue", 4, "METER CHANGE OUT",
     ["Replaced 5/8 in. meter, old meter stopped registering. Final read recorded."]),
    ("Rushmere Ave", "Sarasota", 1, "Curb Stop", 14, "CURB STOP REPLACEMENT",
     ["Replaced broken curb stop. Operated open and closed, no leaks."]),
    ("Brackenridge Ln", "Sarasota", 0, "Water Line Leak", 6, "SERVICE LINE LEAK",
     ["Repaired service line leak at the corporation stop."]),
    ("Copperleaf Dr", "Venice", 1, "Sewer Odor", 9, "MANHOLE ODOR",
     ["Installed odor control insert in manhole."]),
    ("Dunmore Key Way", "Nokomis", 2, "Water Meter Issue", 11, "METER BOX REPLACEMENT",
     ["Replaced crushed meter box."]),
    ("Embersand Ct", "North Port", 0, "Lift Station Alarm", 7, "LS ALARM",
     ["Replaced failed pump 1 contactor. Station normal."]),
    ("Featherstone Rd", "Osprey", 1, "Water Main Break", 13, "MAIN BREAK",
     ["Repaired 6 in. main break, replaced 4 ft section."]),
    ("Gannet Ridge Ave", "Englewood", 0, "Reclaimed Water Issue", 10, "RECLAIM LEAK",
     ["Repaired leaking reclaimed service line."]),
    ("Hollowpine Cir", "Sarasota", 3, "Curb Stop", 15, "CURB STOP LEAK",
     ["Tightened packing nut on the curb stop. No leak."]),
]

# Planned or in-progress projects. (street, city, request type, status, start, finish, description, scope, logs)
PLANNED_WOS = [
    ("Starling Cove Dr", "Sarasota", "Water Main Break", "SCHED", "2026-11-16", "2026-12-18",
     "Starling Cove Dr water main replacement",
     "Replace about 1,400 LF of 8 in. asbestos-cement water main on Starling Cove Dr with PVC. Expect intermittent low pressure and discolored water during tie-ins and flushing.",
     ["Contractor notice to proceed issued. Door hangers to go out the week before start."]),
    ("Willowmarsh Rd", "Venice", "Sewer Issue", "WCONT", "2026-12-07", "2026-12-23",
     "Willowmarsh Rd sanitary sewer main lining",
     "Cured-in-place lining of 1,100 LF of 8 in. gravity sewer and manhole rehab on Willowmarsh Rd. Temporary odor possible during bypass pumping.",
     ["Pre-lining CCTV completed. Odor complaints on this segment expected to resolve after lining."]),
    ("Yarrowfield Ln", "North Port", "Water Meter Issue", "SCHED", "2026-11-02", "2026-11-20",
     "Yarrowfield Ln area automated meter change-out",
     "Replace all residential meters in the Yarrowfield Ln area with automated (AMI) meters. Includes failed and blank-display meters.",
     ["Meter crew assigned. Customers on this route will be notified 48 hours before change-out."]),
    ("Quayside Ct", "Englewood", "Water Line Leak", "INPRG", "2026-10-12", "2026-11-06",
     "Quayside Ct valve and hydrant replacement",
     "Replace two 6 in. gate valves and one fire hydrant on Quayside Ct. Pavement restoration follows each excavation.",
     ["Valve 1 replaced and road patched on 10/20.", "Valve 2 scheduled next week. Watch for settlement at the 10/20 patch."]),
    ("Ironwood Shoals Dr", "Venice", "Water Main Break", "WCONT", "2027-01-11", "2027-02-26",
     "Ironwood Shoals Dr water main upsizing",
     "Upsize 6 in. main to 8 in. on Ironwood Shoals Dr to improve fire flow.",
     ["Design approved. Awaiting contract award."]),
    ("Jessamine Bay Rd", "Sarasota", "Sewer Issue", "SCHED", "2026-11-30", "2026-12-11",
     "Jessamine Bay Rd manhole rehabilitation",
     "Rehabilitate 6 manholes on Jessamine Bay Rd with cementitious liner.",
     ["Traffic control plan approved."]),
    ("Kingfisher Lantern Ln", "North Port", "Lift Station Alarm", "WCONT", "2027-01-18", "2027-03-05",
     "Lift station LS-207 pump and panel upgrade",
     "Replace pumps and control panel at lift station LS-207 off Kingfisher Lantern Ln.",
     ["Equipment on order. Bypass pumping needed during cutover."]),
    ("Lindenhurst Ave", "Nokomis", "Reclaimed Water Issue", "SCHED", "2026-11-09", "2026-11-25",
     "Lindenhurst Ave reclaimed main extension",
     "Extend 6 in. reclaimed main 900 LF along Lindenhurst Ave.",
     ["Locates requested."]),
]
