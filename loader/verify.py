"""Read every loaded record back and compare it with the dataset, field by field.

Dates are compared in UTC and text with whitespace collapsed. A status date that differs is
reported as a known limitation (Maximo may stamp status changes with the load time), not as
a failure. Read only.
"""

from collections.abc import Callable

from . import mapping
from .client import MaximoClient, MaximoError
from .load import Dataset, _log_key, build_remap, parse_date
from .manifest import Manifest

LIMITATION_FIELDS = {"statusdate"}


def _norm(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        date = parse_date(value) if len(value) >= 16 and value[4:5] == "-" and "T" in value else None
        return date if date is not None else " ".join(value.split())
    return value


def compare(expected: dict, actual: dict, fold_case: bool = False) -> list[tuple[str, object, object]]:
    """(field, expected, actual) for every expected field Maximo holds differently."""
    def norm(value):
        value = _norm(value)
        return value.lower() if fold_case and isinstance(value, str) else value
    return [(k, v, actual.get(k)) for k, v in expected.items() if norm(v) != norm(actual.get(k))]


def compare_address(expected: dict, rows) -> list[str]:
    """The SR's one service address row against ours. Maximo uppercases the city, so text is
    compared without case."""
    if len(rows or []) != 1:
        return [f"service address: expected one row, got {len(rows or [])}"]
    return [f"service address {f}: expected {e!r}, got {a!r}" for f, e, a in compare(expected, rows[0], fold_case=True)]


class Verifier:
    def __init__(self, client: MaximoClient, manifest: Manifest, dataset: Dataset | None = None,
                 drop=(), log: Callable[[str], None] = print) -> None:
        self.client, self.manifest, self.log = client, manifest, log
        self.data = dataset or Dataset()
        self.drop = set(drop)
        self.ok = self.diff = self.missing = 0
        self.limitations: list[str] = []

    def _check(self, kind: str, row: dict, remap: mapping.Remap, logs: list[dict]) -> None:
        our_id = row["TICKETID"] if kind == "sr" else row["WONUM"]
        what = f"{kind.upper()} {our_id}"
        entry = self.manifest.get(kind, our_id)
        if entry is None or not entry.get("href"):
            self.missing += 1
            self.log(f"  MISSING  {what} - not in the manifest; run load first")
            return
        drop = set(self.drop)
        if row.get("CLASSSTRUCTUREID") and row["CLASSSTRUCTUREID"] not in remap.classes:
            drop.add("CLASSSTRUCTUREID")
        expected = (mapping.sr_payload if kind == "sr" else mapping.wo_payload)(row, remap, drop)
        expected["status"] = mapping.maximo_status(kind, row["STATUS"])
        expected["ticketid" if kind == "sr" else "wonum"] = entry["maximo_id"]  # Maximo may renumber
        address = (expected.pop(mapping.SR_ADDRESS_CHILD, None) or [None])[0]
        select = ",".join(sorted(set(expected) | {"statusdate"})) + ",worklog{createdate,description,logtype,createby}"
        if address:
            select += f",{mapping.SR_ADDRESS_CHILD}{{{','.join(sorted(address))}}}"
        try:
            actual = self.client.get(entry["href"], select)
        except MaximoError as e:
            self.diff += 1
            self.log(f"  ERROR    {what} - {e}")
            return
        problems = [f"{f}: expected {e!r}, got {a!r}" for f, e, a in compare(expected, actual)]
        if address:
            problems += compare_address(address, actual.get(mapping.SR_ADDRESS_CHILD))
        have = {_log_key(w.get("createdate"), w.get("description")) for w in actual.get("worklog") or []}
        problems += [f"work log {r['WORKLOGID']} not found ({r['CREATEDATE']})" for r in logs
                     if _log_key(r["CREATEDATE"], r["DESCRIPTION"]) not in have]
        if compare({"statusdate": row["STATUSDATE"]}, actual):
            self.limitations.append(f"{what} statusdate: expected {row['STATUSDATE']}, got {actual.get('statusdate')}")
        if problems:
            self.diff += 1
            self.log(f"  DIFF     {what}")
            self.log("\n".join(f"             {p}" for p in problems))
        else:
            self.ok += 1
            self.log(f"  OK       {what} ({len(logs)} work logs)")

    def run(self, only: list[str] | None = None, limit: int | None = None) -> int:
        selection = self.data.select(only, limit)
        logs = self.data.logs_for(selection)
        remap, _ = build_remap(self.client, self.manifest)
        by_parent: dict[tuple[str, str], list[dict]] = {}
        for log in logs:
            by_parent.setdefault((log["CLASS"], log["RECORDKEY"]), []).append(log)
        self.log(f"Verifying {len(selection.srs)} SRs and {len(selection.wos)} WOs")
        for row in selection.srs:
            self._check("sr", row, remap, by_parent.get(("SR", row["TICKETID"]), []))
        for row in selection.wos:
            self._check("wo", row, remap, by_parent.get(("WORKORDER", row["WONUM"]), []))
        self.log(f"\nDone - match {self.ok}, differ {self.diff}, not loaded {self.missing}")
        if self.limitations:
            self.log(f"Known limitation (not a failure): {len(self.limitations)} status dates differ, e.g.")
            self.log("\n".join(f"  - {x}" for x in self.limitations[:5]))
        return 1 if self.diff or self.missing else 0
