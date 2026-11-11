import pytest
from conftest import API_KEY, BASE, FakeResponse, FakeSession

from loader.client import MaximoClient, MaximoError, _RebasingSession, describe_failure, maximo_error, rebase_url
from loader.config import load_settings


def test_rebase_rewrites_internal_links_to_the_public_route():
    session = _RebasingSession(BASE)
    internal = "http://localhost:9080/maximo/api/os/mxapisr/_U1I4MDAwMDE-?lean=1"
    assert session.rebase(internal) == "https://manage.example.test/maximo/api/os/mxapisr/_U1I4MDAwMDE-?lean=1"


def test_rebase_leaves_other_paths_and_relative_links_alone():
    assert rebase_url("https://other.test/elsewhere/x", "https", "manage.example.test", "/maximo") == \
        "https://other.test/elsewhere/x"
    assert rebase_url("/maximo/api/os/mxapisr", "https", "manage.example.test", "/maximo") == "/maximo/api/os/mxapisr"


def test_maximo_error_envelope_is_reported_verbatim():
    resp = FakeResponse(400, {"Error": {"reasonCode": "BMXAA4195E", "message": "A value is required."}})
    assert maximo_error(resp) == "BMXAA4195E - A value is required."
    assert describe_failure(resp) == "400 BMXAA4195E - A value is required."


def test_html_login_page_is_named_as_such():
    resp = FakeResponse(200, text="<html>Log in</html>", content_type="text/html", url=f"{BASE}/oidc/login")
    assert "received HTML, not JSON" in describe_failure(resp)
    client = MaximoClient(BASE, API_KEY, session=FakeSession(lambda *a: resp))
    with pytest.raises(MaximoError, match="login page"):
        client.whoami()


def test_every_call_sends_lean_and_the_key_header():
    session = FakeSession(lambda *a: FakeResponse(body={"member": []}))
    client = MaximoClient(BASE, API_KEY, session=session)
    client.query("mxapisr", where='siteid="SRQSITE"', select="ticketid")
    method, url, params, _, _ = session.calls[0]
    assert (method, url) == ("GET", f"{BASE}/api/os/mxapisr")
    assert params["lean"] == "1" and params["oslc.where"] == 'siteid="SRQSITE"'
    assert session.headers["apikey"] == API_KEY


def test_query_follows_next_page_links(fake_maximo):
    fake = fake_maximo({"mxapiperson": [{"personid": f"P{i:02d}"} for i in range(7)]}, page_size=3)
    rows = fake.client().query("mxapiperson", select="personid")
    assert [r["personid"] for r in rows] == [f"P{i:02d}" for i in range(7)]
    assert len(fake.session.calls) == 3


def test_query_limit_stops_paging(fake_maximo):
    fake = fake_maximo({"mxapiperson": [{"personid": f"P{i:02d}"} for i in range(7)]}, page_size=3)
    assert len(fake.client().query("mxapiperson", limit=4)) == 4
    assert len(fake.session.calls) == 2


def test_count_uses_total_count(fake_maximo):
    fake = fake_maximo({"mxapisr": [{"siteid": "SRQSITE"}] * 5 + [{"siteid": "OTHER"}]})
    assert fake.client().count("mxapisr", 'siteid="SRQSITE"') == 5


def test_writes_use_the_documented_headers():
    session = FakeSession(lambda *a: FakeResponse(body={"href": "h"}))
    client = MaximoClient(BASE, API_KEY, session=session)
    client.create("mxapisr", {"ticketid": "SR1"})
    client.merge(f"{BASE}/api/os/mxapisr/abc", {"description": "x"})
    client.action(f"{BASE}/api/os/mxapiwodetail/abc", "changeStatus", {"status": "COMP"})
    (_, _, _, h_create, p_create), (_, _, _, h_merge, _), (_, _, p_action, h_action, _) = session.calls
    assert h_create["properties"] == "*" and p_create == {"ticketid": "SR1"}
    assert h_merge["x-method-override"] == "PATCH" and h_merge["patchtype"] == "MERGE"
    assert p_action["action"] == "wsmethod:changeStatus" and h_action["x-method-override"] == "PATCH"


def test_unreachable_host_error_names_no_secret():
    import requests

    def boom(*a):
        raise requests.ConnectionError(f"failed with apikey={API_KEY}")

    client = MaximoClient(BASE, API_KEY, session=FakeSession(boom))
    with pytest.raises(MaximoError) as e:
        client.whoami()
    assert API_KEY not in str(e.value)


def test_key_never_appears_in_repr():
    client = MaximoClient(BASE, API_KEY, session=FakeSession(lambda *a: FakeResponse()))
    settings = load_settings({"MAXIMO_URL": BASE + "/", "MAXIMO_API_KEY": API_KEY})
    assert API_KEY not in repr(client)
    assert API_KEY not in repr(settings) and API_KEY not in str(settings)
    assert settings.url == BASE and settings.api_path == "api" and settings.verify_tls


def test_missing_settings_name_the_variables_only():
    with pytest.raises(SystemExit) as e:
        load_settings({"MAXIMO_URL": BASE})
    assert "MAXIMO_API_KEY" in str(e.value)


def test_redirects_are_not_followed_and_name_the_target():
    resp = FakeResponse(302, text="", headers={"location": "https://auth.example.test/oidc/login"})
    session = FakeSession(lambda *a: resp)
    with pytest.raises(MaximoError, match="redirected to auth.example.test") as e:
        MaximoClient(BASE, API_KEY, session=session).whoami()
    assert API_KEY not in str(e.value) and not e.value.refused_by_maximo


def test_only_a_maximo_rejection_counts_as_refused():
    refused = FakeResponse(400, {"Error": {"reasonCode": "BMXAA4590E", "message": "no"}})
    client = MaximoClient(BASE, API_KEY, session=FakeSession(lambda *a: refused))
    with pytest.raises(MaximoError) as e:
        client.whoami()
    assert e.value.refused_by_maximo and e.value.status_code == 400
    timeout = FakeResponse(504, text="Gateway Timeout", content_type="text/plain")
    with pytest.raises(MaximoError) as e:
        MaximoClient(BASE, API_KEY, session=FakeSession(lambda *a: timeout)).whoami()
    assert not e.value.refused_by_maximo


def test_unsafe_where_literals_are_refused():
    from loader.client import oslc_str, quote_list
    assert oslc_str("SR810001") == '"SR810001"' and quote_list(["A", "B"]) == '["A","B"]'
    for bad in ('a"b', "50%", "caf\u00e9"):
        with pytest.raises(ValueError):
            oslc_str(bad)
