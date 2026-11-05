import pytest

from loader import provision as prov
from loader.config import Settings, cat

SETTINGS = Settings(url="https://manage.example.test/maximo", api_key="k", itemsetid="SET1")


def _instance(**overrides):
    records = {
        "mxapiorganization": [{"orgid": "EAGLENA", "active": True, "itemsetid": "SET1", "companysetid": "COMPSET1",
                               "basecurrency1": "USD"}],
        "mxapisite": [{"siteid": "BEDFORD", "orgid": "EAGLENA", "active": True}],
        "mxapiperson": [],
        "mxapipersongroup": [],
        "mxapidomain": [
            {"domainid": "SRSTATUS", "length": 10, "synonymdomain": [{"value": v, "maxvalue": v} for v in
                                                                     ("NEW", "QUEUED", "INPROG", "PENDING",
                                                                      "RESOLVED", "CLOSED")]},
            {"domainid": "WOSTATUS", "length": 10, "synonymdomain": [{"value": v, "maxvalue": v} for v in
                                                                     ("WAPPR", "WSCH", "INPRG", "COMP", "CLOSE",
                                                                      "CAN")]},
        ],
        "mxapiclassstructure": [],
        "mxapijobplan": [],
    }
    records.update(overrides)
    return records


def _run(fake, apply, only=None):
    lines = []
    p = prov.Provisioner(fake.client(), SETTINGS, apply=apply, log=lines.append)
    return p, p.run(only), lines


# -- pure builders ----------------------------------------------------------------------
def test_team_members_put_supervisors_before_leads():
    rows = [{"PERSONGROUP": "WTRPIPE", "SUPERVISOR": "S1", "LEAD": "L1"},
            {"PERSONGROUP": "WTRPIPE", "SUPERVISOR": "S1", "LEAD": "L2"},
            {"PERSONGROUP": "", "SUPERVISOR": "S9", "LEAD": "L9"}]
    members = prov.team_members(rows)
    assert members["WTRPIPE"] == ["S1", "L1", "L2"]
    assert members["RECLAIM"] == []


def test_dataset_teams_and_job_plans_are_complete():
    rows = prov.read_csv("wo.csv")
    members = prov.team_members(rows)
    persons = {r["PERSONID"] for r in prov.read_csv("person.csv")}
    assert all(set(m) <= persons for m in members.values())
    defaults = prov.job_plan_defaults(rows)
    assert set(defaults) == set(cat.JOB_PLANS)
    tree = prov.failure_hierarchy(rows)
    assert "LEAKBROKEN" in tree["SERVLINE"] and set(tree) <= set(cat.FAILURE_CODES)
    assert {p for ps in tree.values() for p in ps} <= set(cat.PROBLEM_CODES)


def test_payloads():
    assert prov.org_payload("SET1", "COMPSET1", "USD")["itemsetid"] == "SET1"
    assert prov.site_payload() == {"site": [{"siteid": "SRQSITE", "description": "Sarasota County pilot site",
                                             "active": True}]}
    person = prov.person_payload({"PERSONID": "MWQSCINT", "DISPLAYNAME": "QAlert Integration", "FIRSTNAME": "",
                                  "STATUS": "ACTIVE", "PRIMARYEMAIL": "mxqscint@example.com"})
    assert person == {"personid": "MWQSCINT", "displayname": "QAlert Integration", "status": "ACTIVE",
                      "primaryemail": "mxqscint@example.com"}
    group = prov.person_group_payload("WTRPIPE", ["S1", "L1"])
    assert group["persongroupteam"][0] == {"respparty": "S1", "resppartyseq": 1, "groupdefault": True}
    assert "persongroupteam" not in prov.person_group_payload("RECLAIM", [])
    cls = prov.classification_payload("9101")
    assert cls["classificationid"] == "WATER-LEAK" and cls["hierarchypath"] == "WATER-LEAK"
    assert {u["objectname"] for u in cls["classusewith"]} == {"SR", "WORKORDER"}
    jp = prov.job_plan_payload("SAN INSP", "0830581", "0831893")
    assert jp["persongroup"] == "SANCLINS" and jp["orgid"] == "SRQ" and jp["siteid"] == "SRQSITE"


# -- runs against the fake --------------------------------------------------------------
def test_dry_run_plans_everything_and_writes_nothing(fake_maximo):
    fake = fake_maximo(_instance())
    p, code, lines = _run(fake, apply=False)
    assert fake.writes() == []
    assert code == 0 and p.counts["CREATED"] == 0
    planned = [line for line in lines if "PLAN" in line]
    assert any("organization SRQ" in line for line in planned)
    assert sum("person " in line and "group" not in line for line in planned) == 18
    assert any("WOSTATUS value WCONT - synonym of WAPPR" in line for line in planned)
    assert any("SRSTATUS value INPRG - synonym of INPROG" in line for line in planned)
    assert p.counts["MANUAL"] == 2  # work types and failure codes: no object structure on this instance


def test_apply_then_rerun_creates_nothing_new(fake_maximo):
    fake = fake_maximo(_instance())
    p, code, _ = _run(fake, apply=True)
    assert code == 0, p.counts
    assert len(fake.records["mxapiperson"]) == 18
    assert len(fake.records["mxapipersongroup"]) == len(cat.PERSON_GROUPS)
    assert len(fake.records["mxapiclassstructure"]) == len(cat.CLASSIFICATIONS)
    assert all(j["status"] == "ACTIVE" for j in fake.records["mxapijobplan"])
    org = next(o for o in fake.records["mxapiorganization"] if o["orgid"] == "SRQ")
    assert org["site"][0]["siteid"] == "SRQSITE"
    wostatus = next(d for d in fake.records["mxapidomain"] if d["domainid"] == "WOSTATUS")
    assert {"value": "SCHED", "maxvalue": "WSCH", "description": "Scheduled", "defaults": False,
            "orgid": "SRQ"} in wostatus["synonymdomain"]

    # Maximo would list the new site; the fake keeps it as a child, so mirror it for the re-run.
    fake.records["mxapisite"].append({"href": "x", "siteid": "SRQSITE", "orgid": "SRQ", "active": True})
    org["active"] = True
    writes_before = len(fake.writes())
    p2, code2, _ = _run(fake, apply=True)
    assert code2 == 0 and p2.counts["CREATED"] == 0 and p2.counts["FAILED"] == 0
    assert len(fake.writes()) == writes_before


def test_existing_records_are_reported_not_changed(fake_maximo):
    fake = fake_maximo(_instance(mxapiperson=[{"personid": "0830144", "displayname": "Someone Else",
                                               "status": "ACTIVE"}]))
    _, _, lines = _run(fake, apply=True, only=["persons"])
    line = next(line for line in lines if "person 0830144" in line)
    assert "EXISTS" in line and "differs from our data: displayname" in line
    assert fake.records["mxapiperson"][0]["displayname"] == "Someone Else"


def test_refused_write_is_counted_and_exit_code_is_nonzero(fake_maximo):
    fake = fake_maximo(_instance(), refuse={"mxapipersongroup"})
    p, code, lines = _run(fake, apply=True, only=["person_groups"])
    assert code == 1 and p.counts["FAILED"] == len(cat.PERSON_GROUPS)
    assert any("BMXAA4195E" in line for line in lines)


def test_unmappable_status_fails_instead_of_guessing(fake_maximo):
    records = _instance()
    records["mxapidomain"][1]["synonymdomain"] = [{"value": "INPRG", "maxvalue": "INPRG"}]
    _, code, lines = _run(fake_maximo(records), apply=False, only=["statuses"])
    assert code == 1
    assert any("WOSTATUS value WCONT" in line and "choose a mapping" in line for line in lines)


def test_org_needs_an_item_set(fake_maximo):
    fake = fake_maximo(_instance())
    lines = []
    p = prov.Provisioner(fake.client(), Settings(url="u", api_key="k"), apply=True, log=lines.append)
    assert p.run(["org"]) == 1
    assert any("MAXIMO_ITEMSETID" in line for line in lines) and fake.writes() == []


def test_new_item_set_copies_company_set_from_an_active_usd_org(fake_maximo):
    fake = fake_maximo(_instance(mxapiorganization=[
        {"orgid": "EAGLESA", "active": True, "itemsetid": "SET2", "companysetid": "COMPSET1", "basecurrency1": "PESO"},
        {"orgid": "EAGLENA", "active": True, "itemsetid": "SET1", "companysetid": "COMPSET1", "basecurrency1": "USD"},
    ]))
    lines = []
    p = prov.Provisioner(fake.client(), Settings(url="u", api_key="k", itemsetid="SRQSET"), apply=True,
                         log=lines.append)
    assert p.run(["org"]) == 0
    org = next(o for o in fake.records["mxapiorganization"] if o["orgid"] == "SRQ")
    assert (org["itemsetid"], org["companysetid"], org["basecurrency1"]) == ("SRQSET", "COMPSET1", "USD")
    assert any("copied from EAGLENA" in line for line in lines)


def test_cli_rejects_unknown_steps():
    from loader.__main__ import main
    with pytest.raises(SystemExit):
        main(["provision", "--only", "persons,bogus"])


def test_job_plans_we_did_not_create_are_never_activated(fake_maximo):
    fake = fake_maximo(_instance(mxapijobplan=[{"jpnum": "LEAK", "status": "INACTIVE", "orgid": None,
                                                "persongroup": "WTRPIPE"}]))
    p, code, lines = _run(fake, apply=True, only=["job_plans"])
    leak = next(j for j in fake.records["mxapijobplan"] if j["jpnum"] == "LEAK")
    assert leak["status"] == "INACTIVE" and any("job plan LEAK" in m for m in p.manual)
    assert p.counts["ACTIVATED"] == len(cat.JOB_PLANS) - 1 and code == 0


def test_status_value_with_another_mapping_is_reported(fake_maximo):
    records = _instance()
    records["mxapidomain"][1]["synonymdomain"].append({"value": "SCHED", "maxvalue": "APPR"})
    _, _, lines = _run(fake_maximo(records), apply=False, only=["statuses"])
    assert any("WOSTATUS value SCHED" in line and "maps to APPR, ours is WSCH" in line for line in lines)


def test_new_site_gets_a_security_group_reminder(fake_maximo):
    p, _, _ = _run(fake_maximo(_instance()), apply=True, only=["org", "site"])
    assert any("Security Groups" in m for m in p.manual)
