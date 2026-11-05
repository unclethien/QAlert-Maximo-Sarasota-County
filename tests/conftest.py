"""Offline doubles for the Maximo REST API. No test touches the network."""

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loader.client import MaximoClient  # noqa: E402

BASE = "https://manage.example.test/maximo"
API_KEY = "test-key-do-not-print-9f3a"


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None, content_type="application/json", url="", headers=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type, **(headers or {})}
        self.url = url
        self.text = text if text is not None else ("" if body is None else json.dumps(body))
        self.ok = 200 <= status_code < 400

    def json(self):
        return json.loads(self.text)


class FakeSession:
    """Records requests and answers each from `handler(method, url, params, headers, payload)`."""

    def __init__(self, handler):
        self.handler = handler
        self.headers = {}
        self.verify = True
        self.calls = []

    def request(self, method, url, params=None, headers=None, data=None, timeout=None, allow_redirects=True):
        assert allow_redirects is False, "the client must not follow redirects"
        query = dict(parse_qsl(urlsplit(url).query))
        params = {**query, **(params or {})}
        payload = json.loads(data) if data else None
        self.calls.append((method, url, params, headers or {}, payload))
        return self.handler(method, url, params, headers or {}, payload)


_COND = re.compile(r'^\s*(\w+)\s*(=|in)\s*(.+?)\s*$')


def _matches(record: dict, where: str | None) -> bool:
    """A small subset of oslc.where: `a="x"` and `a in ["x","y"]`, joined by `and`."""
    if not where:
        return True
    for cond in where.split(" and "):
        m = _COND.match(cond)
        assert m, f"unsupported where clause in fake: {cond!r}"
        field, op, raw = m.groups()
        value = str(record.get(field, ""))
        if op == "=":
            if value != json.loads(raw):
                return False
        elif value not in [str(v) for v in json.loads(raw)]:
            return False
    return True


class FakeMaximo:
    """An in-memory Maximo: `records[structure]` is a list of dicts with an `href`.

    POST creates, POST + x-method-override PATCH merges (child lists are extended, never
    replaced), and `?action=wsmethod:changeStatus` sets `status`. `refuse` holds structures
    whose writes are rejected with a BMXAA error.
    """

    def __init__(self, records=None, missing=(), whoami=None, page_size=None, refuse=(), renumber=False,
                 refuse_dated_status=False, lose_status_answers=0, refuse_status=None):
        self.records = {s: [self._with_href(s, i, r) for i, r in enumerate(rows)]
                        for s, rows in (records or {}).items()}
        self.missing = set(missing)
        self.refuse = set(refuse)
        self.renumber = renumber              # Maximo assigns its own TICKETID / WONUM
        self.refuse_dated_status = refuse_dated_status
        self.lose_status_answers = lose_status_answers  # apply the change, then answer 504 (n times)
        self.refuse_status = refuse_status or {}  # structure -> status values changeStatus rejects
        self.whoami = whoami or {"userName": "loader", "personid": "LOADER"}
        self.page_size = page_size
        self.session = FakeSession(self.handle)

    def client(self) -> MaximoClient:
        return MaximoClient(BASE, API_KEY, session=self.session)

    @staticmethod
    def _with_href(structure, i, record):
        return {"href": f"{BASE}/api/os/{structure}/_{i}", **record}

    def writes(self):
        return [c for c in self.session.calls if c[0] != "GET"]

    def handle(self, method, url, params, headers, payload):
        path = urlsplit(url).path
        if path.endswith("/api/whoami"):
            return FakeResponse(body=self.whoami, url=url)
        m = re.search(r"/api/os/(\w+)(/[^/]+)?$", path)
        assert m, f"unexpected url in fake: {url}"
        structure, record_id = m.group(1), m.group(2)
        if structure in self.missing or structure not in self.records:
            return FakeResponse(404, {"Error": {"reasonCode": "BMXAA9301E",
                                                "message": f"The object structure {structure.upper()} was not found."}}, url=url)
        if method == "POST":
            return self._write(structure, url, record_id, params, headers, payload)
        if record_id is not None:
            record = next((r for r in self.records[structure] if r["href"] == url.split("?")[0]), None)
            return FakeResponse(body=record, url=url) if record else FakeResponse(404, {"Error": {
                "reasonCode": "BMXAA8727E", "message": "The record was not found."}}, url=url)
        rows = [r for r in self.records[structure] if _matches(r, params.get("oslc.where"))]
        size = int(params.get("oslc.pageSize", 0)) or self.page_size or len(rows) or 1
        if self.page_size:
            size = min(size, self.page_size)
        page = int(params.get("pageno", 1))
        chunk = rows[(page - 1) * size: page * size]
        body = {"member": chunk, "responseInfo": {}}
        if params.get("collectioncount") == "1":
            body["responseInfo"]["totalCount"] = len(rows)
        if page * size < len(rows):
            query = {"pageno": page + 1, "oslc.pageSize": size, "oslc.where": params.get("oslc.where", "")}
            # Manage builds links from its internal address, as it does behind an OpenShift route.
            body["responseInfo"]["nextPage"] = {
                "href": f"http://localhost:9080/maximo/api/os/{structure}?{urlencode(query)}"}
        return FakeResponse(body=body, url=url)


    def _write(self, structure, url, record_id, params, headers, payload):
        if structure in self.refuse:
            return FakeResponse(400, {"Error": {"reasonCode": "BMXAA4195E", "message": "A value is required."}}, url=url)
        rows = self.records[structure]
        if record_id is None:
            payload = dict(payload)
            initial = {"mxapisr": "NEW", "mxapiwodetail": "WAPPR"}.get(structure)
            if initial:
                payload.setdefault("status", initial)
            if self.renumber:
                for key in ("ticketid", "wonum"):
                    if key in payload:
                        payload[key] = str(5000 + len(rows))
            record = self._with_href(structure, len(rows), payload)
            rows.append(record)
            return FakeResponse(201, body=record, url=url)
        assert headers.get("x-method-override") == "PATCH", "updates must be PATCH overrides"
        record = next(r for r in rows if r["href"] == url.split("?")[0])
        if params.get("action") == "wsmethod:changeStatus":
            if payload["status"] in self.refuse_status.get(structure, ()):
                return FakeResponse(400, {"Error": {"reasonCode": "BMXAA4295E",
                                                    "message": f"Status {payload['status']} is not in the value list."}},
                                    url=url)
            if self.refuse_dated_status and "date" in payload:
                return FakeResponse(400, {"Error": {"reasonCode": "BMXAA4590E",
                                                    "message": "The status date cannot be in the past."}}, url=url)
            if record.get("status") == payload["status"]:
                return FakeResponse(400, {"Error": {"reasonCode": "BMXAA4590E",
                                                    "message": "The record is already in this status."}}, url=url)
            record["status"] = payload["status"]
            record["statusdate"] = payload.get("date", "2026-11-06T15:00:00+00:00")
            if self.lose_status_answers:
                self.lose_status_answers -= 1
                return FakeResponse(504, text="Gateway Timeout", content_type="text/plain", url=url)
            return FakeResponse(204, text="", url=url)
        assert headers.get("patchtype") == "MERGE", "a PATCH without MERGE deletes children"
        for key, value in payload.items():
            if isinstance(value, list):
                record.setdefault(key, []).extend(value)
            else:
                record[key] = value
        return FakeResponse(204, text="", url=url)


@pytest.fixture
def fake_maximo():
    return FakeMaximo
