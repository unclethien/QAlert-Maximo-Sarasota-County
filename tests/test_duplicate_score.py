"""The duplicate score script, run against the pilot SRs and the answer key's duplicate clusters."""

import csv
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "autoscript" / "srqdupscore.py"

# The script is Jython for Maximo; its scoring functions are plain Python. Running it here without
# `mbo` defines the functions and skips the Maximo part.
ns: dict = {}
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), ns)
coordinates, distance_m, duplicate_score = ns["coordinates"], ns["distance_m"], ns["duplicate_score"]
deductions = ns["deductions"]

SHOW_AT = 85  # a duplicate score at or above this marks a likely duplicate in the AISIMSR dialog
# The AI scored every pilot pair between 83 and 97 on TechZone (2026-11-08), so a true duplicate is
# tested at the low end and a wrong match at the high end.
AI_LOW, AI_HIGH = 93, 97


def _rows(path):
    with open(ROOT / path, newline="") as f:
        return list(csv.DictReader(f))


SRS = {r["TICKETID"]: r for r in _rows("data/maximo/sr.csv")}
KEY = {r["TICKETID"]: r for r in _rows("data/answer-key.csv")}


def _score(a, b, ai):
    sa, sb = SRS[a], SRS[b]
    # Scored as in Maximo: the service address coordinates, falling back to the Maps link.
    meters = distance_m(coordinates(sa["DESCRIPTION_LONGDESCRIPTION"], *_field_point(sa)),
                        coordinates(sb["DESCRIPTION_LONGDESCRIPTION"], *_field_point(sb)))
    days = abs((datetime.fromisoformat(sa["REPORTDATE"]) - datetime.fromisoformat(sb["REPORTDATE"])).total_seconds()) / 86400
    return duplicate_score(ai, meters, days)


def _related_srs(ticket):
    return [t for t in KEY[ticket]["RELATED_RECORDS"].split(";") if t.startswith("SR")]


def _pairs(scenario_word):
    return [(t, r) for t, row in KEY.items() if scenario_word in row["SCENARIO"] for r in _related_srs(t)]


def _field_point(sr):
    return (sr["LATITUDEY"], sr["LONGITUDEX"]) if sr["LATITUDEY"] else (None, None)


def test_the_service_address_coordinates_agree_with_the_map_link():
    located = [sr for sr in SRS.values() if sr["LATITUDEY"]]
    assert len(located) == 63  # all but the two with no street
    for sr in SRS.values():
        assert coordinates(sr["DESCRIPTION_LONGDESCRIPTION"], *_field_point(sr)) == coordinates(
            sr["DESCRIPTION_LONGDESCRIPTION"]), sr["TICKETID"]


def test_the_service_address_wins_over_the_map_link():
    assert coordinates("<a href='https://www.google.com/maps/search/27.1,-82.4'>Map</a>", "27.2", "-82.5") == (27.2, -82.5)
    assert coordinates("no link", 27.2, -82.5) == (27.2, -82.5) and coordinates("no link", 27.2, None) is None
    assert coordinates("no link", "", "") is None and coordinates("no link", "27.2", "-82.5") == (27.2, -82.5)


def test_reads_the_map_link():
    lat, lon = coordinates(SRS["SR810044"]["DESCRIPTION_LONGDESCRIPTION"])
    assert (lat, lon) == pytest.approx((27.05563, -82.398293))
    assert coordinates(SRS["SR810005"]["DESCRIPTION_LONGDESCRIPTION"]) is None
    assert coordinates("") is None and coordinates(None) is None


def test_distance_between_the_gulfwren_and_willowmarsh_sewer_odors():
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR810044", "SR810025"))
    assert distance_m(a, b) == pytest.approx(6107, abs=25)
    assert distance_m(a, a) == 0
    assert distance_m(a, None) is None


def test_same_type_at_another_address_scores_40_to_50_on_location_alone():
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR810044", "SR810025"))
    assert 40 <= duplicate_score(93, distance_m(a, b), 0) <= 50
    assert _score("SR810044", "SR810025", 93) < 40  # and lower again, 25 days apart


def test_the_true_duplicate_keeps_its_ai_score():
    assert _score("SR810044", "SR810046", 97) == 97


@pytest.mark.parametrize("dup,first", _pairs("Duplicate cluster"))
def test_every_duplicate_clears_the_cut(dup, first):
    assert _score(dup, first, AI_LOW) >= SHOW_AT


@pytest.mark.parametrize("lookalike,resembles", _pairs("Look-alike"))
def test_every_look_alike_falls_below_the_cut(lookalike, resembles):
    assert _score(lookalike, resembles, AI_HIGH) < SHOW_AT


def test_same_type_reports_over_a_kilometre_apart_score_50_or_less():
    located = [t for t, r in SRS.items() if coordinates(r["DESCRIPTION_LONGDESCRIPTION"])]
    far = [(a, b) for a, b in combinations(located, 2)
           if SRS[a]["CLASSSTRUCTUREID"] == SRS[b]["CLASSSTRUCTUREID"]
           and distance_m(coordinates(SRS[a]["DESCRIPTION_LONGDESCRIPTION"]),
                          coordinates(SRS[b]["DESCRIPTION_LONGDESCRIPTION"])) > 1000]
    assert far
    assert max(_score(a, b, AI_HIGH) for a, b in far) <= 50


@pytest.mark.parametrize("ai", range(80, 101))
@pytest.mark.parametrize("meters", [None, 0, 150, 400, 575, 999, 6107])
@pytest.mark.parametrize("days", [None, 0, 3, 6, 14, 25])
def test_deductions_add_up_to_the_ai_score(ai, meters, days):
    score, distance_pts, time_pts = deductions(ai, meters, days)
    assert score == duplicate_score(ai, meters, days)
    assert score + distance_pts + time_pts == ai
    assert distance_pts >= 0 and time_pts >= 0


def test_deductions_for_the_willowmarsh_match_and_the_true_duplicate():
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR810044", "SR810025"))
    assert deductions(93, distance_m(a, b), 25) == (33, 46, 14)
    assert deductions(97, 12, 2) == (97, 0, 0)
    assert deductions(92, 30, 42) == (64, 0, 28)


def test_an_sr_without_a_map_link_ranks_below_located_matches():
    assert duplicate_score(97, None, 0) < SHOW_AT
    assert duplicate_score(97, None, 0) > duplicate_score(97, 5000, 0)


# ---- Work order pairs (WOSIMILARITY) ----------------------------------------------------------

WOS = {r["WONUM"]: r for r in _rows("data/maximo/wo.csv") + _rows("data/maximo/drafts/wo.csv")}
# The AI scored the related WOs 88 to 95 and the unrelated ones 83 to 95 on TechZone (2026-11-12).
WO_AI_LOW, WO_AI_HIGH = 88, 95


def _wo_meters_days(a, b):
    wa, wb = WOS[a], WOS[b]
    meters = distance_m(coordinates(wa["DESCRIPTION_LONGDESCRIPTION"], *_field_point(wa)),
                        coordinates(wb["DESCRIPTION_LONGDESCRIPTION"], *_field_point(wb)))
    days = abs((datetime.fromisoformat(wa["REPORTDATE"]) - datetime.fromisoformat(wb["REPORTDATE"])).total_seconds()) / 86400
    return meters, days


def _checked_wo(ticket):
    """The WO a planner opens for the SR: its draft, else its open follow-up, else a closed one."""
    own = sorted((w["WONUM"][:6] != "WO2915", w["STATUS"] in ("CLOSE", "CAN"), w["WONUM"])
                 for w in WOS.values() if w["ORIGRECORDID"] == ticket and w["STATUS"] != "CAN")
    return own[0][2] if own else None


RELATED_WO_PAIRS = [(_checked_wo(t), r) for t, row in KEY.items() if _checked_wo(t)
                    for r in row["RELATED_RECORDS"].split(";") if r.startswith("WO") and r in WOS
                    and WOS[r]["ORIGRECORDID"] != t]


def test_the_pilot_has_twelve_related_work_order_pairs():
    assert len(RELATED_WO_PAIRS) == 12


def test_every_related_work_order_beats_every_same_type_work_order_a_kilometre_away():
    related = [duplicate_score(WO_AI_LOW, *_wo_meters_days(a, b)) for a, b in RELATED_WO_PAIRS]
    far = []
    for a, b in combinations(sorted(WOS), 2):
        same_type = WOS[a]["CLASSSTRUCTUREID"] == WOS[b]["CLASSSTRUCTUREID"] != ""
        meters, days = _wo_meters_days(a, b)
        if same_type and meters is not None and meters >= 1000:
            far.append(duplicate_score(WO_AI_HIGH, meters, days))
    assert far and min(related) > max(far)
    assert max(far) <= WO_AI_HIGH // 2 + 1  # half the AI score at most


class FakeMbo:
    """Just enough of a Maximo record for score_pair: attributes, and sets found by (name, object, where)."""

    def __init__(self, values=None, sets=None):
        self.values, self.sets, self.asked, self.set_values = values or {}, sets or {}, [], {}

    def getString(self, a):
        return str(self.values.get(a, ""))

    def getLong(self, a):
        return int(self.values[a])

    getInt = getLong

    def getDouble(self, a):
        return float(self.values[a])

    def isNull(self, a):
        return self.values.get(a) in (None, "")

    def getDate(self, a):
        d = self.values.get(a)
        return None if d is None else type("D", (), {"getTime": lambda _s: d.timestamp() * 1000})()

    def getMboSet(self, name, obj, where):
        self.asked.append((name, obj, where))
        found = self.sets.get((obj, where))
        return type("S", (), {"getMbo": lambda _s, i: found})()

    def setValue(self, a, v):
        self.set_values[a] = v


def _fake_record(lat, lon, date, address, scope):
    row = FakeMbo({"LATITUDEY": lat, "LONGITUDEX": lon})
    return FakeMbo({"DESCRIPTION_LONGDESCRIPTION": "", "REPORTDATE": date}, {(address, scope): row})


def test_score_pair_scores_a_work_order_pair_from_its_service_addresses():
    score_pair = ns["score_pair"]
    scope = "wonum=:wonum and siteid=:siteid"
    a = _fake_record(27.0, -82.0, datetime(2026, 1, 1), "WOSERVICEADDRESS", scope)
    b = _fake_record(27.0, -82.0 + 0.0202, datetime(2026, 1, 2), "WOSERVICEADDRESS", scope)  # about 2 km
    pair = FakeMbo({"OBJECTNAME": "WORKORDER", "AICFGNAME": "WOSIMILARITY", "OBJECTID": 1,
                    "SIMILARTOOBJECTID": 2, "SCORE": 92},
                   {("WORKORDER", "workorderid=1"): a, ("WORKORDER", "workorderid=2"): b})
    assert score_pair(pair) == 46
    assert pair.set_values == {"DUPSCORE": 46, "DUPDISTPTS": 46, "DUPTIMEPTS": 0}
    assert ("$SRQDUPADDRWORKORDER", "WOSERVICEADDRESS", scope) in a.asked


def test_score_pair_still_scores_sr_pairs_and_skips_a_mismatched_configuration():
    score_pair = ns["score_pair"]
    scope = "ticketid=:ticketid and class=:class"
    a = _fake_record(27.0, -82.0, datetime(2026, 1, 1), "TKSERVICEADDRESS", scope)
    b = _fake_record(27.0, -82.0, datetime(2026, 1, 1, 6), "TKSERVICEADDRESS", scope)
    sr_pair = FakeMbo({"OBJECTNAME": "SR", "AICFGNAME": "SRSIMILARITY", "OBJECTID": 1,
                       "SIMILARTOOBJECTID": 2, "SCORE": 97},
                      {("SR", "ticketuid=1"): a, ("SR", "ticketuid=2"): b})
    assert score_pair(sr_pair) == 97 and sr_pair.set_values["DUPDISTPTS"] == 0
    for name, cfg in (("SR", "WOSIMILARITY"), ("WORKORDER", "SRSIMILARITY"), ("ASSET", "ASSETSIMILARITY")):
        other = FakeMbo({"OBJECTNAME": name, "AICFGNAME": cfg})
        assert score_pair(other) is None and other.set_values == {}
