# Maximo automation script SRQMISSINFO (language: python / Jython 2.7).
#
# Flags service requests that lack information a crew needs, without blocking the save, so a
# report from QAlert is never lost. Each gap becomes one work log entry of type MISSINFO on the
# SR; a Work Queue lists the open SRs that have one. Rules follow
# data/reference/required-information.csv. Only the rules the record itself can decide are here:
#   ADDR        no house number in the address
#   LS-ID       a lift station alarm with neither a street nor a station name or number
#   ADDR-VALID  an address in a city outside Sarasota County, or a house number and street that
#               match no address in the County file (the service address has no address code)
#
# The address is read from both the SR's service address (TKSERVICEADDRESS) and the "Address:" line
# of the long description, and a detail counts as given when either has it, so a partly filled
# service address (a code picked in the UI, a city only) never raises a false flag, and an SR with
# an empty service address, such as one from the text-only history, is judged on its text as
# before. Only the service address can say whether an address is in the County file: a house
# number and street with no address code matched nothing there.
# Rules that need the request to be read and understood (what the meter problem is, two issues in
# one request) are left to the reviewer and the AI.
#
# Runs from an object launch point on SR: event Save (Add and Update), Before Save. SRs loaded
# before the script existed are checked once with scripts/flag_missing_info.py, which runs these
# same rules through the REST API.
#
# The rule functions are plain Python so tests/test_missing_info_rules.py can run them against
# the answer key outside Maximo. They import nothing: Maximo's Jython has no standard library, so
# `import re` fails and, in a Before Save script, blocks every SR save.

SITE = "SRQSITE"
LOG_TYPE = "MISSINFO"
LIFT_STATION_CLASS = "WW-LIFT"

# Places a resident may name that are outside Sarasota County. Englewood and Lakewood Ranch
# straddle the county line, so they are not listed.
OUT_OF_COUNTY = ("BRADENTON", "PALMETTO", "ELLENTON", "PARRISH", "MYAKKA CITY", "PORT CHARLOTTE",
                 "PUNTA GORDA", "ARCADIA", "CHARLOTTE COUNTY", "MANATEE COUNTY")

MESSAGES = {
    "ADDR": "No house number in the address. Ask the resident for the house number, or a cross "
            "street or landmark a crew can find.",
    "LS-ID": "Lift station alarm with no station name or number and no street. Ask for the "
             "station name or number shown on the panel, or the street it is on.",
    "ADDR-VALID": "The address is in %s, outside Sarasota County. Confirm the location, and "
                  "whether the property is a Sarasota County utility customer.",
}
UNMATCHED_MESSAGE = ("%s is not in the County address file. Confirm the house number and street with "
                     "the resident before dispatch.")
ADDRESS_FIELDS = (("number", "STADDRNUMBER"), ("street", "STADDRSTREET"), ("streetaddress", "STREETADDRESS"),
                  ("city", "CITY"), ("code", "SADDRESSCODE"))
MAX_ADDRESS_ROWS = 5  # an SR has one service address row; never scan a whole table in a save
# The SR's relationship to its TKSERVICEADDRESS rows, as MXAPISR uses it. A relationship named
# TKSERVICEADDRESS does not exist on SR.
ADDRESS_RELATIONSHIP = "SERVICEADDRESS"

STATION_WORDS = ("station", "ls")  # "lift station" ends in "station"
STATION_MARKERS = ("#", "no.", "no", "number")


def _starts_ci(text, word, i):
    return text[i:i + len(word)].lower() == word


def _skip_spaces(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _line_breaks(html):
    """</div>, <br>, <br/> and <br /> become line breaks."""
    out = []
    i = 0
    while i < len(html):
        if _starts_ci(html, "</div>", i):
            out.append("\n")
            i += len("</div>")
            continue
        if _starts_ci(html, "<br", i):
            end = _skip_spaces(html, i + 3)
            if html.startswith("/", end):
                end += 1
            if html.startswith(">", end):
                out.append("\n")
                i = end + 1
                continue
        out.append(html[i])
        i += 1
    return "".join(out)


def _text(html):
    """Long descriptions are HTML: one <div> per line. Returns the text, a line per div."""
    if not html:
        return ""
    html = _line_breaks(html)
    out = []
    i = 0
    while i < len(html):
        end = html.find(">", i + 1) if html[i] == "<" else -1
        if end > i + 1:  # a tag: "<", at least one character, ">"
            i = end + 1
        else:
            out.append(html[i])
            i += 1
    return "".join(out)


def address_of(longdesc):
    """The address as the resident gave it, without the map link text."""
    text = _text(longdesc)
    start = 0
    while start < len(text) and not _starts_ci(text, "address:", start):
        start += 1
    if start == len(text):
        return ""
    line = text[start + len("address:"):].lstrip().split("\n")[0].rstrip()
    if line.endswith("Map"):
        line = line[:-len("Map")]
    return line.strip()


def _is_word_char(ch):
    return ch.isalnum() or ch == "_"


def _is_letter(ch):
    return "a" <= ch <= "z" or "A" <= ch <= "Z"


def _number_at(text, i):
    """True when a whole number starts at text[i], optionally after one letter: 42, B12."""
    if i < len(text) and _is_letter(text[i]) and _digits_at(text, i + 1):
        return True
    return _digits_at(text, i)


def _digits_at(text, i):
    """True when text[i:] starts with digits that end the word."""
    end = i
    while end < len(text) and text[end].isdigit():
        end += 1
    return end > i and (end == len(text) or not _is_word_char(text[end]))


def has_house_number(address):
    """The address starts with a house number, such as 1530 or 12B, then the street."""
    text = address.lstrip()
    i = 0
    while i < len(text) and text[i].isdigit():
        i += 1
    if i == 0:
        return False
    if i < len(text) and _is_letter(text[i]) and not text[i + 1:i + 2].isalnum():
        i += 1
    after = _skip_spaces(text, i)
    return after > i and after < len(text)


def has_station_id(text):
    """The text names a station: "lift station #42", "station no. 7", "LS 12", "station B3"."""
    low = text.lower()
    for word in STATION_WORDS:
        start = low.find(word)
        while start >= 0:
            if start == 0 or not _is_word_char(low[start - 1]):
                i = _skip_spaces(low, start + len(word))
                if _number_at(low, i):
                    return True
                for marker in STATION_MARKERS:
                    if low.startswith(marker, i) and _number_at(low, _skip_spaces(low, i + len(marker))):
                        return True
            start = low.find(word, start + 1)
    return False


def _field(address, key):
    value = address.get(key)
    return str(value).strip() if value is not None else ""


def structured_address(address):
    """The service address as a dict of ADDRESS_FIELDS keys, or None when it is empty."""
    if not address or not [k for k, _ in ADDRESS_FIELDS if _field(address, k)]:
        return None
    return {k: _field(address, k) for k, _ in ADDRESS_FIELDS}


def _place(city):
    """A city name for the county check: case, dots and extra spaces ignored."""
    return " ".join(city.replace(".", " ").split()).upper()


def find_gaps(description, longdesc, class_path, address=None):
    """The required-information rules a request breaks, as (rule id, message) pairs.

    `address` is the SR's service address, a dict with the ADDRESS_FIELDS keys. A detail counts as
    given when the service address or the long description has it.
    """
    written = address_of(longdesc)
    parts = [p.strip() for p in written.split(",") if p.strip()]
    has_number = has_house_number(written)
    # "Fennimore Pines Blvd, North Port, FL" has a street; "North Port, FL" has only a city.
    has_street = len(parts) >= 3
    city = parts[-2] if len(parts) >= 2 else ""
    unmatched = False
    fields = structured_address(address)
    if fields:
        coded = bool(fields["code"])  # a County address point: a full, known address
        field_number = bool(fields["number"]) or has_house_number(fields["streetaddress"]) or has_house_number(fields["street"])
        field_street = bool(fields["street"] or fields["streetaddress"])
        # A house number and street with no code matched nothing in the County address file.
        unmatched = field_number and field_street and not coded
        has_number = has_number or field_number or coded
        has_street = has_street or field_street or coded
        city = fields["city"] or city
    gaps = []
    if not has_number:
        gaps.append(("ADDR", MESSAGES["ADDR"]))
    if class_path == LIFT_STATION_CLASS and not has_street:
        text = (description or "") + "\n" + _text(longdesc)
        if not has_station_id(text):
            gaps.append(("LS-ID", MESSAGES["LS-ID"]))
    if _place(city) in OUT_OF_COUNTY:
        gaps.append(("ADDR-VALID", MESSAGES["ADDR-VALID"] % city))
    elif unmatched:
        shown = fields["streetaddress"] or " ".join([v for v in (fields["number"], fields["street"]) if v])
        gaps.append(("ADDR-VALID", UNMATCHED_MESSAGE % shown))
    return gaps


# ---- Maximo side -----------------------------------------------------------------------------

def _summary(rule):
    return ("Missing information: " + rule)[:100]


def _get(mbo, attribute):
    try:
        return mbo.getString(attribute)
    except:  # noqa: E722  a missing relationship raises a Java exception, which `Exception` misses
        return ""


def _first_address(rows, ticket):
    """The first non-empty row of this SR among the first few, or None.

    A row being added with the SR may not carry the ticket yet, so a new row counts as this SR's.
    """
    i = 0
    row = rows.getMbo(i)
    while row is not None and i < MAX_ADDRESS_ROWS:
        if row.getString("TICKETID") == ticket or row.toBeAdded():
            found = structured_address({k: row.getString(a) for k, a in ADDRESS_FIELDS})
            if found:
                return found
        i += 1
        row = rows.getMbo(i)
    return None


def service_address(sr):
    """The SR's service address fields, or None.

    An SR being added has not saved its address row yet, so for a new SR the set of its
    SERVICEADDRESS relationship, which holds the row in memory, is read. A saved SR is read
    through a set scoped to it. The
    row's ORGID is another org's or blank on TechZone, so the scope is ticket and class only. Rows
    of another SR are ignored and only the first few are read, in case a relationship returns
    every SR's rows, as WORKLOG does.
    """
    ticket = sr.getString("TICKETID")
    try:
        if sr.toBeAdded():
            return _first_address(sr.getMboSet(ADDRESS_RELATIONSHIP), ticket)
        return _first_address(sr.getMboSet("$SRQMISSADDR", "TKSERVICEADDRESS", "ticketid=:ticketid and class=:class"),
                              ticket)
    except:  # noqa: E722  an unknown relationship raises a Java exception; the text decides then
        return None


def check_sr(sr):
    """Add one MISSINFO work log per gap not already noted. Returns the number added."""
    if sr.getString("SITEID") != SITE:
        return 0
    gaps = find_gaps(sr.getString("DESCRIPTION"), sr.getString("DESCRIPTION_LONGDESCRIPTION"),
                     _get(sr, "CLASSSTRUCTURE.HIERARCHYPATH"), service_address(sr))
    if not gaps:
        return 0
    # SR's own WORKLOG relationship returns every SR's work logs on TechZone, so use one scoped to
    # this SR. A log added to it takes this SR's ticket, class, site and organization.
    logs = sr.getMboSet("$SRQMISSINFO", "WORKLOG", "recordkey=:ticketid and class=:class and siteid=:siteid")
    noted = set()
    i = 0
    log = logs.getMbo(i)
    while log is not None:
        if log.getString("LOGTYPE") == LOG_TYPE:
            noted.add(log.getString("DESCRIPTION"))
        i += 1
        log = logs.getMbo(i)
    added = 0
    for rule, message in gaps:
        if _summary(rule) in noted:
            continue
        log = logs.add()
        log.setValue("LOGTYPE", LOG_TYPE)
        log.setValue("DESCRIPTION", _summary(rule))
        log.setValue("DESCRIPTION_LONGDESCRIPTION", message)
        log.setValue("CLIENTVIEWABLE", False)
        added += 1
    return added


# Maximo passes the SR being saved as `mbo`. It is not defined when the tests or the backfill load
# these rules.
try:
    launch_mbo = mbo  # noqa: F821  (provided by Maximo)
except NameError:
    launch_mbo = None
if launch_mbo is not None:
    check_sr(launch_mbo)
