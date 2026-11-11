"""How much of a QAlert request the text parsers can recover from today's long description.

The SR scripts can only parse the long description when the integration sends text. This runs
their parsers over the 65 pilot SRs and counts, per field, how often the parsed value equals what
QAlert holds (data/qalert/requests.json). The counts are evidence for the County integration
proposal (docs/qalert-integration-proposal.md):

- The address, coordinates, phone and email come back for every SR, but only because the
  synthetic long description has one fixed layout. Real QAlert text varies, so treat this as the
  best case.
- The channel and the priority are not in the text at all.
- Whether an address is in the County address file needs a lookup the text cannot give: the
  structured service address carries the answer as its address code.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rules: dict = {}
exec(compile((ROOT / "scripts/autoscript/srqmissinfo.py").read_text(), "srqmissinfo.py", "exec"), rules)
dup: dict = {}
exec(compile((ROOT / "scripts/autoscript/srqdupscore.py").read_text(), "srqdupscore.py", "exec"), dup)

FIELDS = ("house number", "street", "city", "coordinates", "phone", "email", "channel", "priority",
          "in the County address file")
NOT_IN_TEXT = {"channel", "priority", "in the County address file"}


def _rows(path):
    with open(ROOT / path, newline="") as f:
        return list(csv.DictReader(f))


def parse_text(longdesc):
    """Every field the long description yields, with the scripts' own parsers where they exist."""
    written = rules["address_of"](longdesc)
    parts = [p.strip() for p in written.split(",") if p.strip()]
    first = parts[0] if len(parts) >= 3 else ""  # "<number> <street>, <city>, FL"
    number = first.split(" ", 1)[0] if rules["has_house_number"](first) else ""
    customer = next((line for line in rules["_text"](longdesc).split("\n") if line.startswith("Customer:")), "")
    tokens = customer.split()
    return {
        "house number": number,
        "street": first[len(number):].strip(),
        "city": parts[-2] if len(parts) >= 2 else "",
        "coordinates": dup["coordinates"](longdesc),
        "phone": next((t for t in tokens if len(t) == 12 and t[3] == "-" and t[7] == "-"), ""),
        "email": next((t for t in tokens if "@" in t), ""),
    }


def qalert_values(request):
    return {
        "house number": request["streetNum"], "street": request["streetName"], "city": request["cityName"],
        "coordinates": (request["latitude"], request["longitude"]) if request["latitude"] else None,
        "phone": request["phone"], "email": request["email"],
    }


def recovery():
    requests = {str(r["id"]): r for r in json.loads((ROOT / "data/qalert/requests.json").read_text())}
    counts = dict.fromkeys(FIELDS, 0)
    srs = _rows("data/maximo/sr.csv")
    for sr in srs:
        parsed, truth = parse_text(sr["DESCRIPTION_LONGDESCRIPTION"]), qalert_values(requests[sr["EXTERNALSYSTEM_TICKETID"]])
        for f in FIELDS:
            if f in NOT_IN_TEXT:
                continue
            value = parsed[f].upper() if f == "street" else parsed[f]
            counts[f] += value == truth[f]
    return counts, len(srs)


def test_parser_recovery_per_field(capsys):
    counts, total = recovery()
    with capsys.disabled():
        print(f"\nText parser recovery over {total} pilot SRs:")
        for f in FIELDS:
            print(f"  {f:<28} {counts[f]:>2} of {total}")
    assert total == 65
    assert counts == {"house number": 65, "street": 65, "city": 65, "coordinates": 65, "phone": 65, "email": 65,
                      "channel": 0, "priority": 0, "in the County address file": 0}
