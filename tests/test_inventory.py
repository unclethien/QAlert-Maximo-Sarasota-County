import json

from conftest import API_KEY

from loader import inventory
from loader.config import cat


def _empty_instance():
    """A fresh instance: the standard structures, one unrelated org, nothing of ours."""
    return {
        "mxapiorganization": [{"orgid": "EAGLENA", "active": True, "itemsetid": "SET1", "companysetid": "COMPSET1",
                               "basecurrency1": "USD"}],
        "mxapisite": [{"siteid": "BEDFORD", "orgid": "EAGLENA", "active": True}],
        "mxapiperson": [{"personid": "WILSON", "status": "ACTIVE"}],
        "mxapipersongroup": [],
        "mxapidomain": [
            {"domainid": "SRSTATUS", "synonymdomain": [{"value": v, "maxvalue": v} for v in
                                                       ("NEW", "QUEUED", "INPRG", "PENDING", "RESOLVED", "CLOSED")]},
            {"domainid": "WOSTATUS", "synonymdomain": [{"value": v, "maxvalue": v} for v in
                                                       ("WAPPR", "WSCH", "INPRG", "COMP", "CLOSE", "CAN")]},
            {"domainid": "LOGTYPE", "alndomain": [{"value": "CLIENTNOTE"}]},
        ],
        "mxapiclassstructure": [],
        "mxapijobplan": [],
        "mxapisr": [],
        "mxapiwodetail": [],
        "mxapiseraddress": [],
    }


def test_inventory_on_an_empty_instance(fake_maximo):
    fake = fake_maximo(_empty_instance())
    report = inventory.run_inventory(fake.client())

    assert report["identity"]["status"] == "ok"
    assert all(report["structures"][s]["status"] == "ok" for s in inventory.REQUIRED_STRUCTURES)
    assert report["structures"]["mxapifailurelist"]["status"] == "missing"
    assert report["org_and_site"]["status"] == "missing" and report["org_and_site"]["org"] is None
    assert report["org_and_site"]["existing_orgs"][0]["itemsetid"] == "SET1"
    assert report["record_counts"] == {"status": "ok", "sr_at_site": 0, "wo_at_site": 0,
                                      "service_addresses_in_org": 0}
    assert report["domains"]["SRSTATUS"]["status"] == "ok"
    assert report["domains"]["WOSTATUS"]["missing"] == ["WCONT", "SCHED"]
    assert report["domains"]["LOGTYPE"]["missing"] == ["UPDATE"]  # what RESOLUTION is written as
    assert report["work_types"]["status"] == "unknown"
    refs = report["reference_data"]
    assert len(refs["persons"]["missing"]) == 18 and "MWQSCINT" in refs["persons"]["missing"]
    assert refs["job_plans"]["missing"] == list(cat.JOB_PLANS)
    assert fake.writes() == []  # inventory never writes


def test_inventory_spots_earlier_demo_data_and_our_org(fake_maximo):
    records = _empty_instance()
    records["mxapiorganization"].append({"orgid": "SRQ", "active": False, "itemsetid": "SET1"})
    records["mxapisite"].append({"siteid": "SRQSITE", "orgid": "SRQ", "active": True})
    records["mxapisr"] = [{"siteid": "SRQSITE", "externalrecid": "710001"}] * 3
    records["mxapiperson"].append({"personid": "MWQSCINT", "status": "ACTIVE"})
    report = inventory.run_inventory(fake_maximo(records).client())

    assert report["org_and_site"]["status"] == "ok"
    assert report["org_and_site"]["org"]["active"] is False
    assert report["record_counts"]["sr_at_site"] == 3
    assert "MWQSCINT" in report["reference_data"]["persons"]["found"]
    assert "SRQ" in inventory.summarize(report)


def test_one_refused_check_does_not_hide_the_rest(fake_maximo):
    records = _empty_instance()
    del records["mxapijobplan"]
    report = inventory.run_inventory(fake_maximo(records).client())
    assert report["structures"]["mxapijobplan"]["status"] == "error"
    assert "BMXAA9301E" in report["reference_data"]["job_plans"]["reason"]
    assert report["reference_data"]["persons"]["status"] == "missing"


def test_bad_route_stops_early_and_report_holds_no_key(fake_maximo, tmp_path):
    fake = fake_maximo({})
    fake.whoami = None
    from conftest import FakeResponse
    fake.session.handler = lambda *a: FakeResponse(200, text="<html>login</html>", content_type="text/html")
    report = inventory.run_inventory(fake.client())
    assert report["identity"]["status"] == "error" and "structures" not in report
    path = inventory.save_report(report, tmp_path)
    assert API_KEY not in path.read_text()
    assert json.loads(path.read_text())["identity"]["status"] == "error"
    assert "received HTML" in inventory.summarize(report)


def test_classifications_are_matched_by_name(fake_maximo):
    records = _empty_instance()
    records["mxapiclassstructure"] = [{"classificationid": name, "classstructureid": 9000 + i}
                                      for i, (name, _) in enumerate(cat.CLASSIFICATIONS.values())]
    report = inventory.run_inventory(fake_maximo(records).client())
    assert report["reference_data"]["classifications"]["status"] == "ok"
    assert report["sr_attributes"]["status"] == "ok"


def test_log_types_are_found_in_a_synonym_domain(fake_maximo):
    records = _empty_instance()
    for d in records["mxapidomain"]:
        if d["domainid"] == "LOGTYPE":
            d.pop("alndomain", None)
            d["synonymdomain"] = [{"value": "CLIENTNOTE", "maxvalue": "CLIENTNOTE"}, {"value": "UPDATE", "maxvalue": "UPDATE"}]
    report = inventory.run_inventory(fake_maximo(records).client())
    assert report["domains"]["LOGTYPE"]["status"] == "ok"
