# Sarasota MAS AI Pilot: synthetic sample dataset

This dataset supports Sprint 2 of the Sarasota MAS AI Pilot. It is a representative, **fully synthetic** set of Maximo service requests (SRs), work orders (WOs), and work logs, together with the mock QAlert data that supplies requester and intake context. It covers the three pilot use cases:

- Missing-Information Detection
- Duplicate Identification
- Historical / Planned Work Context

An answer key states what MAS AI is expected to recommend for every SR.

No value in the dataset comes from real Sarasota County records:
- People, phone numbers, emails, and street names are invented.
- City names and ZIP codes are real Sarasota County places, so addresses look local.
- Phones use the `941-555-0100` to `941-555-0199` range, which is reserved for fiction.
- Emails use the reserved `example.com`, `example.org`, and `example.net` domains.

## Regenerate and validate

```bash
python3 scripts/generate_pilot_dataset.py   # rewrites everything under data/
python3 scripts/validate_pilot_dataset.py   # exits 1 if any check fails
```

Generation is deterministic (fixed seed), so rerunning produces identical files.

To change the data, edit `scripts/pilot_catalog.py` and regenerate. That file holds the people, request types, scenarios, and past and planned work.

The validator checks the following:
- Every link between files resolves.
- Scenario counts match the catalog.
- Location scenarios agree with the GIS stand-in.
- The Maximo person-record gap and an inactive employee are both represented.
- Every phone number and email stays in the fictional ranges.

## Files

| File | Rows | What it represents |
|---|---|---|
| `data/maximo/sr.csv` | 60 | Maximo SRs as the current QAlert feed creates them |
| `data/maximo/wo.csv` | 41 | 19 follow-up WOs created from SRs, 14 past WOs, and 8 planned or in-progress project WOs |
| `data/maximo/worklog.csv` | 125 | Field notes on WOs and planner notes on SRs |
| `data/maximo/person.csv` | 18 | Maximo PERSON records: the integration account, field staff, and 9 of the 15 QAlert staff |
| `data/qalert/requests.json` | 60 | The QAlert requests behind each SR |
| `data/qalert/activity.json` | 139 | QAlert request history (Created, Assigned, Closed) |
| `data/qalert/employees.json` | 15 | QAlert staff who enter requests; this is the contact lookup target |
| `data/qalert/types.json` / `departments.json` | 12 / 5 | QAlert request types and departments |
| `data/reference/address-points.csv` | 236 | A stand-in for the County GIS address layer, used to validate locations |
| `data/answer-key.csv` | 60 | The expected scenario, alert, contact, clarification question, related records, and recommendation for every SR |

## How the files link

```
sr.csv  EXTERNALSYSTEM_TICKETID ──► qalert/requests.json  id
sr.csv  long description "Entered by: <id>" ──► qalert/employees.json  id  (──► person.csv PERSONID, when mapped)
wo.csv  ORIGRECORDID ──► sr.csv TICKETID          (follow-up WOs only)
worklog.csv  RECORDKEY ──► sr.csv TICKETID or wo.csv WONUM  (by CLASS)
qalert/activity.json  requestId ──► qalert/requests.json id
answer-key.csv  TICKETID ──► sr.csv;  RELATED_RECORDS ──► sr.csv / wo.csv
```

ID ranges are distinct from real Sarasota ranges:

| Record | ID range |
|---|---|
| SR | `SR800001` and up |
| WO | `WO2900001` and up |
| QAlert request | `700001` and up |
| Work log | `3000001` and up |
| Address point | `AP00001` and up |

## Maximo SRs: today's shape, plus the employee ID

Each SR looks the way the current integration produces it:

- `REPORTEDBY`, `AFFECTEDPERSON`, and `CREATEDBY` are `MWQSCINT`, and `REPORTEDNAME` is "QAlert Integration". `REPORTEDPHONE` is empty.
- `EXTERNALSYSTEM` is `QAlert`, and `EXTERNALSYSTEM_TICKETID` holds the QAlert request ID.
- `DESCRIPTION` is `<request type>, <street address>`.
- `DESCRIPTION_LONGDESCRIPTION` follows the observed HTML pattern, with one addition, the **"Entered by"** line. It shows how the QAlert employee ID could reach Maximo:

```html
<div>Customer: NAME EMAIL PHONE</div>
<div>Address: 123 Street, City, FL <a target="_blank" href="https://www.google.com/maps/search/LAT,LON">Map</a></div>
<div>What the caller reported</div>
<div>Entered by: 0821106</div>
```

The real file has no line breaks between the `div` elements. When the resident gave no email, a double space is left, as in real records. When there is no usable address, the map link is omitted.

Dates are ISO 8601 with the Eastern offset (for example `2026-10-19T14:52:36-04:00`). SR report dates run from 2026-08-03 to 2026-10-27. 41 SRs are `QUEUED` (awaiting review); the rest are `RESOLVED` or `CLOSED`, each with a follow-up WO.

## Mock QAlert data

`requests.json` is a top-level array, matching the documented `requests/get` response. Field names follow the QAlert v1 evidence in [the API research](../plans/reports/researcher-261027-1254-qalert-api-schema.md).

| Field(s) | Basis |
|---|---|
| `id`, `status`, `createDate`, `createDateUnix`, `lastAction`, `lastActionUnix`, `typeId`, `typeName`, `priorityToDisplay`, `hasLinks`, `comments`, `streetNum`, `streetName`, `crossName`, `cityName`, `latitude`, `longitude` | Confirmed in public QAlert client code and fixtures |
| `origin` | Confirmed field. Every value is `Control Panel`, because the pilot assumes only staff enter requests. |
| `name`, `email` (resident) | Seen in a public test fixture only |
| `phone` (resident), `intakeMethod`, `employeeId` | **Provisional.** These are our assumption and are not in any public source. |

Other conventions:

- `status` uses `0` for open, `1` for closed, and `3` for in progress (from public Somerville configuration).
- Dates use QAlert's `M/D/YYYY h:mm AM` format.
- Requests with no usable address have `latitude` and `longitude` set to `0`.
- `streetName` is uppercase, as in the public fixture.

`activity.json` uses the confirmed fields `id`, `requestId`, `displayDate`, `code`, `codeDesc`, and `routeId`.
- On the "Created" entry, `routeId` is the employee's username.
- On "Assigned" and "Closed" entries, `routeId` is a department route such as `PUWater`.
- The numeric `code` values (1, 4, and 15) are illustrative.

`employees.json` is **provisional**: no public QAlert employee schema exists. Each record has `id`, `username`, `firstName`, `lastName`, `email`, `phone`, `department`, and `active`.
- The `id` uses the same 7-digit format as Maximo PERSONID. This reflects the pilot assumption that employee IDs are shared across QAlert and Maximo.
- Six of the 15 employees have no Maximo PERSON record. This reproduces the "requester does not map to a Maximo person" gap.
- Two employees are inactive.

## Scenarios

| Use case | Scenario | SRs | What the AI should notice |
|---|---|---|---|
| Missing-Information Detection | Missing location | 4 | No house number, or no address at all |
| | Invalid location | 3 | A house number that is not in the GIS file, a misspelled street, or an address outside the County |
| | Insufficient problem detail | 4 | For example "Customer has a question about the meter." |
| | Unclear request | 3 | The device or problem is never identified |
| | Incorrect classification | 4 | For example stormwater flooding filed as a water leak, or a force main filed as a water main |
| | Multiple issues in one request | 3 | Two problems combined in one SR |
| | County responsibility review | 3 | A single-fixture or inside-the-home problem that is likely private plumbing |
| Duplicate Identification | Duplicate clusters A–E | 12 | 5 clusters of 2–3 SRs: same problem, same or neighboring address, within hours to days, sometimes under a different request type. One cluster is the same caller calling back. |
| | Look-alike (not a duplicate) | 3 | The same street or the same night as a cluster, but a different problem |
| Historical / Planned Work Context | Related past work | 5 | Earlier WOs at the same address or on the same street |
| | Related planned work | 4 | A scheduled or in-progress project on the same street |
| Control | Complete request | 12 | Nothing to flag |

Several missing-information SRs also have a follow-up WO in which the crew found nothing, or could not find the address. These illustrate the unnecessary dispatches the pilot aims to avoid.

## Answer key

`answer-key.csv` has one row per SR with these columns:
- `USE_CASE`, `SCENARIO`, and `EXPECTED_ALERT`. The alert is `Missing or incorrect information`, `Possible duplicate`, `Related past work`, `Related planned work`, or `None`.
- `ISSUE_SUMMARY` and `MISSING_INFORMATION`.
- The QAlert employee who entered the request: ID, name, department, phone, email, active flag, and whether that employee has a Maximo PERSON record.
- `SUGGESTED_CLARIFICATION_QUESTION`, `RELATED_RECORDS`, and `EXPECTED_RECOMMENDATION`.

Here is an example of the expected output for a missing-location SR:

> Flag before dispatch: Street only; no house number. Contact Linda Chen (Contact Center, 941-555-0102, linda.chen@example.org), who entered the request in QAlert as employee 0821106. Ask: "Can the caller give the house number or describe the closest house to the leak?"

When the employee who entered the request is inactive, the recommendation routes the question to the department supervisor. When the employee has no Maximo person record, it notes that the contact details came from QAlert.

The recommendations encode the team's assumptions. Stakeholders should review them; this is the Sprint 2 "refine based on feedback" step.

## Assumptions to revisit

- QAlert employee IDs equal Maximo PERSONIDs, and only staff enter requests.
- The employee ID reaches Maximo as an "Entered by" line in the long description. In production, a dedicated field would be cleaner.
- The QAlert `employees.json` schema and the fields `phone`, `intakeMethod`, and `employeeId` are provisional until Sarasota confirms what the QAlert API returns.
- These Maximo values are illustrative, not Sarasota's actual configuration:
  - `OWNERGROUP` codes other than `WTRPIPE`;
  - the `CP` work type for planned projects;
  - `COMMODITY` values other than `WATER_PIPE`, `WATER_SERV`, and `COLLECTION`.
- Street names were invented and checked only by eye. Rename any that match a real Sarasota County street.
- The CSVs use Maximo attribute names. Loading them into the TechZone environment may require column mapping for MXLoader or the REST API.
