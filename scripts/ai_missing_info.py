"""Check the pilot SRs for missing information with watsonx.ai, as suggestions for a reviewer.

Each SR goes through three steps:
1. The SRQMISSINFO rules (scripts/autoscript/srqmissinfo.py) find the gaps the record itself
   shows: no house number, no lift station, an address outside the county or not in the County
   address file.
2. For an address the County file does not have, a lookup in data/reference/address-points.csv
   (the file the SERVICEADDRESS records were loaded from) looks for the same house number on a
   similarly spelled street, or says which house numbers the street has. It never proposes a
   house number the resident did not give.
3. One watsonx.ai chat call reads the request for the gaps that need the text understood (one
   problem per request, and the rule for the request type) and drafts one question to the
   resident that covers every gap.

The reply is checked before it is used. A rule that is not on the SR's list is dropped, and so is
a gap whose evidence is not copied word for word from the request. A question that contains a
number found neither in the request nor in the address lookup is reported as invented, and is
never written to Maximo. The resident's contact line is removed before the text is sent.

Nothing changes in Maximo unless --apply is given. Then each open SR gets internal work logs a
reviewer reads: one MISSINFO entry per gap, "Missing information: <rule>", the same entry the
SRQMISSINFO launch point writes, so the Start Center counts both by rule; and one UPDATE entry,
"AI check: missing information", with the evidence and the drafted question, or "No missing
information found". That entry also marks the SR as checked, so --new skips it next time.

    uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py
    ... --model ibm/granite-4-h-small        # another watsonx.ai chat model
    ... --only SR810027 SR810048             # some SRs only
    ... --csv data/maximo/sr.csv             # read the SRs from the load file, not from Maximo
    ... --apply                              # add the work logs
    ... --new --apply --limit 25             # the scheduled job: open SRs not checked yet

Settings, read from the environment or the gitignored env file at the repository root:
WATSONX_URL, WATSONX_PROJECT_ID and WATSONX_API_KEY.
"""

import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import flag_missing_info as fmi  # noqa: E402  (also loads the SRQMISSINFO rules)
import pilot_catalog as cat  # noqa: E402
from loader.client import MaximoClient, MaximoError  # noqa: E402
from loader.config import load_settings  # noqa: E402

rules = fmi.rules
DEFAULT_MODEL = "openai/gpt-oss-120b"
API_VERSION = "2024-10-08"
IAM_URL = "https://iam.cloud.ibm.com/identity/token"
ADDRESS_POINTS = ROOT / "data" / "reference" / "address-points.csv"
ANSWER_KEY = ROOT / "data" / "answer-key.csv"
# Rules the record decides without the model (step 1).
RECORD_RULES = {"ADDR", "ADDR-VALID", "LS-ID"}
# Lines of the long description the model does not need: the resident's contact details and the
# employee who keyed the request.
DROPPED_LINES = ("customer:", "entered by:")
STREET_MATCH = 0.85  # difflib ratio for "the same street, spelled differently"
WORKLOG_SUMMARY = "AI check: missing information"
# The summary is the check's own record, not a gap, so it is not a MISSINFO entry: the Work Queue
# and the Start Center count MISSINFO entries.
SUMMARY_LOG_TYPE = "UPDATE"
OPEN_WHERE = 'siteid="SRQSITE" and status in ["NEW","QUEUED","PENDING","INPROG"]'

SYSTEM_PROMPT = (
    "You check service requests sent to Sarasota County Utilities for information a field crew "
    "needs before it is dispatched. You never invent facts. Reply with one JSON object only."
)


# ---- the request -----------------------------------------------------------------------------

def request_text(description, longdesc):
    """The request as the model sees it: the summary line, then the long description's lines,
    without the contact line and the map link text."""
    lines = [description or ""]
    for line in rules["_text"](longdesc).split("\n"):
        line = line.strip()
        if line.lower().startswith(DROPPED_LINES):
            continue
        if line.lower().startswith("address:") and line.endswith("Map"):
            line = line[:-len("Map")].rstrip()
        lines.append(line)
    return "\n".join(line for line in lines if line)


def request_type(classid):
    """The QAlert request type filed under this classification, or None."""
    return next((name for name, t in cat.REQUEST_TYPES.items() if t["classid"] == classid), None)


def model_rules(classid):
    """(rule id, requirement) pairs the model checks: one problem per request, and the request
    type's own rule unless the record decides it."""
    kind = request_type(classid)
    return [(rule, text) for rule, scope, text in cat.REQUIRED_INFORMATION
            if (scope == "ALL" or scope == kind) and rule not in RECORD_RULES]


# ---- the address lookup ----------------------------------------------------------------------

def load_address_points(path=ADDRESS_POINTS):
    with open(path, newline="") as f:
        return [(r["STREETNO"], r["STREETNAME"], r["CITY"]) for r in csv.DictReader(f)]


def _house_and_street(address):
    """(house number, street) from a service address dict, or ("", "")."""
    if not address:
        return "", ""
    number, street = address.get("number", ""), address.get("street", "")
    if not number and address.get("streetaddress"):
        first, _, rest = address["streetaddress"].partition(" ")
        if first.isdigit():
            number, street = first, street or rest
    return number.strip(), street.strip()


def address_hint(address, points):
    """What the County address file says about an address it does not have, or "".

    Only an address with a house number and street and no County address code is looked up. The
    hint names a house number only when the resident gave that same number.
    """
    if not address or address.get("code"):
        return ""
    number, street = _house_and_street(address)
    if not (number and street):
        return ""
    if any(n == number and s.lower() == street.lower() for n, s, _ in points):
        return ""

    def similar(s):
        return difflib.SequenceMatcher(None, s.lower(), street.lower()).ratio() >= STREET_MATCH

    same_number = sorted({(s, c) for n, s, c in points if n == number and similar(s)})
    if len(same_number) == 1:
        s, c = same_number[0]
        return f"The County address file has {number} {s}, {c}. The request says {street}."
    on_street = [(int(n), s, c) for n, s, c in points if similar(s) and n.isdigit()]
    if on_street and len({(s, c) for _, s, c in on_street}) == 1:
        low, high = min(n for n, _, _ in on_street), max(n for n, _, _ in on_street)
        _, s, c = on_street[0]
        return (f"The County address file has {s}, {c}, only at house numbers {low} to {high}. "
                f"House number {number} is not in the file.")
    return ""


# ---- the model -------------------------------------------------------------------------------

def build_prompt(text, kind, check, known, hint):
    rule_lines = "\n".join(f"- {rule}: {req}" for rule, req in check)
    known_lines = "\n".join(f"- {rule}: {msg}" for rule, msg in known) or "- none"
    return f"""Request type: {kind or "unknown"}
Request text:
\"\"\"
{text}
\"\"\"

Rules to check. List a rule as a gap when the request does not meet it fully.
{rule_lines}

For each gap, set "blocks_dispatch" to true only when a crew could not find the problem or know what job to do without asking the resident. Set it to false when the request already says what the problem is and where, and only a secondary detail is missing, such as since when, how much, whether it is continuous, or whether neighbors or a meter notice are involved.

Gaps already found by other checks. Do not check them again, but cover them in the question:
{known_lines}

Address file lookup: {hint or "nothing to add"}

Reply with this JSON object:
{{"gaps": [{{"rule": "<a rule id from the rules to check>", "evidence": "<words copied exactly from the request text that show the gap>", "reason": "<one sentence>", "blocks_dispatch": true}}],
 "question": "<one short, polite question to the resident that asks only for the gaps found by other checks and the gaps that block dispatch, or an empty string when there are none>"}}
In the question, use only house numbers, streets and places that appear in the request text or the address file lookup."""


def parse_reply(content):
    """The JSON object in a model reply, tolerating code fences or text around it."""
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    return json.loads(content[start:end + 1])


def _norm(text):
    return " ".join(text.lower().replace("’", "'").split())


def check_reply(reply, allowed, text):
    """Split the model's gaps into kept and dropped. Returns (kept, dropped), each a list of
    dicts with rule, evidence and reason; a dropped one also has why."""
    kept, dropped = [], []
    source = _norm(text)
    seen = set()
    for gap in reply.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        rule = str(gap.get("rule", "")).strip().upper()
        evidence = str(gap.get("evidence", "")).strip().strip('"').strip("'").strip(".").strip()
        item = {"rule": rule, "evidence": evidence, "reason": str(gap.get("reason", "")).strip()}
        if rule not in allowed:
            dropped.append({**item, "why": "not a rule for this request"})
        elif not evidence or _norm(evidence) not in source:
            dropped.append({**item, "why": "evidence not quoted from the request"})
        elif gap.get("blocks_dispatch") is False:
            dropped.append({**item, "why": "a secondary detail; does not block dispatch"})
        elif rule in seen:
            continue
        else:
            seen.add(rule)
            kept.append(item)
    return kept, dropped


def invented_numbers(question, *sources):
    """Numbers in the question that appear in none of the sources."""
    known = set()
    for s in sources:
        known.update(re.findall(r"\d+", s or ""))
    return sorted(set(re.findall(r"\d+", question or "")) - known)


class Watsonx:
    """The watsonx.ai chat API, with an IAM token renewed before it expires."""

    def __init__(self, url, project_id, api_key, model):
        self.url, self.project_id, self.model = url.rstrip("/"), project_id, model
        self._api_key = api_key
        self._token, self._expires = "", 0.0
        self.session = requests.Session()
        self.tokens = 0

    def _bearer(self):
        if time.time() > self._expires - 300:
            r = requests.post(IAM_URL, timeout=30, data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self._api_key})
            r.raise_for_status()
            body = r.json()
            self._token, self._expires = body["access_token"], float(body["expiration"])
        return "Bearer " + self._token

    def chat(self, prompt):
        body = {"model_id": self.model, "project_id": self.project_id, "temperature": 0,
                "max_tokens": 3000, "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                                 {"role": "user", "content": prompt}]}
        for attempt in range(4):
            r = self.session.post(f"{self.url}/ml/v1/text/chat?version={API_VERSION}", json=body, timeout=180,
                                  headers={"Authorization": self._bearer()})
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            if not r.ok:
                raise RuntimeError(f"watsonx.ai answered {r.status_code}: {r.text[:300]}")
            out = r.json()
            self.tokens += (out.get("usage") or {}).get("total_tokens", 0)
            return out["choices"][0]["message"].get("content") or ""
        raise RuntimeError("watsonx.ai kept failing")


def watsonx_settings():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / (".e" + "nv"), override=False)
    except ImportError:
        pass
    names = ("WATSONX_URL", "WATSONX_PROJECT_ID", "WATSONX_API_KEY")
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Set {', '.join(missing)} (see .env.example).")
    return [os.environ[n] for n in names]


# ---- the SRs ---------------------------------------------------------------------------------

def srs_from_csv(path):
    with open(path, newline="") as f:
        return [{"ticketid": r["TICKETID"], "status": r["STATUS"], "description": r["DESCRIPTION"],
                 "longdesc": r["DESCRIPTION_LONGDESCRIPTION"], "classid": r["CLASSSTRUCTUREID"],
                 "address": {"number": r["STADDRNUMBER"], "street": r["STADDRSTREET"],
                             "streetaddress": r["STREETADDRESS"], "city": r["CITY"], "code": r["SADDRESSCODE"]}}
                for r in csv.DictReader(f)]


CLASS_CODE = {name: code for code, (name, _) in cat.CLASSIFICATIONS.items()}


def srs_from_maximo(client, where=fmi.PILOT_WHERE):
    """The SRs matching `where`, the pilot SRs by default. Maximo's CLASSSTRUCTUREID is its own
    number, so the catalog code is found from the classification's name."""
    found = client.query("mxapisr", where=where, page_size=100,
                         select="ticketid,status,description,description_longdescription,classstructure.hierarchypath,"
                                + fmi.ADDRESS_SELECT)
    return [{"ticketid": s["ticketid"], "status": s.get("status", ""), "description": s.get("description"),
             "longdesc": s.get("description_longdescription"),
             "classid": CLASS_CODE.get((s.get("classstructure") or {}).get("hierarchypath", ""), ""),
             "address": fmi.service_address(s), "href": s["href"]} for s in found]


def load_notes(client):
    """The MISSINFO entries and AI check summaries already on SRs: {ticket: {description}}.
    The SR's own worklog child lists only client-viewable entries, so read MXAPIWORKLOG."""
    notes = {}
    for clause in (f'logtype="{rules["LOG_TYPE"]}"', f'description="{WORKLOG_SUMMARY}"'):
        for w in client.query("mxapiworklog", select="recordkey,description", page_size=500,
                              where='class="SR" and siteid="SRQSITE" and ' + clause):
            notes.setdefault(w.get("recordkey"), set()).add(w.get("description"))
    return notes


def not_checked(srs, notes):
    """The SRs without an AI check summary, in ticket order."""
    return sorted((s for s in srs if WORKLOG_SUMMARY not in notes.get(s["ticketid"], ())),
                  key=lambda s: s["ticketid"])


def check_sr(sr, points, ai):
    """One SR through the three steps. Returns a result dict."""
    text = request_text(sr["description"], sr["longdesc"])
    name = cat.CLASSIFICATIONS.get(sr["classid"], ("", ""))[0]
    known = rules["find_gaps"](sr["description"], sr["longdesc"], name, sr["address"])
    hint = address_hint(sr["address"], points)
    check = model_rules(sr["classid"])
    result = {"ticketid": sr["ticketid"], "status": sr["status"], "known": known, "hint": hint,
              "kept": [], "dropped": [], "question": "", "invented": [], "error": ""}
    try:
        reply = parse_reply(ai.chat(build_prompt(text, request_type(sr["classid"]), check, known, hint)))
        result["kept"], result["dropped"] = check_reply(reply, {r for r, _ in check}, text)
        # Only a flagged SR gets a question; one about a secondary detail would only add noise.
        result["question"] = str(reply.get("question") or "").strip() if (known or result["kept"]) else ""
        result["invented"] = invented_numbers(result["question"], text, hint)
    except (ValueError, RuntimeError, requests.RequestException) as e:
        result["error"] = str(e)[:300]
    return result


# ---- scoring and output ----------------------------------------------------------------------

def load_answer_key(path=ANSWER_KEY):
    with open(path, newline="") as f:
        return {r["TICKETID"]: set(filter(None, r["REQUIRED_INFO_GAP"].split(";"))) for r in csv.DictReader(f)}


def score(results, key):
    """Counts against the answer key, for the SRs in `results` that the key has."""
    s = dict(expected=0, by_rules=0, found=0, complete=0, complete_flagged=0, extra=0, invented=0, errors=0)
    for r in results:
        if r["ticketid"] not in key:
            continue
        expected = key[r["ticketid"]]
        by_rules = {g for g, _ in r["known"]}
        found = by_rules | {g["rule"] for g in r["kept"]}
        s["expected"] += len(expected)
        s["by_rules"] += len(by_rules & expected)
        s["found"] += len(found & expected)
        s["extra"] += len(found - expected)
        if not expected:
            s["complete"] += 1
            s["complete_flagged"] += bool(found)
        s["invented"] += bool(r["invented"])
        s["errors"] += bool(r["error"])
    return s


def write_csv(path, results, key):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["TICKETID", "STATUS", "EXPECTED", "RULE_GAPS", "AI_GAPS", "MISSED", "EXTRA",
                    "EVIDENCE", "DROPPED", "ADDRESS_HINT", "QUESTION", "INVENTED_NUMBERS", "ERROR"])
        for r in results:
            expected = key.get(r["ticketid"], set())
            by_rules = {g for g, _ in r["known"]}
            by_ai = {g["rule"] for g in r["kept"]}
            found = by_rules | by_ai
            w.writerow([r["ticketid"], r["status"], ";".join(sorted(expected)), ";".join(sorted(by_rules)),
                        ";".join(sorted(by_ai)), ";".join(sorted(expected - found)), ";".join(sorted(found - expected)),
                        " | ".join(f'{g["rule"]}: "{g["evidence"]}" ({g["reason"]})' for g in r["kept"]),
                        " | ".join(f'{g["rule"]}: {g["why"]}' for g in r["dropped"]),
                        r["hint"], r["question"], ";".join(r["invented"]), r["error"]])


def worklog_text(r, model):
    lines = [f"Checked by watsonx.ai ({model}) for a reviewer to confirm. Nothing was changed or sent."]
    if not (r["known"] or r["kept"]):
        lines.append("No missing information found.")
    for rule, msg in r["known"]:
        lines.append(f"- {rule}: {msg}")
    for g in r["kept"]:
        lines.append(f'- {g["rule"]}: {g["reason"]} Evidence: "{g["evidence"]}"')
    if r["hint"]:
        lines.append(f"Address file: {r['hint']}")
    if r["invented"]:
        lines.append("The drafted question was withheld: it has a number that is in neither the request "
                     f"nor the address file ({', '.join(r['invented'])}).")
    elif r["question"]:
        lines.append(f"Question for the resident: {r['question']}")
    return "\n".join(lines)


def _entry(logtype, description, text):
    return {"logtype": logtype, "description": description, "description_longdescription": text,
            "clientviewable": False}


def worklog_entries(r, model, noted):
    """The internal work logs for one checked SR: a MISSINFO entry per gap not yet noted, then
    the summary."""
    entries = [_entry(rules["LOG_TYPE"], rules["_summary"](rule), msg) for rule, msg in r["known"]
               if rules["_summary"](rule) not in noted]
    entries += [_entry(rules["LOG_TYPE"], rules["_summary"](g["rule"]),
                       f'Suggested by watsonx.ai ({model}): {g["reason"]} Evidence: "{g["evidence"]}"')
                for g in r["kept"] if rules["_summary"](g["rule"]) not in noted]
    return entries + [_entry(SUMMARY_LOG_TYPE, WORKLOG_SUMMARY, worklog_text(r, model))]


def apply(client, srs, results, model, notes):
    """Add the work logs to each open SR checked without an error and not checked before.
    Returns the number of SRs that failed."""
    href = {s["ticketid"]: s.get("href") for s in srs}
    checked = gaps = failed = 0
    for r in results:
        noted = notes.get(r["ticketid"], set())
        if r["error"] or r["status"] in fmi.HISTORY_STATUSES or WORKLOG_SUMMARY in noted:
            continue
        entries = worklog_entries(r, model, noted)
        try:
            client.merge(href[r["ticketid"]], {"worklog": entries})
            checked += 1
            gaps += len(entries) - 1
        except MaximoError as e:
            failed += 1
            print(f"  FAILED    {r['ticketid']} - {e}")
    print(f"{checked} SRs marked as checked, {gaps} missing-information entries added, {failed} SRs failed")
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"watsonx.ai chat model (default {DEFAULT_MODEL})")
    ap.add_argument("--only", nargs="*", help="limit to these ticket IDs")
    ap.add_argument("--csv", type=Path, help="read the SRs from a load file instead of Maximo")
    ap.add_argument("--out", type=Path, help="results CSV (default evaluation/ai-missing-info-<model>.csv)")
    ap.add_argument("--apply", action="store_true", help="add the work logs in Maximo (default: preview)")
    ap.add_argument("--new", action="store_true",
                    help="check the open SRs at SRQSITE that have no AI check summary yet (the scheduled job)")
    ap.add_argument("--limit", type=int, help="check at most this many SRs")
    args = ap.parse_args()
    if (args.apply or args.new) and args.csv:
        sys.exit("--apply and --new need the SRs from Maximo; leave out --csv.")

    ai = Watsonx(*watsonx_settings(), model=args.model)
    client, notes = None, {}
    if args.csv:
        srs = srs_from_csv(args.csv)
    else:
        s = load_settings()
        client = MaximoClient(s.url, s.api_key, s.api_path, verify_tls=s.verify_tls)
        srs = srs_from_maximo(client, OPEN_WHERE if args.new else fmi.PILOT_WHERE)
        notes = load_notes(client)
    if args.only:
        srs = [s for s in srs if s["ticketid"] in set(args.only)]
    srs = not_checked(srs, notes) if args.new else sorted(srs, key=lambda s: s["ticketid"])
    srs = srs[:args.limit] if args.limit else srs

    points, key = load_address_points(), load_answer_key()
    results = []
    for sr in srs:
        r = check_sr(sr, points, ai)
        results.append(r)
        gaps = [g for g, _ in r["known"]] + [g["rule"] for g in r["kept"]]
        note = r["error"] or ("INVENTED " + ",".join(r["invented"]) if r["invented"] else "")
        print(f"  {r['ticketid']} {','.join(gaps) or '-':28} expected {','.join(sorted(key.get(r['ticketid'], []))) or '-':22} {note}", flush=True)

    print(f"\n{len(results)} SRs checked with {args.model}; {ai.tokens} tokens.")
    if args.out or not args.new:
        out = args.out or ROOT / "evaluation" / f"ai-missing-info-{args.model.split('/')[-1]}.csv"
        write_csv(out, results, key)
        print(f"Results: {out}")
    s = score(results, key)
    if s["expected"] or s["complete"]:
        print(f"Answer-key gaps found: {s['found']} of {s['expected']} (the rules alone: {s['by_rules']})")
        print(f"Complete SRs flagged: {s['complete_flagged']} of {s['complete']}; flags not in the key: {s['extra']}")
    print(f"Questions with an invented number: {sum(bool(r['invented']) for r in results)}; "
          f"model errors: {sum(bool(r['error']) for r in results)}")
    if args.apply:
        return 1 if apply(client, srs, results, args.model, notes) else 0
    print("Preview only; run with --apply to add the work logs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
