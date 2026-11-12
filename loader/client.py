"""Thin Maximo Manage REST client.

Ported from the BCPS ingestion project (bcps_maximo/ingest/maximo_api.py) so connection,
URL handling, and error reporting behave the same way:

- authentication is an API key in the `apikey` header;
- every call sends `lean=1`, so attributes are plain names and collections come back as
  `member` with `href` links;
- Manage builds `href` links from its internal address behind an OpenShift route, so links
  are rewritten to the address we connected to;
- Maximo's error envelope (`BMXAA...` reason code and message) is surfaced verbatim, and an
  HTML login page is reported as such instead of as a JSON decode error.

Updates are POST + `x-method-override: PATCH` + `patchtype: MERGE`. Without MERGE, a PATCH
deletes child rows (work logs, sites, synonym values) that are absent from the payload.
"""

import json
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import requests

JsonDict = dict[str, Any]


class MaximoError(RuntimeError):
    """A request Maximo refused, with the best available explanation.

    `status_code` is the HTTP status (None when Maximo was not reached) and `reason` is
    Maximo's own BMXAA error, when the response carried one.
    """

    def __init__(self, message: str, status_code: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code, self.reason = status_code, reason

    @property
    def refused_by_maximo(self) -> bool:
        """Maximo answered and rejected the request (not a timeout, redirect or server fault)."""
        return self.reason is not None and self.status_code is not None and 400 <= self.status_code < 500


class _RebasingSession(requests.Session):
    """Sends Maximo's own links back to the address we connected to."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        base = urlsplit(base_url)
        self._scheme, self._netloc, self._path = base.scheme, base.netloc, base.path.rstrip("/")

    def rebase(self, url: str) -> str:
        return rebase_url(url, self._scheme, self._netloc, self._path)

    def request(self, method, url, *args, **kwargs):  # type: ignore[override]
        return super().request(method, self.rebase(str(url)), *args, **kwargs)


def rebase_url(url: str, scheme: str, netloc: str, path: str) -> str:
    parts = urlsplit(url)
    if not parts.netloc or (parts.scheme, parts.netloc) == (scheme, netloc):
        return url
    if path and not (parts.path == path or parts.path.startswith(path + "/")):
        return url
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...
    @property
    def headers(self) -> Mapping[str, str]: ...
    @property
    def url(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def ok(self) -> bool: ...
    def json(self) -> object: ...


def maximo_error(resp: HttpResponse) -> str | None:
    """Maximo's `reasonCode - message`, if the response carries its error envelope."""
    if "json" not in resp.headers.get("content-type", "").lower():
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    error = body.get("Error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None
    parts = [str(p) for p in (error.get("reasonCode"), error.get("message")) if p]
    return " - ".join(parts) if parts else None


def describe_failure(resp: HttpResponse) -> str:
    detail = maximo_error(resp)
    if detail:
        return f"{resp.status_code} {detail}"
    content_type = resp.headers.get("content-type", "unknown")
    if "html" in content_type.lower():
        return (f"{resp.status_code} received HTML, not JSON (final URL: {resp.url}). The request was "
                "redirected to a login page, so the API key was never evaluated. Check that MAXIMO_URL "
                "is the Manage route ending in /maximo.")
    return f"{resp.status_code} {resp.text[:200]}"


def _members(body: object) -> list[JsonDict]:
    if not isinstance(body, dict):
        return []
    members = body.get("member")
    if not isinstance(members, list):
        members = body.get("rdfs:member")  # non-lean fallback
    return [m for m in members if isinstance(m, dict)] if isinstance(members, list) else []


def oslc_str(value) -> str:
    """An OSLC string literal. Quotes and `%` (which makes `=` a LIKE match) are refused."""
    text = str(value)
    if '"' in text or "%" in text or not text.isascii():
        raise ValueError(f"value not safe in an oslc.where literal: {text!r}")
    return f'"{text}"'


def quote_list(values) -> str:
    """An OSLC `in [...]` list of string literals."""
    return "[" + ",".join(oslc_str(v) for v in values) + "]"


class MaximoClient:
    def __init__(self, base_url: str, api_key: str, api_path: str = "api", timeout: int = 60,
                 verify_tls: bool = True, session: requests.Session | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_path = api_path.strip("/")
        self.timeout = timeout
        self.session = session if session is not None else _RebasingSession(self.base_url)
        self.session.verify = verify_tls
        self.session.headers.update({"apikey": api_key, "Content-Type": "application/json",
                                     "Accept": "application/json"})

    def __repr__(self) -> str:
        return f"MaximoClient({self.base_url!r})"

    # -- urls ------------------------------------------------------------
    def os_url(self, structure: str) -> str:
        return f"{self.base_url}/{self.api_path}/os/{structure}"

    # -- low level -------------------------------------------------------
    def _send(self, method: str, url: str, *, params: Mapping[str, str] | None = None,
              payload: JsonDict | None = None, headers: Mapping[str, str] | None = None) -> HttpResponse:
        merged = {"lean": "1", **(params or {})}
        try:
            # No redirects: requests re-sends custom headers such as `apikey` to the redirect
            # target, and a redirect here means the URL is wrong (usually a login page).
            resp = self.session.request(method, url, params=merged, headers=dict(headers or {}),
                                        data=json.dumps(payload) if payload is not None else None,
                                        timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as e:
            raise MaximoError(f"cannot reach Maximo at {self.base_url}: {type(e).__name__}") from None
        if 300 <= resp.status_code < 400:
            target = urlsplit(resp.headers.get("location", "")).netloc or "an unknown address"
            raise MaximoError(f"{resp.status_code} redirected to {target}. The API key was not sent on. Check that "
                              "MAXIMO_URL is the Manage route ending in /maximo.", resp.status_code)
        if not resp.ok or ("json" not in resp.headers.get("content-type", "").lower() and resp.text.strip()):
            raise MaximoError(describe_failure(resp), resp.status_code, maximo_error(resp))
        return resp

    @staticmethod
    def _body(resp: HttpResponse) -> JsonDict:
        if not resp.text.strip():
            return {}
        body = resp.json()
        return body if isinstance(body, dict) else {}

    # -- reads -----------------------------------------------------------
    def whoami(self) -> JsonDict:
        return self._body(self._send("GET", f"{self.base_url}/{self.api_path}/whoami"))

    def verify_connection(self, structure: str = "mxapiorganization") -> JsonDict:
        """One-row read to prove the route and key, then the identity behind the key."""
        self._send("GET", self.os_url(structure), params={"oslc.pageSize": "1", "oslc.select": "href"})
        return self.whoami()

    def probe(self, structure: str) -> tuple[bool, str]:
        """Whether an object structure answers a one-row read."""
        try:
            self._send("GET", self.os_url(structure), params={"oslc.pageSize": "1"})
            return True, ""
        except MaximoError as e:
            return False, str(e)

    def query(self, structure: str, where: str | None = None, select: str = "*",
              page_size: int = 200, limit: int | None = None) -> list[JsonDict]:
        """All matching records, following `responseInfo.nextPage.href`."""
        params = {"oslc.select": select, "oslc.pageSize": str(page_size)}
        if where:
            params["oslc.where"] = where
        out: list[JsonDict] = []
        url: str | None = self.os_url(structure)
        seen: set[str] = set()
        while url and url not in seen and (limit is None or len(out) < limit):
            seen.add(url)
            body = self._body(self._send("GET", url, params=params))
            out += _members(body)
            info = body.get("responseInfo")
            nxt = info.get("nextPage") if isinstance(info, dict) else None
            url = str(nxt["href"]) if isinstance(nxt, dict) and nxt.get("href") else None
            params = {}  # the nextPage href already carries the query
        return out[:limit] if limit is not None else out

    def count(self, structure: str, where: str | None = None) -> int:
        params = {"oslc.pageSize": "1", "collectioncount": "1", "oslc.select": "href"}
        if where:
            params["oslc.where"] = where
        body = self._body(self._send("GET", self.os_url(structure), params=params))
        info = body.get("responseInfo")
        total = info.get("totalCount") if isinstance(info, dict) else None
        return int(total) if isinstance(total, int) else len(_members(body))

    def get(self, href: str, select: str = "*") -> JsonDict:
        return self._body(self._send("GET", href, params={"oslc.select": select}))

    # -- writes (callers guard these behind --apply) ----------------------
    def create(self, structure: str, payload: JsonDict) -> JsonDict:
        """Create a record and return it as Maximo stored it."""
        resp = self._send("POST", self.os_url(structure), payload=payload, headers={"properties": "*"})
        return self._body(resp)

    def merge(self, href: str, payload: JsonDict) -> JsonDict:
        """Update a record, keeping children absent from the payload."""
        resp = self._send("POST", href, payload=payload,
                          headers={"x-method-override": "PATCH", "patchtype": "MERGE", "properties": "*"})
        return self._body(resp)

    def action(self, href: str, wsmethod: str, payload: JsonDict) -> JsonDict:
        """Run an object structure action such as `changeStatus`."""
        resp = self._send("POST", href, params={"action": f"wsmethod:{wsmethod}"}, payload=payload,
                          headers={"x-method-override": "PATCH"})
        return self._body(resp)

    def delete(self, href: str) -> None:
        """Delete a record."""
        self._send("DELETE", href)

    def script(self, name: str, payload: JsonDict) -> JsonDict:
        """Run an automation script directly, with `payload` as its `requestBody`; returns its `responseBody`."""
        return self._body(self._send("POST", f"{self.base_url}/{self.api_path}/script/{name}", payload=payload))
