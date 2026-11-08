"""Load SRs, WOs and work logs from data/maximo/ into the SRQ org and SRQSITE site.

Order: SRs, WOs (ORIGRECORDID remapped to Maximo's TICKETID), work logs (merged onto their
parent), then status changes. Before creating anything the loader checks the manifest, then a
natural key on the instance, so a re-run creates nothing. Dry run unless --apply. There is
no delete code path.
"""

import csv
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from . import mapping
from .client import MaximoClient, MaximoError, oslc_str, quote_list
from .config import DATA_DIR, SITEID, STATE_DIR, cat
from .manifest import Manifest

FAILURE_CODE_COLUMNS = ("FAILURECODE", "PROBLEMCODE")  # provisioning leaves failure codes as a manual step
# Service groups and services must exist in Maximo, and the County's codes (WATER_PIPE) are longer
# than standard Maximo's 8-character COMMODITY, so they are not sent until set up.
COMMODITY_COLUMNS = ("COMMODITYGROUP", "COMMODITY")
DEFAULT_DROP = FAILURE_CODE_COLUMNS + COMMODITY_COLUMNS
STATUS_MEMO = "Loaded from the synthetic Sarasota pilot dataset"
SR_SELECT = "ticketid,status,externalrecid,siteid"
WO_SELECT = "wonum,status,externalrefid,siteid"


def read_csv(path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def parse_date(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed


@dataclass
class Chain:
    """An SR with its follow-up WOs, or a WO with no SR. The unit of --only and --limit."""
    srs: list[dict]
    wos: list[dict]


# The pilot SRs are what the AI is tested on; the history is what it learns from. The drafts are
# work orders for pilot SRs that have none yet, so they load after the pilot. Same columns.
DATASETS = {"pilot": "maximo", "history": "maximo/history", "drafts": "maximo/drafts"}


class Dataset:
    def __init__(self, data_dir=DATA_DIR, name: str = "pilot") -> None:
        base = data_dir / DATASETS[name]
        self.name = name
        self.sr_header, self.srs = read_csv(base / "sr.csv")
        self.wo_header, self.wos = read_csv(base / "wo.csv")
        self.wl_header, self.worklogs = read_csv(base / "worklog.csv")
        # Only the pilot is scored, so only the pilot has an answer key.
        self.answer_header, self.answers = read_csv(data_dir / "answer-key.csv") if name == "pilot" else ([], [])

    def chains(self) -> list[Chain]:
        followups = defaultdict(list)
        for wo in self.wos:
            followups[wo["ORIGRECORDID"]].append(wo)
        out = [Chain([sr], followups.get(sr["TICKETID"], [])) for sr in self.srs]
        tickets = {sr["TICKETID"] for sr in self.srs}
        out += [Chain([], [wo]) for wo in self.wos if wo["ORIGRECORDID"] not in tickets]
        return out

    def select(self, only: list[str] | None = None, limit: int | None = None) -> Chain:
        chains = self.chains()
        if only:
            wanted = set(only)
            chains = [c for c in chains if wanted & {r["TICKETID"] for r in c.srs} | wanted & {r["WONUM"] for r in c.wos}]
            unknown = wanted - {r["TICKETID"] for c in chains for r in c.srs} - {r["WONUM"] for c in chains for r in c.wos}
            if unknown:
                raise SystemExit(f"Not in the dataset: {', '.join(sorted(unknown))}")
        if limit is not None:
            chains = chains[:limit]
        return Chain([r for c in chains for r in c.srs], [r for c in chains for r in c.wos])

    def logs_for(self, selection: Chain) -> list[dict]:
        keys = {("SR", r["TICKETID"]) for r in selection.srs} | {("WORKORDER", r["WONUM"]) for r in selection.wos}
        return [w for w in self.worklogs if (w["CLASS"], w["RECORDKEY"]) in keys]


def build_remap(client: MaximoClient, manifest: Manifest) -> tuple[mapping.Remap, list[str]]:
    """Our keys -> Maximo's: tickets and WOs from the manifest, classifications by name."""
    remap = mapping.Remap(
        tickets={e["our_id"]: e["maximo_id"] for e in manifest.of_kind("sr") if e.get("maximo_id")},
        wonums={e["our_id"]: e["maximo_id"] for e in manifest.of_kind("wo") if e.get("maximo_id")},
    )
    names = {name: ours for ours, (name, _) in cat.CLASSIFICATIONS.items()}
    rows = client.query("mxapiclassstructure", where=f"classificationid in {quote_list(names)}",
                        select="classificationid,classstructureid")
    for row in rows:
        if row.get("classificationid") in names and row.get("classstructureid") is not None:
            remap.classes[names[row["classificationid"]]] = str(row["classstructureid"])
    missing = [name for name, ours in names.items() if ours not in remap.classes]
    return remap, missing


def _log_key(createdate, description) -> tuple:
    return (parse_date(createdate), " ".join(str(description or "").split()))


class Loader:
    def __init__(self, client: MaximoClient, manifest: Manifest, dataset: Dataset | None = None,
                 apply: bool = False, drop=DEFAULT_DROP, log: Callable[[str], None] = print,
                 state_dir=STATE_DIR) -> None:
        self.client, self.manifest, self.apply, self.log = client, manifest, apply, log
        self.manifest.persist = self.manifest.persist and apply  # a dry run never writes the manifest
        self.data = dataset or Dataset()
        self.drop = set(drop)
        self.state_dir = state_dir
        self.counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.limitations: list[str] = []

    def _line(self, kind: str, outcome: str, what: str, detail: str = "") -> None:
        self.counts[kind][outcome] += 1
        self.log(f"  {outcome:<8} {what}{f' - {detail}' if detail else ''}")

    # -- natural-key lookups (read only) ------------------------------------------
    def _find_sr(self, row: dict) -> dict | None:
        found = self.client.query("mxapisr", select=SR_SELECT, page_size=5, where=(
            f'externalrecid={oslc_str(row["EXTERNALSYSTEM_TICKETID"])} and siteid="{SITEID}"'))
        return found[0] if found else None

    def _find_wo(self, row: dict) -> tuple[dict | None, str]:
        """(record, conflict). Every WO this loader creates carries our WONUM as its external
        ref, so a WO with our number and any other ref (blank included) belongs to someone else."""
        by_num = self.client.query("mxapiwodetail", select=WO_SELECT, page_size=5,
                                   where=f'wonum={oslc_str(row["WONUM"])} and siteid="{SITEID}"')
        if by_num:
            ref = by_num[0].get("externalrefid")
            if ref != row["WONUM"]:
                return None, f"WO {row['WONUM']} already exists with external ref {ref or '(blank)'}, so it is not ours"
            return by_num[0], ""
        by_ref = self.client.query("mxapiwodetail", select=WO_SELECT, page_size=5,
                                   where=f'externalrefid={oslc_str(row["WONUM"])} and siteid="{SITEID}"')
        return (by_ref[0] if by_ref else None), ""

    def _lookup(self, kind: str, row: dict) -> tuple[dict | None, str]:
        return (self._find_sr(row), "") if kind == "sr" else self._find_wo(row)

    # -- records --------------------------------------------------------------------
    def _load_record(self, kind: str, row: dict, remap: mapping.Remap) -> None:
        our_id = row["TICKETID"] if kind == "sr" else row["WONUM"]
        what = f"{kind.upper()} {our_id}"
        try:
            self._load_one(kind, our_id, what, row, remap)
        except MaximoError as e:
            self._line(kind, "FAILED", what, str(e))

    def _load_one(self, kind: str, our_id: str, what: str, row: dict, remap: mapping.Remap) -> None:
        id_attr, structure = ("ticketid", "mxapisr") if kind == "sr" else ("wonum", "mxapiwodetail")
        entry = self.manifest.get(kind, our_id)
        if entry is None or not entry.get("href"):
            # Not in the manifest, or created earlier without an href we could read: look it up.
            found, conflict = self._lookup(kind, row)
            if conflict:
                self._line(kind, "FAILED", what, conflict + " (left unchanged)")
                return
            if found:
                entry = self.manifest.record(kind, our_id, maximo_id=found.get(id_attr), href=found.get("href"),
                                             status=found.get("status"), source="found")
            elif entry is not None:
                self._line(kind, "FAILED", what, "created by an earlier run but not found now; check it in Maximo")
                return
        if entry is not None:
            self._remember(kind, our_id, entry["maximo_id"], remap)
            self._line(kind, "EXISTS", what, "" if entry["maximo_id"] == our_id else f"Maximo id {entry['maximo_id']}")
            return
        # A WO must point at the SR (and parent WO) Maximo actually holds; never at our own id.
        if self.apply and kind == "wo":
            for column, known in (("ORIGRECORDID", remap.tickets), ("PARENT", remap.wonums)):
                if row.get(column) and row[column] not in known:
                    self._line(kind, "FAILED", what, f"{column} {row[column]} is not loaded yet; re-run after it is")
                    return
        payload = (mapping.sr_payload if kind == "sr" else mapping.wo_payload)(row, remap, self._drop_for(row, remap))
        if not self.apply:
            self._line(kind, "PLAN", what, row["DESCRIPTION"])
            self._remember(kind, our_id, our_id, remap)
            return
        created = self.client.create(structure, payload)
        maximo_id = str(created.get(id_attr) or our_id)
        href = created.get("href")
        if not href:  # some instances answer 201 with no body; find what we just made
            found = self._lookup(kind, row)[0] or {}
            href, maximo_id = found.get("href"), str(found.get(id_attr) or maximo_id)
        self.manifest.record(kind, our_id, maximo_id=maximo_id, href=href, status=None)
        self._remember(kind, our_id, maximo_id, remap)
        self._line(kind, "CREATED", what, "" if maximo_id == our_id else f"Maximo renumbered it {maximo_id}")

    def _drop_for(self, row: dict, remap: mapping.Remap) -> set[str]:
        drop = set(self.drop)
        if row.get("CLASSSTRUCTUREID") and row["CLASSSTRUCTUREID"] not in remap.classes:
            drop.add("CLASSSTRUCTUREID")
        return drop

    @staticmethod
    def _remember(kind: str, our_id: str, maximo_id: str, remap: mapping.Remap) -> None:
        (remap.tickets if kind == "sr" else remap.wonums)[our_id] = maximo_id

    # -- work logs ------------------------------------------------------------------
    def _load_worklogs(self, logs: list[dict]) -> None:
        by_parent = defaultdict(list)
        for log in logs:
            by_parent[("sr" if log["CLASS"] == "SR" else "wo", log["RECORDKEY"])].append(log)
        for (kind, parent_id), rows in by_parent.items():
            try:
                self._load_parent_logs(kind, parent_id, rows)
            except MaximoError as e:
                for r in rows:
                    if self.manifest.get("worklog", r["WORKLOGID"]) is None:
                        self._line("worklog", "FAILED", f"work log {r['WORKLOGID']} on {parent_id}", str(e))

    def _load_parent_logs(self, kind: str, parent_id: str, rows: list[dict]) -> None:
        pending = [r for r in rows if self.manifest.get("worklog", r["WORKLOGID"]) is None]
        for r in rows:
            if r not in pending:
                self._line("worklog", "EXISTS", f"work log {r['WORKLOGID']} on {parent_id}")
        if not pending:
            return
        parent = self.manifest.get(kind, parent_id)
        if parent is None or not parent.get("href"):
            for r in pending:
                self._line("worklog", "FAILED" if self.apply else "PLAN", f"work log {r['WORKLOGID']} on {parent_id}",
                           "parent record not loaded" if self.apply else "")
            return
        on_instance = {_log_key(w.get("createdate"), w.get("description")) for w in
                       self.client.get(parent["href"], "worklog{createdate,description}").get("worklog") or []}
        additions = []
        for r in pending:
            what = f"work log {r['WORKLOGID']} on {parent_id}"
            if _log_key(r["CREATEDATE"], r["DESCRIPTION"]) in on_instance:
                self.manifest.record("worklog", r["WORKLOGID"], maximo_id=None, href=parent["href"], source="found")
                self._line("worklog", "EXISTS", what)
            elif not self.apply:
                self._line("worklog", "PLAN", what)
            else:
                additions.append(r)
        if not additions:
            return
        self.client.merge(parent["href"], {"worklog": [mapping.worklog_payload(r) for r in additions]})
        for r in additions:
            self.manifest.record("worklog", r["WORKLOGID"], maximo_id=None, href=parent["href"])
            self._line("worklog", "CREATED", f"work log {r['WORKLOGID']} on {parent_id}")

    # -- statuses -------------------------------------------------------------------
    def _live_status(self, kind: str, href: str) -> str | None:
        return mapping.dataset_status(kind, self.client.get(href, "status").get("status"))

    def _apply_status(self, kind: str, row: dict, stop_at: str | None = None) -> None:
        our_id = row["TICKETID"] if kind == "sr" else row["WONUM"]
        entry = self.manifest.get(kind, our_id)
        what = f"{kind.upper()} {our_id} status"
        final = row["STATUS"]
        if entry is None or not entry.get("href"):
            if not self.apply and mapping.status_steps(kind, final):
                self._line("status", "PLAN", what, " -> ".join(mapping.status_steps(kind, final)))
            return
        try:
            # The live status, not the manifest's: a change whose response was lost still happened.
            current = self._live_status(kind, entry["href"]) if self.apply else entry.get("status")
        except MaximoError as e:
            self._line("status", "FAILED", what, str(e))
            return
        if current == mapping.INITIAL_STATUS[kind] and final != current:
            current = None  # as Maximo created it; no status change applied yet
        if current not in (None, final) and current not in mapping.status_steps(kind, final):
            self._line("status", "EXISTS", what, f"is {current}, ours is {final} (left unchanged)")
            return
        steps = mapping.status_steps(kind, final, current)
        if stop_at in mapping.status_steps(kind, final):  # this pass only goes as far as stop_at
            steps = steps[:steps.index(stop_at) + 1] if stop_at in steps else []
            if not steps:
                return
        if not steps:
            if self.apply and entry.get("status") != final:
                self.manifest.set_status(kind, our_id, final)
            return
        if not self.apply:
            self._line("status", "PLAN", what, " -> ".join(steps))
            return
        history = next((i for i, step in enumerate(steps) if step in mapping.HISTORY_STATUSES[kind]), None)
        unloaded = self._unloaded_logs(kind, our_id) if history is not None else []
        if unloaded:
            self._line("status", "FAILED", f"{what} {steps[history]}",
                       f"held back: work log {', '.join(unloaded)} is not loaded, and {steps[history]} would lock "
                       f"the record; re-run after it loads")
            steps = steps[:history]
        for step in steps:
            if not self._change_status(kind, our_id, what, entry["href"], step, row["STATUSDATE"]):
                return
        if steps:
            self._line("status", "CREATED", what, " -> ".join(steps))

    def _unloaded_logs(self, kind: str, our_id: str) -> list[str]:
        cls = "SR" if kind == "sr" else "WORKORDER"
        return [w["WORKLOGID"] for w in self.data.worklogs if (w["CLASS"], w["RECORDKEY"]) == (cls, our_id)
                and self.manifest.get("worklog", w["WORKLOGID"]) is None]

    def _change_status(self, kind: str, our_id: str, what: str, href: str, step: str, date: str) -> bool:
        body = {"status": mapping.maximo_status(kind, step), "date": date, "memo": STATUS_MEMO}
        try:
            try:
                self.client.action(href, "changeStatus", body)
            except MaximoError as e:
                if not e.refused_by_maximo:
                    raise
                # Maximo can refuse a back-dated status; set it without the date and say so.
                self.client.action(href, "changeStatus", {k: v for k, v in body.items() if k != "date"})
                self.limitations.append(f"{what} {step}: historical date refused ({e}); Maximo used the load time")
        except MaximoError as e:
            try:  # the change may have gone through even though the answer did not come back
                applied = self._live_status(kind, href) == step
            except MaximoError:
                applied = False
            if not applied:
                self._line("status", "FAILED", f"{what} {step}", str(e))
                return False
        self.manifest.set_status(kind, our_id, step)
        return True

    # -- driver ----------------------------------------------------------------------
    def run(self, only: list[str] | None = None, limit: int | None = None) -> int:
        selection = self.data.select(only, limit)
        logs = self.data.logs_for(selection)
        self.log(f"Loading {len(selection.srs)} SRs, {len(selection.wos)} WOs, {len(logs)} work logs "
                 f"({'APPLY' if self.apply else 'dry run: nothing is written'})")
        remap, missing_classes = build_remap(self.client, self.manifest)
        self.log("Columns not sent on create:")
        for kind, header in (("sr", self.data.sr_header), ("wo", self.data.wo_header),
                             ("worklog", self.data.wl_header)):
            for column, reason in mapping.dropped_columns(kind, header, self.drop).items():
                self.log(f"  {kind.upper():<8} {column}: {reason}")
        if missing_classes:
            self.log(f"  {'SR, WO':<8} CLASSSTRUCTUREID: dropped where the classification is not on the instance "
                     f"({', '.join(missing_classes)}); run provision first")
        self.log("Service requests:")
        for row in selection.srs:
            self._load_record("sr", row, remap)
        self.log("Work orders:")
        for row in selection.wos:
            self._load_record("wo", row, remap)
        self.log("Work logs:")
        self._load_worklogs(logs)
        self.log("Statuses:")
        # The order work happens in: Maximo moves a follow-up WO's SR when the WO starts, and
        # refuses that while the SR is still queued, so SRs go in progress first, then the WOs
        # run, then the SRs are resolved or closed.
        if self.apply:
            for row in selection.srs:
                self._apply_status("sr", row, stop_at=mapping.SR_IN_PROGRESS)
        for row in selection.wos:
            self._apply_status("wo", row)
        for row in selection.srs:
            self._apply_status("sr", row)
        if self.apply and self.data.answers:
            self.log(f"Answer key with Maximo ids: "
                     f"{write_answer_key(self.data, remap, self.state_dir / 'answer-key-maximo.csv')}")
        return self.summary()

    def summary(self) -> int:
        self.log("\nDone:")
        failed = 0
        for kind in ("sr", "wo", "worklog", "status"):
            c = self.counts[kind]
            failed += c["FAILED"]
            self.log(f"  {kind:<8} created {c['CREATED']}, planned {c['PLAN']}, existing {c['EXISTS']}, failed {c['FAILED']}")
        if self.limitations:
            self.log("Known limitations hit:")
            self.log("\n".join(f"  - {x}" for x in self.limitations))
        return 1 if failed else 0


def write_answer_key(data: Dataset, remap: mapping.Remap, path=STATE_DIR / "answer-key-maximo.csv"):
    """The answer key with every SR and WO id, and every team code, as Maximo holds it."""
    ids = {**remap.tickets, **remap.wonums}

    def swap(text: str) -> str:  # one pass, whole ids only, so a renumbered id is never swapped twice
        return re.sub(r"\b(?:SR|WO)\d+\b", lambda m: ids.get(m.group(), m.group()), text)

    def team(text: str) -> str:
        return re.sub(r"\b(?:" + "|".join(mapping.TEAM_CODES) + r")\b", lambda m: mapping.maximo_team(m.group()), text)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.answer_header)
        writer.writeheader()
        for row in data.answers:
            row = {k: swap(v) if k in ("TICKETID", "RELATED_RECORDS", "EXPECTED_RECOMMENDATION") else v
                   for k, v in row.items()}
            writer.writerow({k: team(v) if k in ("EXPECTED_PERSONGROUP", "EXPECTED_RECOMMENDATION") else v
                             for k, v in row.items()})
    return path
