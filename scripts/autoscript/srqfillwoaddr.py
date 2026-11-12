# SRQFILLWOADDR: one-off. Fills the service address of pilot WOs that are already in history.
#
# Maximo refuses a closed or cancelled WO's address through the API: setting the coordinates adds
# a GEOMETRY row, and a WO in history takes no new child rows (BMXAA0024E). This script sets the
# fields on the WO's one WOSERVICEADDRESS row with access checks off and without field actions,
# so no GEOMETRY row is added. The nearby-work relationship reads LATITUDEY and LONGITUDEX from
# the address row itself. Synthetic pilot data only.
#
# It has no launch point. scripts/fill_wo_service_addresses.py --history creates it, POSTs to
# /maximo/api/script/SRQFILLWOADDR, and deletes it afterwards.
#
# Request body: {"apply": true | false, "wos": {"<our WONUM>": {"<field>": <value>, ...}, ...}}
# Response:     {"<our WONUM>": "filled" | "would fill" | "<why not>", ...}
# Without "apply" every change is rolled back.

from com.ibm.json.java import JSONObject
from java.lang import Exception as JavaException
from psdi.mbo import MboConstants
from psdi.server import MXServer

FIELDS = ("staddrnumber", "staddrstreet", "streetaddress", "city", "stateprovince", "postalcode", "country",
          "latitudey", "longitudex")
DECIMALS = ("latitudey", "longitudex")
FLAGS = MboConstants.NOACCESSCHECK | MboConstants.NOVALIDATION_AND_NOACTION


def fill(server, ours, address, apply):
    # Maximo's Jython has no `re`. A pilot or draft WO is WO291 and four digits.
    if not (len(ours) == 9 and ours.startswith("WO291") and ours[2:].isdigit()):
        return "not a pilot WO number"
    unknown = [f for f in address.keySet() if f not in FIELDS]
    if unknown:
        return "unknown fields: " + ", ".join(sorted(unknown))
    wos = server.getMboSet("WORKORDER", userInfo)
    rows = None
    try:
        # Only WOs in history: an open WO takes its address through the API.
        wos.setWhere("siteid = 'SRQSITE' and historyflag = 1 and externalrefid = '%s'" % ours)
        wo = wos.moveFirst()
        if wo is None:
            return "no pilot WO in history with this number"
        rows = server.getMboSet("WOSERVICEADDRESS", userInfo)
        rows.setWhere("siteid = 'SRQSITE' and wonum = '%s'" % wo.getString("WONUM").replace("'", "''"))
        if rows.count() != 1:
            return "%d address rows; expected one" % rows.count()
        row = rows.moveFirst()
        for field in address.keySet():
            value = address.get(field)
            row.setValue(field, float(value) if field in DECIMALS else unicode(value), FLAGS)
        if apply:
            rows.save()
            return "filled"
        rows.rollback()
        return "would fill"
    except (Exception, JavaException) as e:
        return "error: " + unicode(e)
    finally:
        if rows is not None:
            rows.close()
        wos.close()


body = JSONObject.parse(requestBody)
server = MXServer.getMXServer()
result = JSONObject()
for ours in body.get("wos").keySet():
    result.put(ours, fill(server, ours, body.get("wos").get(ours), bool(body.get("apply"))))
responseBody = result.serialize()
