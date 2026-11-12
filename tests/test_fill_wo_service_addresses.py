"""Filling the loaded WOs' service addresses from the dataset, with no network."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fill_wo_service_addresses as fill_wo  # noqa: E402
from loader import mapping  # noqa: E402
from loader.client import MaximoError  # noqa: E402
from loader.load import Dataset  # noqa: E402

CHILD = mapping.WO_ADDRESS_CHILD
ADDRESS = {"staddrnumber": "7042", "staddrstreet": "Hollowpine Cir", "streetaddress": "7042 Hollowpine Cir",
           "city": "Sarasota", "stateprovince": "FL", "postalcode": "34241", "country": "US",
           "latitudey": 27.297222, "longitudex": -82.494813}


class StubMaximo:
    """Holds each WO's address rows by href; a merge replaces the one row, as TechZone does."""

    def __init__(self, rows, refuse=()):
        self.rows, self.refuse, self.merges = rows, set(refuse), []

    def merge(self, href, payload):
        self.merges.append((href, payload))
        if href in self.refuse:
            raise MaximoError("BMXAA0024E - the record is in history", 400, "BMXAA0024E")
        self.rows[href] = [dict(payload[CHILD][0], city=payload[CHILD][0]["city"].upper())]
        return {}

    def get(self, href, select="*"):
        return {CHILD: self.rows[href]}


def loaded(stub, **status):
    return [{"wonum": w, "externalrefid": w, "status": status.get(w, "WAPPR"), "href": h, CHILD: stub.rows[h]}
            for w, h in (("WO2910001", "h1"), ("WO2915021", "h2"))]


def run(stub, wanted, apply=False, **status):
    lines, backups = [], []
    result = fill_wo.fill(wanted, loaded(stub, **status), stub, apply=apply, backup=backups.append,
                          report=lines.append)
    return result, lines, backups


def test_every_pilot_wo_and_draft_has_an_address_to_fill():
    wanted = fill_wo.wanted_addresses(Dataset().wos + Dataset(name="drafts").wos)
    assert len(wanted) == 76 and all("saddresscode" not in a for a in wanted.values())
    assert sum("latitudey" in a for a in wanted.values()) == 74


def test_a_preview_writes_nothing_and_takes_no_backup():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [{"woserviceaddressid": 2}]})
    (changed, same, failed), lines, backups = run(stub, {"WO2910001": ADDRESS, "WO2915021": ADDRESS})
    assert (changed, same, failed) == (2, 0, 0) and stub.merges == [] and backups == []
    assert all(line.strip().startswith("WOULD") for line in lines)


def test_apply_backs_up_then_merges_each_changed_wo_and_skips_a_match_regardless_of_case():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [dict(ADDRESS, city="SARASOTA")]})
    (changed, same, failed), _, backups = run(stub, {"WO2910001": ADDRESS, "WO2915021": ADDRESS}, apply=True)
    assert (changed, same, failed) == (1, 1, 0)
    assert stub.merges == [("h1", {CHILD: [ADDRESS]})]
    assert backups == [[{"wonum": "WO2910001", "externalrefid": "WO2910001", "href": "h1",
                         CHILD: [{"woserviceaddressid": 1}]}]]
    (changed, same, failed), _, backups = run(stub, {"WO2910001": ADDRESS, "WO2915021": ADDRESS}, apply=True)
    assert (changed, same, failed) == (0, 2, 0) and backups == []  # a second run changes nothing


def test_a_refused_merge_a_missing_wo_and_two_rows_are_failures():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [{"woserviceaddressid": 2}, {"woserviceaddressid": 3}]},
                      refuse={"h1"})
    (changed, same, failed), lines, _ = run(stub, {"WO2910001": ADDRESS, "WO2915021": ADDRESS, "WO2919999": ADDRESS},
                                            apply=True)
    assert (changed, same, failed) == (0, 0, 3)
    assert any("WO2910001 (WAPPR)" in line and "BMXAA0024E" in line for line in lines)
    assert any("WO2915021" in line and "2 address rows" in line for line in lines)
    assert any("WO2919999" in line and "not in Maximo" in line for line in lines)


def test_a_merge_that_does_not_stick_is_a_failure():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": []})
    stub.get = lambda href, select="*": {CHILD: [{"woserviceaddressid": 1}]}  # Maximo kept the old row
    (changed, same, failed), lines, _ = run(stub, {"WO2910001": ADDRESS}, apply=True)
    assert (changed, failed) == (0, 1) and "service address staddrstreet" in lines[0]


def test_a_wo_in_history_is_reported_without_a_merge_unless_it_already_matches():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [dict(ADDRESS)]})
    (changed, same, failed), lines, backups = run(stub, {"WO2910001": ADDRESS, "WO2915021": ADDRESS}, apply=True,
                                                  WO2910001="CLOSE", WO2915021="CAN")
    assert (changed, same, failed) == (0, 1, 1) and stub.merges == [] and backups == []
    assert "WO2910001 (CLOSE) - in history" in lines[0]


class StubScript:
    """The SRQFILLWOADDR script: fills (or would fill) each WO it is sent, as `outcome` says."""

    def __init__(self, stub, outcome=None):
        self.stub, self.outcome, self.calls = stub, outcome or {}, []

    def __call__(self, addresses, apply):
        self.calls.append((sorted(addresses), apply))
        for wonum, address in addresses.items():
            if apply and wonum not in self.outcome:
                self.stub.rows[{"WO2910001": "h1", "WO2915021": "h2"}[wonum]] = [dict(address)]
        return {w: self.outcome.get(w, "filled" if apply else "would fill") for w in addresses}


def test_with_history_a_closed_wo_goes_through_the_script_is_backed_up_and_read_back():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [{"woserviceaddressid": 2}]})
    script = StubScript(stub)
    lines, backups = [], []
    wanted = {"WO2910001": ADDRESS, "WO2915021": ADDRESS}
    result = fill_wo.fill(wanted, loaded(stub, WO2910001="CLOSE"), stub, apply=False, backup=backups.append,
                          report=lines.append, history=script)
    assert result == (2, 0, 0) and stub.merges == [] and backups == [] and script.calls == [(["WO2910001"], False)]
    assert "WO2910001 (CLOSE) via script" in lines[-1]
    result = fill_wo.fill(wanted, loaded(stub, WO2910001="CLOSE"), stub, apply=True, backup=backups.append,
                          report=lines.append, history=script)
    assert result == (2, 0, 0) and [h for h, _ in stub.merges] == ["h2"]  # the open WO by merge only
    assert [r["externalrefid"] for r in backups[0]] == ["WO2915021", "WO2910001"]
    assert stub.rows["h1"] == [ADDRESS]


def test_a_script_refusal_or_a_script_error_is_a_failure():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [{"woserviceaddressid": 2}]})
    script = StubScript(stub, {"WO2910001": "2 address rows; expected one"})
    lines = []
    assert fill_wo.fill({"WO2910001": ADDRESS}, loaded(stub, WO2910001="CLOSE"), stub, apply=True,
                        report=lines.append, history=script) == (0, 0, 1)
    assert "via script - 2 address rows" in lines[0]

    def broken(addresses, apply):
        raise MaximoError("BMXAA7837E - ImportError", 400, "BMXAA7837E")
    lines = []
    assert fill_wo.fill({"WO2910001": ADDRESS}, loaded(stub, WO2910001="CAN"), stub, report=lines.append,
                        history=broken) == (0, 0, 1)
    assert "BMXAA7837E" in lines[0]


class ScriptRecords:
    """MXAPIAUTOSCRIPT as the history_script context sees it."""

    def __init__(self, existing=False):
        self.records = [{"autoscript": "SRQFILLWOADDR", "href": "s0"}] if existing else []
        self.created, self.deleted, self.sent = [], [], []

    def query(self, structure, where=None, select="*", page_size=200, limit=None):
        return list(self.records)

    def create(self, structure, payload):
        self.created.append(payload)
        self.records.append({"autoscript": payload["autoscript"], "href": "s1"})

    def delete(self, href):
        self.deleted.append(href)
        self.records = [r for r in self.records if r["href"] != href]

    def script(self, name, payload):
        self.sent.append((name, payload))
        return {"WO2910001": "would fill"}


def test_the_history_script_is_created_from_the_file_and_removed_even_after_a_failure():
    maximo = ScriptRecords()
    with pytest.raises(RuntimeError):
        with fill_wo.history_script(maximo) as history:
            assert history({"WO2910001": ADDRESS}, False) == {"WO2910001": "would fill"}
            raise RuntimeError("the run broke")
    assert maximo.created[0]["source"] == fill_wo.SCRIPT_SOURCE.read_text()
    assert maximo.sent == [("SRQFILLWOADDR", {"apply": False, "wos": {"WO2910001": ADDRESS}})]
    assert maximo.deleted == ["s1"] and maximo.records == []


def test_a_leftover_history_script_stops_the_run_untouched():
    maximo = ScriptRecords(existing=True)
    with pytest.raises(MaximoError):
        with fill_wo.history_script(maximo):
            pass
    assert maximo.created == [] and maximo.deleted == []


class LostReply(ScriptRecords):
    """Maximo stores the script, but the reply never arrives."""

    def create(self, structure, payload):
        super().create(structure, payload)
        raise MaximoError("cannot reach Maximo at https://manage.example.test: ReadTimeout")


def test_a_script_stored_without_a_reply_is_still_removed():
    maximo = LostReply()
    with pytest.raises(MaximoError):
        with fill_wo.history_script(maximo):
            pass
    assert maximo.deleted == ["s1"] and maximo.records == []


def test_a_failed_cleanup_does_not_hide_the_runs_error(capsys):
    maximo = ScriptRecords()
    maximo.delete = lambda href: (_ for _ in ()).throw(MaximoError("403 not allowed"))
    with pytest.raises(RuntimeError, match="the run broke"):
        with fill_wo.history_script(maximo):
            raise RuntimeError("the run broke")
    assert "Delete it in Automation Scripts" in capsys.readouterr().out


def test_a_number_carried_by_two_wos_is_a_failure():
    stub = StubMaximo({"h1": [{"woserviceaddressid": 1}], "h2": [{"woserviceaddressid": 2}]})
    twins = [{"wonum": w, "externalrefid": "WO2910001", "status": "WAPPR", "href": h, CHILD: stub.rows[h]}
             for w, h in (("1001", "h1"), ("1002", "h2"))]
    lines = []
    assert fill_wo.fill({"WO2910001": ADDRESS}, twins, stub, apply=True, report=lines.append) == (0, 0, 1)
    assert stub.merges == [] and "2 WOs in Maximo carry this number" in lines[0]


def test_only_with_an_unknown_number_stops_before_reaching_maximo(monkeypatch):
    monkeypatch.setattr(fill_wo, "load_settings", lambda: pytest.fail("must not connect"))
    with pytest.raises(SystemExit, match="WO291001"):
        fill_wo.main(["--only", "WO291001"])
