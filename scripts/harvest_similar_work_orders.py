#!/usr/bin/env python3
"""Fill the similar_wo or nearby_wo rows of the AI results sheet from Maximo.

For each SR with a row for the feature, the script reads the work order a planner would open: the
SR's draft, otherwise its follow-up WO, open ones first.
- similar_wo: the WOs Maximo's WOSIMILARITY lists as similar to it, the same list the View similar
  work orders dialog shows, by score. Without --refresh it only reads. With --refresh it first asks
  Maximo to work out each WO's similar WOs again, which replaces the stored AI results for that WO.
- nearby_wo: the WOs within about 150 m, from the NEARBYWO relationship the Nearby work dialog
  shows, newest first, with no score. The relationship is live, so there is nothing to refresh.

    uv run --no-project python scripts/harvest_similar_work_orders.py                     # preview
    uv run --no-project python scripts/harvest_similar_work_orders.py --refresh --write   # re-run and save
    uv run --no-project python scripts/harvest_similar_work_orders.py --feature nearby_wo --write
    uv run --no-project python scripts/harvest_similar_work_orders.py --only SR810036
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loader.client import MaximoClient, MaximoError  # noqa: E402
from loader.config import load_settings  # noqa: E402

RESULTS = ROOT / "evaluation" / "ai-results.csv"
WO_FILES = (ROOT / "data" / "maximo" / "drafts" / "wo.csv", ROOT / "data" / "maximo" / "wo.csv")
FEATURE, CONFIG = "similar_wo", "WOSIMILARITY"
PILOT_WHERE = 'siteid="SRQSITE" and externalrefid="WO291%"'
# The statuses the WOSIMILARITY inference filter leaves out: such a WO gets no suggestions of its own.
HISTORY = {"CLOSE", "CAN"}
NOT_SHOWN, NOTHING = "n/a", "none"


def read_csv(path):
    """The rows and the header. utf-8-sig, because reviewers save the sheet from Excel."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def wo_to_open(wos):
    """Each SR -> the WO a planner opens for it: its draft, then an open follow-up, then a closed
    one. A cancelled WO is never chosen. Drafts are WAPPR and numbered WO2915xxx."""
    best = {}
    for w in wos:
        sr, status = w.get("ORIGRECORDID"), w.get("STATUS", "")
        if not sr or status == "CAN":
            continue
        key = (w["WONUM"][:6] != "WO2915", status in HISTORY, w["WONUM"])
        if sr not in best or key < best[sr][0]:
            best[sr] = (key, w["WONUM"])
    return {sr: wonum for sr, (_, wonum) in best.items()}


def as_row(row, checked, similar, by_score=True):
    """The results row with Maximo's answer: WO numbers by score, highest first, and the top score.
    Without `by_score` the WOs keep the order given and there is no score. `similar` is None when
    there was no WO to ask about. The reviewer's columns are kept."""
    if similar is None:
        return {**row, "AI_VALUE": NOT_SHOWN, "AI_SCORE": ""}
    if not by_score:
        listed = [w for w in similar if w != checked]
        return {**row, "AI_VALUE": ";".join(listed) or NOTHING, "AI_SCORE": ""}
    ranked = sorted(((score, wonum) for wonum, score in similar.items() if wonum != checked),
                    key=lambda p: (-(p[0] or 0), p[1]))
    if not ranked:
        return {**row, "AI_VALUE": NOTHING, "AI_SCORE": ""}
    top = ranked[0][0]
    return {**row, "AI_VALUE": ";".join(w for _, w in ranked), "AI_SCORE": "" if top is None else str(top)}


class SimilarWorkOrders:
    """Maximo's WOSIMILARITY results for one work order at a time."""
    feature, by_score = "similar_wo", True

    def __init__(self, client: MaximoClient):
        self.client = client

    def refresh(self, href: str) -> None:
        """Work the WO's similar WOs out again. The endpoint replaces the stored results."""
        self.client._send("POST", f"{self.client.base_url}/{self.client.api_path}/aicfg_wosimilarity",
                          payload={"href": href, "usecache": False})

    def similar(self, workorderid: int) -> dict:
        """WONUM -> score of each WO listed as similar. The list is the `similarObjects` saved
        query the dialog reads. Its score sits on the listed WO's MAXAISIMILARWO rows, which are
        keyed by the WO that was found, so the row whose objectid is the checked WO holds it."""
        body = self.client._body(self.client._send(
            "GET", self.client.os_url("mxapiwodetail"),
            params={"savedQuery": "similarObjects", "sqp:objectId": str(workorderid),
                    "oslc.select": "wonum,workorderid", "oslc.pageSize": "50"}))
        listed = {m["workorderid"]: m["wonum"] for m in body.get("member", []) if m.get("wonum")}
        if not listed:
            return {}
        ids = ",".join(str(i) for i in listed)  # integers, unquoted: Maximo refuses "133767"
        scores = {}
        for w in self.client.query("mxapiwodetail", where=f"workorderid in [{ids}]",
                                   select="workorderid,rel.maxaisimilarwo{objectid,score,aicfgname}"):
            for pair in w.get("maxaisimilarwo") or []:
                if pair.get("objectid") == workorderid and pair.get("aicfgname") == CONFIG:
                    scores[w["workorderid"]] = pair.get("score")
        return {wonum: scores.get(wid) for wid, wonum in listed.items()}


class NearbyWorkOrders:
    """The WOs within about 150 m of one work order: the NEARBYWO relationship on WORKORDER."""
    feature, by_score = "nearby_wo", False

    def __init__(self, client: MaximoClient):
        self.client = client

    def refresh(self, href: str) -> None:
        raise MaximoError("nearby_wo reads a live relationship; there is nothing to refresh")

    def similar(self, workorderid: int) -> dict:
        """WONUM -> report date of each nearby WO, newest first."""
        found = self.client.query("mxapiwodetail", where=f"workorderid={workorderid}",
                                  select="workorderid,rel.nearbywo{wonum,reportdate}")
        if not found:
            raise MaximoError(f"workorderid {workorderid} not found")
        near = sorted(found[0].get("nearbywo") or [], key=lambda w: (w.get("reportdate") or "", w["wonum"]),
                      reverse=True)
        return {w["wonum"]: w.get("reportdate") for w in near}


def harvest(rows, choose, lookup, maximo, refresh=False, only=None, report=print):
    """The results rows with every row of `maximo.feature` asked of Maximo, in the same order, and
    how many failed. `lookup` maps our WO number (Maximo's EXTERNALREFID) -> (workorderid, href, Maximo's
    WONUM), so a WO Maximo renumbered is still found. A row is `n/a` only when the SR has no WO.
    A WO Maximo does not return, or fails on, is reported and its row left as it was."""
    out, failed = [], 0
    for row in rows:
        if row["FEATURE"] != maximo.feature or (only and row["TICKETID"] not in only):
            out.append(row)
            continue
        wonum = choose.get(row["TICKETID"])
        if wonum is None:
            out.append(as_row(row, None, None))
            continue
        try:
            if wonum not in lookup:
                raise MaximoError("not among the pilot WOs in Maximo; is it loaded?")
            workorderid, href, maximo_wonum = lookup[wonum]
            if refresh:
                maximo.refresh(href)
            out.append(as_row(row, maximo_wonum, maximo.similar(workorderid), by_score=maximo.by_score))
        except MaximoError as e:
            report(f"  {row['TICKETID']} ({wonum}): {e}")
            out.append(row)
            failed += 1
    return out, failed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=RESULTS, type=Path, help="results sheet (default: %(default)s)")
    ap.add_argument("--feature", choices=("similar_wo", "nearby_wo"), default=FEATURE,
                    help="which rows to fill (default: %(default)s)")
    ap.add_argument("--refresh", action="store_true", help="re-run WO similarity for each WO first (similar_wo only)")
    ap.add_argument("--write", action="store_true", help="save the sheet (default: preview)")
    ap.add_argument("--only", nargs="*", help="limit to these ticket IDs")
    args = ap.parse_args(argv)
    if args.refresh and args.feature != FEATURE:
        ap.error("--refresh applies to similar_wo only")

    rows, columns = read_csv(args.results)
    choose = wo_to_open([w for path in WO_FILES if path.exists() for w in read_csv(path)[0]])
    s = load_settings()
    client = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)
    lookup = {w.get("externalrefid") or w["wonum"]: (w["workorderid"], w["href"], w["wonum"])
              for w in client.query("mxapiwodetail", where=PILOT_WHERE, select="wonum,workorderid,externalrefid",
                                    page_size=200)}
    maximo = (SimilarWorkOrders if args.feature == FEATURE else NearbyWorkOrders)(client)
    filled, failed = harvest(rows, choose, lookup, maximo, refresh=args.refresh,
                     only=set(args.only or ()), report=print)

    for row in filled:
        if row["FEATURE"] == args.feature and (not args.only or row["TICKETID"] in args.only):
            print(f"{row['TICKETID']:<9} {choose.get(row['TICKETID'], '-'):<10} "
                  f"{row['AI_SCORE'] or '':>3}  {row['AI_VALUE']}")
    if args.write:
        with args.results.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(filled)
        print(f"Wrote {args.results}")
    else:
        print("Preview only. Add --write to save.")
    if failed:
        print(f"{failed} WO(s) failed; their rows were left as they were.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
