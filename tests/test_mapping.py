from loader import mapping
from loader.load import Dataset
from loader.manifest import Manifest

DATA = Dataset()


def _sr(ticket):
    return next(r for r in DATA.srs if r["TICKETID"] == ticket)


def _followup():
    return next(w for w in DATA.wos if w["ORIGRECORDID"])


def test_sr_payload_sends_mapped_columns_and_skips_derived_and_blank():
    row = _sr("SR800001")
    payload = mapping.sr_payload(row, mapping.Remap(classes={"9101": "1234"}))
    assert payload["ticketid"] == "SR800001" and payload["externalrecid"] == "700001"
    assert "externalsystem" not in payload and "externalsystem_ticketid" not in payload
    assert payload["classstructureid"] == "1234"
    assert "ownergroup" not in payload  # blank on every SR: the team belongs on the WO
    assert not {"status", "statusdate", "createdby", "creationdate", "class"} & set(payload)


def test_wo_payload_remaps_origin_and_keeps_our_id_as_external_ref():
    row = _followup()
    payload = mapping.wo_payload(row, mapping.Remap(tickets={row["ORIGRECORDID"]: "1001"}),
                                 drop={"FAILURECODE", "PROBLEMCODE"})
    assert payload["origrecordid"] == "1001" and payload["externalrefid"] == row["WONUM"]
    assert "failurecode" not in payload and "problemcode" not in payload
    assert payload["persongroup"] == payload["ownergroup"]


def test_planned_wo_sends_no_job_plan_or_actual_finish():
    row = next(w for w in DATA.wos if w["WORKTYPE"] == "CP" and w["STATUS"] == "SCHED")
    payload = mapping.wo_payload(row, mapping.Remap())
    assert "jpnum" not in payload and "actfinish" not in payload and payload["schedstart"]


def test_worklog_payload_is_a_child_row():
    payload = mapping.worklog_payload(DATA.worklogs[0])
    assert payload["clientviewable"] is True and payload["logtype"] == "CLIENTNOTE"
    assert not {"worklogid", "recordkey", "siteid"} & set(payload)


def test_dropped_column_report_names_every_unsent_column():
    sr = mapping.dropped_columns("sr", DATA.sr_header, set())
    assert set(sr) == {"CLASS", "STATUS", "STATUSDATE", "CREATEDBY", "CREATIONDATE", "EXTERNALSYSTEM"}
    wo = mapping.dropped_columns("wo", DATA.wo_header, {"FAILURECODE", "PROBLEMCODE"})
    assert set(wo) == {"STATUS", "STATUSDATE", "FAILURECODE", "PROBLEMCODE"}
    assert set(mapping.dropped_columns("worklog", DATA.wl_header, set())) == {
        "WORKLOGID", "RECORDKEY", "CLASS", "SITEID", "ORGID"}


def test_every_dataset_status_has_a_path():
    assert {r["STATUS"] for r in DATA.srs} <= set(mapping.SR_STEPS)
    assert {r["STATUS"] for r in DATA.wos} <= set(mapping.WO_STEPS)


def test_status_steps_resume_from_where_a_run_stopped():
    assert mapping.status_steps("wo", "CLOSE") == ["INPRG", "COMP", "CLOSE"]
    assert mapping.status_steps("wo", "CLOSE", "COMP") == ["CLOSE"]
    assert mapping.status_steps("wo", "CLOSE", "CLOSE") == []
    assert mapping.status_steps("sr", "NEW") == []


def test_chains_cover_every_record_once():
    chains = DATA.chains()
    assert sum(len(c.srs) for c in chains) == 60 and sum(len(c.wos) for c in chains) == 41
    one = DATA.select(only=["SR800008"])
    assert [r["TICKETID"] for r in one.srs] == ["SR800008"] and [w["WONUM"] for w in one.wos] == ["WO2900014"]
    assert len(DATA.select(limit=3).srs) == 3


def test_manifest_writes_atomically_and_reloads(tmp_path):
    path = tmp_path / "manifest.json"
    m = Manifest(path)
    m.record("sr", "SR800001", maximo_id="1001", href="h1")
    m.set_status("sr", "SR800001", "QUEUED")
    again = Manifest(path)
    assert again.get("sr", "SR800001")["maximo_id"] == "1001"
    assert again.get("sr", "SR800001")["status"] == "QUEUED"
    assert not list(tmp_path.glob("*.tmp"))


def test_long_team_codes_are_written_under_their_maximo_code():
    row = next(w for w in DATA.wos if w["PERSONGROUP"] == "SANCLINSP")
    payload = mapping.wo_payload(row, mapping.Remap(), drop={"FAILURECODE", "PROBLEMCODE"})
    assert payload["persongroup"] == "SANCLINS"
    assert all(len(mapping.maximo_team(g)) <= 8 for g in {w["PERSONGROUP"] for w in DATA.wos if w["PERSONGROUP"]})
