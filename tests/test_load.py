import csv

from loader.config import cat
from loader.load import Dataset, Loader, write_answer_key
from loader.manifest import Manifest
from loader.verify import Verifier

DATA = Dataset()


def _instance():
    return {
        "mxapisr": [], "mxapiwodetail": [],
        "mxapiclassstructure": [{"classificationid": name, "classstructureid": 7000 + i}
                                for i, (name, _) in enumerate(cat.CLASSIFICATIONS.values())],
    }


def _load(fake, tmp_path, apply=True, **kw):
    lines = []
    loader = Loader(fake.client(), Manifest(tmp_path / "manifest.json"), DATA, apply=apply, log=lines.append,
                    state_dir=tmp_path)
    return loader, loader.run(**kw), lines


def test_dry_run_writes_nothing(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    loader, code, lines = _load(fake, tmp_path, apply=False)
    assert code == 0 and fake.writes() == []
    assert loader.counts["sr"]["PLAN"] == 60 and loader.counts["wo"]["PLAN"] == 41
    assert loader.counts["worklog"]["PLAN"] == len(DATA.worklogs)
    assert any("FAILURECODE: dropped for this run" in line for line in lines)
    assert not (tmp_path / "manifest.json").exists()


def test_full_load_then_rerun_creates_nothing(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _, code, _ = _load(fake, tmp_path)
    assert code == 0
    assert len(fake.records["mxapisr"]) == 60 and len(fake.records["mxapiwodetail"]) == 41
    assert sum(len(r.get("worklog", [])) for k in ("mxapisr", "mxapiwodetail") for r in fake.records[k]) == len(DATA.worklogs)
    final = {r["TICKETID"]: r["STATUS"] for r in DATA.srs} | {r["WONUM"]: r["STATUS"] for r in DATA.wos}
    assert all(r["status"] == final[r["ticketid"]] for r in fake.records["mxapisr"])
    assert all(r["status"] == final[r["wonum"]] for r in fake.records["mxapiwodetail"])
    assert all(r["classstructureid"].startswith("70") for r in fake.records["mxapisr"])

    writes = len(fake.writes())
    again, code2, _ = _load(fake, tmp_path)
    assert code2 == 0 and len(fake.writes()) == writes
    assert all(again.counts[k]["CREATED"] == 0 for k in ("sr", "wo", "worklog", "status"))

    # Lost manifest: natural keys still find every record, and nothing is posted again.
    (tmp_path / "manifest.json").unlink()
    third, code3, _ = _load(fake, tmp_path)
    assert code3 == 0 and len(fake.writes()) == writes
    assert third.counts["sr"]["EXISTS"] == 60 and third.counts["worklog"]["EXISTS"] == len(DATA.worklogs)


def test_renumbered_keys_are_remapped(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), renumber=True)
    _, code, _ = _load(fake, tmp_path, only=["SR800008"])
    assert code == 0
    sr, = fake.records["mxapisr"]
    wo, = fake.records["mxapiwodetail"]
    assert sr["ticketid"] != "SR800008" and wo["origrecordid"] == sr["ticketid"]
    assert wo["externalrefid"] == "WO2900014"
    key = write_answer_key(DATA, _remap_from(tmp_path), tmp_path / "answer-key-maximo.csv")
    rows = list(csv.DictReader(key.open()))
    assert sr["ticketid"] in {r["TICKETID"] for r in rows} and "SR800008" not in {r["TICKETID"] for r in rows}


def _remap_from(tmp_path):
    from loader.mapping import Remap
    m = Manifest(tmp_path / "manifest.json")
    return Remap(tickets={e["our_id"]: e["maximo_id"] for e in m.of_kind("sr")},
                 wonums={e["our_id"]: e["maximo_id"] for e in m.of_kind("wo")})


def test_failure_mid_run_resumes_cleanly(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), refuse={"mxapiwodetail"})
    loader, code, _ = _load(fake, tmp_path, limit=10)
    assert code == 1 and loader.counts["wo"]["FAILED"] > 0
    assert len(fake.records["mxapisr"]) == 10 and fake.records["mxapiwodetail"] == []

    fake.refuse.clear()
    again, code2, _ = _load(fake, tmp_path, limit=10)
    assert code2 == 0 and again.counts["sr"]["CREATED"] == 0
    assert len(fake.records["mxapisr"]) == 10
    assert len(fake.records["mxapiwodetail"]) == again.counts["wo"]["CREATED"] > 0


def test_a_wo_number_taken_by_someone_else_is_left_alone(fake_maximo, tmp_path):
    records = _instance()
    records["mxapiwodetail"] = [{"wonum": "WO2900014", "siteid": "SRQSITE", "externalrefid": "OTHER-1"}]
    fake = fake_maximo(records)
    _, code, lines = _load(fake, tmp_path, only=["SR800008"])
    assert code == 1 and any("already exists with external ref OTHER-1" in line for line in lines)
    assert fake.records["mxapiwodetail"][0] == {"href": fake.records["mxapiwodetail"][0]["href"], "wonum": "WO2900014",
                                                "siteid": "SRQSITE", "externalrefid": "OTHER-1"}


def test_refused_historical_status_date_falls_back_and_is_reported(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), refuse_dated_status=True)
    loader, code, lines = _load(fake, tmp_path, only=["SR800008"])
    assert code == 0 and loader.limitations
    assert any("historical date refused" in line for line in lines)


def test_verify_matches_after_load_and_flags_a_changed_field(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR800008", "SR800001"])
    lines = []
    manifest = Manifest(tmp_path / "manifest.json")
    verifier = Verifier(fake.client(), manifest, DATA, drop=("FAILURECODE", "PROBLEMCODE"), log=lines.append)
    assert verifier.run(only=["SR800008", "SR800001"]) == 0, "\n".join(lines)
    assert verifier.ok == 3

    fake.records["mxapisr"][0]["description"] = "changed by hand"
    lines.clear()
    verifier = Verifier(fake.client(), manifest, DATA, drop=("FAILURECODE", "PROBLEMCODE"), log=lines.append)
    assert verifier.run(only=["SR800008", "SR800001"]) == 1
    assert any("description: expected" in line for line in lines)


def test_verify_reports_records_never_loaded(fake_maximo, tmp_path):
    lines = []
    verifier = Verifier(fake_maximo(_instance()).client(), Manifest(tmp_path / "m.json"), DATA, log=lines.append)
    assert verifier.run(only=["SR800001"]) == 1 and verifier.missing == 1


def test_a_wo_number_with_a_blank_ref_is_not_adopted(fake_maximo, tmp_path):
    records = _instance()
    records["mxapiwodetail"] = [{"wonum": "WO2900014", "siteid": "SRQSITE", "status": "WAPPR"}]
    fake = fake_maximo(records)
    _, code, lines = _load(fake, tmp_path, only=["SR800008"])
    assert code == 1 and any("external ref (blank), so it is not ours" in line for line in lines)
    wo = fake.records["mxapiwodetail"][0]
    assert wo["status"] == "WAPPR" and "worklog" not in wo


def test_a_wo_is_never_linked_to_an_sr_that_failed(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), refuse={"mxapisr"})
    loader, code, lines = _load(fake, tmp_path, only=["SR800008"])
    assert code == 1 and fake.records["mxapiwodetail"] == []
    assert any("ORIGRECORDID SR800008 is not loaded yet" in line for line in lines)


def test_a_status_change_whose_answer_was_lost_is_not_retried_forever(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), lose_status_answers=1)
    loader, code, _ = _load(fake, tmp_path, only=["SR800008"])
    assert code == 0, loader.counts
    sr, = fake.records["mxapisr"]
    assert sr["status"] == "RESOLVED" and not loader.limitations
    again, code2, _ = _load(fake, tmp_path, only=["SR800008"])
    assert code2 == 0 and again.counts["status"]["CREATED"] == 0


def test_a_record_with_no_href_is_looked_up_again(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR800001"])
    manifest = Manifest(tmp_path / "manifest.json")
    manifest.entries["sr:SR800001"]["href"] = None
    manifest.save()
    again, code, _ = _load(fake, tmp_path, only=["SR800001"])
    assert code == 0 and again.counts["sr"]["EXISTS"] == 1
    assert Manifest(tmp_path / "manifest.json").get("sr", "SR800001")["href"]


def test_dry_run_against_a_loaded_instance_writes_no_state(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR800008"])
    (tmp_path / "manifest.json").unlink()
    _, code, _ = _load(fake, tmp_path, apply=False)
    assert code == 0 and not (tmp_path / "manifest.json").exists()


def test_manifest_from_another_instance_is_refused(tmp_path):
    import pytest
    Manifest(tmp_path / "m.json", instance="https://a.test/maximo").record("sr", "X", maximo_id="X", href="h")
    with pytest.raises(SystemExit, match="was made against https://a.test/maximo"):
        Manifest(tmp_path / "m.json", instance="https://b.test/maximo")


def test_verify_accepts_renumbered_records(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), renumber=True)
    _load(fake, tmp_path, only=["SR800008"])
    lines = []
    verifier = Verifier(fake.client(), Manifest(tmp_path / "manifest.json"), DATA,
                        drop=("FAILURECODE", "PROBLEMCODE"), log=lines.append)
    assert verifier.run(only=["SR800008"]) == 0, "\n".join(lines)
