"""Turn rows of data/maximo/*.csv into Maximo REST payloads. Pure: no HTTP, no state.

Columns are either mapped to an attribute, applied later (STATUS, via changeStatus), or
dropped because Maximo derives them. Callers can drop more columns (for example the failure
codes when provisioning left them as a manual step); every dropped column is reported.
"""

from dataclasses import dataclass, field

# CSV column -> attribute. Attributes are the lowercase column names, so only the lists matter.
SR_COLUMNS = ("TICKETID", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "REPORTEDBY", "REPORTEDNAME",
              "REPORTEDPHONE", "REPORTEDEMAIL", "REPORTDATE", "AFFECTEDPERSON", "AFFECTEDNAME", "AFFECTEDEMAIL",
              "EXTERNALSYSTEM", "EXTERNALSYSTEM_TICKETID", "COMMODITYGROUP", "COMMODITY", "CLASSSTRUCTUREID",
              "OWNERGROUP", "SITEID", "ORGID")
WO_COLUMNS = ("WONUM", "PARENT", "WORKTYPE", "DESCRIPTION", "DESCRIPTION_LONGDESCRIPTION", "ORIGRECORDID",
              "ORIGRECORDCLASS", "REPORTEDBY", "REPORTDATE", "CLASSSTRUCTUREID", "JPNUM", "PERSONGROUP",
              "OWNERGROUP", "SUPERVISOR", "LEAD", "FAILURECODE", "PROBLEMCODE", "SCHEDSTART", "SCHEDFINISH",
              "ACTSTART", "ACTFINISH", "SITEID", "ORGID")
WORKLOG_COLUMNS = ("LOGTYPE", "CREATEBY", "CREATEDATE", "CLIENTVIEWABLE", "DESCRIPTION",
                   "DESCRIPTION_LONGDESCRIPTION")

# Set by Maximo, or by the loader through another call. Never sent on create.
DERIVED = {
    "sr": {"CLASS": "Maximo sets it from the object structure", "STATUS": "applied with changeStatus",
           "STATUSDATE": "set by changeStatus", "CREATEDBY": "the API key's user",
           "CREATIONDATE": "the time of the load"},
    "wo": {"STATUS": "applied with changeStatus", "STATUSDATE": "set by changeStatus"},
    "worklog": {"WORKLOGID": "Maximo numbers work logs", "RECORDKEY": "the parent record",
                "CLASS": "the parent record", "SITEID": "the parent record", "ORGID": "the parent record"},
}
BOOLEAN_COLUMNS = {"CLIENTVIEWABLE"}


@dataclass
class Remap:
    """Our keys -> Maximo's, filled from the manifest and the instance."""
    tickets: dict[str, str] = field(default_factory=dict)        # our TICKETID -> Maximo TICKETID
    wonums: dict[str, str] = field(default_factory=dict)         # our WONUM -> Maximo WONUM
    classes: dict[str, str] = field(default_factory=dict)        # our CLASSSTRUCTUREID -> Maximo's


def _value(column: str, raw: str):
    if column in BOOLEAN_COLUMNS:
        return raw.strip() in ("1", "true", "True", "Y")
    return raw


def _payload(row: dict, columns, drop: set[str]) -> dict:
    return {c.lower(): _value(c, row[c]) for c in columns if c not in drop and row.get(c, "") != ""}


def sr_payload(row: dict, remap: Remap, drop: set[str] = frozenset()) -> dict:
    payload = _payload(row, SR_COLUMNS, drop)
    if "classstructureid" in payload:
        payload["classstructureid"] = remap.classes.get(row["CLASSSTRUCTUREID"], row["CLASSSTRUCTUREID"])
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
    return payload


def worklog_payload(row: dict) -> dict:
    return _payload(row, WORKLOG_COLUMNS, set())


def dropped_columns(kind: str, header, drop: set[str]) -> dict[str, str]:
    """Every CSV column not sent on create, with the reason."""
    columns = {"sr": SR_COLUMNS, "wo": WO_COLUMNS, "worklog": WORKLOG_COLUMNS}[kind]
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
WO_STEPS = {"WCONT": ["WCONT"], "SCHED": ["SCHED"], "INPRG": ["INPRG"], "COMP": ["INPRG", "COMP"],
            "CLOSE": ["INPRG", "COMP", "CLOSE"], "CAN": ["CAN"]}


def status_steps(kind: str, final: str, current: str | None = None) -> list[str]:
    """The changeStatus calls still needed to reach `final` from `current` (None = just created)."""
    steps = (SR_STEPS if kind == "sr" else WO_STEPS)[final]
    if current in steps:
        return steps[steps.index(current) + 1:]
    return [] if current == final else steps
