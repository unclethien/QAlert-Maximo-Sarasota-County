"""Old-to-new pilot IDs for the reload with structured SR fields.

The pilot is regenerated in the same chronological order under new ranges, so each new ID is the
old one plus a fixed offset. The rename of docs and tests and the script that retires the
superseded TechZone records both use this map. The training history keeps its IDs.
"""

import re

import pilot_catalog as cat

OLD_SR_START, OLD_REQUEST_START, OLD_WO_START, OLD_DRAFT_WO_START = 800001, 700001, 2900001, 2950001
OLD_WORKLOG_START = 3000001
SIZE = 1000  # every range holds fewer records than this

# (kind, prefix, old start, new start)
RANGES = (
    ("sr", "SR", OLD_SR_START, cat.SR_START),
    ("request", "", OLD_REQUEST_START, cat.REQUEST_START),
    ("wo", "WO", OLD_WO_START, cat.WO_START),
    ("draft", "WO", OLD_DRAFT_WO_START, cat.DRAFT_WO_START),
    ("worklog", "", OLD_WORKLOG_START, cat.WORKLOG_START),
)
_ID = re.compile(r"([A-Z]*)(\d+)")


def _shift(value, frm, to):
    m = _ID.fullmatch(str(value))
    if not m:
        return None
    prefix, number = m.group(1), int(m.group(2))
    for kind, kind_prefix, old_start, new_start in RANGES:
        start, other = (old_start, new_start) if frm == "old" else (new_start, old_start)
        if prefix == kind_prefix and start <= number < start + SIZE:
            return kind, f"{prefix}{number - start + other}"
    return None


def kind_of(value, side="old"):
    """'sr', 'request', 'wo', 'draft' or 'worklog' when the ID is in one of that side's ranges, else None."""
    found = _shift(value, side, side)
    return found[0] if found else None


def new_id(old):
    """The new ID for an old pilot SR, QAlert request, WO, draft WO or work log, or None outside those ranges."""
    found = _shift(old, "old", "new")
    return found[1] if found else None


def old_id(new):
    """The superseded ID for a new pilot ID, or None outside the new ranges."""
    found = _shift(new, "new", "old")
    return found[1] if found else None
