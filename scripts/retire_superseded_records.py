"""Close the old pilot copies on TechZone, each with a note that points to its new copy.

The pilot was reloaded under new IDs once its SRs carried structured fields (scripts/id_map.py).
The old copies stay in Maximo as the "before" records, but an open one would still show in
queues, the Assistant and similar-record results. This gives every old pilot SR, follow-up WO
and draft WO that is not final a work log "Superseded by <new ID>", then:
- a completed WO (COMP) goes to CLOSE, an in-progress one (INPRG, which Maximo refuses to
  cancel) through COMP to CLOSE, and any other open WO or draft is cancelled (CAN);
- an SR goes through the usual steps to CLOSED.
Every note is written before any status changes: Maximo closes an SR when its WO is closed or
cancelled, and refuses a note on a closed SR. WOs change status first, and an SR waits while one
of its old WOs is skipped or fails, so an SR is never closed over an open WO. A record is retired
only once its new copy is in Maximo, a status the script does not know is left alone, nothing is
deleted, and a second run does nothing.

    uv run --no-project --with-requirements requirements.txt python scripts/retire_superseded_records.py
    uv run --no-project --with-requirements requirements.txt python scripts/retire_superseded_records.py --apply
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import id_map  # noqa: E402

from loader.client import MaximoClient, MaximoError, quote_list  # noqa: E402
from loader.config import load_settings  # noqa: E402

SITE = "SRQSITE"
NOTE = "Superseded by "
# Copies of cluster B made by hand on TechZone on 2026-11-10, after the old SR800044 was cancelled
# by mistake. No ID range covers them.
MANUAL_COPIES = {"SR700044": "SR810044", "SR700046": "SR810046"}

# Statuses as Maximo reports them on TechZone, synonyms included.
SR_STATUSES = {"NEW", "QUEUED", "PENDING", "INPROG", "RESOLVED", "CLOSED", "CANCELLED"}
SR_FINAL = {"CLOSED", "CANCELLED"}
SR_CLOSE_STEPS = ["QUEUED", "INPROG", "RESOLVED", "CLOSED"]
WO_STATUSES = {"WAPPR", "WCONT", "APPR", "WSCH", "SCHED", "WMATL", "WPCOND", "INPRG", "COMP", "CLOSE", "CAN"}
WO_FINAL = {"CLOSE", "CAN"}


def new_copy(old: str) -> str | None:
    return MANUAL_COPIES.get(old) or id_map.new_id(old)


def sr_steps(status: str) -> list[str] | None:
    """The changeStatus calls that take an SR from `status` to CLOSED, or None for an unknown status."""
    if status not in SR_STATUSES:
        return None
    if status in SR_FINAL:
        return []
    return SR_CLOSE_STEPS[SR_CLOSE_STEPS.index(status) + 1:] if status in SR_CLOSE_STEPS else SR_CLOSE_STEPS


def wo_steps(status: str) -> list[str] | None:
    """Finished work is closed, work in progress completed and closed, and other open work
    cancelled; None for an unknown status."""
    if status not in WO_STATUSES:
        return None
    if status in WO_FINAL:
        return []
    return {"COMP": ["CLOSE"], "INPRG": ["COMP", "CLOSE"]}.get(status, ["CAN"])


def _skip(status, todo, new, loaded):
    if todo is None:
        return f"unknown status {status!r}"
    if new is None:
        return "no new ID"
    return None if new in loaded else f"{new} not loaded yet"


def plan(old_wos: list[dict], old_srs: list[dict], loaded: set[str], noted: set[str]) -> list[dict]:
    """One action per old record that is not final: WOs first, then SRs, each in ID order.

    `loaded` holds the new IDs already in Maximo; `noted` the old IDs that already carry the note.
    """
    actions, waiting = [], {}  # waiting: old SR -> its old WO that stays open
    for kind, rows, key, steps in (("wo", old_wos, "wonum", wo_steps), ("sr", old_srs, "ticketid", sr_steps)):
        for row in sorted(rows, key=lambda r: r[key]):
            old, status = row[key], row.get("status") or ""
            todo = steps(status)
            if todo == []:
                continue
            new = new_copy(old)
            skip = _skip(status, todo, new, loaded)
            if kind == "wo" and skip and row.get("origrecordid"):
                waiting.setdefault(row["origrecordid"], old)
            if kind == "sr" and not skip and old in waiting:
                skip = f"its old WO {waiting[old]} stays open"
            actions.append({"kind": kind, "old": old, "new": new, "href": row.get("href"), "status": status,
                            "steps": todo or [], "note": old not in noted, "origin": row.get("origrecordid"),
                            "skip": skip})
    return actions


def worklog(new: str) -> dict:
    return {"logtype": "CLIENTNOTE", "description": NOTE + new, "clientviewable": False,
            "description_longdescription": f"This copy was loaded before the pilot SRs carried structured fields. "
                                           f"The current copy is {new}; work on that one."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the notes and status changes (default: preview)")
    args = ap.parse_args()
    s = load_settings()
    client = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)

    old_srs = [r for r in client.query("mxapisr", select="ticketid,status", page_size=200,
                                       where=f'siteid="{SITE}" and externalrecid="70%"')
               if id_map.kind_of(r["ticketid"]) == "sr"]
    old_srs += client.query("mxapisr", select="ticketid,status",
                            where=f'siteid="{SITE}" and ticketid in {quote_list(list(MANUAL_COPIES))}')
    old_wos = [w for pattern in ("WO290%", "WO295%")
               for w in client.query("mxapiwodetail", select="wonum,status,origrecordid", page_size=200,
                                     where=f'siteid="{SITE}" and externalrefid="{pattern}"')
               if id_map.kind_of(w["wonum"]) in ("wo", "draft")]
    loaded = {r["ticketid"] for r in client.query("mxapisr", select="ticketid", page_size=200,
                                                   where=f'siteid="{SITE}" and externalrecid="71%"')}
    loaded |= {w["wonum"] for pattern in ("WO291%",)
               for w in client.query("mxapiwodetail", select="wonum", page_size=200,
                                     where=f'siteid="{SITE}" and externalrefid="{pattern}"')}
    noted = {w.get("recordkey") for cls in ("SR", "WORKORDER")
             for w in client.query("mxapiworklog", select="recordkey,description", page_size=500,
                                   where=f'class="{cls}" and siteid="{SITE}" and description="{NOTE}%"')}

    actions = plan(old_wos, old_srs, loaded, noted)
    counts = {"retired": 0, "skipped": 0, "failed": 0}
    failed_origins = set()  # SRs whose old WO failed in this run stay open

    def fail(a, what, e):
        counts["failed"] += 1
        a["failed"] = True
        if a["origin"]:
            failed_origins.add(a["origin"])
        print(f"  FAILED  {what} - {e}")

    todo = [a for a in actions if not a["skip"]]
    for a in actions:
        if a["skip"]:
            counts["skipped"] += 1
            print(f"  SKIP    {a['kind'].upper()} {a['old']} ({a['status']}) - {a['skip']}")
    # Notes first: closing or cancelling a WO closes its SR, and a closed SR takes no new note.
    for a in todo:
        what = f"{a['kind'].upper()} {a['old']} ({a['status']})"
        detail = f"note 'Superseded by {a['new']}', " if a["note"] else ""
        print(f"  {'RETIRE' if args.apply else 'PLAN':<7} {what} - {detail}status {' > '.join(a['steps'])}")
        if args.apply and a["note"]:
            try:
                client.merge(a["href"], {"worklog": [worklog(a["new"])]})
            except MaximoError as e:
                fail(a, what, e)
    if args.apply:
        for a in todo:
            if a.get("failed"):
                continue
            what = f"{a['kind'].upper()} {a['old']} ({a['status']})"
            steps = a["steps"]
            if a["kind"] == "sr":
                if a["old"] in failed_origins:
                    counts["skipped"] += 1
                    print(f"  SKIP    {what} - its old WO failed above")
                    continue
            try:
                if a["kind"] == "sr":  # Maximo may have closed it along with its WO
                    steps = sr_steps(client.get(a["href"], select="status").get("status") or "") or []
                for status in steps:
                    client.action(a["href"], "changeStatus", {"status": status, "memo": NOTE + a["new"]})
                counts["retired"] += 1
            except MaximoError as e:
                fail(a, what, e)
    planned = len(actions) - counts["skipped"]
    print(f"{len(actions)} old records not final: " + (f"{counts['retired']} retired, {counts['failed']} failed, "
                                                     if args.apply else f"{planned} to retire (preview), ")
          + f"{counts['skipped']} skipped")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
