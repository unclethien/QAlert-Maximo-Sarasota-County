# Maximo automation script SRQDUPSCORE (language: python / Jython 2.7).
#
# Gives each AI similarity pair of service requests a duplicate score that also counts place and
# time. The AI's `similarity` template compares text only, and pilot SRs all read "<type>, <address>"
# plus the same Customer/Address/Map layout, so two sewer odor reports kilometres apart score 93
# while the true duplicate scores 97. The duplicate score is
#
#     AI score x location factor x time factor
#
# so a same-type report at another address lands near 46, and a same-address report a few hours
# later keeps its AI score. The AISIMSR dialog sorts on it (relationship AISIMSRPAIR) and shows the
# points each factor took off (DUPDISTPTS, DUPTIMEPTS), which add up with it to the AI score.
#
# Location comes from the Maps link QAlert writes into the long description
# (".../maps/search/<lat>,<lon>"), because the SRs' service address holds no coordinates.
#
# Runs from an action launch point (action SRQDUPSCORE), called by an escalation on MAXAISIMILAROBJ
# with condition aicfgname='SRSIMILARITY' and (dupscore is null or duptimepts is null). The results
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


def coordinates(longdesc):
    """(latitude, longitude) from the Maps link in the long description, or None."""
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

def _sr(pair, attribute):
    """The SR a pair column points to (OBJECTID and SIMILARTOOBJECTID hold its TICKETUID)."""
    srs = pair.getMboSet("$SRQDUP" + attribute, "SR", "ticketuid=" + str(pair.getLong(attribute)))
    return srs.getMbo(0)


def _days_between(a, b):
    da, db = a.getDate("REPORTDATE"), b.getDate("REPORTDATE")
    if da is None or db is None:
        return None
    return abs(da.getTime() - db.getTime()) / 86400000.0


def score_pair(pair):
    """Set DUPSCORE, DUPDISTPTS and DUPTIMEPTS on one MAXAISIMILAROBJ row.

    Returns the score, or None if the row was skipped.
    """
    if pair.getString("OBJECTNAME") != "SR" or pair.getString("AICFGNAME") != CONFIG:
        return None
    a, b = _sr(pair, "OBJECTID"), _sr(pair, "SIMILARTOOBJECTID")
    if a is None or b is None:
        return None
    meters = distance_m(coordinates(a.getString("DESCRIPTION_LONGDESCRIPTION")),
                        coordinates(b.getString("DESCRIPTION_LONGDESCRIPTION")))
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
