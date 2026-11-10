"""The missing-information rule script, run against the pilot SRs and the answer key."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "autoscript" / "srqmissinfo.py"
sys.path.insert(0, str(ROOT / "scripts"))

# The script is Jython for Maximo; its rule functions are plain Python. Running it here without
# `mbo` or `request` defines the functions and skips the Maximo part.
rules: dict = {}
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), rules)
find_gaps = rules["find_gaps"]

import pilot_catalog as cat  # noqa: E402

AUTOMATABLE = {"ADDR", "LS-ID", "ADDR-VALID"}
# ADDR-VALID needs the County address file to catch a misspelled or unknown street. The script
# only sees the text, so it catches a city outside the county and misses these two.
NEEDS_ADDRESS_FILE = {"SR800002", "SR800033"}


def _rows(path):
    with open(ROOT / path, newline="") as f:
        return list(csv.DictReader(f))


def _flags():
    return {sr["TICKETID"]: {rule for rule, _ in find_gaps(sr["DESCRIPTION"], sr["DESCRIPTION_LONGDESCRIPTION"],
                                                           cat.CLASSIFICATIONS[sr["CLASSSTRUCTUREID"]][0])}
            for sr in _rows("data/maximo/sr.csv")}


def test_flags_match_the_answer_key_for_the_rules_text_can_decide():
    flags = _flags()
    for row in _rows("data/answer-key.csv"):
        expected = set(filter(None, row["REQUIRED_INFO_GAP"].split(";"))) & AUTOMATABLE
        if row["TICKETID"] in NEEDS_ADDRESS_FILE:
            expected -= {"ADDR-VALID"}
        assert flags[row["TICKETID"]] == expected, row["TICKETID"]


def test_the_address_file_cases_are_still_in_the_answer_key():
    gaps = {r["TICKETID"]: r["REQUIRED_INFO_GAP"] for r in _rows("data/answer-key.csv")}
    assert all("ADDR-VALID" in gaps[t] for t in NEEDS_ADDRESS_FILE)


def test_the_pilot_has_the_expected_number_of_flags():
    flags = _flags()
    assert sorted(t for t, f in flags.items() if f) == ["SR800001", "SR800005", "SR800008", "SR800012", "SR800020"]


def test_the_history_has_no_flags():
    for sr in _rows("data/maximo/history/sr.csv"):
        assert not find_gaps(sr["DESCRIPTION"], sr["DESCRIPTION_LONGDESCRIPTION"],
                             cat.CLASSIFICATIONS[sr["CLASSSTRUCTUREID"]][0]), sr["TICKETID"]


@pytest.mark.parametrize("address, rules_broken", [
    ("1530 Zephyr Palm Dr, North Port, FL", set()),
    ("12B Bay St, Venice, FL", set()),
    ("Halyard Reach Rd, Nokomis, FL", {"ADDR"}),
    ("North Port, FL", {"ADDR", "LS-ID"}),
    ("4410 Riverbluff Ln, Bradenton, FL", {"ADDR-VALID"}),
])
def test_address_rules_on_a_lift_station_alarm(address, rules_broken):
    longdesc = f"<div>Customer: A B</div><div>Address: {address} <a href='x'>Map</a></div><div>Alarm.</div>"
    assert {r for r, _ in find_gaps("Lift Station Alarm", longdesc, "WW-LIFT")} == rules_broken


def test_a_station_number_in_the_text_satisfies_ls_id():
    longdesc = "<div>Address: North Port, FL</div><div>Red light on lift station #42.</div>"
    assert {r for r, _ in find_gaps("Lift Station Alarm", longdesc, "WW-LIFT")} == {"ADDR"}


def test_the_script_imports_nothing():
    # Maximo's Jython has no standard library: an import fails and blocks every SR save.
    assert not [line for line in SCRIPT.read_text().splitlines() if line.lstrip().startswith(("import ", "from "))]


@pytest.mark.parametrize("text, named", [
    ("Red light on lift station #42.", True),
    ("Alarm at Station no. 7", True),
    ("LS 12 is beeping", True),
    ("station B3 panel", True),
    ("the station number is 5a", False),
    ("substation 4", False),
    ("ls is not a station name", False),
])
def test_station_names(text, named):
    assert rules["has_station_id"](text) is named


def test_a_structured_house_number_counts():
    assert find_gaps("Water Line Leak", "<div>Address: Main St, Venice, FL</div>", "WATER-LEAK", "120") == []
