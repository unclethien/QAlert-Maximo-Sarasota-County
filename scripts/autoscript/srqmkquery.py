# Maximo automation script SRQMKQUERY (language: python / Jython 2.7), no launch point.
#
# Creates or updates public saved queries in Service Requests, so the "Missing Information"
# Start Center can list the SRs behind each count. Saved queries cannot be created through the
# REST API (MXAPIQUERY and MXAPIUSERQUERY refuse ADD), but a script called directly can.
#
# Called by scripts/setup_missinfo_start_center.py:
#   POST /maximo/api/script/SRQMKQUERY  with a JSON body
#   {"queries": [{"name": ..., "description": ..., "clause": ...}]}   create or update these
#   {"remove": ["name", ...]}                                          delete these
# The response is JSON: {"done": [names handled], "owner": the user who owns the queries}.
#
# Maximo's Jython has no standard library, so the body is parsed with Maximo's Java JSON classes.

from com.ibm.json.java import JSONArray, JSONObject
from psdi.server import MXServer

APP = "SR"


def _queries(name):
    qs = MXServer.getMXServer().getMboSet("QUERY", userInfo)
    qs.setWhere("app='" + APP + "' and clausename='" + name.replace("'", "''") + "'")
    qs.reset()
    return qs


body = JSONObject.parse(requestBody)
done = []
for item in body.get("queries") or []:
    qs = _queries(item.get("name"))
    q = qs.getMbo(0)
    if q is None:
        q = qs.add()
        q.setValue("APP", APP)
        q.setValue("CLAUSENAME", item.get("name"))
    q.setValue("DESCRIPTION", item.get("description"))
    q.setValue("CLAUSE", item.get("clause"))
    q.setValue("ISPUBLIC", True)
    qs.save()
    qs.close()
    done.append(item.get("name"))
for name in body.get("remove") or []:
    qs = _queries(name)
    q = qs.getMbo(0)
    if q is not None:
        q.delete()
        qs.save()
        done.append(name)
    qs.close()
out = JSONObject()
names = JSONArray()
for name in done:
    names.add(name)
out.put("done", names)
out.put("owner", userInfo.getUserName())
responseBody = out.serialize()
