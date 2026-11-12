"""Harvesting WOSIMILARITY results into the AI results sheet, with no network."""

import sys
from pathlib import Path

import pytest
from conftest import BASE, API_KEY, FakeResponse, FakeSession

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import harvest_similar_work_orders as hv  # noqa: E402
from loader.client import MaximoClient  # noqa: E402

CHECKED = 134519  # WO2915021


def row(ticket, feature="similar_wo", **extra):
    return {"TICKETID": ticket, "FEATURE": feature, "AI_VALUE": "", "AI_SCORE": "",
            "REVIEWER_DECISION": "", "OVERRIDE_REASON": "", **extra}


def wo(wonum, sr, status):
    return {"WONUM": wonum, "ORIGRECORDID": sr, "STATUS": status}


def test_the_draft_is_chosen_before_any_follow_up():
    choose = hv.wo_to_open([wo("WO2910007", "SR810036", "INPRG"), wo("WO2915021", "SR810036", "WAPPR")])
    assert choose == {"SR810036": "WO2915021"}


def test_an_open_follow_up_is_chosen_before_a_closed_one_and_cancelled_never():
    choose = hv.wo_to_open([wo("WO2910002", "SR1", "CLOSE"), wo("WO2910009", "SR1", "COMP"),
                            wo("WO2910003", "SR2", "CLOSE"), wo("WO2910004", "SR3", "CAN"), wo("WO2910005", "", "WAPPR")])
    assert choose == {"SR1": "WO2910009", "SR2": "WO2910003"}


def test_a_row_lists_the_similar_wos_by_score_without_the_checked_wo():
    out = hv.as_row(row("SR810036", REVIEWER_DECISION="accept", OVERRIDE_REASON="kept"), "WO2915021",
                    {"WO2910012": 88, "WO2910007": 91, "WO2915021": 100, "WO2910003": 88, "WO2910020": None})
    assert out["AI_VALUE"] == "WO2910007;WO2910003;WO2910012;WO2910020"
    assert out["AI_SCORE"] == "91"
    assert (out["REVIEWER_DECISION"], out["OVERRIDE_REASON"]) == ("accept", "kept")


def test_no_match_is_none_and_no_work_order_is_not_available():
    assert hv.as_row(row("SR1"), "WO1", {"WO1": 99})["AI_VALUE"] == "none"
    assert hv.as_row(row("SR1"), None, None)["AI_VALUE"] == "n/a"


class FakeWoSimilarity:
    """The two reads and the refresh the harvest uses, answered from `similar` (checked id -> {found id: score})."""

    def __init__(self, similar, wonums, fail_on=(), fail_post=False):
        self.similar, self.wonums, self.fail_on, self.fail_post = similar, wonums, set(fail_on), fail_post
        self.session = FakeSession(self.handle)

    def client(self):
        return MaximoClient(BASE, API_KEY, session=self.session)

    def posts(self):
        return [c for c in self.session.calls if c[0] == "POST"]

    def handle(self, method, url, params, headers, payload):
        if method == "POST":
            assert url.endswith("/api/aicfg_wosimilarity") and payload["usecache"] is False
            if self.fail_post:
                return FakeResponse(400, {"Error": {"reasonCode": "BMXAA10138E", "message": "model not ready"}}, url=url)
            return FakeResponse(body={"predictions": []}, url=url)
        if params.get("savedQuery") == "similarObjects":
            checked = int(params["sqp:objectId"])
            if checked in self.fail_on:
                return FakeResponse(500, {"Error": {"reasonCode": "BMXAA1649E", "message": "null pointer"}}, url=url)
            members = [{"wonum": self.wonums[f], "workorderid": f} for f in self.similar.get(checked, {})]
            return FakeResponse(body={"member": members}, url=url)
        # workorderid in [1,2]: each found WO with its pairs, keyed by the WO that found it.
        assert '"' not in params["oslc.where"], "Maximo refuses quoted workorderid values"
        ids = [int(x) for x in params["oslc.where"].split("[")[1].rstrip("]").split(",")]
        members = [{"workorderid": f, "maxaisimilarwo": [
            {"objectid": c, "score": s, "aicfgname": "WOSIMILARITY"}
            for c, found in self.similar.items() for ff, s in found.items() if ff == f]
            + [{"objectid": 1, "score": 99, "aicfgname": "OTHER"}]} for f in ids]
        return FakeResponse(body={"member": members}, url=url)


def run(fake, rows, refresh=False, only=None):
    lookup = {"WO2915021": (CHECKED, f"{BASE}/api/os/mxapiwodetail/_a", "WO2915021"),
              "WO2915099": (777, f"{BASE}/api/os/mxapiwodetail/_b", "WO2915099")}
    choose = {"SR810036": "WO2915021", "SR810099": "WO2915099", "SR810050": "WO2919999"}
    errors = []
    out, failed = hv.harvest(rows, choose, lookup, hv.SimilarWorkOrders(fake.client()), refresh=refresh,
                             only=only, report=errors.append)
    assert failed == len(errors)
    return out, errors


def test_a_read_only_run_sends_no_post_and_reads_the_score_for_the_checked_wo():
    fake = FakeWoSimilarity({CHECKED: {201: 91, 202: 87}, 555: {201: 40}}, {201: "WO2910007", 202: "WO2910012"})
    out, errors = run(fake, [row("SR810036")])
    assert fake.posts() == [] and errors == []
    assert (out[0]["AI_VALUE"], out[0]["AI_SCORE"]) == ("WO2910007;WO2910012", "91")


def test_refresh_posts_once_per_work_order_asked_about():
    fake = FakeWoSimilarity({CHECKED: {201: 91}}, {201: "WO2910007"})
    run(fake, [row("SR810036"), row("SR810050"), row("SR810036", feature="team")], refresh=True)
    assert [c[4]["href"] for c in fake.posts()] == [f"{BASE}/api/os/mxapiwodetail/_a"]


def test_other_features_and_rows_outside_only_are_left_as_they_were():
    fake = FakeWoSimilarity({CHECKED: {201: 91}}, {201: "WO2910007"})
    rows = [row("SR810036", feature="classification", AI_VALUE="WATER-LEAK"), row("SR810036"),
            row("SR810099", AI_VALUE="kept")]
    out, _ = run(fake, rows, only={"SR810036"})
    assert out[0] == rows[0] and out[2] == rows[2]
    assert out[1]["AI_VALUE"] == "WO2910007"


def test_a_failed_or_missing_work_order_is_reported_and_its_row_kept():
    fake = FakeWoSimilarity({}, {}, fail_on={777})
    rows = [row("SR810099", AI_VALUE="WO1", AI_SCORE="90"), row("SR810050", AI_VALUE="WO2", AI_SCORE="88"),
            row("SR810001", AI_VALUE="old")]
    out, errors = run(fake, rows)
    assert out[:2] == rows[:2]
    assert len(errors) == 2 and "SR810099" in errors[0] and "SR810050" in errors[1]
    assert out[2]["AI_VALUE"] == "n/a"  # the SR has no WO at all


def test_a_failed_refresh_keeps_the_row():
    fake = FakeWoSimilarity({CHECKED: {201: 91}}, {201: "WO2910007"}, fail_post=True)
    rows = [row("SR810036", AI_VALUE="WO1", AI_SCORE="90")]
    out, errors = run(fake, rows, refresh=True)
    assert out == rows and len(errors) == 1


def test_a_renumbered_wo_is_found_by_our_number_and_left_out_of_its_own_list():
    fake = FakeWoSimilarity({CHECKED: {CHECKED: 100, 201: 91}}, {CHECKED: "1042", 201: "1007"})
    lookup = {"WO2915021": (CHECKED, f"{BASE}/api/os/mxapiwodetail/_a", "1042")}
    out, failed = hv.harvest([row("SR810036")], {"SR810036": "WO2915021"}, lookup,
                             hv.SimilarWorkOrders(fake.client()))
    assert failed == 0 and out[0]["AI_VALUE"] == "1007"


def test_main_writes_only_with_write_and_exits_1_on_a_failure(tmp_path, monkeypatch):
    sheet = tmp_path / "ai-results.csv"
    sheet.write_text("\ufeffTICKETID,FEATURE,AI_VALUE,AI_SCORE,REVIEWER_DECISION,OVERRIDE_REASON\r\n"
                     "SR810036,similar_wo,,,,\r\nSR810099,similar_wo,old,90,accept,\r\n", encoding="utf-8")
    fake = FakeWoSimilarity({CHECKED: {201: 91}}, {201: "WO2910007"}, fail_on={777})
    pilot = [{"wonum": "WO2915021", "workorderid": CHECKED, "externalrefid": "WO2915021", "href": f"{BASE}/a"},
             {"wonum": "WO2915099", "workorderid": 777, "externalrefid": "WO2915099", "href": f"{BASE}/b"}]
    client = fake.client()
    client.query = lambda structure, where=None, select="*", page_size=200, limit=None: (
        pilot if where == hv.PILOT_WHERE else MaximoClient.query(client, structure, where, select, page_size, limit))
    monkeypatch.setattr(hv, "MaximoClient", lambda *a, **k: client)
    monkeypatch.setattr(hv, "load_settings", lambda: type("S", (), {"url": BASE, "api_key": API_KEY,
                                                                     "api_path": "api", "verify_tls": True})())
    monkeypatch.setattr(hv, "wo_to_open", lambda wos: {"SR810036": "WO2915021", "SR810099": "WO2915099"})
    before = sheet.read_bytes()
    assert hv.main(["--results", str(sheet)]) == 1
    assert sheet.read_bytes() == before
    assert hv.main(["--results", str(sheet), "--write"]) == 1
    lines = sheet.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "TICKETID,FEATURE,AI_VALUE,AI_SCORE,REVIEWER_DECISION,OVERRIDE_REASON"
    assert lines[1] == "SR810036,similar_wo,WO2910007,91,," and lines[2] == "SR810099,similar_wo,old,90,accept,"


def test_nearby_rows_keep_the_given_order_and_have_no_score():
    out = hv.as_row(row("SR810036", feature="nearby_wo"), "WO2915021",
                    {"WO2910012": "2026-07-17", "WO2915021": None, "WO2910007": "2026-02-16"}, by_score=False)
    assert (out["AI_VALUE"], out["AI_SCORE"]) == ("WO2910012;WO2910007", "")
    assert hv.as_row(row("SR1", feature="nearby_wo"), "WO1", {}, by_score=False)["AI_VALUE"] == "none"


class FakeNearby:
    """The NEARBYWO relationship on one WO, answered from `near` (workorderid -> [(wonum, reportdate)])."""

    def __init__(self, near):
        self.near = near
        self.session = FakeSession(self.handle)

    def handle(self, method, url, params, headers, payload):
        assert method == "GET" and params["oslc.select"] == "workorderid,rel.nearbywo{wonum,reportdate}"
        wid = int(params["oslc.where"].split("=")[1])
        if wid not in self.near:
            return FakeResponse(body={"member": []}, url=url)
        return FakeResponse(body={"member": [{"workorderid": wid, "nearbywo": [
            {"wonum": w, "reportdate": d} for w, d in self.near[wid]]}]}, url=url)


def test_nearby_harvest_fills_only_nearby_rows_newest_first_and_cannot_refresh():
    fake = FakeNearby({CHECKED: [("WO2910007", "2026-02-16T15:44:00-05:00"), ("WO2910012", "2026-07-17T14:23:00-05:00")],
                       777: []})
    maximo = hv.NearbyWorkOrders(MaximoClient(BASE, API_KEY, session=fake.session))
    rows = [row("SR810036"), row("SR810036", feature="nearby_wo"), row("SR810099", feature="nearby_wo")]
    lookup = {"WO2915021": (CHECKED, "h", "WO2915021"), "WO2915099": (777, "h2", "WO2915099")}
    out, failed = hv.harvest(rows, {"SR810036": "WO2915021", "SR810099": "WO2915099"}, lookup, maximo)
    assert failed == 0 and out[0] == rows[0]
    assert out[1]["AI_VALUE"] == "WO2910012;WO2910007" and out[2]["AI_VALUE"] == "none"
    errors = []
    out, failed = hv.harvest(rows, {"SR810036": "WO2915021"}, lookup, maximo, refresh=True, report=errors.append)
    assert failed == 1 and out[1] == rows[1] and "nothing to refresh" in errors[0]


def test_main_refuses_refresh_for_nearby_work(capsys):
    with pytest.raises(SystemExit):
        hv.main(["--feature", "nearby_wo", "--refresh"])
    assert "--refresh applies to similar_wo only" in capsys.readouterr().err
