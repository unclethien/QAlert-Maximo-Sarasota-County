"""Read-only inventory of a Maximo instance before anything is provisioned or loaded.

Every check is a GET. Each one records `ok`, `missing`, or `error` with a reason, so a single
refused call never hides the rest of the report.
"""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from .client import MaximoClient, MaximoError, quote_list
from .config import DATA_DIR, ORGID, SITEID, STATE_DIR, cat
from .mapping import maximo_logtype, maximo_team

# Object structures the loader uses. Failure codes have no standard API structure, so a few
# candidate names are probed and whichever answers is recorded.
REQUIRED_STRUCTURES = (
    "mxapiorganization", "mxapisite", "mxapiperson", "mxapipersongroup", "mxapidomain",
    "mxapiclassstructure", "mxapijobplan", "mxapisr", "mxapiwodetail",
)
OPTIONAL_STRUCTURES = ("mxapifailurelist", "mxfailurelist", "mxapiworktype", "mxworktype")

# whoami fields worth keeping. The rest of the response (email, phone, preferences) is left out.
WHOAMI_FIELDS = ("personid", "userName", "loginID", "displayName", "defsite", "defaultSite",
                 "insertOrg", "insertSite", "langcode")


def dataset_person_ids() -> list[str]:
    with (DATA_DIR / "maximo" / "person.csv").open(newline="", encoding="utf-8") as f:
        return [row["PERSONID"] for row in csv.DictReader(f)]


def _check(fn):
    """Run one check; a Maximo refusal becomes an `error` entry instead of an exception."""
    try:
        return fn()
    except MaximoError as e:
        return {"status": "error", "reason": str(e)}


def _present(found: list[str], wanted) -> dict:
    found_set = set(found)
    missing = [w for w in wanted if w not in found_set]
    return {"status": "ok" if not missing else "missing", "found": sorted(found_set & set(wanted)),
            "missing": missing}


def check_identity(client: MaximoClient) -> dict:
    who = client.verify_connection()
    return {"status": "ok", **{k: who[k] for k in WHOAMI_FIELDS if who.get(k) not in (None, "")}}


def check_structures(client: MaximoClient) -> dict:
    result = {}
    for name in REQUIRED_STRUCTURES + OPTIONAL_STRUCTURES:
        ok, reason = client.probe(name)
        result[name] = {"status": "ok"} if ok else {
            "status": "missing" if name in OPTIONAL_STRUCTURES else "error", "reason": reason}
    return result


def check_org_and_site(client: MaximoClient) -> dict:
    orgs = client.query("mxapiorganization", select="orgid,description,active,itemsetid,companysetid,basecurrency1")
    sites = client.query("mxapisite", where=f'siteid="{SITEID}"', select="siteid,orgid,description,active")
    org = next((o for o in orgs if o.get("orgid") == ORGID), None)
    site = sites[0] if sites else None
    return {
        "status": "ok" if org and site else "missing",
        "org": org and {k: org.get(k) for k in ("orgid", "active", "itemsetid", "companysetid", "basecurrency1")},
        "site": site and {k: site.get(k) for k in ("siteid", "orgid", "active")},
        # Item sets and company sets already in use, to help choose MAXIMO_ITEMSETID.
        "existing_orgs": [{k: o.get(k) for k in ("orgid", "active", "itemsetid", "companysetid", "basecurrency1")}
                          for o in orgs],
    }


def check_record_counts(client: MaximoClient) -> dict:
    return {
        "status": "ok",
        "sr_at_site": client.count("mxapisr", f'siteid="{SITEID}"'),
        "wo_at_site": client.count("mxapiwodetail", f'siteid="{SITEID}"'),
    }


def check_domains(client: MaximoClient) -> dict:
    """Status values (synonym domains) and work log types the dataset uses."""
    wanted = {"SRSTATUS": cat.SR_STATUSES, "WOSTATUS": cat.WO_STATUSES, "LOGTYPE": tuple(dict.fromkeys(maximo_logtype(t) for t in cat.LOG_TYPES))}
    rows = client.query("mxapidomain", where=f"domainid in {quote_list(wanted)}",
                        select="domainid,domaintype,synonymdomain{value,maxvalue,defaults},alndomain{value}")
    result = {}
    for domainid, values in wanted.items():
        row = next((r for r in rows if r.get("domainid") == domainid), None)
        if row is None:
            result[domainid] = {"status": "missing", "reason": "domain not found"}
            continue
        if domainid == "LOGTYPE":  # an ALN domain on some instances, a synonym domain on others
            found = [v.get("value") for v in (row.get("alndomain") or []) + (row.get("synonymdomain") or [])]
            result[domainid] = _present(found, values)
            continue
        synonyms = {s.get("value"): s.get("maxvalue") for s in row.get("synonymdomain") or []}
        entry = _present(list(synonyms), values)
        entry["internal"] = {v: synonyms[v] for v in values if v in synonyms}
        result[domainid] = entry
    return result


def check_work_types(client: MaximoClient, structures: dict) -> dict:
    name = next((n for n in ("mxapiworktype", "mxworktype") if structures.get(n, {}).get("status") == "ok"), None)
    if name is None:
        return {"status": "unknown", "reason": "no work type object structure; check Organizations > Work Types in the UI"}
    rows = client.query(name, where=f'orgid="{ORGID}"', select="worktype,orgid")
    return _present([r.get("worktype") for r in rows], cat.WORK_TYPES)


def check_reference_data(client: MaximoClient) -> dict:
    persons = dataset_person_ids()
    groups = [maximo_team(g) for g in cat.PERSON_GROUPS]
    plans = list(cat.JOB_PLANS)
    classes = [name for name, _ in cat.CLASSIFICATIONS.values()]
    return {
        "persons": _check(lambda: _present(
            [r.get("personid") for r in client.query(
                "mxapiperson", f"personid in {quote_list(persons)}", "personid,status")], persons)),
        "person_groups": _check(lambda: _present(
            [r.get("persongroup") for r in client.query(
                "mxapipersongroup", f"persongroup in {quote_list(groups)}", "persongroup")], groups)),
        "job_plans": _check(lambda: _present(
            [r.get("jpnum") for r in client.query(
                "mxapijobplan", f"jpnum in {quote_list(plans)}", "jpnum,status,orgid,siteid")], plans)),
        # Maximo numbers classifications itself, so they are matched by name.
        "classifications": _check(lambda: _present(
            [r.get("classificationid") for r in client.query(
                "mxapiclassstructure", f"classificationid in {quote_list(classes)}",
                "classstructureid,classificationid")], classes)),
    }


def check_sr_attributes(client: MaximoClient) -> dict:
    """The load finds earlier SRs by EXTERNALRECID (the QAlert request id). It must be queryable."""
    client.query("mxapisr", where='externalrecid="0"', select="ticketid,externalrecid", page_size=1, limit=1)
    return {"status": "ok"}


def run_inventory(client: MaximoClient) -> dict:
    report: dict = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "maximo_url": client.base_url, "orgid": ORGID, "siteid": SITEID}
    report["identity"] = _check(lambda: check_identity(client))
    if report["identity"]["status"] == "error":
        return report  # wrong route or key: nothing else will answer
    report["structures"] = check_structures(client)
    report["org_and_site"] = _check(lambda: check_org_and_site(client))
    report["record_counts"] = _check(lambda: check_record_counts(client))
    report["sr_attributes"] = _check(lambda: check_sr_attributes(client))
    report["domains"] = _check(lambda: check_domains(client))
    report["work_types"] = _check(lambda: check_work_types(client, report["structures"]))
    report["reference_data"] = check_reference_data(client)
    return report


def save_report(report: dict, state_dir: Path = STATE_DIR) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = state_dir / f"inventory-{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def _line(label: str, entry: dict) -> str:
    status = entry.get("status", "?")
    detail = entry.get("reason") or (f"missing: {', '.join(entry['missing'])}" if entry.get("missing") else "")
    return f"  {label:<24} {status:<8} {detail}".rstrip()


def summarize(report: dict) -> str:
    out = [f"Maximo inventory for {report['maximo_url']} (org {report['orgid']}, site {report['siteid']})"]
    ident = report["identity"]
    if ident["status"] == "error":
        return "\n".join(out + [_line("connection", ident)])
    who = ident.get("userName") or ident.get("loginID") or ident.get("personid") or "?"
    out.append(f"  {'connected as':<24} {who}")
    out.append("Object structures:")
    out += [_line(name, entry) for name, entry in report["structures"].items()]
    org = report["org_and_site"]
    out.append("Org and site:")
    if org["status"] == "error":
        out.append(_line("org/site", org))
    else:
        out.append(f"  {ORGID:<24} {'present' if org['org'] else 'not found'}"
                   + (f" (active={org['org']['active']})" if org["org"] else ""))
        out.append(f"  {SITEID:<24} {'present' if org['site'] else 'not found'}"
                   + (f" (active={org['site']['active']})" if org["site"] else ""))
        sets = sorted({o["itemsetid"] for o in org["existing_orgs"] if o.get("itemsetid")})
        out.append(f"  {'item sets in use':<24} {', '.join(sets) or 'none'}")
    counts = report["record_counts"]
    out.append("Records:")
    if counts["status"] == "error":
        out.append(_line("counts", counts))
    else:
        out.append(f"  {'SRs at site':<24} {counts['sr_at_site']}")
        out.append(f"  {'WOs at site':<24} {counts['wo_at_site']}")
    out.append(_line("SR key (externalrecid)", report["sr_attributes"]))
    out.append("Configuration values:")
    domains = report["domains"]
    if domains.get("status") == "error":
        out.append(_line("domains", domains))
    else:
        out += [_line(name, entry) for name, entry in domains.items()]
    out.append(_line("work types", report["work_types"]))
    out += [_line(name.replace("_", " "), entry) for name, entry in report["reference_data"].items()]
    return "\n".join(out)
