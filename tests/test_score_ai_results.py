import csv

from loader.config import DATA_DIR  # puts scripts/ on the path

import score_ai_results as score

ANSWERS = score.read(DATA_DIR / "answer-key.csv")
WOS = score.read(DATA_DIR / "maximo" / "wo.csv")
DRAFTS = score.read(DATA_DIR / "maximo" / "drafts" / "wo.csv")
SRS = score.read(DATA_DIR / "maximo" / "sr.csv")
BY_ID = {a["TICKETID"]: a for a in ANSWERS}
MISFILED = next(a for a in ANSWERS if "Suggested reclassification:" in a["EXPECTED_RECOMMENDATION"])
WITH_WOS = next(a for a in ANSWERS if len(score.expected_wos(a, score.own_wos(WOS))) >= 2)
CONTROL = next(a for a in ANSWERS if a["USE_CASE"] == score.CONTROL)


def _row(ticket, feature, value="", decision="", reason=""):
    return {"TICKETID": ticket, "FEATURE": feature, "AI_VALUE": value, "AI_SCORE": "",
            "REVIEWER_DECISION": decision, "OVERRIDE_REASON": reason}


def _report(rows):
    report, problems = score.score(rows, ANSWERS, WOS)
    assert problems == []
    return "\n".join(report)


def test_classification_is_compared_by_name_and_counts_corrections():
    name = score.cat.CLASSIFICATIONS[MISFILED["EXPECTED_CLASSSTRUCTUREID"]][0]
    others = [a for a in ANSWERS if a is not MISFILED]
    report = _report([_row(MISFILED["TICKETID"], "classification", name.lower(), "accept"),
                      _row(others[0]["TICKETID"], "classification", others[0]["EXPECTED_CLASSSTRUCTUREID"]),
                      _row(others[1]["TICKETID"], "classification", "none"),
                      _row(others[2]["TICKETID"], "classification", "n/a"),
                      _row(others[3]["TICKETID"], "classification", "")])
    assert "scored 3; not tried yet 1; not available 1" in report
    assert "recommendation given   2/3" in report and "matches the answer key 2/3" in report
    assert "misclassified SRs corrected 1/1" in report


def test_a_maximo_numeric_class_id_is_refused_with_a_hint():
    _, problems = score.score([_row(CONTROL["TICKETID"], "classification", "1234")], ANSWERS, WOS)
    assert len(problems) == 1 and "classification name" in problems[0]


def test_team_accepts_the_eight_character_maximo_code():
    sewer = next(a for a in ANSWERS if a["EXPECTED_PERSONGROUP"] == "SANCLINSP")
    report = _report([_row(sewer["TICKETID"], "team", "SANCLINS", "override", "wrong crew")])
    assert "matches the answer key 1/1" in report and "1 x wrong crew" in report


def test_similar_work_orders_report_recall_and_control_noise():
    wanted = sorted(score.expected_wos(WITH_WOS, score.own_wos(WOS)))
    other_control = next(a for a in ANSWERS if a["USE_CASE"] == score.CONTROL and a is not CONTROL)
    report = _report([_row(WITH_WOS["TICKETID"], "similar_wo", f"{wanted[0]};WO2999999"),
                      _row(CONTROL["TICKETID"], "similar_wo", "WO2900001"),
                      _row(other_control["TICKETID"], "similar_wo", "none")])
    assert f"related WOs surfaced    1/{len(wanted)}" in report
    assert "SRs with every related WO 0/1" in report and "control SRs with any match 1/2" in report


def test_an_srs_own_work_order_is_never_counted_as_similar():
    own = score.own_wos(WOS)
    dispatched = next(a for a in ANSWERS if own.get(a["TICKETID"], set()) & set(a["RELATED_RECORDS"].split(";")))
    assert not score.expected_wos(dispatched, own) & own[dispatched["TICKETID"]]
    report = _report([_row(dispatched["TICKETID"], "similar_wo", ";".join(own[dispatched["TICKETID"]]))])
    assert "across 0 SRs" in report


def test_rows_that_do_not_fit_the_answer_key_are_rejected():
    rows = [_row("SR123", "classification"), _row(CONTROL["TICKETID"], "colour"),
            _row(CONTROL["TICKETID"], "team", decision="maybe"),
            _row(CONTROL["TICKETID"], "classification"), _row(CONTROL["TICKETID"], "classification")]
    _, problems = score.score(rows, ANSWERS, WOS)
    assert len(problems) == 4 and any("appears twice" in p for p in problems)


def test_an_answer_key_without_the_expected_class_column_says_how_to_refresh_it():
    old = [{k: v for k, v in a.items() if k != "EXPECTED_CLASSSTRUCTUREID"} for a in ANSWERS]
    _, problems = score.score([], old, WOS)
    assert "load --apply" in problems[0]


def test_an_excel_utf8_sheet_with_a_byte_order_mark_and_short_rows_reads(tmp_path):
    path = tmp_path / "results.csv"
    path.write_text("﻿TICKETID,FEATURE,AI_VALUE\n" f"{CONTROL['TICKETID']},classification\n", encoding="utf-8")
    rows = score.read(path)
    assert rows[0]["TICKETID"] == CONTROL["TICKETID"] and rows[0]["AI_VALUE"] == ""
    assert "scored 0; not tried yet 1" in _report(rows)


def test_template_covers_every_sr_and_a_blank_sheet_scores(tmp_path):
    path = tmp_path / "results.csv"
    assert score.main(["--template", str(path)]) == 0
    rows = list(csv.DictReader(path.open()))
    assert {r["TICKETID"] for r in rows if r["FEATURE"] == "classification"} == set(BY_ID)
    assert score.main([str(path)]) == 0


def test_duplicate_clusters_come_from_the_answer_key_scenario():
    group = score.clusters(ANSWERS)
    assert group["SR800031"] == {"SR800030", "SR800032"} and group["SR800046"] == {"SR800044"}
    assert "SR800059" not in group  # a look-alike is not in the cluster it resembles


def test_similar_service_requests_report_grouping_look_alikes_and_noise():
    other_control = next(a for a in ANSWERS if a["USE_CASE"] == score.CONTROL and a is not CONTROL)
    report = _report([_row("SR800031", "similar_sr", "SR800030;SR800059;SR800031", "accept"),
                      _row("SR800046", "similar_sr", "none"),
                      _row("SR800059", "similar_sr", "SR800030"),
                      _row("SR800060", "similar_sr", "n/a"),
                      _row(CONTROL["TICKETID"], "similar_sr", "SR800044"),
                      _row(other_control["TICKETID"], "similar_sr", "none")])
    assert "scored 5; not tried yet 0; not available 1" in report
    assert "reports matched to their duplicate group 1/2" in report
    assert "duplicates shown their first report (the Global Issue) 1/2" in report
    assert "group members surfaced   1/3" in report  # SR800031's own number is not a match
    assert "look-alikes wrongly matched to the group they resemble (lower is better) 1/1" in report
    assert "control SRs with any match (lower is better) 1/2" in report


def test_a_look_alike_matched_only_to_a_clusters_duplicate_report_still_counts_as_wrong():
    report = _report([_row("SR800060", "similar_sr", "SR800054;SR800055"), _row("SR800042", "similar_sr", "SR800041")])
    assert "look-alikes wrongly matched to the group they resemble (lower is better) 2/2" in report


def test_a_team_row_on_a_duplicate_is_left_out_of_the_score():
    report = _report([_row("SR800031", "team", "WTRPIPE")])
    assert "scored 0; not tried yet 0" in report


def test_template_gives_duplicates_no_team_or_work_order_rows_and_open_srs_similar_sr_rows():
    rows = score.template(ANSWERS, WOS + DRAFTS, SRS)
    features = {}
    for r in rows:
        features.setdefault(r["TICKETID"], set()).add(r["FEATURE"])
    assert features["SR800031"] == {"classification", "similar_sr"}  # grouped, never dispatched on its own
    assert "similar_sr" in features["SR800044"] and "team" in features["SR800044"]  # cluster B's first report
    assert "similar_sr" not in features["SR800030"]  # resolved, so not in the inference filter
    assert "similar_sr" in features["SR800042"]  # look-alike
