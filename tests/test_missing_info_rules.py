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
# ADDR-VALID needs the County address file to catch a misspelled or unknown street. The service
# address says so (a full address with no address code); the text alone cannot, so the fallback
# catches a city outside the county and misses these two.
NEEDS_ADDRESS_FILE = {"SR810002", "SR810033"}


def _rows(path):
    with open(ROOT / path, newline="") as f:
        return list(csv.DictReader(f))


def _address(sr):
    return {"number": sr["STADDRNUMBER"], "street": sr["STADDRSTREET"], "city": sr["CITY"], "code": sr["SADDRESSCODE"]}


def _flags(fields=True):
    return {sr["TICKETID"]: {rule for rule, _ in find_gaps(sr["DESCRIPTION"], sr["DESCRIPTION_LONGDESCRIPTION"],
                                                           cat.CLASSIFICATIONS[sr["CLASSSTRUCTUREID"]][0],
                                                           _address(sr) if fields else None)}
            for sr in _rows("data/maximo/sr.csv")}


def _expected(row):
    return set(filter(None, row["REQUIRED_INFO_GAP"].split(";"))) & AUTOMATABLE


def test_flags_match_the_answer_key_for_the_rules_the_record_can_decide():
    flags = _flags()
    for row in _rows("data/answer-key.csv"):
        assert flags[row["TICKETID"]] == _expected(row), row["TICKETID"]


def test_without_a_service_address_the_text_decides_all_but_the_address_file_cases():
    flags = _flags(fields=False)
    for row in _rows("data/answer-key.csv"):
        expected = _expected(row) - ({"ADDR-VALID"} if row["TICKETID"] in NEEDS_ADDRESS_FILE else set())
        assert flags[row["TICKETID"]] == expected, row["TICKETID"]


def test_the_service_address_catches_8_of_the_18_gaps_and_the_text_6():
    rows = _rows("data/answer-key.csv")
    gaps = {r["TICKETID"]: set(filter(None, r["REQUIRED_INFO_GAP"].split(";"))) for r in rows}
    def caught(flags):
        return sum(len(flags[t] & g) for t, g in gaps.items())
    assert sum(map(len, gaps.values())) == 18
    assert (caught(_flags()), caught(_flags(fields=False))) == (8, 6)


def test_the_address_file_cases_are_still_in_the_answer_key():
    gaps = {r["TICKETID"]: r["REQUIRED_INFO_GAP"] for r in _rows("data/answer-key.csv")}
    assert all("ADDR-VALID" in gaps[t] for t in NEEDS_ADDRESS_FILE)


def test_the_pilot_has_the_expected_number_of_flags():
    flagged = sorted(t for t, f in _flags().items() if f)
    assert flagged == ["SR810001", "SR810002", "SR810005", "SR810008", "SR810012", "SR810020", "SR810033"]


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


TEXT_WITHOUT_NUMBER = "<div>Address: Main St, Venice, FL</div>"


def test_the_service_address_wins_over_the_text():
    matched = {"number": "120", "street": "Main St", "city": "VENICE", "code": "AP00007"}
    assert find_gaps("Water Line Leak", TEXT_WITHOUT_NUMBER, "WATER-LEAK", matched) == []


def test_an_empty_service_address_falls_back_to_the_text():
    empty = {"number": "", "street": " ", "city": "", "code": ""}
    assert [r for r, _ in find_gaps("Water Line Leak", TEXT_WITHOUT_NUMBER, "WATER-LEAK", empty)] == ["ADDR"]


CITY_ONLY_TEXT = "<div>Address: Venice, FL</div><div>Alarm.</div>"
FULL_TEXT = "<div>Address: 7012 Aldersea Cir, Venice, FL</div><div>Alarm.</div>"


@pytest.mark.parametrize("address, rules_broken", [
    ({"number": "9870", "street": "Wrenhaven Pl", "city": "SARASOTA"}, {"ADDR-VALID"}),  # not in the file
    ({"street": "Halyard Reach Rd", "city": "NOKOMIS"}, {"ADDR"}),  # street only: no house number to look up
    ({"city": "NORTH PORT"}, {"ADDR", "LS-ID"}),
    ({"number": "4410", "street": "Riverbluff Ln", "city": "BRADENTON"}, {"ADDR-VALID"}),  # once, as out of county
    ({"code": "AP00001"}, set()),  # a County address point picked in the UI, with no other field copied
    ({"street": "1530 Zephyr Palm Dr", "city": "VENICE"}, {"ADDR-VALID"}),  # number typed into the street field
    ({"streetaddress": "1530 Zephyr Palm Dr", "code": "AP00002"}, set()),
])
def test_address_rules_on_the_service_address(address, rules_broken):
    gaps = find_gaps("Lift Station Alarm", CITY_ONLY_TEXT, "WW-LIFT", address)
    assert [r for r, _ in gaps].count("ADDR-VALID") <= 1 and {r for r, _ in gaps} == rules_broken


@pytest.mark.parametrize("address", [{"code": "AP00001"}, {"city": "SARASOTA"}, {"number": None, "city": "VENICE"}])
def test_a_partly_filled_service_address_never_overrides_a_full_text_address(address):
    assert find_gaps("Lift Station Alarm", FULL_TEXT, "WW-LIFT", address) == []


@pytest.mark.parametrize("city", ["bradenton", "Bradenton.", "Port  Charlotte", " PUNTA GORDA "])
def test_out_of_county_cities_match_without_case_dots_or_extra_spaces(city):
    assert [r for r, _ in find_gaps("x", FULL_TEXT, "WATER-LEAK", {"city": city})] == ["ADDR-VALID"]


def test_odd_values_in_the_service_address_never_raise():
    gaps = find_gaps("x", CITY_ONLY_TEXT, "WATER-LEAK", {"number": 120, "street": "Main St", "city": None, "code": ""})
    assert [r for r, _ in gaps] == ["ADDR-VALID"]  # 120 Main St, with no code


def test_an_unmatched_address_names_itself_in_the_note():
    (_, message), = find_gaps("x", "", "WATER-LEAK", {"number": "9870", "street": "Wrenhaven Pl", "city": "SARASOTA"})
    assert message.startswith("9870 Wrenhaven Pl is not in the County address file")


class _FakeMbo:
    """Just enough of a Maximo Mbo for the script's address lookup."""

    def __init__(self, values, new=False, sets=None):
        self.values, self.new, self.sets = values, new, sets or {}

    def getString(self, attribute):
        return self.values.get(attribute, "")

    def toBeAdded(self):
        return self.new

    def getMboSet(self, name, *scoped):
        if name not in self.sets:
            raise RuntimeError("BMXAA: no relationship " + name)  # Maximo raises a Java exception
        return _FakeSet(self.sets[name])


class _FakeSet:
    def __init__(self, rows):
        self.rows = rows

    def getMbo(self, i):
        return self.rows[i] if i < len(self.rows) else None


ROW = {"STADDRNUMBER": "2496", "STREETADDRESS": "2496 Sandpiper Glenn Way", "CITY": "SARASOTA"}


def test_a_new_sr_reads_its_address_through_the_serviceaddress_relationship():
    # The row being added has no ticket yet; the SR's TKSERVICEADDRESS rows hang off SERVICEADDRESS.
    sr = _FakeMbo({"TICKETID": "SR810002"}, new=True, sets={"SERVICEADDRESS": [_FakeMbo({**ROW, "TICKETID": ""}, new=True)]})
    assert rules["service_address"](sr)["streetaddress"] == "2496 Sandpiper Glenn Way"


def test_a_saved_sr_reads_its_address_through_the_scoped_set_and_skips_other_srs():
    rows = [_FakeMbo({**ROW, "TICKETID": "SR810001"}), _FakeMbo({"TICKETID": "SR810002"}),
            _FakeMbo({**ROW, "TICKETID": "SR810002"})]
    sr = _FakeMbo({"TICKETID": "SR810002"}, sets={"$SRQMISSADDR": rows})
    assert rules["service_address"](sr)["number"] == "2496"


def test_an_unknown_relationship_falls_back_to_the_text():
    assert rules["service_address"](_FakeMbo({"TICKETID": "SR810002"}, new=True)) is None
