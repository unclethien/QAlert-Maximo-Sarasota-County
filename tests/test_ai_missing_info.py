"""The watsonx.ai missing-information check, without calling watsonx.ai or Maximo."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ai_missing_info as ami  # noqa: E402

SRS = {s["ticketid"]: s for s in ami.srs_from_csv(ROOT / "data" / "maximo" / "sr.csv")}
POINTS = ami.load_address_points()


class FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def chat(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def test_the_text_sent_leaves_out_the_residents_contact_line():
    sr = SRS["SR810001"]
    text = ami.request_text(sr["description"], sr["longdesc"])
    assert "THERESA SHEFFIELD" not in text and "941-555-0123" not in text and "@" not in text
    assert text.startswith("Water Line Leak, Fennimore Pines Blvd")
    assert "Leak in the grass next to the sidewalk" in text
    assert "Map" not in text.split("\n")[1]


def test_the_model_checks_one_issue_and_the_type_rule_but_not_the_record_rules():
    assert [r for r, _ in ami.model_rules("9105")] == ["ONE-ISSUE", "METER-PROBLEM"]
    assert [r for r, _ in ami.model_rules("9203")] == ["ONE-ISSUE"]  # LS-ID is decided by the record
    assert [r for r, _ in ami.model_rules("9401")] == ["ONE-ISSUE"]  # no Utilities rule for drainage


def test_a_misspelled_street_gets_the_county_spelling_with_the_residents_own_house_number():
    hint = ami.address_hint(SRS["SR810002"]["address"], POINTS)
    assert "2496 Sandpiper Glen Way, Sarasota" in hint


def test_an_unknown_house_number_gets_the_streets_range_and_no_proposed_number():
    hint = ami.address_hint(SRS["SR810033"]["address"], POINTS)
    assert "Wrenhaven Pl" in hint and "9870 is not in the file" in hint
    assert "9870 Wrenhaven" not in hint


def test_no_hint_without_a_house_number_or_for_a_known_address():
    assert ami.address_hint(SRS["SR810001"]["address"], POINTS) == ""  # street only: never guess a number
    assert ami.address_hint({"number": "2496", "street": "Sandpiper Glen Way", "code": ""}, POINTS) == ""
    assert ami.address_hint({"number": "1", "street": "X", "code": "AP00001"}, POINTS) == ""


def test_srs_from_maximo_find_the_catalog_code_from_the_classification_name():
    class Client:
        def query(self, *a, **k):
            return [{"ticketid": "SR810020", "status": "QUEUED", "description": "Lift Station Alarm", "href": "h",
                     "classstructureid": "1033", "classstructure": {"hierarchypath": "WW-LIFT"},
                     "tkserviceaddress": [{"city": "NORTH PORT"}]}]

    sr = ami.srs_from_maximo(Client())[0]
    assert sr["classid"] == "9203" and sr["address"]["city"] == "NORTH PORT"
    assert ami.request_type(sr["classid"]) == "Lift Station Alarm"


def test_gaps_off_the_list_or_without_quoted_evidence_are_dropped():
    text = "Water Meter Issue, 7018 Aldersea Cir\nCustomer has a question about the meter."
    reply = {"gaps": [
        {"rule": "METER-PROBLEM", "evidence": "Customer has a question about the meter.", "reason": "vague"},
        {"rule": "LEAK-WHERE", "evidence": "the meter", "reason": "not this type"},
        {"rule": "ONE-ISSUE", "evidence": "two problems here", "reason": "made up"},
        {"rule": "METER-PROBLEM", "evidence": "the meter", "reason": "duplicate"},
        {"rule": "ONE-ISSUE", "evidence": "the meter", "reason": "minor", "blocks_dispatch": False},
    ]}
    kept, dropped = ami.check_reply(reply, {"ONE-ISSUE", "METER-PROBLEM"}, text)
    assert [g["rule"] for g in kept] == ["METER-PROBLEM"]
    assert [(g["rule"], g["why"]) for g in dropped] == [
        ("LEAK-WHERE", "not a rule for this request"), ("ONE-ISSUE", "evidence not quoted from the request"),
        ("ONE-ISSUE", "a secondary detail; does not block dispatch")]


def test_a_number_in_the_question_must_come_from_the_request_or_the_address_file():
    assert ami.invented_numbers("Is it 2496 Sandpiper Glen Way?", "2496 Sandpiper Glenn Way") == []
    assert ami.invented_numbers("Is it 2500 Sandpiper Glen Way?", "2496 Sandpiper Glenn Way", "") == ["2500"]


def test_parse_reply_tolerates_code_fences():
    assert ami.parse_reply('```json\n{"gaps": [], "question": ""}\n```') == {"gaps": [], "question": ""}


def test_check_sr_combines_the_rules_the_lookup_and_the_model():
    model = FakeModel(json.dumps({"gaps": [], "question": "Could you confirm the address is 2496 Sandpiper Glen Way?"}))
    r = ami.check_sr(SRS["SR810002"], POINTS, model)
    assert [g for g, _ in r["known"]] == ["ADDR-VALID"]
    assert "Sandpiper Glen Way" in r["hint"] and r["invented"] == [] and r["error"] == ""
    assert "ADDR-VALID" in model.prompts[0] and "HAROLD PEMBERTON" not in model.prompts[0]


def test_an_sr_with_only_secondary_gaps_gets_no_question():
    model = FakeModel(json.dumps({"question": "When did it start?", "gaps": [
        {"rule": "LEAK-WHERE", "evidence": "Water Line Leak", "reason": "timing", "blocks_dispatch": False}]}))
    r = ami.check_sr(SRS["SR810003"], POINTS, model)
    assert r["kept"] == [] and r["question"] == "" and r["dropped"][0]["rule"] == "LEAK-WHERE"


def test_a_reply_that_is_not_json_is_an_error_not_a_crash():
    r = ami.check_sr(SRS["SR810003"], POINTS, FakeModel("I cannot help with that."))
    assert r["error"] and r["kept"] == []


def test_score_counts_found_missed_and_wrong_flags_against_the_answer_key():
    key = {"A": {"ADDR"}, "B": {"ONE-ISSUE"}, "C": set()}
    results = [
        {"ticketid": "A", "known": [("ADDR", "")], "kept": [], "invented": [], "error": ""},
        {"ticketid": "B", "known": [], "kept": [{"rule": "ONE-ISSUE"}, {"rule": "METER-PROBLEM"}], "invented": [], "error": ""},
        {"ticketid": "C", "known": [], "kept": [{"rule": "LEAK-WHERE"}], "invented": ["12"], "error": ""},
    ]
    s = ami.score(results, key)
    assert (s["expected"], s["by_rules"], s["found"]) == (2, 1, 2)
    assert (s["complete"], s["complete_flagged"], s["extra"], s["invented"]) == (1, 1, 2, 1)


def test_the_answer_key_has_18_gaps_and_the_rules_alone_find_8():
    key = ami.load_answer_key()
    results = [{"ticketid": t, "known": ami.rules["find_gaps"](s["description"], s["longdesc"],
                                                             ami.cat.CLASSIFICATIONS[s["classid"]][0], s["address"]),
                "kept": [], "invented": [], "error": ""} for t, s in SRS.items()]
    s = ami.score(results, key)
    assert (s["expected"], s["by_rules"], s["complete"], s["complete_flagged"]) == (18, 8, 48, 0)


def test_results_csv_lists_missed_and_extra_gaps(tmp_path):
    out = tmp_path / "r.csv"
    ami.write_csv(out, [{"ticketid": "B", "status": "QUEUED", "known": [], "hint": "", "question": "q?",
                         "kept": [{"rule": "METER-PROBLEM", "evidence": "e", "reason": "r"}],
                         "dropped": [], "invented": [], "error": ""}], {"B": {"ONE-ISSUE"}})
    row = next(csv.DictReader(open(out)))
    assert (row["MISSED"], row["EXTRA"], row["AI_GAPS"]) == ("ONE-ISSUE", "METER-PROBLEM", "METER-PROBLEM")


def _result(ticket="SR810002", status="QUEUED", known=(), kept=(), question="", invented=(), error=""):
    return {"ticketid": ticket, "status": status, "known": list(known), "hint": "", "kept": list(kept),
            "dropped": [], "question": question, "invented": list(invented), "error": error}


class WriteClient:
    def __init__(self, worklogs=()):
        self.worklogs, self.merged = list(worklogs), []

    def query(self, structure, where=None, **k):
        assert structure == "mxapiworklog"
        return [w for w in self.worklogs if w["match"] in where]

    def merge(self, href, payload):
        self.merged.append((href, payload))


def test_load_notes_reads_missinfo_entries_and_ai_summaries():
    client = WriteClient([{"recordkey": "SR1", "description": "Missing information: ADDR", "match": 'logtype="MISSINFO"'},
                          {"recordkey": "SR2", "description": ami.WORKLOG_SUMMARY, "match": "AI check"}])
    assert ami.load_notes(client) == {"SR1": {"Missing information: ADDR"}, "SR2": {ami.WORKLOG_SUMMARY}}


def test_the_scheduled_run_skips_srs_already_checked():
    srs = [{"ticketid": "SR3"}, {"ticketid": "SR1"}, {"ticketid": "SR2"}]
    notes = {"SR2": {ami.WORKLOG_SUMMARY}, "SR3": {"Missing information: ADDR"}}
    assert [s["ticketid"] for s in ami.not_checked(srs, notes)] == ["SR1", "SR3"]


def test_each_gap_gets_its_own_missinfo_entry_and_the_summary_is_not_a_missinfo_entry():
    r = _result(known=[("ADDR", "No house number.")],
                kept=[{"rule": "ONE-ISSUE", "evidence": "and also", "reason": "Two problems."}], question="Which house?")
    entries = ami.worklog_entries(r, "m", noted={"Missing information: ADDR"})  # the launch point noted ADDR
    assert [(e["logtype"], e["description"]) for e in entries] == [
        ("MISSINFO", "Missing information: ONE-ISSUE"), ("UPDATE", ami.WORKLOG_SUMMARY)]
    assert not any(e["clientviewable"] for e in entries)
    assert "Question for the resident: Which house?" in entries[-1]["description_longdescription"]


def test_a_complete_sr_gets_only_the_summary():
    entries = ami.worklog_entries(_result(), "m", noted=set())
    assert [e["logtype"] for e in entries] == ["UPDATE"]
    assert "No missing information found." in entries[0]["description_longdescription"]


def test_a_question_with_an_invented_number_is_withheld_but_the_gaps_are_noted():
    r = _result(known=[("ADDR", "No house number.")], question="Is it 2500 Main St?", invented=["2500"])
    entries = ami.worklog_entries(r, "m", noted=set())
    assert entries[0]["description"] == "Missing information: ADDR"
    text = entries[-1]["description_longdescription"]
    assert "2500 Main" not in text and "withheld" in text


def test_apply_skips_closed_errored_and_already_checked_srs():
    client = WriteClient()
    srs = [{"ticketid": t, "href": "h/" + t} for t in ("SR1", "SR2", "SR3", "SR4")]
    results = [_result("SR1"), _result("SR2", status="CLOSED"), _result("SR3", error="timeout"), _result("SR4")]
    failed = ami.apply(client, srs, results, "m", notes={"SR4": {ami.WORKLOG_SUMMARY}})
    assert failed == 0 and [h for h, _ in client.merged] == ["h/SR1"]
