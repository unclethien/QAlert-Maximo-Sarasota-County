# Maximo automation script SRQDUPSCORE (language: python / Jython 2.7).
#
# Gives each AI similarity pair of service requests, and of work orders, a duplicate score that
# also counts place and time. The AI's `similarity` template compares text only, and pilot SRs all read "<type>, <address>"
# plus the same Customer/Address/Map layout, so two sewer odor reports kilometres apart score 93
# while the true duplicate scores 97. The duplicate score is
#
#     AI score x location factor x time factor
#
# so a same-type report at another address lands near 46, and a same-address report a few hours
# later keeps its AI score. The AISIMSR dialog sorts on it (relationship AISIMSRPAIR) and shows the
# points each factor took off (DUPDISTPTS, DUPTIMEPTS), which add up with it to the AI score.
#
# Work order pairs (WOSIMILARITY) get the same score: the AI compares their text only too, so a
# leak on another street scores 90 or more. The AISIMWO dialog in Work Order Tracking sorts on it
# (relationship AISIMWOPAIR). Related past work at the same place loses points for age; that was
# the user's choice, so the time factor is the same for both.
#
# Location comes from the record's service address (TKSERVICEADDRESS or WOSERVICEADDRESS, LATITUDEY
# and LONGITUDEX). A record whose service address has no coordinates, such as one from the
# text-only history, falls back to the Maps link QAlert writes into the long description
# (".../maps/search/<lat>,<lon>"); a draft WO carries its SR's.
#
# Runs from an action launch point (action SRQDUPSCORE), called by an escalation on MAXAISIMILAROBJ
# with condition aicfgname in ('SRSIMILARITY','WOSIMILARITY') and (dupscore is null or duptimepts is null). The results
# go into DUPSCORE, DUPDISTPTS and DUPTIMEPTS, custom INTEGER attributes added to MAXAISIMILAROBJ in
# Database Configuration.
#
# The scoring functions are plain Python so tests/test_duplicate_score.py can run them against the
# pilot data outside Maximo. Maximo's Jython has no standard library, so the only import is the
# trigonometry, taken from java.lang.Math in Maximo and from math elsewhere.

try:
    from java.lang import Math as _trig  # Maximo
except ImportError:
    import math as _trig  # tests

CONFIG = "SRSIMILARITY"
# What each pair's OBJECTNAME scores: its AI configuration, how OBJECTID and SIMILARTOOBJECTID find
# the record, and how the record's one service address row is read. The row is read through a set
# scoped to the record, never through ORGID: on TechZone an SR's address row has another org's or
# a blank ORGID.
KINDS = {
    "SR": (CONFIG, "ticketuid", "TKSERVICEADDRESS", "ticketid=:ticketid and class=:class"),
    "WORKORDER": ("WOSIMILARITY", "workorderid", "WOSERVICEADDRESS", "wonum=:wonum and siteid=:siteid"),
}
MAP_MARKER = "maps/search/"
EARTH_RADIUS_M = 6371000.0
DEGREE = 3.141592653589793 / 180.0

# Location factor: full weight up to NEAR_M, falling in a straight line to FAR_FACTOR at FAR_M, and
# FAR_FACTOR beyond. Pilot duplicates sit within 78 m (neighbouring houses); wrong matches are 1.3 km
# or more apart. An SR without a Maps link gets UNKNOWN_FACTOR, so it can still be listed but ranks
# below located matches.
NEAR_M = 150.0
FAR_M = 1000.0
FAR_FACTOR = 0.5
UNKNOWN_FACTOR = 0.75

# Time factor by days between the two reports. Pilot duplicates come within 2.1 days; look-alikes
# (a new problem at the same place) come 6 to 42 days later.
TIME_STEPS = ((3.0, 1.0), (14.0, 0.85))
TIME_LATER = 0.7


def coordinates(longdesc, lat=None, lon=None):
    """(latitude, longitude) from the service address when both are set, else from the Maps link
    in the long description, else None."""
    if lat not in (None, "") and lon not in (None, ""):
        return float(lat), float(lon)
    text = longdesc or ""
    start = text.find(MAP_MARKER)
    if start < 0:
        return None
    i = start + len(MAP_MARKER)
    end = i
    while end < len(text) and (text[end].isdigit() or text[end] in "-.,"):
        end += 1
    parts = text[i:end].split(",")
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def distance_m(a, b):
    """Great-circle distance in metres, or None when either point is unknown."""
    if a is None or b is None:
        return None
    lat1, lon1 = a[0] * DEGREE, a[1] * DEGREE
    lat2, lon2 = b[0] * DEGREE, b[1] * DEGREE
    h = (_trig.sin((lat2 - lat1) / 2) ** 2
         + _trig.cos(lat1) * _trig.cos(lat2) * _trig.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * _trig.asin(min(1.0, h ** 0.5))


def location_factor(meters):
    if meters is None:
        return UNKNOWN_FACTOR
    if meters <= NEAR_M:
        return 1.0
    if meters >= FAR_M:
        return FAR_FACTOR
    return 1.0 - (1.0 - FAR_FACTOR) * (meters - NEAR_M) / (FAR_M - NEAR_M)


def time_factor(days):
    if days is None:
        return 1.0
    for limit, factor in TIME_STEPS:
        if days <= limit:
            return factor
    return TIME_LATER


def _round(x):
    """Half up to a whole number. By hand because round() differs: Jython 2 rounds .5 up, Python 3 to even."""
    return int(x + 0.5)


def duplicate_score(ai_score, meters, days):
    """The AI score weighted by distance and time, rounded to a whole number."""
    return _round(ai_score * location_factor(meters) * time_factor(days))


def deductions(ai_score, meters, days):
    """(duplicate score, points taken off for distance, points taken off for time).

    Distance is applied first, then time, so the three always add up to the AI score and a factor
    of 1.0 takes off nothing.
    """
    after_distance = _round(ai_score * location_factor(meters))
    score = duplicate_score(ai_score, meters, days)
    return score, ai_score - after_distance, after_distance - score


# ---- Maximo side -----------------------------------------------------------------------------

def _record(pair, attribute, kind):
    """The SR or WO a pair column points to (OBJECTID and SIMILARTOOBJECTID hold its TICKETUID or
    WORKORDERID)."""
    key = KINDS[kind][1]
    records = pair.getMboSet("$SRQDUP" + kind + attribute, kind, key + "=" + str(pair.getLong(attribute)))
    return records.getMbo(0)


def _service_point(record, kind):
    """(lat, lon) from the record's service address, or (None, None)."""
    _, _, address, scope = KINDS[kind]
    try:
        rows = record.getMboSet("$SRQDUPADDR" + kind, address, scope)
        row = rows.getMbo(0)
        if row is None or row.isNull("LATITUDEY") or row.isNull("LONGITUDEX"):
            return None, None
        return row.getDouble("LATITUDEY"), row.getDouble("LONGITUDEX")
    except:  # noqa: E722  an unknown relationship or attribute raises a Java exception
        return None, None


def _point(record, kind):
    lat, lon = _service_point(record, kind)
    return coordinates(record.getString("DESCRIPTION_LONGDESCRIPTION"), lat, lon)


def _days_between(a, b):
    da, db = a.getDate("REPORTDATE"), b.getDate("REPORTDATE")
    if da is None or db is None:
        return None
    return abs(da.getTime() - db.getTime()) / 86400000.0


def score_pair(pair):
    """Set DUPSCORE, DUPDISTPTS and DUPTIMEPTS on one MAXAISIMILAROBJ row.

    Returns the score, or None if the row was skipped.
    """
    kind = pair.getString("OBJECTNAME")
    if kind not in KINDS or pair.getString("AICFGNAME") != KINDS[kind][0]:
        return None
    a, b = _record(pair, "OBJECTID", kind), _record(pair, "SIMILARTOOBJECTID", kind)
    if a is None or b is None:
        return None
    meters = distance_m(_point(a, kind), _point(b, kind))
    score, distance_pts, time_pts = deductions(pair.getInt("SCORE"), meters, _days_between(a, b))
    pair.setValue("DUPSCORE", score)
    pair.setValue("DUPDISTPTS", distance_pts)
    pair.setValue("DUPTIMEPTS", time_pts)
    return score


# Maximo passes the similarity pair as `mbo`. It is not defined when the tests load these functions.
try:
    launch_mbo = mbo  # noqa: F821  (provided by Maximo)
except NameError:
    launch_mbo = None
if launch_mbo is not None:
    score_pair(launch_mbo)
