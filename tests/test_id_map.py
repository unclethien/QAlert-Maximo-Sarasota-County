"""The old-to-new pilot ID map: every regenerated pilot ID maps back to its old one, and no new
pilot ID collides with the training history."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import id_map  # noqa: E402

DATA = ROOT / "data"


def _column(path, column):
    with open(path, newline="", encoding="utf-8") as f:
        return [row[column] for row in csv.DictReader(f)]


def _pilot_ids():
    ids = {"sr": _column(DATA / "maximo/sr.csv", "TICKETID"), "wo": _column(DATA / "maximo/wo.csv", "WONUM"),
           "draft": _column(DATA / "maximo/drafts/wo.csv", "WONUM"),
           "worklog": _column(DATA / "maximo/worklog.csv", "WORKLOGID"),
           "request": [str(r["id"]) for r in json.loads((DATA / "qalert/requests.json").read_text())]}
    assert all(ids.values())
    return ids


def test_every_new_pilot_id_is_in_its_range_and_round_trips():
    for kind, values in _pilot_ids().items():
        for new in values:
            assert id_map.kind_of(new, "new") == kind, new
            old = id_map.old_id(new)
            assert id_map.kind_of(old, "old") == kind and id_map.new_id(old) == new, new


def test_no_new_pilot_id_collides_with_the_history():
    history = set(_column(DATA / "maximo/history/sr.csv", "TICKETID")) | set(_column(DATA / "maximo/history/wo.csv", "WONUM"))
    history |= set(_column(DATA / "maximo/history/worklog.csv", "WORKLOGID"))
    history |= set(_column(DATA / "maximo/history/sr.csv", "EXTERNALSYSTEM_TICKETID"))
    pilot = {v for values in _pilot_ids().values() for v in values}
    assert not pilot & history
    assert not {id_map.old_id(v) for v in pilot} & history  # nor do the old copies


def test_the_old_and_new_ranges_do_not_overlap():
    new_ids = {v for values in _pilot_ids().values() for v in values}
    assert not {id_map.kind_of(v, "old") for v in new_ids} - {None}
