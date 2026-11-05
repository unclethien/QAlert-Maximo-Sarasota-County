"""Create the setup records the pilot SRs and WOs point to.

Follows the BCPS provisioner (bcps_maximo/ingest/provision_maximo.py): each record is looked
up first and created only when it is missing, and each step prints one line per record:

  CREATED  written by this run
  EXISTS   already there (any field that differs from our data is named, never changed)
  PLAN     would be created (dry run, the default)
  MANUAL   needs a person in the Maximo UI; the line says what to do
  FAILED   Maximo refused; the BMXAA message is shown

Nothing is updated or deleted except adding children (a site, synonym values) to a record
through a MERGE, which never removes existing children.
"""

import csv
from collections import Counter, defaultdict
from collections.abc import Callable

from .client import JsonDict, MaximoClient, MaximoError, quote_list
from .mapping import maximo_team
from .config import DATA_DIR, ORGID, SITEID, Settings, cat

STEPS = ("org", "site", "persons", "person_groups", "statuses", "work_types", "classifications",
         "job_plans", "failure_codes")

# Our status values and the internal Maximo value each one is a synonym of. A value that
# Maximo already has (as a synonym) is left alone. Standard SR statuses use INPROG internally.
STATUS_VALUES = {
    "SRSTATUS": {"NEW": ("NEW", "New"), "QUEUED": ("QUEUED", "Queued"), "INPRG": ("INPROG", "In progress"),
                 "PENDING": ("PENDING", "Pending"), "RESOLVED": ("RESOLVED", "Resolved"),
                 "CLOSED": ("CLOSED", "Closed")},
    "WOSTATUS": {"WCONT": ("WAPPR", "Waiting for a contract"), "SCHED": ("WSCH", "Scheduled"),
                 "INPRG": ("INPRG", "In progress"), "COMP": ("COMP", "Completed"),
                 "CLOSE": ("CLOSE", "Closed"), "CAN": ("CAN", "Canceled")},
}
WORK_TYPE_DESCRIPTIONS = {"CM": "Corrective maintenance", "CS": "Customer service",
                          "IN": "Inspection", "CP": "Planned capital work"}
WORK_TYPE_STRUCTURES = ("mxapiworktype", "mxworktype")
FAILURE_STRUCTURES = ("mxapifailurelist", "mxfailurelist", "mxapifailurecode", "mxfailurecode")


# -- data from the generated dataset --------------------------------------------------
def read_csv(name: str) -> list[dict]:
    with (DATA_DIR / "maximo" / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def team_members(wo_rows: list[dict]) -> dict[str, list[str]]:
    """Each person group's supervisor(s) then leads, in order of first appearance on a WO."""
    sups, leads = defaultdict(list), defaultdict(list)
    for row in wo_rows:
        group = row["PERSONGROUP"]
        for bucket, person in ((sups, row["SUPERVISOR"]), (leads, row["LEAD"])):
            if group and person and person not in bucket[group]:
                bucket[group].append(person)
    return {g: sups[g] + [p for p in leads[g] if p not in sups[g]] for g in cat.PERSON_GROUPS}


def job_plan_defaults(wo_rows: list[dict]) -> dict[str, tuple[str, str]]:
    """The supervisor and lead most often on WOs with each job plan."""
    sups, leads = defaultdict(Counter), defaultdict(Counter)
    for row in wo_rows:
        if row["JPNUM"]:
            sups[row["JPNUM"]][row["SUPERVISOR"]] += 1
            leads[row["JPNUM"]][row["LEAD"]] += 1
    first = lambda c: c.most_common(1)[0][0] if c else ""  # noqa: E731
    return {jp: (first(sups[jp]), first(leads[jp])) for jp in cat.JOB_PLANS}


def failure_hierarchy(wo_rows: list[dict]) -> dict[str, list[str]]:
    """Failure class -> problem codes, from the request type catalog and the WOs."""
    pairs = [(rt["failure"], rt["problem"]) for rt in cat.REQUEST_TYPES.values()]
    pairs += [(r["FAILURECODE"], r["PROBLEMCODE"]) for r in wo_rows]
    tree: dict[str, list[str]] = {}
    for failure, problem in pairs:
        if failure and problem and problem not in tree.setdefault(failure, []):
            tree[failure].append(problem)
    return tree


# -- payload builders (pure, tested without HTTP) ---------------------------------------
def org_payload(itemsetid: str, companysetid: str, currency: str) -> JsonDict:
    return {"orgid": ORGID, "description": "Sarasota County pilot (synthetic data)", "basecurrency1": currency,
            "itemsetid": itemsetid, "companysetid": companysetid, "dfltitemstatus": "PENDING"}


def site_payload() -> JsonDict:
    return {"site": [{"siteid": SITEID, "description": "Sarasota County pilot site", "active": True}]}


PERSON_FIELDS = {"personid": "PERSONID", "displayname": "DISPLAYNAME", "firstname": "FIRSTNAME",
                 "lastname": "LASTNAME", "title": "TITLE", "department": "DEPARTMENT", "status": "STATUS",
                 "primaryemail": "PRIMARYEMAIL", "primaryphone": "PRIMARYPHONE"}


def person_payload(row: dict) -> JsonDict:
    return {attr: row[col] for attr, col in PERSON_FIELDS.items() if row.get(col)}


def person_group_payload(group: str, members: list[str]) -> JsonDict:
    payload: JsonDict = {"persongroup": maximo_team(group), "description": cat.PERSON_GROUPS[group][0]}
    if members:
        payload["persongroupteam"] = [{"respparty": p, "resppartyseq": i, "groupdefault": i == 1}
                                      for i, p in enumerate(members, start=1)]
    return payload


def classification_payload(classid: str) -> JsonDict:
    classificationid, description = cat.CLASSIFICATIONS[classid]
    return {"classificationid": classificationid, "description": description,
            # A top-level classification's hierarchy path is its own id (BMXAA5592E otherwise).
            "hierarchypath": classificationid,
            "classusewith": [{"objectname": "SR", "objectvalue": "SR"},
                             {"objectname": "WORKORDER", "objectvalue": "WORKORDER"}]}


def job_plan_payload(jpnum: str, supervisor: str, lead: str) -> JsonDict:
    description, group, _ = cat.JOB_PLANS[jpnum]
    payload: JsonDict = {"jpnum": jpnum, "description": description, "persongroup": maximo_team(group),
                         "orgid": ORGID, "siteid": SITEID}
    if supervisor:
        payload["supervisor"] = supervisor
    if lead:
        payload["lead"] = lead
    return payload


def work_type_payload(worktype: str) -> JsonDict:
    return {"worktype": worktype, "wtypedesc": WORK_TYPE_DESCRIPTIONS[worktype], "woclass": "WORKORDER",
            "orgid": ORGID}


def differences(existing: dict, payload: dict, fields) -> list[str]:
    """Fields whose existing value differs from ours (compared as text, case-insensitive)."""
    return [f for f in fields if f in payload and existing.get(f) is not None
            and str(existing[f]).strip().lower() != str(payload[f]).strip().lower()]


class Provisioner:
    def __init__(self, client: MaximoClient, settings: Settings, apply: bool = False,
                 log: Callable[[str], None] = print) -> None:
        self.client, self.settings, self.apply, self.log = client, settings, apply, log
        self.counts = Counter()
        self.manual: list[str] = []
        self.wo_rows = read_csv("wo.csv")
        self.org_href: str | None = None

    # -- reporting -----------------------------------------------------------------
    def _line(self, kind: str, what: str, detail: str = "") -> None:
        self.counts[kind] += 1
        self.log(f"  {kind:<8} {what}{f' - {detail}' if detail else ''}")

    def _exists(self, what: str, diff: list[str] | None = None) -> None:
        self._line("EXISTS", what, f"differs from our data: {', '.join(diff)} (left unchanged)" if diff else "")

    def _manual(self, what: str, detail: str) -> None:
        self.manual.append(f"{what}: {detail}")
        self._line("MANUAL", what, detail)

    # -- helpers -------------------------------------------------------------------
    def _find(self, structure: str, where: str, select: str) -> list[JsonDict]:
        return self.client.query(structure, where=where, select=select, page_size=50)

    def _create(self, structure: str, what: str, payload: JsonDict, detail: str = "") -> JsonDict | None:
        if not self.apply:
            self._line("PLAN", what, detail)
            return None
        try:
            created = self.client.create(structure, payload)
        except MaximoError as e:
            self._line("FAILED", what, str(e))
            return None
        self._line("CREATED", what, detail)
        return created

    def _available(self, candidates) -> str | None:
        return next((name for name in candidates if self.client.probe(name)[0]), None)

    # -- steps -----------------------------------------------------------------------
    def org(self) -> None:
        orgs = self._find("mxapiorganization", "", "orgid,active,itemsetid,companysetid,basecurrency1")
        ours = next((o for o in orgs if o.get("orgid") == ORGID), None)
        if ours:
            self.org_href = ours.get("href")
            wanted = {"itemsetid": self.settings.itemsetid} if self.settings.itemsetid else {}
            self._exists(f"organization {ORGID}", differences(ours, wanted, ("itemsetid",)))
            if not ours.get("active"):
                self._manual(f"organization {ORGID}", "inactive: set its clearing account in Organizations, "
                                                      "activate it, then re-run")
            return
        itemsetid = self.settings.itemsetid
        if not itemsetid:
            self._line("FAILED", f"organization {ORGID}", "set MAXIMO_ITEMSETID in .env (run inventory to see "
                                                          "the item sets in use)")
            return
        # Company set and currency come from an org that shares the item set. A new item set
        # (made in the Sets application) has no such org yet, so fall back to an active USD org.
        sibling = (next((o for o in orgs if o.get("itemsetid") == itemsetid), None)
                   or next((o for o in orgs if o.get("active") and o.get("basecurrency1") == "USD"
                            and o.get("companysetid")), None))
        if sibling is None:
            self._line("FAILED", f"organization {ORGID}", f"no existing org to copy a company set from for item "
                                                          f"set {itemsetid}")
            return
        payload = org_payload(itemsetid, sibling.get("companysetid") or "", sibling.get("basecurrency1") or "USD")
        if self._create("mxapiorganization", f"organization {ORGID}", payload,
                        f"item set {itemsetid}, company set {payload['companysetid']} "
                        f"(copied from {sibling.get('orgid')})") is not None:
            found = self._find("mxapiorganization", f'orgid="{ORGID}"', "orgid")
            self.org_href = found[0].get("href") if found else None
            self._manual(f"organization {ORGID}", "created inactive: set its clearing account in Organizations, "
                                                  "activate it, then re-run")

    def site(self) -> None:
        found = self._find("mxapisite", f'siteid="{SITEID}"', "siteid,orgid,active")
        if found:
            org = found[0].get("orgid")
            if org != ORGID:
                self._line("FAILED", f"site {SITEID}", f"exists under org {org}, not {ORGID}")
            else:
                self._exists(f"site {SITEID}")
            return
        if self.org_href is None:
            found = self._find("mxapiorganization", f'orgid="{ORGID}"', "orgid")
            self.org_href = found[0].get("href") if found else None
        if not self.apply:
            self._line("PLAN", f"site {SITEID}", f"as a child of organization {ORGID}")
            return
        if self.org_href is None:
            self._line("FAILED", f"site {SITEID}", f"organization {ORGID} not found")
            return
        # A site cannot be posted on its own (BMXAA3917E); it is a child of its organization.
        try:
            self.client.merge(self.org_href, site_payload())
            self._line("CREATED", f"site {SITEID}")
            self._manual(f"site {SITEID}", "in Security Groups, give the API key user's group access to this site; "
                                           "until then Maximo refuses every SR and WO for it")
        except MaximoError as e:
            self._line("FAILED", f"site {SITEID}", str(e))

    def persons(self) -> None:
        rows = read_csv("person.csv")
        ids = [r["PERSONID"] for r in rows]
        existing = {p.get("personid"): p for p in self._find(
            "mxapiperson", f"personid in {quote_list(ids)}", ",".join(PERSON_FIELDS))}
        for row in rows:
            payload = person_payload(row)
            what = f"person {row['PERSONID']}"
            if row["PERSONID"] in existing:
                self._exists(what, differences(existing[row["PERSONID"]], payload,
                                               ("displayname", "status", "title")))
            else:
                self._create("mxapiperson", what, payload, row["DISPLAYNAME"])

    def person_groups(self) -> None:
        members = team_members(self.wo_rows)
        groups = list(cat.PERSON_GROUPS)
        existing = {g.get("persongroup") for g in self._find(
            "mxapipersongroup", f"persongroup in {quote_list([maximo_team(g) for g in groups])}", "persongroup")}
        for group in groups:
            ours = maximo_team(group)
            what = f"person group {ours}" + (f" (dataset {group})" if ours != group else "")
            if ours in existing:
                self._exists(what)
            else:
                self._create("mxapipersongroup", what, person_group_payload(group, members[group]),
                             f"{len(members[group])} members")

    def statuses(self) -> None:
        for domainid, values in STATUS_VALUES.items():
            found = self._find("mxapidomain", f'domainid="{domainid}"',
                               "domainid,length,synonymdomain{value,maxvalue}")
            if not found:
                self._line("FAILED", f"domain {domainid}", "not found")
                continue
            domain = found[0]
            synonyms = domain.get("synonymdomain") or []
            have = {s.get("value"): s.get("maxvalue") for s in synonyms}
            internal = {s.get("maxvalue") for s in synonyms}
            length = domain.get("length") if isinstance(domain.get("length"), int) else None
            additions = []
            for value, (maxvalue, description) in values.items():
                what = f"{domainid} value {value}"
                if value in have:
                    self._exists(what, [f"maps to {have[value]}, ours is {maxvalue}"] if have[value] != maxvalue
                                 else None)
                elif maxvalue not in internal:
                    self._line("FAILED", what, f"internal value {maxvalue} not in {domainid}; choose a mapping")
                elif length is not None and len(value) > length:
                    self._line("FAILED", what, f"longer than the domain's {length} characters")
                else:
                    # Scoped to our org: the domain is shared by every org on the instance.
                    additions.append((what, {"value": value, "maxvalue": maxvalue, "description": description,
                                             "defaults": False, "orgid": ORGID}))
            if not additions:
                continue
            if not self.apply:
                for what, a in additions:
                    self._line("PLAN", what, f"synonym of {a['maxvalue']}, for org {ORGID} only")
                continue
            try:
                self.client.merge(domain["href"], {"synonymdomain": [a for _, a in additions]})
                for what, a in additions:
                    self._line("CREATED", what, f"synonym of {a['maxvalue']}, for org {ORGID} only")
            except MaximoError as e:
                for what, _ in additions:
                    self._line("FAILED", what, str(e))

    def work_types(self) -> None:
        structure = self._available(WORK_TYPE_STRUCTURES)
        if structure is None:
            self._manual("work types", f"no work type object structure; in Organizations > {ORGID} > Work Order "
                                       f"Options > Work Type, check for {', '.join(cat.WORK_TYPES)} and add any missing")
            return
        existing = {w.get("worktype") for w in self._find(structure, f'orgid="{ORGID}"', "worktype,orgid")}
        for wt in cat.WORK_TYPES:
            what = f"work type {wt}"
            if wt in existing:
                self._exists(what)
            else:
                self._create(structure, what, work_type_payload(wt))

    def classifications(self) -> None:
        ids = [name for name, _ in cat.CLASSIFICATIONS.values()]
        existing = {c.get("classificationid"): c for c in self._find(
            "mxapiclassstructure", f"classificationid in {quote_list(ids)}", "classificationid,classstructureid")}
        for classid, (name, _) in cat.CLASSIFICATIONS.items():
            what = f"classification {name}"
            if name in existing:
                # Maximo numbers classifications itself; the load maps our ids by classification name.
                self._exists(what + f" (id {existing[name].get('classstructureid')})")
            else:
                self._create("mxapiclassstructure", what, classification_payload(classid), f"our id {classid}")

    def job_plans(self) -> None:
        defaults = job_plan_defaults(self.wo_rows)
        plans = list(cat.JOB_PLANS)
        found = self._find("mxapijobplan", f"jpnum in {quote_list(plans)}",
                           "jpnum,pluscrevnum,status,orgid,siteid,persongroup")
        for jpnum in plans:
            what = f"job plan {jpnum}"
            # A plan in our org or a global one (no org) is usable as it is; one in another org is not.
            usable = [r for r in found if r.get("jpnum") == jpnum and r.get("orgid") in (ORGID, None, "")]
            payload = job_plan_payload(jpnum, *defaults[jpnum])
            if usable:
                plan = next((r for r in usable if r.get("status") == "ACTIVE"), usable[0])
                self._exists(what + f" ({plan.get('orgid') or 'global'}, {plan.get('status')})",
                             differences(plan, payload, ("persongroup",)))
                if plan.get("status") != "ACTIVE":
                    # Not created by this run, so its status is not ours to change.
                    self._manual(what, f"exists as {plan.get('status')}; activate it in Job Plans if it should be used")
                continue
            created = self._create("mxapijobplan", what, payload, f"team {payload['persongroup']}, then ACTIVE")
            if created is not None:
                self._activate_job_plan(what, created)
            elif not self.apply:
                self._line("PLAN", what, "status DRAFT -> ACTIVE")

    def _activate_job_plan(self, what: str, record: JsonDict) -> None:
        """Only for a plan this run just created."""
        href = record.get("href")
        if not href:
            self._line("FAILED", what + " status", "no href to change status; activate it in Job Plans")
            return
        try:
            self.client.action(href, "changeStatus", {"status": "ACTIVE"})
            self._line("ACTIVATED", what)
        except MaximoError as e:
            self._line("FAILED", what + " status", str(e))

    def failure_codes(self) -> None:
        tree = failure_hierarchy(self.wo_rows)
        listing = "; ".join(f"{f} > {', '.join(p)}" for f, p in tree.items())
        structure = self._available(FAILURE_STRUCTURES)
        where = f"object structure {structure} exists, but its payload is unverified" if structure else \
            "no failure code object structure"
        # Writing a failure hierarchy blind risks half-built trees, so this stays a manual step
        # until the inventory shows the structure. The WO load drops the codes if they are absent.
        self._manual("failure codes", f"{where}; in Failure Codes for org {ORGID} add: {listing}")

    # -- driver --------------------------------------------------------------------
    def run(self, only: list[str] | None = None) -> int:
        self.log(f"Provisioning org {ORGID}, site {SITEID} ({'APPLY' if self.apply else 'dry run: nothing is written'})")
        for step in STEPS:
            if only and step not in only:
                continue
            self.log(f"{step.replace('_', ' ').capitalize()}:")
            try:
                getattr(self, step)()
            except MaximoError as e:
                self._line("FAILED", step, str(e))
        return self.summary()

    def summary(self) -> int:
        c = self.counts
        self.log(f"\nDone - created {c['CREATED']}, activated {c['ACTIVATED']}, planned {c['PLAN']}, "
                 f"existing {c['EXISTS']}, manual {c['MANUAL']}, failed {c['FAILED']}")
        if self.manual:
            self.log("Manual steps in the Maximo UI:")
            self.log("\n".join(f"  - {m}" for m in self.manual))
        return 1 if c["FAILED"] else 0
