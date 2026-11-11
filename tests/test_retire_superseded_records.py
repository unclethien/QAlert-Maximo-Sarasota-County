"""The plan for retiring the old pilot copies: mapping, order and status steps, with no HTTP."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import id_map  # noqa: E402
import retire_superseded_records as retire  # noqa: E402


@pytest.mark.parametrize("old, new", [
    ("SR800001", "SR810001"), ("SR800065", "SR810065"), ("700044", "710044"), ("WO2900014", "WO2910014"),
    ("WO2950024", "WO2915024"), ("3000126", "3010126"), ("SR700044", "SR810044"), ("SR700046", "SR810046"),
])
def test_each_old_copy_maps_to_its_new_one(old, new):
    assert retire.new_copy(old) == new


def test_ids_outside_the_old_ranges_do_not_map():
    assert [retire.new_copy(x) for x in ("SR600001", "WO2700001", "SR810001", "PRECHK1")] == [None] * 4
    assert id_map.old_id("SR810044") == "SR800044" and id_map.kind_of("WO2915001", "new") == "draft"


@pytest.mark.parametrize("status, steps", [
    ("NEW", ["QUEUED", "INPROG", "RESOLVED", "CLOSED"]), ("PENDING", ["QUEUED", "INPROG", "RESOLVED", "CLOSED"]),
    ("QUEUED", ["INPROG", "RESOLVED", "CLOSED"]), ("INPROG", ["RESOLVED", "CLOSED"]), ("RESOLVED", ["CLOSED"]),
    ("CLOSED", []), ("CANCELLED", []), ("INPRG", None), ("", None), ("WHATEVER", None),
])
def test_sr_steps_to_closed(status, steps):
    assert retire.sr_steps(status) == steps


@pytest.mark.parametrize("status, steps", [
    ("WAPPR", ["CAN"]), ("APPR", ["CAN"]), ("WCONT", ["CAN"]), ("SCHED", ["CAN"]), ("INPRG", ["COMP", "CLOSE"]),
    ("COMP", ["CLOSE"]), ("CLOSE", []), ("CAN", []), ("", None), ("HOLD", None),
])
def test_wo_steps_close_finished_work_and_cancel_the_rest(status, steps):
    assert retire.wo_steps(status) == steps


def test_plan_retires_wos_before_srs_and_skips_final_or_unloaded_records():
    old_srs = [{"ticketid": "SR800002", "status": "QUEUED", "href": "s2"}, {"ticketid": "SR800001", "status": "CLOSED"},
               {"ticketid": "SR700044", "status": "INPROG", "href": "s44"}, {"ticketid": "SR800003", "status": "NEW"}]
    old_wos = [{"wonum": "WO2950001", "status": "WAPPR", "href": "d1"}, {"wonum": "WO2900002", "status": "COMP", "href": "w2"},
               {"wonum": "WO2900001", "status": "CLOSE"}]
    loaded = {"SR810002", "SR810044", "WO2915001", "WO2910002"}  # SR810003 is not loaded yet
    actions = retire.plan(old_wos, old_srs, loaded, noted={"SR700044"})
    assert [(a["kind"], a["old"], a["new"]) for a in actions] == [
        ("wo", "WO2900002", "WO2910002"), ("wo", "WO2950001", "WO2915001"),
        ("sr", "SR700044", "SR810044"), ("sr", "SR800002", "SR810002"), ("sr", "SR800003", "SR810003")]
    by_old = {a["old"]: a for a in actions}
    assert by_old["WO2900002"]["steps"] == ["CLOSE"] and by_old["WO2950001"]["steps"] == ["CAN"]
    assert by_old["SR700044"]["note"] is False and by_old["SR800002"]["note"] is True  # never noted twice
    assert by_old["SR800003"]["skip"] == "SR810003 not loaded yet" and by_old["SR800002"]["skip"] is None


def test_a_record_already_final_needs_nothing():
    assert retire.plan([{"wonum": "WO2900001", "status": "CAN"}], [{"ticketid": "SR800001", "status": "CLOSED"}],
                       loaded=set(), noted=set()) == []


def test_the_note_points_to_the_new_copy_and_stays_internal():
    log = retire.worklog("SR810044")
    assert log["description"] == "Superseded by SR810044" and log["clientviewable"] is False
    assert len(log["description"]) <= 100


def test_an_sr_waits_while_one_of_its_old_wos_stays_open():
    old_wos = [{"wonum": "WO2950001", "status": "WAPPR", "origrecordid": "SR800002"},  # draft copy not loaded yet
               {"wonum": "WO2900003", "status": "HOLD", "origrecordid": "SR800003"},   # unknown status: left alone
               {"wonum": "WO2900004", "status": "COMP", "origrecordid": "SR800004"}]
    old_srs = [{"ticketid": t, "status": "QUEUED"} for t in ("SR800002", "SR800003", "SR800004")]
    loaded = {"SR810002", "SR810003", "SR810004", "WO2910003", "WO2910004"}
    skip = {a["old"]: a["skip"] for a in retire.plan(old_wos, old_srs, loaded, noted=set())}
    assert skip == {"WO2950001": "WO2915001 not loaded yet", "WO2900003": "unknown status 'HOLD'",
                    "WO2900004": None, "SR800002": "its old WO WO2950001 stays open",
                    "SR800003": "its old WO WO2900003 stays open", "SR800004": None}
