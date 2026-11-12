import csv

from loader import mapping
from loader.config import cat
from loader.load import DEFAULT_DROP, Dataset, Loader, write_answer_key
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
    assert loader.counts["sr"]["PLAN"] == 65 and loader.counts["wo"]["PLAN"] == 41
    assert loader.counts["worklog"]["PLAN"] == len(DATA.worklogs)
    assert any("FAILURECODE: dropped for this run" in line for line in lines)
    assert not (tmp_path / "manifest.json").exists()


def test_full_load_then_rerun_creates_nothing(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _, code, _ = _load(fake, tmp_path)
    assert code == 0
    assert len(fake.records["mxapisr"]) == 65 and len(fake.records["mxapiwodetail"]) == 41
    assert sum(len(r.get("worklog", [])) for k in ("mxapisr", "mxapiwodetail") for r in fake.records[k]) == len(DATA.worklogs)
    final = {r["TICKETID"]: r["STATUS"] for r in DATA.srs} | {r["WONUM"]: r["STATUS"] for r in DATA.wos}
    assert all(r["status"] == mapping.maximo_status("sr", final[r["ticketid"]]) for r in fake.records["mxapisr"])
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
    assert third.counts["sr"]["EXISTS"] == 65 and third.counts["worklog"]["EXISTS"] == len(DATA.worklogs)


def test_renumbered_keys_are_remapped(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), renumber=True)
    _, code, _ = _load(fake, tmp_path, only=["SR810008"])
    assert code == 0
    sr, = fake.records["mxapisr"]
    wo, = fake.records["mxapiwodetail"]
    assert sr["ticketid"] != "SR810008" and wo["origrecordid"] == sr["ticketid"]
    assert wo["externalrefid"] == "WO2910014"
    key = write_answer_key(DATA, _remap_from(tmp_path), tmp_path / "answer-key-maximo.csv")
    rows = list(csv.DictReader(key.open()))
    assert sr["ticketid"] in {r["TICKETID"] for r in rows} and "SR810008" not in {r["TICKETID"] for r in rows}


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
    records["mxapiwodetail"] = [{"wonum": "WO2910014", "siteid": "SRQSITE", "externalrefid": "OTHER-1"}]
    fake = fake_maximo(records)
    _, code, lines = _load(fake, tmp_path, only=["SR810008"])
    assert code == 1 and any("already exists with external ref OTHER-1" in line for line in lines)
    assert fake.records["mxapiwodetail"][0] == {"href": fake.records["mxapiwodetail"][0]["href"], "wonum": "WO2910014",
                                                "siteid": "SRQSITE", "externalrefid": "OTHER-1"}


def test_refused_historical_status_date_falls_back_and_is_reported(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), refuse_dated_status=True)
    loader, code, lines = _load(fake, tmp_path, only=["SR810008"])
    assert code == 0 and loader.limitations
    assert any("historical date refused" in line for line in lines)


def test_verify_matches_after_load_and_flags_a_changed_field(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR810008", "SR810001"])
    lines = []
    manifest = Manifest(tmp_path / "manifest.json")
    verifier = Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append)
    assert verifier.run(only=["SR810008", "SR810001"]) == 0, "\n".join(lines)
    assert verifier.ok == 3

    fake.records["mxapisr"][0]["description"] = "changed by hand"
    lines.clear()
    verifier = Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append)
    assert verifier.run(only=["SR810008", "SR810001"]) == 1
    assert any("description: expected" in line for line in lines)


def test_verify_compares_the_service_address_without_case(fake_maximo, tmp_path):
    ticket = next(r["TICKETID"] for r in DATA.srs if r["SADDRESSCODE"])
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=[ticket])
    address = fake.records["mxapisr"][0][mapping.SR_ADDRESS_CHILD][0]
    address["city"] = address["city"].upper()  # as Maximo stores it
    lines = []
    manifest = Manifest(tmp_path / "manifest.json")
    assert Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append).run(only=[ticket]) == 0, lines
    address["staddrstreet"] = "Elsewhere Rd"
    lines.clear()
    assert Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append).run(only=[ticket]) == 1
    assert any("service address staddrstreet: expected" in line for line in lines)


def test_verify_reads_back_the_wo_service_address(fake_maximo, tmp_path):
    wo = next(w for w in DATA.wos if w["ORIGRECORDID"])
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=[wo["ORIGRECORDID"]])
    [loaded] = [r for r in fake.records["mxapiwodetail"] if r["externalrefid"] == wo["WONUM"]]
    [address] = loaded[mapping.WO_ADDRESS_CHILD]
    assert address["latitudey"] == float(wo["LATITUDEY"]) and "saddresscode" not in address
    lines = []
    manifest = Manifest(tmp_path / "manifest.json")
    assert Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append).run(
        only=[wo["ORIGRECORDID"]]) == 0, lines
    address["staddrstreet"] = "Elsewhere Rd"
    lines.clear()
    assert Verifier(fake.client(), manifest, DATA, drop=DEFAULT_DROP, log=lines.append).run(
        only=[wo["ORIGRECORDID"]]) == 1
    assert any("service address staddrstreet: expected" in line for line in lines)


def test_verify_reports_records_never_loaded(fake_maximo, tmp_path):
    lines = []
    verifier = Verifier(fake_maximo(_instance()).client(), Manifest(tmp_path / "m.json"), DATA, log=lines.append)
    assert verifier.run(only=["SR810001"]) == 1 and verifier.missing == 1


def test_a_wo_number_with_a_blank_ref_is_not_adopted(fake_maximo, tmp_path):
    records = _instance()
    records["mxapiwodetail"] = [{"wonum": "WO2910014", "siteid": "SRQSITE", "status": "WAPPR"}]
    fake = fake_maximo(records)
    _, code, lines = _load(fake, tmp_path, only=["SR810008"])
    assert code == 1 and any("external ref (blank), so it is not ours" in line for line in lines)
    wo = fake.records["mxapiwodetail"][0]
    assert wo["status"] == "WAPPR" and "worklog" not in wo


def test_a_wo_is_never_linked_to_an_sr_that_failed(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), refuse={"mxapisr"})
    loader, code, lines = _load(fake, tmp_path, only=["SR810008"])
    assert code == 1 and fake.records["mxapiwodetail"] == []
    assert any("ORIGRECORDID SR810008 is not loaded yet" in line for line in lines)


def test_a_status_change_whose_answer_was_lost_is_not_retried_forever(fake_maximo, tmp_path):
    fake = fake_maximo(_instance(), lose_status_answers=1)
    loader, code, _ = _load(fake, tmp_path, only=["SR810008"])
    assert code == 0, loader.counts
    sr, = fake.records["mxapisr"]
    assert sr["status"] == "RESOLVED" and not loader.limitations
    again, code2, _ = _load(fake, tmp_path, only=["SR810008"])
    assert code2 == 0 and again.counts["status"]["CREATED"] == 0


def test_a_record_with_no_href_is_looked_up_again(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR810001"])
    manifest = Manifest(tmp_path / "manifest.json")
    manifest.entries["sr:SR810001"]["href"] = None
    manifest.save()
    again, code, _ = _load(fake, tmp_path, only=["SR810001"])
    assert code == 0 and again.counts["sr"]["EXISTS"] == 1
    assert Manifest(tmp_path / "manifest.json").get("sr", "SR810001")["href"]


def test_dry_run_against_a_loaded_instance_writes_no_state(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR810008"])
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
    _load(fake, tmp_path, only=["SR810008"])
    lines = []
    verifier = Verifier(fake.client(), Manifest(tmp_path / "manifest.json"), DATA,
                        drop=DEFAULT_DROP, log=lines.append)
    assert verifier.run(only=["SR810008"]) == 0, "\n".join(lines)


def test_sr_in_progress_is_sent_as_maximo_inprog(fake_maximo, tmp_path):
    # The real instance rejects the SRSTATUS synonym INPRG in changeStatus.
    fake = fake_maximo(_instance(), refuse_status={"mxapisr": {"INPRG"}})
    chains = ["SR810008", "SR810058"]  # one goes through in-progress to RESOLVED, one stops there
    _, code, lines = _load(fake, tmp_path, only=chains)
    assert code == 0, "\n".join(lines)
    status = {r["ticketid"]: r["status"] for r in fake.records["mxapisr"]}
    assert status == {"SR810008": "RESOLVED", "SR810058": "INPROG"}

    writes = len(fake.writes())
    again, code2, _ = _load(fake, tmp_path, only=chains)
    assert code2 == 0 and len(fake.writes()) == writes and again.counts["status"]["EXISTS"] == 0

    lines = []
    verifier = Verifier(fake.client(), Manifest(tmp_path / "manifest.json"), DATA, drop=DEFAULT_DROP, log=lines.append)
    assert verifier.run(only=chains) == 0, "\n".join(lines)


def test_srs_go_in_progress_before_their_work_orders_start_and_resolve_after(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path, only=["SR810008"])
    sr = fake.records["mxapisr"][0]["href"]
    order = [(url.split("?")[0] == sr, body["status"]) for _, url, params, _, body in fake.session.calls
             if params and params.get("action") == "wsmethod:changeStatus"]
    assert order.index((True, "INPROG")) < order.index((False, "INPRG")) < order.index((True, "RESOLVED"))


def test_a_record_is_not_closed_while_one_of_its_work_logs_is_missing(fake_maximo, tmp_path):
    # SR810061 ends CLOSED, and its RESOLUTION work log fails on an instance without that log type.
    fake = fake_maximo(_instance())
    manifest = Manifest(tmp_path / "manifest.json")
    loader = Loader(fake.client(), manifest, DATA, apply=True, log=[].append, state_dir=tmp_path)
    loader._load_worklogs = lambda logs: None  # every work log fails to load
    assert loader.run(only=["SR810061"]) == 1
    sr = fake.records["mxapisr"][0]
    assert sr["status"] == "RESOLVED"
    assert loader.counts["status"]["FAILED"] == 1

    _, code, _ = _load(fake, tmp_path, only=["SR810061"])  # the log loads now, so the SR closes
    assert code == 0 and sr["status"] == "CLOSED"


HISTORY = Dataset(name="history")


def test_history_is_its_own_dataset_without_an_answer_key():
    import history_catalog as hc  # on sys.path through loader.config
    from generate_pilot_dataset import MAXIMO_SR_COLUMNS, MAXIMO_WO_COLUMNS

    n_srs = hc.PER_CLASS * len(cat.REQUEST_TYPES)
    assert len(HISTORY.srs) == n_srs and len(HISTORY.wos) == 11 * hc.PER_CLASS and HISTORY.answers == []
    # The history keeps the text-only SR shape it was loaded with; the pilot SRs carry structured fields.
    assert HISTORY.sr_header == MAXIMO_SR_COLUMNS and HISTORY.wo_header == MAXIMO_WO_COLUMNS
    assert set(DATA.sr_header) - set(HISTORY.sr_header) >= {"SOURCE", "SADDRESSCODE"}
    assert len(HISTORY.chains()) == n_srs  # every history WO follows one history SR
    assert not {r["TICKETID"] for r in HISTORY.srs} & {r["TICKETID"] for r in DATA.srs}


def test_history_loads_beside_the_pilot_and_a_rerun_creates_nothing(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path)
    lines = []
    manifest = tmp_path / "manifest.json"
    loader = Loader(fake.client(), Manifest(manifest), HISTORY, apply=True, log=lines.append, state_dir=tmp_path)
    assert loader.run(limit=40) == 0
    assert len(fake.records["mxapisr"]) == 65 + 40
    assert all(r["status"] == "CLOSE" for r in fake.records["mxapiwodetail"] if r["externalrefid"].startswith("WO27"))
    assert not any("Answer key" in line for line in lines)  # the history is not scored
    writes = len(fake.writes())
    again = Loader(fake.client(), Manifest(manifest), HISTORY, apply=True, log=lambda _: None, state_dir=tmp_path)
    assert again.run(limit=40) == 0 and len(fake.writes()) == writes
    assert Verifier(fake.client(), Manifest(manifest, persist=False), HISTORY, drop=DEFAULT_DROP,
                    log=lambda _: None).run(limit=40) == 0


DRAFTS = Dataset(name="drafts")


def test_drafts_are_work_orders_for_pilot_srs_only():
    assert DRAFTS.srs == [] and DRAFTS.worklogs == [] and DRAFTS.answers == [] and len(DRAFTS.wos) == 35
    assert DRAFTS.wo_header == DATA.wo_header
    pilot_srs = {r["TICKETID"] for r in DATA.srs}
    assert {w["ORIGRECORDID"] for w in DRAFTS.wos} <= pilot_srs
    assert not {w["WONUM"] for w in DRAFTS.wos} & {w["WONUM"] for w in DATA.wos + HISTORY.wos}


def test_drafts_load_after_the_pilot_link_to_its_srs_and_stay_wappr(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    _load(fake, tmp_path)
    manifest = tmp_path / "manifest.json"
    loader = Loader(fake.client(), Manifest(manifest), DRAFTS, apply=True, log=lambda _: None, state_dir=tmp_path)
    assert loader.run() == 0
    drafts = [r for r in fake.records["mxapiwodetail"] if r["externalrefid"].startswith("WO2915")]
    assert len(drafts) == 35 and all(r["status"] == "WAPPR" for r in drafts)
    loaded = {r["ticketid"] for r in fake.records["mxapisr"]}
    origin = {w["WONUM"]: w["ORIGRECORDID"] for w in DRAFTS.wos}
    assert all(r["origrecordid"] == origin[r["externalrefid"]] and r["origrecordid"] in loaded for r in drafts)
    writes = len(fake.writes())
    again = Loader(fake.client(), Manifest(manifest), DRAFTS, apply=True, log=lambda _: None, state_dir=tmp_path)
    assert again.run() == 0 and len(fake.writes()) == writes
    assert Verifier(fake.client(), Manifest(manifest, persist=False), DRAFTS, drop=DEFAULT_DROP,
                    log=lambda _: None).run() == 0


def test_drafts_before_the_pilot_are_refused_until_their_sr_is_loaded(fake_maximo, tmp_path):
    fake = fake_maximo(_instance())
    lines = []
    loader = Loader(fake.client(), Manifest(tmp_path / "m.json"), DRAFTS, apply=True, log=lines.append,
                    state_dir=tmp_path)
    assert loader.run(limit=3) == 1
    assert not fake.records["mxapiwodetail"]
    assert sum("is not loaded yet" in line for line in lines) == 3


def test_maximo_answer_key_keeps_our_classification_ids_for_scoring_by_name(tmp_path):
    from loader.mapping import Remap
    classes = {ours: str(7000 + i) for i, ours in enumerate(cat.CLASSIFICATIONS)}
    rows = list(csv.DictReader(write_answer_key(DATA, Remap(classes=classes), tmp_path / "key.csv").open()))
    assert [r["EXPECTED_CLASSSTRUCTUREID"] for r in rows] == [a["EXPECTED_CLASSSTRUCTUREID"] for a in DATA.answers]


def test_load_and_verify_take_a_dataset_option():
    import subprocess
    import sys
    for command in ("load", "verify"):
        out = subprocess.run([sys.executable, "-m", "loader", command, "--help"], capture_output=True, text=True,
                             check=True).stdout
        assert "--dataset {pilot,history,drafts}" in out
