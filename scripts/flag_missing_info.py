"""Add MISSINFO work log notes to SRs already in Maximo, with the SRQMISSINFO script's rules.

The SRQMISSINFO launch point checks an SR each time it is saved. SRs loaded before the script
existed were never checked, so this runs the same rules over them once through the REST API.
It skips gaps already noted, so running it again adds nothing.

    uv run --no-project python scripts/flag_missing_info.py                # preview
    uv run --no-project python scripts/flag_missing_info.py --apply        # add the notes
    uv run --no-project python scripts/flag_missing_info.py --only SR810020 --apply
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loader.client import MaximoClient, MaximoError  # noqa: E402
from loader.config import load_settings  # noqa: E402

SCRIPT = ROOT / "scripts" / "autoscript" / "srqmissinfo.py"
rules: dict = {}
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), rules)  # defines the rules, runs nothing

PILOT_WHERE = 'siteid="SRQSITE" and externalrecid="71%"'
# A closed SR is in history: Maximo refuses new work logs on it. The SRQMISSINFO launch point
# notes such an SR while it is still open; here it is only reported.
HISTORY_STATUSES = {"CLOSED", "CANCELLED"}
ADDRESS_SELECT = "tkserviceaddress{" + ",".join(attr.lower() for _, attr in rules["ADDRESS_FIELDS"]) + "}"


def service_address(sr: dict) -> dict | None:
    """The SR's one service address row in the script's terms, or None when it has none."""
    rows = sr.get("tkserviceaddress") or []
    if not rows:
        return None
    return {key: str(rows[0].get(attr.lower()) or "") for key, attr in rules["ADDRESS_FIELDS"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the notes (default: preview)")
    ap.add_argument("--only", nargs="*", help="limit to these ticket IDs")
    args = ap.parse_args()

    s = load_settings()
    client = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)
    where = PILOT_WHERE
    if args.only:
        where += " and ticketid in [" + ",".join(f'"{t}"' for t in args.only) + "]"
    srs = client.query("mxapisr", where=where, page_size=100,
                       select="ticketid,status,description,description_longdescription,classstructure.hierarchypath,"
                              + ADDRESS_SELECT)
    # The SR's own worklog child lists only client-viewable notes, and MISSINFO notes are internal.
    noted_by_sr: dict[str, set] = {}
    for w in client.query("mxapiworklog", select="recordkey,description", page_size=500,
                          where=f'class="SR" and siteid="SRQSITE" and logtype="{rules["LOG_TYPE"]}"'):
        noted_by_sr.setdefault(w.get("recordkey"), set()).add(w.get("description"))
    added = failed = 0
    for sr in sorted(srs, key=lambda r: r["ticketid"]):
        gaps = rules["find_gaps"](sr.get("description"), sr.get("description_longdescription"),
                                  (sr.get("classstructure") or {}).get("hierarchypath", ""), service_address(sr))
        noted = noted_by_sr.get(sr["ticketid"], set())
        new = [(rule, msg) for rule, msg in gaps if rules["_summary"](rule) not in noted]
        closed = sr.get("status") in HISTORY_STATUSES
        for rule, _ in gaps:
            state = "NOTED" if (rule, _) not in new else (sr.get("status") if closed else "NEW")
            print(f"  {state:9} {sr['ticketid']} {rule}" + (" (closed: Maximo refuses a new note)" if closed and (rule, _) in new else ""))
        if new and args.apply and not closed:
            try:
                client.merge(sr["href"], {"worklog": [
                    {"logtype": rules["LOG_TYPE"], "description": rules["_summary"](rule),
                     "description_longdescription": msg, "clientviewable": False} for rule, msg in new]})
                added += len(new)
            except MaximoError as e:
                failed += 1
                print(f"  FAILED    {sr['ticketid']} - {e}")
    print(f"{len(srs)} SRs checked; {added} notes added, {failed} SRs failed"
          if args.apply else f"{len(srs)} SRs checked (preview; run with --apply to add the NEW notes)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
