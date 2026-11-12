#!/usr/bin/env python3
"""Score MAS AI recommendations on the pilot SRs against the answer key.

The results file has one row per pilot SR and feature:
    TICKETID, FEATURE, AI_VALUE, AI_SCORE, REVIEWER_DECISION, OVERRIDE_REASON
FEATURE is one of:
    classification  the recommended classification, by name as Maximo shows it (e.g. WATER-LEAK)
    team            the recommended PERSONGROUP on the SR's work order (its draft, if it had none)
    similar_wo      the work orders Maximo listed as similar, separated by ";"
    nearby_wo       the work orders the Nearby work dialog listed (within about 150 m), separated by ";"
    similar_sr      the service requests Maximo listed as similar to an open SR, separated by ";"
AI_VALUE can also be:
    (blank)  not tried yet; the row is left out of the score
    n/a      the feature was not available on this record, e.g. the SR has no work order; left out
    none     Maximo was asked and recommended nothing; counts against the AI
REVIEWER_DECISION is accept, override or skip.

Usage (from the repository root):
    python3 scripts/score_ai_results.py --template evaluation/ai-results.csv   # a blank sheet to fill in
    python3 scripts/score_ai_results.py evaluation/ai-results.csv             # score it
Use --answer-key loader-state/answer-key-maximo.csv only if Maximo renumbered the SRs or WOs.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import pilot_catalog as cat

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["TICKETID", "FEATURE", "AI_VALUE", "AI_SCORE", "REVIEWER_DECISION", "OVERRIDE_REASON"]
FEATURES = ("classification", "team", "similar_wo", "nearby_wo", "similar_sr")
# Both list other work orders for the SR's work order, and are scored the same way.
WO_LISTS = {"similar_wo": "Similar work orders", "nearby_wo": "Nearby work orders (within about 150 m)"}
DECISIONS = ("", "accept", "override", "skip")
NOT_TRIED, NOT_SHOWN, NOTHING = "", "N/A", "NONE"
CONTROL = "Control (no issue)"
DUPLICATE = "Possible duplicate"
CLUSTER, LOOK_ALIKE = "Duplicate cluster ", "Look-alike"
OPEN = ("NEW", "QUEUED", "PENDING", "INPRG")
NAMES = {name for name, _ in cat.CLASSIFICATIONS.values()}


def read(path):
    # utf-8-sig: Excel's "CSV UTF-8" starts the file with a byte-order mark.
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def class_name(value):
    """Classifications are compared by name: Maximo numbers them itself, so ids differ by instance."""
    value = value.strip().upper()
    return cat.CLASSIFICATIONS[value][0] if value in cat.CLASSIFICATIONS else value


def team_matches(value, expected):
    # Maximo team codes hold 8 characters, so SANCLINSP is written as SANCLINS.
    return bool(expected) and value.strip().upper()[:8] == expected.upper()[:8]


def own_wos(wos):
    """Each SR's own follow-up work orders, which are never a 'similar' match for it."""
    own = {}
    for w in wos:
        if w["ORIGRECORDID"]:
            own.setdefault(w["ORIGRECORDID"], set()).add(w["WONUM"])
    return own


def expected_wos(answer, own=None):
    """Other work orders the reviewer should see: past, planned, or another SR's crew."""
    related = {r for r in answer["RELATED_RECORDS"].split(";") if r.startswith("WO")}
    return related - (own or {}).get(answer["TICKETID"], set())


def clusters(answers):
    """Each SR in a duplicate cluster -> the other reports of the same problem. The answer key names
    the cluster in SCENARIO, e.g. "Duplicate cluster A (primary)" and "Duplicate cluster A"."""
    groups = {}
    for a in answers:
        if a["SCENARIO"].startswith(CLUSTER):
            groups.setdefault(a["SCENARIO"][len(CLUSTER):].split()[0], set()).add(a["TICKETID"])
    return {t: group - {t} for group in groups.values() for t in group}


def first_reports(answers):
    """Each SR in a duplicate cluster -> the cluster's first report, which becomes the Global Issue."""
    first = {a["SCENARIO"][len(CLUSTER):].split()[0]: a["TICKETID"] for a in answers
             if a["SCENARIO"].startswith(CLUSTER) and a["SCENARIO"].endswith("(primary)")}
    return {a["TICKETID"]: first[a["SCENARIO"][len(CLUSTER):].split()[0]] for a in answers
            if a["SCENARIO"].startswith(CLUSTER)}


def template(answers, wos, srs=()):
    """One row per feature worth scoring:
    - every SR is classified;
    - the team where the answer key names one, except on a duplicate, which joins its cluster's
      work order instead of getting its own;
    - similar and nearby work orders where the answer key expects some, except on a duplicate, and
      on control SRs, where any match is noise;
    - similar service requests on every open SR in a duplicate cluster, every look-alike and every
      open control: the first should find their cluster, the others nothing.
    Team and similar work orders show on a work order; the drafts give most open SRs one. Similar
    SRs only run on open SRs, the ones the inference filter picks."""
    own, group = own_wos(wos), clusters(answers)
    # By the QAlert request ID, which Maximo never renumbers, so a remapped answer key still works.
    status = {sr["EXTERNALSYSTEM_TICKETID"]: sr["STATUS"] for sr in srs}
    rows = []
    for a in answers:
        t, duplicate = a["TICKETID"], a["EXPECTED_ALERT"] == DUPLICATE
        rows.append({"TICKETID": t, "FEATURE": "classification"})
        if a["EXPECTED_PERSONGROUP"] and not duplicate:
            rows.append({"TICKETID": t, "FEATURE": "team"})
        if (expected_wos(a, own) and not duplicate) or a["USE_CASE"] == CONTROL:
            rows += [{"TICKETID": t, "FEATURE": f} for f in WO_LISTS]
        if status.get(a["QALERT_REQUEST_ID"]) in OPEN and (t in group or a["SCENARIO"].startswith(LOOK_ALIKE) or a["USE_CASE"] == CONTROL):
            rows.append({"TICKETID": t, "FEATURE": "similar_sr"})
    return rows


def score(results, answers, wos=()):
    """Return (report lines, problems). Problems are rows that do not fit the answer key."""
    missing = {"TICKETID", "EXPECTED_CLASSSTRUCTUREID", "EXPECTED_PERSONGROUP", "RELATED_RECORDS",
               "EXPECTED_RECOMMENDATION", "USE_CASE", "SCENARIO", "EXPECTED_ALERT"} - set(answers[0] if answers else ())
    if missing:
        return [], [f"the answer key has no {', '.join(sorted(missing))} column. If it is "
                    "loader-state/answer-key-maximo.csv, run `python -m loader load --apply` to rewrite it"]
    by_id = {a["TICKETID"]: a for a in answers}
    problems, seen = [], set()
    for i, r in enumerate(results, start=2):
        ticket, feature, value = r.get("TICKETID", ""), r.get("FEATURE", ""), r.get("AI_VALUE", "")
        if ticket not in by_id:
            problems.append(f"line {i}: {ticket!r} is not a pilot SR")
        if feature not in FEATURES:
            problems.append(f"line {i}: unknown feature {feature!r}")
        if (ticket, feature) in seen:
            problems.append(f"line {i}: {ticket} {feature} appears twice")
        seen.add((ticket, feature))
        if r.get("REVIEWER_DECISION", "").lower() not in DECISIONS:
            problems.append(f"line {i}: decision must be accept, override or skip")
        if feature == "classification" and value.upper() not in (NOT_TRIED, NOT_SHOWN, NOTHING) \
                and class_name(value) not in NAMES:
            problems.append(f"line {i}: {value!r} is not a classification name; record the name Maximo shows, "
                            "e.g. WATER-LEAK, not Maximo's numeric id")
    if problems:
        return [], problems

    out = []
    rows = {f: [r for r in results if r.get("FEATURE") == f] for f in FEATURES}

    def pct(n, d):
        return f"{n}/{d} ({n / d:.0%})" if d else "0/0"

    def tried(feature_rows):
        """Rows where Maximo was asked, and a line saying how many were not."""
        values = Counter(r.get("AI_VALUE", "").upper() for r in feature_rows)
        kept = [r for r in feature_rows if r.get("AI_VALUE", "").upper() not in (NOT_TRIED, NOT_SHOWN)]
        return kept, f"  scored {len(kept)}; not tried yet {values[NOT_TRIED]}; not available {values[NOT_SHOWN]}"

    cls, note = tried(rows["classification"])
    if rows["classification"]:
        answered = [r for r in cls if r["AI_VALUE"].upper() != NOTHING]
        hits = {r["TICKETID"] for r in answered
                if class_name(r["AI_VALUE"]) == class_name(by_id[r["TICKETID"]]["EXPECTED_CLASSSTRUCTUREID"])}
        misfiled = [r for r in cls if "Suggested reclassification:" in by_id[r["TICKETID"]]["EXPECTED_RECOMMENDATION"]]
        out += ["Classification", note,
                f"  recommendation given   {pct(len(answered), len(cls))}",
                f"  matches the answer key {pct(len(hits), len(cls))}",
                f"  misclassified SRs corrected {pct(sum(r['TICKETID'] in hits for r in misfiled), len(misfiled))}"]

    # A duplicate joins its cluster's work order, so it has no team of its own to recommend.
    team, note = tried([r for r in rows["team"] if by_id[r["TICKETID"]]["EXPECTED_PERSONGROUP"]
                        and by_id[r["TICKETID"]]["EXPECTED_ALERT"] != DUPLICATE])
    if rows["team"]:
        answered = [r for r in team if r["AI_VALUE"].upper() != NOTHING]
        hits = [r for r in answered if team_matches(r["AI_VALUE"], by_id[r["TICKETID"]]["EXPECTED_PERSONGROUP"])]
        out += ["Team", note,
                f"  recommendation given   {pct(len(answered), len(team))}",
                f"  matches the answer key {pct(len(hits), len(team))}"]

    own = own_wos(wos)
    for feature, title in WO_LISTS.items():
        if not rows[feature]:
            continue
        sim, note = tried(rows[feature])
        listed = {r["TICKETID"]: {v.strip() for v in r["AI_VALUE"].split(";") if v.strip() and v.strip().upper() != NOTHING}
                  - own.get(r["TICKETID"], set()) for r in sim}
        wanted = {t: expected_wos(by_id[t], own) for t in listed}
        with_expected = [t for t in listed if wanted[t]]
        found = sum(len(listed[t] & wanted[t]) for t in with_expected)
        total = sum(len(wanted[t]) for t in with_expected)
        controls = [t for t in listed if by_id[t]["USE_CASE"] == CONTROL]
        out += [title, note,
                f"  related WOs surfaced    {pct(found, total)} across {len(with_expected)} SRs",
                f"  SRs with every related WO {pct(sum(wanted[t] <= listed[t] for t in with_expected), len(with_expected))}",
                f"  control SRs with any match {pct(sum(bool(listed[t]) for t in controls), len(controls))}"]

    simsr, note = tried(rows["similar_sr"])
    if rows["similar_sr"]:
        group, first = clusters(answers), first_reports(answers)
        listed = {r["TICKETID"]: {v.strip() for v in r["AI_VALUE"].split(";") if v.strip() and v.strip().upper() != NOTHING}
                  - {r["TICKETID"]} for r in simsr}
        in_cluster = [t for t in listed if t in group]
        duplicates = [t for t in in_cluster if first[t] != t]
        look_alikes = [t for t in listed if by_id[t]["SCENARIO"].startswith(LOOK_ALIKE)]
        # A look-alike resembles a cluster: matching any of its reports would group it wrongly.
        resembles = {t: {m for r in by_id[t]["RELATED_RECORDS"].split(";") if r.startswith("SR")
                         for m in {r} | group.get(r, set())} for t in look_alikes}
        controls = [t for t in listed if by_id[t]["USE_CASE"] == CONTROL]
        out += ["Similar service requests (duplicate reports)", note,
                f"  reports matched to their duplicate group {pct(sum(bool(listed[t] & group[t]) for t in in_cluster), len(in_cluster))}",
                f"  duplicates shown their first report (the Global Issue) "
                f"{pct(sum(first[t] in listed[t] for t in duplicates), len(duplicates))}",
                f"  group members surfaced   {pct(sum(len(listed[t] & group[t]) for t in in_cluster), sum(len(group[t]) for t in in_cluster))}",
                f"  look-alikes wrongly matched to the group they resemble (lower is better) "
                f"{pct(sum(bool(listed[t] & resembles[t]) for t in look_alikes), len(look_alikes))}",
                f"  control SRs with any match (lower is better) {pct(sum(bool(listed[t]) for t in controls), len(controls))}"]

    decisions = Counter(r.get("REVIEWER_DECISION", "").lower() or "not reviewed" for r in results)
    reasons = Counter(r["OVERRIDE_REASON"] for r in results if r.get("OVERRIDE_REASON"))
    out += ["Reviewer decisions", *(f"  {k:<22} {v}" for k, v in sorted(decisions.items()))]
    if reasons:
        out += ["Override reasons", *(f"  {v} x {k}" for k, v in reasons.most_common())]
    out.append(f"Small sample: {len(by_id)} pilot SRs. Read the counts, not only the percentages.")
    return out, []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", nargs="?", help="results CSV to score")
    parser.add_argument("--template", metavar="PATH", help="write a blank results sheet to PATH and stop")
    parser.add_argument("--answer-key", default=ROOT / "data" / "answer-key.csv", help="answer key to score against")
    args = parser.parse_args(argv)
    answers = read(args.answer_key)
    # The drafts are the SRs' own work orders too, so they are never a "similar" match for them.
    drafts = ROOT / "data" / "maximo" / "drafts" / "wo.csv"
    wos = read(ROOT / "data" / "maximo" / "wo.csv") + (read(drafts) if drafts.exists() else [])
    if args.template:
        path = Path(args.template)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
            writer.writeheader()
            writer.writerows(template(answers, wos, read(ROOT / "data" / "maximo" / "sr.csv")))
        print(f"Wrote {path}")
        return 0
    if not args.results:
        parser.error("give a results CSV, or --template PATH")
    report, problems = score(read(args.results), answers, wos)
    if problems:
        print("Results do not fit the answer key:", *problems, sep="\n  ", file=sys.stderr)
        return 2
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
