"""Fill the service address of the pilot and draft WOs already in Maximo, from the dataset.

The WOs were loaded before the dataset carried a service address, so each has one empty
WOSERVICEADDRESS row. This merges the dataset's address into it: the same child row the loader
now sends on create. A WO whose address already matches is skipped, so running it again changes
nothing. Every WO's current address row is saved to logs/ before the first write, and each
written WO is read back.

A closed or cancelled WO is in history, and Maximo refuses its address through the API: setting
the coordinates adds a GEOMETRY row, which a history record cannot take (BMXAA0024E). Without
--history those are reported, not sent. With --history they go through the one-off automation
script scripts/autoscript/srqfillwoaddr.py, which this creates for the run and deletes afterwards.
A preview runs that script too, and it rolls its changes back.

    uv run --no-project --with-requirements requirements.txt python scripts/fill_wo_service_addresses.py
    uv run --no-project --with-requirements requirements.txt python scripts/fill_wo_service_addresses.py --apply
    uv run --no-project --with-requirements requirements.txt python scripts/fill_wo_service_addresses.py \\
        --history --only WO2910011 --apply
"""

import argparse
import json
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loader import mapping  # noqa: E402
from loader.client import MaximoClient, MaximoError  # noqa: E402
from loader.config import load_settings  # noqa: E402
from loader.load import Dataset  # noqa: E402
from loader.verify import compare_address  # noqa: E402

PILOT_WHERE = 'siteid="SRQSITE" and externalrefid="WO291%"'
CHILD = mapping.WO_ADDRESS_CHILD
SELECT = ("wonum,externalrefid,status," + CHILD + "{woserviceaddressid,"
          + ",".join(sorted(c.lower() for c in mapping.WO_ADDRESS_COLUMNS)) + "}")
LOGS = ROOT / "logs"
IN_HISTORY = mapping.HISTORY_STATUSES["wo"]
SCRIPT_NAME = "SRQFILLWOADDR"
SCRIPT_SOURCE = ROOT / "scripts" / "autoscript" / "srqfillwoaddr.py"

# Sends {our WONUM: address} for WOs in history, with apply on or off; returns {our WONUM: outcome}.
HistoryWriter = Callable[[dict[str, dict], bool], dict[str, str]]


def wanted_addresses(rows) -> dict[str, dict]:
    """Our WO number -> the address row the loader sends for it, for every WO that has one."""
    out = {}
    for row in rows:
        child = mapping.wo_payload(row, mapping.Remap()).get(CHILD)
        if child:
            out[row["WONUM"]] = child[0]
    return out


def _where(address: dict) -> str:
    return f"{address.get('streetaddress', '')}, {address.get('city', '')}".strip(", ")


def fill(wanted: dict[str, dict], loaded: list[dict], client: MaximoClient, apply: bool = False,
         backup: Callable[[list[dict]], None] = lambda rows: None, report: Callable[[str], None] = print,
         history: HistoryWriter | None = None):
    """Write each wanted address that Maximo holds differently. Returns (changed, same, failed)."""
    by_ours: dict[str, list[dict]] = {}
    for w in loaded:
        by_ours.setdefault(w.get("externalrefid") or w.get("wonum"), []).append(w)
    todo, closed, same, failed = [], [], 0, 0
    for wonum, address in sorted(wanted.items()):
        if len(by_ours.get(wonum, [])) > 1:
            failed += 1
            report(f"  FAILED   {wonum} - {len(by_ours[wonum])} WOs in Maximo carry this number")
            continue
        wo = (by_ours.get(wonum) or [None])[0]
        if wo is None:
            failed += 1
            report(f"  FAILED   {wonum} - not in Maximo")
            continue
        rows = wo.get(CHILD) or []
        if len(rows) > 1:
            failed += 1
            report(f"  FAILED   {wonum} - {len(rows)} address rows; expected one")
            continue
        if not compare_address(address, rows):
            same += 1
            continue
        if wo.get("status") in IN_HISTORY:
            if history is None:
                failed += 1
                report(f"  FAILED   {wonum} ({wo.get('status')}) - in history: Maximo refuses a new address; "
                       "use --history")
                continue
            closed.append((wonum, wo, address))
        else:
            todo.append((wonum, wo, address))
    if apply and (todo or closed):
        backup([{"wonum": wo.get("wonum"), "externalrefid": wonum, "href": wo["href"], CHILD: wo.get(CHILD) or []}
                for wonum, wo, _ in todo + closed])

    def read_back(wonum, wo, address, how=""):
        try:
            problems = compare_address(address, client.get(wo["href"], SELECT).get(CHILD))
        except MaximoError as e:
            problems = [str(e)]
        if problems:
            report(f"  FAILED   {wonum} ({wo.get('status')}){how} - " + "; ".join(problems))
            return False
        report(f"  FILLED   {wonum} ({wo.get('status')}){how} -> {_where(address)}")
        return True

    changed = 0
    for wonum, wo, address in todo:
        if not apply:
            changed += 1
            report(f"  WOULD    {wonum} ({wo.get('status')}) -> {_where(address)}")
            continue
        try:
            client.merge(wo["href"], {CHILD: [address]})
        except MaximoError as e:
            failed += 1
            report(f"  FAILED   {wonum} ({wo.get('status')}) - {e}")
            continue
        if read_back(wonum, wo, address):
            changed += 1
        else:
            failed += 1

    if closed:
        try:
            outcome = history({wonum: address for wonum, _, address in closed}, apply)
        except MaximoError as e:
            outcome = {wonum: str(e) for wonum, _, _ in closed}
        for wonum, wo, address in closed:
            result = outcome.get(wonum, "no answer from the script")
            if result == ("filled" if apply else "would fill"):
                if not apply:
                    changed += 1
                    report(f"  WOULD    {wonum} ({wo.get('status')}) via script -> {_where(address)}")
                elif read_back(wonum, wo, address, " via script"):
                    changed += 1
                else:
                    failed += 1
            else:
                failed += 1
                report(f"  FAILED   {wonum} ({wo.get('status')}) via script - {result}")
    return changed, same, failed


@contextmanager
def history_script(client: MaximoClient) -> Iterator[HistoryWriter]:
    """Create the one-off SRQFILLWOADDR script for the run, and delete it afterwards, even on failure."""
    if client.query("mxapiautoscript", where=f'autoscript="{SCRIPT_NAME}"', select="autoscript"):
        raise MaximoError(f"{SCRIPT_NAME} already exists; delete it in Automation Scripts before running")
    try:
        # Inside the try: if Maximo stores the script but the reply is lost, it is still removed.
        client.create("mxapiautoscript", {"autoscript": SCRIPT_NAME, "scriptlanguage": "python", "status": "Active",
                                          "loglevel": "ERROR", "source": SCRIPT_SOURCE.read_text(),
                                          "description": "One-off: fill the address of pilot WOs in history"})
        yield lambda addresses, apply: client.script(SCRIPT_NAME, {"apply": apply, "wos": addresses})
    finally:
        try:
            # The check above proved no script of this name was there before, so any found is ours.
            removed = 0
            for record in client.query("mxapiautoscript", where=f'autoscript="{SCRIPT_NAME}"', select="autoscript"):
                client.delete(record["href"])
                removed += 1
            if removed:
                print(f"Removed the {SCRIPT_NAME} script")
        except MaximoError as e:  # never hide the run's own error behind this one
            print(f"Could not remove the {SCRIPT_NAME} script ({e}). Delete it in Automation Scripts.")


def write_backup(rows: list[dict]) -> Path:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / f"backup-{datetime.now():%y%m%d-%H%M%S}-wo-serviceaddress.json"
    path.write_text(json.dumps(rows, indent=2))
    print(f"Backup of {len(rows)} address rows: {path.relative_to(ROOT)}")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the addresses (default: preview)")
    ap.add_argument("--history", action="store_true",
                    help="also fill closed and cancelled WOs, through a one-off automation script")
    ap.add_argument("--only", nargs="*", help="limit to these WO numbers (ours)")
    args = ap.parse_args(argv)

    wanted = wanted_addresses(Dataset().wos + Dataset(name="drafts").wos)
    if args.only:
        unknown = sorted(set(args.only) - set(wanted))
        if unknown:
            raise SystemExit(f"Not a pilot or draft WO with an address: {', '.join(unknown)}")
        wanted = {w: a for w, a in wanted.items() if w in set(args.only)}
    s = load_settings()
    client = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)
    loaded = client.query("mxapiwodetail", where=PILOT_WHERE, select=SELECT, page_size=100)

    def run(history=None):
        return fill(wanted, loaded, client, apply=args.apply, backup=write_backup, history=history)

    if args.history:
        with history_script(client) as history:
            changed, same, failed = run(history)
    else:
        changed, same, failed = run()
    verb = "filled" if args.apply else "to fill"
    print(f"\n{changed} {verb}, {same} already match, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
