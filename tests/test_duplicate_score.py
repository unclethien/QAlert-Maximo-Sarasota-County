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
    meters = distance_m(coordinates(sa["DESCRIPTION_LONGDESCRIPTION"]), coordinates(sb["DESCRIPTION_LONGDESCRIPTION"]))
    days = abs((datetime.fromisoformat(sa["REPORTDATE"]) - datetime.fromisoformat(sb["REPORTDATE"])).total_seconds()) / 86400
    return duplicate_score(ai, meters, days)


def _related_srs(ticket):
    return [t for t in KEY[ticket]["RELATED_RECORDS"].split(";") if t.startswith("SR")]


def _pairs(scenario_word):
    return [(t, r) for t, row in KEY.items() if scenario_word in row["SCENARIO"] for r in _related_srs(t)]


def test_reads_the_map_link():
    lat, lon = coordinates(SRS["SR800044"]["DESCRIPTION_LONGDESCRIPTION"])
    assert (lat, lon) == pytest.approx((27.05563, -82.398293))
    assert coordinates(SRS["SR800005"]["DESCRIPTION_LONGDESCRIPTION"]) is None
    assert coordinates("") is None and coordinates(None) is None


def test_distance_between_the_gulfwren_and_willowmarsh_sewer_odors():
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR800044", "SR800025"))
    assert distance_m(a, b) == pytest.approx(6107, abs=25)
    assert distance_m(a, a) == 0
    assert distance_m(a, None) is None


def test_same_type_at_another_address_scores_40_to_50_on_location_alone():
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR800044", "SR800025"))
    assert 40 <= duplicate_score(93, distance_m(a, b), 0) <= 50
    assert _score("SR800044", "SR800025", 93) < 40  # and lower again, 25 days apart


def test_the_true_duplicate_keeps_its_ai_score():
    assert _score("SR800044", "SR800046", 97) == 97


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
    a, b = (coordinates(SRS[t]["DESCRIPTION_LONGDESCRIPTION"]) for t in ("SR800044", "SR800025"))
    assert deductions(93, distance_m(a, b), 25) == (33, 46, 14)
    assert deductions(97, 12, 2) == (97, 0, 0)
    assert deductions(92, 30, 42) == (64, 0, 28)


def test_an_sr_without_a_map_link_ranks_below_located_matches():
    assert duplicate_score(97, None, 0) < SHOW_AT
    assert duplicate_score(97, None, 0) > duplicate_score(97, 5000, 0)
