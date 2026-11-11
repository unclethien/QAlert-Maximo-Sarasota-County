"""Turn rows of data/maximo/*.csv into Maximo REST payloads. Pure: no HTTP, no state.

Columns are either mapped to an attribute, applied later (STATUS, via changeStatus), or
dropped because Maximo derives them. Callers can drop more columns (for example the failure
codes when provisioning left them as a manual step); every dropped column is reported.
"""

from dataclasses import dataclass, field

# CSV column -> attribute. Attributes are the lowercase column names, except those in RENAMED.
SR_COLUMNS = ("TICKETID", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "SOURCE", "REPORTEDPRIORITY", "REPORTEDBY",
              "REPORTEDPHONE", "REPORTEDEMAIL", "REPORTDATE", "AFFECTEDPERSON", "AFFECTEDPHONE", "AFFECTEDEMAIL",
              "EXTERNALSYSTEM_TICKETID", "COMMODITYGROUP", "COMMODITY", "CLASSSTRUCTUREID",
              "OWNERGROUP", "SITEID", "ORGID")
# The SR's service address, sent as its one TKSERVICEADDRESS child row. With a code, Maximo stores
# only the code unless every field is sent too, so the dataset carries them all.
SR_ADDRESS_COLUMNS = ("SADDRESSCODE", "STADDRNUMBER", "STADDRSTREET", "STREETADDRESS", "CITY", "STATEPROVINCE",
                      "POSTALCODE", "COUNTRY", "LATITUDEY", "LONGITUDEX")
SR_ADDRESS_CHILD = "tkserviceaddress"
WO_COLUMNS = ("WONUM", "PARENT", "WORKTYPE", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "ORIGRECORDID",
              "ORIGRECORDCLASS", "REPORTEDBY", "REPORTDATE", "CLASSSTRUCTUREID", "JPNUM", "PERSONGROUP",
              "OWNERGROUP", "SUPERVISOR", "LEAD", "FAILURECODE", "PROBLEMCODE", "SCHEDSTART", "SCHEDFINISH",
              "ACTSTART", "ACTFINISH", "SITEID", "ORGID")
# Standard Maximo has no EXTERNALSYSTEM_TICKETID on tickets, so the QAlert request id goes into
# the standard EXTERNALRECID. It is also the SR's natural key for re-runs.
RENAMED = {"EXTERNALSYSTEM_TICKETID": "externalrecid"}
WORKLOG_COLUMNS = ("LOGTYPE", "CREATEBY", "CREATEDATE", "CLIENTVIEWABLE", "DESCRIPTION",
                   "DESCRIPTION_LONGDESCRIPTION")

# The County's PERSONGROUP holds more than standard Maximo's 8 characters. A longer team code is
# written under a shorter one; verify and the Maximo answer key use the same mapping.
TEAM_CODES = {"SANCLINSP": "SANCLINS"}


def maximo_team(code: str) -> str:
    return TEAM_CODES.get(code, code)


# Set by Maximo, set by the loader through another call, or implied. Never sent on create.
DERIVED = {
    "sr": {"CLASS": "Maximo sets it from the object structure", "STATUS": "applied with changeStatus",
           "STATUSDATE": "set by changeStatus", "CREATEDBY": "the API key's user",
           "CREATIONDATE": "the time of the load",
           "EXTERNALSYSTEM": "always QAlert; standard Maximo has no such ticket attribute",
           # Only in the training history, which keeps the text-only shape of today's feed.
           "REPORTEDNAME": "Maximo clears it when REPORTEDBY is a person and shows that person's name",
           "AFFECTEDNAME": "Maximo clears it when AFFECTEDPERSON is a person and shows that person's name"},
    "wo": {"STATUS": "applied with changeStatus", "STATUSDATE": "set by changeStatus"},
    "worklog": {"WORKLOGID": "Maximo numbers work logs", "RECORDKEY": "the parent record",
                "CLASS": "the parent record", "SITEID": "the parent record", "ORGID": "the parent record"},
}
BOOLEAN_COLUMNS = {"CLIENTVIEWABLE"}
INTEGER_COLUMNS = {"REPORTEDPRIORITY"}
DECIMAL_COLUMNS = {"LATITUDEY", "LONGITUDEX"}


@dataclass
class Remap:
    """Our keys -> Maximo's, filled from the manifest and the instance."""
    tickets: dict[str, str] = field(default_factory=dict)        # our TICKETID -> Maximo TICKETID
    wonums: dict[str, str] = field(default_factory=dict)         # our WONUM -> Maximo WONUM
    classes: dict[str, str] = field(default_factory=dict)        # our CLASSSTRUCTUREID -> Maximo's


def _value(column: str, raw: str):
    if column in BOOLEAN_COLUMNS:
        return raw.strip() in ("1", "true", "True", "Y")
    if column in INTEGER_COLUMNS:
        return int(raw)
    if column in DECIMAL_COLUMNS:
        return float(raw)
    return raw


def _payload(row: dict, columns, drop: set[str]) -> dict:
    return {RENAMED.get(c, c.lower()): _value(c, row[c]) for c in columns if c not in drop and row.get(c, "") != ""}


def sr_payload(row: dict, remap: Remap, drop: set[str] = frozenset()) -> dict:
    payload = _payload(row, SR_COLUMNS, drop)
    if "classstructureid" in payload:
        payload["classstructureid"] = remap.classes.get(row["CLASSSTRUCTUREID"], row["CLASSSTRUCTUREID"])
    address = _payload(row, SR_ADDRESS_COLUMNS, drop)
    if address:  # the history's text-only rows have none
        payload[SR_ADDRESS_CHILD] = [address]
    return payload


def wo_payload(row: dict, remap: Remap, drop: set[str] = frozenset()) -> dict:
    payload = _payload(row, WO_COLUMNS, drop)
    payload["externalrefid"] = row["WONUM"]  # our id survives even if Maximo renumbers the WO
    if "origrecordid" in payload:
        payload["origrecordid"] = remap.tickets.get(row["ORIGRECORDID"], row["ORIGRECORDID"])
    if "parent" in payload:
        payload["parent"] = remap.wonums.get(row["PARENT"], row["PARENT"])
    if "classstructureid" in payload:
        payload["classstructureid"] = remap.classes.get(row["CLASSSTRUCTUREID"], row["CLASSSTRUCTUREID"])
    for team in ("persongroup", "ownergroup"):
        if team in payload:
            payload[team] = maximo_team(payload[team])
    return payload


# The County's RESOLUTION note has no standard Maximo log type; UPDATE is the nearest.
LOG_TYPES = {"RESOLUTION": "UPDATE"}


def maximo_logtype(logtype: str) -> str:
    return LOG_TYPES.get(logtype, logtype)


def worklog_payload(row: dict) -> dict:
    payload = _payload(row, WORKLOG_COLUMNS, set())
    if payload.get("logtype"):
        payload["logtype"] = maximo_logtype(payload["logtype"])
    return payload


def dropped_columns(kind: str, header, drop: set[str]) -> dict[str, str]:
    """Every CSV column not sent on create, with the reason."""
    columns = {"sr": SR_COLUMNS + SR_ADDRESS_COLUMNS, "wo": WO_COLUMNS, "worklog": WORKLOG_COLUMNS}[kind]
    out = {}
    for c in header:
        if c in DERIVED[kind]:
            out[c] = DERIVED[kind][c]
        elif c in drop:
            out[c] = "dropped for this run (reference data not provisioned)"
        elif c not in columns:
            out[c] = "not mapped"
    return out


# Status changes after create. SRs start NEW and WOs start WAPPR (our WCONT is a WAPPR synonym,
# so it is still set explicitly). Each final status is reached through the usual steps.
SR_STEPS = {"NEW": [], "QUEUED": ["QUEUED"], "INPRG": ["QUEUED", "INPRG"], "PENDING": ["QUEUED", "PENDING"],
            "RESOLVED": ["QUEUED", "INPRG", "RESOLVED"], "CLOSED": ["QUEUED", "INPRG", "RESOLVED", "CLOSED"]}
INITIAL_STATUS = {"sr": "NEW", "wo": "WAPPR"}
SR_IN_PROGRESS = "INPRG"
# Statuses that put a record in history: Maximo refuses every later change, work logs included.
HISTORY_STATUSES = {"sr": {"CLOSED"}, "wo": {"CLOSE", "CAN"}}
WO_STEPS = {"WAPPR": [], "WCONT": ["WCONT"], "SCHED": ["SCHED"], "INPRG": ["INPRG"], "COMP": ["INPRG", "COMP"],
            "CLOSE": ["INPRG", "COMP", "CLOSE"], "CAN": ["CAN"]}


# Maximo refuses the SRSTATUS synonym INPRG in changeStatus ("not in the value list"), even
# once the synonym exists, so SRs move through the standard INPROG. WOs keep INPRG, which is
# standard on WOSTATUS. The dataset, the manifest and the step lists stay in dataset terms.
STATUS_CODES = {"sr": {"INPRG": "INPROG"}, "wo": {}}


def maximo_status(kind: str, status: str) -> str:
    return STATUS_CODES[kind].get(status, status)


def dataset_status(kind: str, status: str | None) -> str | None:
    """A status as Maximo reports it, in the dataset's terms."""
    return next((ours for ours, theirs in STATUS_CODES[kind].items() if theirs == status), status)


def status_steps(kind: str, final: str, current: str | None = None) -> list[str]:
    """The changeStatus calls still needed to reach `final` from `current` (None = just created)."""
    steps = (SR_STEPS if kind == "sr" else WO_STEPS)[final]
    if current in steps:
        return steps[steps.index(current) + 1:]
    return [] if current == final else steps
