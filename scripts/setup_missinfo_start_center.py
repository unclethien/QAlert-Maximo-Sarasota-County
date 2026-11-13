"""Set up the "Missing Information" Start Center for the EVERYONE security group: KPIs that count
the open SRs by the type of information missing, and one list of SRs per type.

The counts come from the internal MISSINFO work log entries, "Missing information: <rule>", that
the SRQMISSINFO launch point and the scheduled watsonx.ai check (scripts/ai_missing_info.py) add.
- The KPIs are real-time: Maximo calculates one when it is created and when a Start Center shows
  it. Saving it again through the API does not recalculate it, so MXAPIKPIMAIN can return an old
  count. A KPI List row cannot open the SRs behind it.
- So each type also gets a public saved query in Service Requests and a Result Set portlet; a row
  opens the SR. The REST API cannot create saved queries, so the automation script SRQMKQUERY
  (scripts/autoscript/srqmkquery.py) is deployed and called directly to create them.
- The API does not save a group's Start Center template, so that step is done in Security Groups;
  the script says when.

    uv run -q --no-project --with-requirements requirements.txt python scripts/setup_missinfo_start_center.py           # preview
    uv run -q --no-project --with-requirements requirements.txt python scripts/setup_missinfo_start_center.py --apply   # create or update
    uv run -q --no-project --with-requirements requirements.txt python scripts/setup_missinfo_start_center.py --remove  # undo
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pilot_catalog as cat  # noqa: E402
from loader.client import MaximoClient, MaximoError  # noqa: E402
from loader.config import load_settings  # noqa: E402

from xml.sax.saxutils import quoteattr  # noqa: E402

GROUP = "EVERYONE"
QUERY_SCRIPT = "SRQMKQUERY"
QUERY_SCRIPT_SOURCE = ROOT / "scripts" / "autoscript" / "srqmkquery.py"
LIST_COLUMNS = (("TICKETID", "Service Request"), ("DESCRIPTION", "Summary"), ("STATUS", "Status"),
                ("REPORTDATE", "Reported"))
TEMPLATE = "Missing Information"
AI_SUMMARY = "AI check: missing information"
OPEN_SR = ("siteid='SRQSITE' and status in (select value from synonymdomain where domainid='SRSTATUS' "
           "and maxvalue in ('NEW','QUEUED','PENDING','INPROG'))")
ADDRESS_RULES, LIFT_RULES, ONE_ISSUE = ("ADDR", "ADDR-VALID"), ("LS-ID",), ("ONE-ISSUE",)
DETAIL_RULES = tuple(r for r, _, _ in cat.REQUIRED_INFORMATION if r not in ADDRESS_RULES + LIFT_RULES + ONE_ISSUE)


def _has_note(rules=None):
    """An SQL condition: the SR has a MISSINFO entry, for one of `rules` when given."""
    which = ""
    if rules:
        which = " and w.description in (" + ",".join(f"'Missing information: {r}'" for r in rules) + ")"
    return ("exists (select 1 from worklog w where w.recordkey=ticketid and w.class='SR' "
            "and w.siteid='SRQSITE' and w.logtype='MISSINFO'" + which + ")")


# (KPI and saved query name, description, condition on an open SR). The first is the total.
KPIS = [
    ("SRQMI-ALL", "Open SRs missing information", _has_note()),
    ("SRQMI-ADDR", "No house number", _has_note(["ADDR"])),
    ("SRQMI-ADDRVALID", "Address not in the County file or outside the county", _has_note(["ADDR-VALID"])),
    ("SRQMI-LSID", "Lift station not named", _has_note(LIFT_RULES)),
    ("SRQMI-ONEISSUE", "More than one problem in one request", _has_note(ONE_ISSUE)),
    ("SRQMI-DETAIL", "Problem not described well enough", _has_note(DETAIL_RULES)),
    ("SRQMI-WAITING", "Open SRs waiting for the AI check",
     f"not exists (select 1 from worklog w where w.recordkey=ticketid and w.class='SR' "
     f"and w.siteid='SRQSITE' and w.description='{AI_SUMMARY}')"),
]


# The types that get a saved query in Service Requests.
LISTS = ("SRQMI-ADDR", "SRQMI-ADDRVALID", "SRQMI-LSID", "SRQMI-ONEISSUE", "SRQMI-DETAIL", "SRQMI-ALL")
# The page: column 0 (left), then column 1 (right), each top to bottom. "KPIS" is the counts.
# Every Start Center layout here is "NW", a narrow column 0 and a wide column 1. SRQMI-ALL is a
# saved query only; the counts show its total.
PAGE = (("KPIS", "SRQMI-ONEISSUE", "SRQMI-DETAIL"), ("SRQMI-ADDRVALID", "SRQMI-ADDR", "SRQMI-LSID"))


def kpi_record(name, description, condition):
    return {"kpiname": name, "description": description, "selectstmt": "select count(*) from sr",
            "clause": f"where {OPEN_SR} and {condition}", "format": "DECIMAL", "app": "SR",
            "ispublic": True, "realtime": True, "target": 0, "cautionmin": 1, "cautionmax": 5}


def saved_queries():
    """The public Service Requests queries behind the lists."""
    by_name = {name: (description, condition) for name, description, condition in KPIS}
    return [{"name": name, "description": f"Missing information: {by_name[name][0]}",
             "clause": f"{OPEN_SR} and {by_name[name][1]}"} for name in LISTS]


def _result_set(column, order, name, description, owner):
    uid = f"SRQMIR{column}{order}"
    columns = " ".join(f'<attribute columnorder="{i}" contentuid="{uid}{col}" description={quoteattr(label)} '
                       f'display="1" isconditionset="0" isgraphon="0" querycolumn="{col}"/>'
                       for i, (col, label) in enumerate(LIST_COLUMNS, 1))
    return (f'<resultset charttype="BAR" columnnum="{column}" contentuid="{uid}" description={quoteattr(description)} '
            f'minormax="1" ordernum="{order}" portletid="RSCONFIG" queryapp="SR" queryclausename="{name}" '
            f'queryowner="{owner}" showchart="0"> {columns} </resultset>')


def _kpi_list(column, order):
    kpis = " ".join(f'<kpi kpiname="{name}"/>' for name, _, _ in KPIS)
    return (f'<kpilist charttype="BAR" columnnum="{column}" contentuid="SRQMIP1" description="Open SRs missing '
            f'information, by type" minormax="1" ordernum="{order}" portletid="KPILCONFIG" showchart="0"> {kpis} </kpilist>')


def presentation(owner):
    titles = {name: description for name, description, _ in KPIS}
    portlets = "".join(_kpi_list(col, order) if name == "KPIS" else _result_set(col, order, name, titles[name], owner)
                       for col, names in enumerate(PAGE) for order, name in enumerate(names, 1))
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<startcenter contentuid="SRQMI" description="{TEMPLATE}" layout="NW">{portlets}</startcenter>')


def deploy_query_script(c):
    """Create or update the SRQMKQUERY automation script (no launch point)."""
    record = {"autoscript": QUERY_SCRIPT, "description": "Create the missing-information saved queries",
              "scriptlanguage": "python", "source": QUERY_SCRIPT_SOURCE.read_text(), "active": True}
    found = c.query("mxapiautoscript", where=f'autoscript="{QUERY_SCRIPT}"', select="autoscript")
    if found:
        c.merge(found[0]["href"], record)
    else:
        c.create("mxapiautoscript", record)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="create or update the KPIs and the Start Center")
    mode.add_argument("--remove", action="store_true", help="delete them and clear the group's Start Center")
    args = ap.parse_args()

    s = load_settings()
    c = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)
    kpis = {k["kpiname"]: k for k in c.query("mxapikpimain", select="kpiname,kpivalue",
                                             where='kpiname in [' + ",".join(f'"{n}"' for n, _, _ in KPIS) + "]")}
    templates = [t for t in c.query("mxapistartcntr", select="sctemplateid,description", page_size=200)
                 if t.get("description") == TEMPLATE]
    group = c.query("mxapigroup", where=f'groupname="{GROUP}"', select="groupname,sctemplateid")[0]
    ours = {t["sctemplateid"] for t in templates}
    print(f"Group {GROUP}: Start Center template {group.get('sctemplateid')}; "
          f"existing '{TEMPLATE}' templates: {sorted(ours) or 'none'}")

    for name, description, _ in KPIS:
        state = "update" if name in kpis else "create"
        print(f"  {state:6} {name:16} {description}")

    if args.remove:
        script = c.query("mxapiautoscript", where=f'autoscript="{QUERY_SCRIPT}"', select="autoscript")
        if script:
            c.script(QUERY_SCRIPT, {"remove": list(LISTS)})
            c.delete(script[0]["href"])
        if group.get("sctemplateid") in ours:
            c.merge(group["href"], {"sctemplateid": None})
        for t in templates:
            c.delete(t["href"])
        for k in kpis.values():
            c.delete(k["href"])
        print(f"Removed {len(kpis)} KPIs and {len(templates)} templates")
        return 0
    if not args.apply:
        print("Preview only; run with --apply to create or update them.")
        return 0

    failed = 0
    for name, description, condition in KPIS:
        try:
            if name in kpis:
                c.merge(kpis[name]["href"], kpi_record(name, description, condition))
            else:
                c.create("mxapikpimain", kpi_record(name, description, condition))
        except MaximoError as e:
            failed += 1
            print(f"  FAILED {name} - {e}")
    if failed:
        return 1
    deploy_query_script(c)
    made = c.script(QUERY_SCRIPT, {"queries": saved_queries()})
    if sorted(made.get("done") or []) != sorted(LISTS):
        print(f"  FAILED saved queries: the script made {made.get('done')}")
        return 1
    owner = made["owner"]
    print(f"  {len(LISTS)} public saved queries in Service Requests, owned by {owner}")
    layout = presentation(owner)
    if templates:
        c.merge(templates[0]["href"], {"presentation": layout})
        template_id = templates[0]["sctemplateid"]
    else:
        template_id = c.create("mxapistartcntr", {"description": TEMPLATE, "presentation": layout})["sctemplateid"]
    if group.get("sctemplateid") not in (None, template_id):
        print(f"{GROUP} already has Start Center template {group['sctemplateid']}; not replaced. "
              f"Assign template {template_id} in Security Groups.")
        return 1
    # MXAPIGROUP accepts a SCTEMPLATEID change without an error but does not save it, so read it back.
    c.merge(group["href"], {"sctemplateid": template_id})
    saved = c.query("mxapigroup", where=f'groupname="{GROUP}"', select="groupname,sctemplateid")[0].get("sctemplateid")
    print(f"{len(KPIS)} KPIs, {len(LISTS)} saved queries and Start Center template {template_id} ('{TEMPLATE}') set up")
    if saved != template_id:
        print(f"The API did not save the template on {GROUP}. In Security Groups, open {GROUP}, set Start Center "
              f"Template to {template_id} ('{TEMPLATE}') and save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
