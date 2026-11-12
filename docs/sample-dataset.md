# Sarasota MAS AI Pilot: synthetic sample dataset

This dataset supports Sprint 2 of the Sarasota MAS AI Pilot. It is a representative, **fully synthetic** set of Maximo service requests (SRs), work orders (WOs), and work logs, together with the mock QAlert data that supplies requester and intake context. It covers the three pilot use cases:

- Missing-Information Detection
- Duplicate Identification
- Historical / Planned Work Context

An answer key states what MAS AI is expected to recommend for every SR.

## Where requests come from

Every request reaches Maximo through QAlert, but residents get into QAlert in four ways. Sarasota County's 311 service offers:
- the **311Connect mobile app** (iPhone and Android);
- the **311 web portal**;
- a **phone call to 311** (941-861-5000 from outside the county), answered by the County Contact Center;
- **email** to the Contact Center.

Residents submit app and web requests themselves. Contact Center staff type phone and email requests into QAlert. The County says only a small share comes through the Contact Center. The dataset uses a provisional mix to reflect that:

| Channel | SRs | Who entered it | QAlert `origin` (assumed) |
|---|---|---|---|
| 311Connect mobile app | 32 | The resident | `QAlert Mobile iOS` or `QAlert Mobile Android` |
| 311 web portal | 19 | The resident | `Web Portal` |
| Phone call to 311 | 11 | Contact Center staff | `Control Panel`, with `intakeMethod` `Phone` |
| Email to the Contact Center | 3 | Contact Center staff | `Control Panel`, with `intakeMethod` `Email` |

When a request needs clarification, who to ask depends on the channel:
- **App and web requests:** ask the resident, using the contact details they gave.
- **Phone and email requests:** ask the staff member who entered the request. One phone request records no employee anywhere, like many of the County's staff-written samples; its question goes back to the Contact Center as a team.

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
- The channel mix matches the table above.
- Only staff-entered SRs carry an "Entered by" line. The one unattributed request carries none, and has no employee in QAlert either.
- The answer key's follow-up contact matches each request's channel.
- Records follow the County's Maximo shapes:
  - SRs have no team, and every SR and WO has a known classification;
  - every non-capital WO has a job plan, its team, and failure and problem codes;
  - statuses and work types come from the Sarasota sets below.
- The Maximo person-record gap, an inactive employee, and an anonymous request are all represented.
- Requests that may not be the County's job are flagged and say who to refer the customer to. An address another utility serves, according to the GIS stand-in's `UTILITY` column, has no County team.
- A `RESOLUTION` work log only closes an SR that has no work order, and at least one misclassified SR is closed that way.
- Every County request type has one required-information rule. Each missing-information SR names the rules it breaks, and each of those rules applies to its request type.
- At least one look-alike sits at the same address as earlier work that was finished before it came in.
- Every phone number and email stays in the fictional ranges.
- Every SR has an expected classification. It differs from the SR's own classification exactly on the misclassified requests.

## Files

| File | Rows | What it represents |
|---|---|---|
| `data/maximo/sr.csv` | 65 | Maximo SRs as the current QAlert feed creates them |
| `data/maximo/wo.csv` | 41 | 19 follow-up WOs created from SRs, 14 past WOs, and 8 planned or in-progress project WOs |
| `data/maximo/worklog.csv` | 127 | Field notes on WOs and planner notes on SRs. `LOGTYPE` is `CLIENTNOTE`, except one `RESOLUTION` note that closes a misrouted SR |
| `data/maximo/person.csv` | 18 | Maximo PERSON records: the integration account, field staff, and 9 of the 15 QAlert staff |
| `data/qalert/requests.json` | 65 | The QAlert requests behind each SR, including the channel each one came from (`origin`) |
| `data/qalert/activity.json` | 150 | QAlert request history (Created, Assigned, Closed) |
| `data/qalert/employees.json` | 15 | QAlert staff who enter phone and email requests; this is the contact lookup target for those requests |
| `data/qalert/types.json` / `departments.json` | 13 / 5 | QAlert request types and departments |
| `data/reference/address-points.csv` | 244 | A stand-in for the County GIS address layer, used to validate locations. `UTILITY` says who supplies water at each address |
| `data/reference/required-information.csv` | 15 | The information a request needs before a crew is sent: three rules for every request type, and one rule per type |
| `data/answer-key.csv` | 65 | The expected scenario, alert, broken required-information rules, channel, follow-up contact, clarification question, expected team, related records, and recommendation for every SR |

## How the files link

```
sr.csv  EXTERNALSYSTEM_TICKETID ──► qalert/requests.json  id
sr.csv  long description "Entered by: <id>" ──► qalert/employees.json  id  (staff-entered SRs only; ──► person.csv PERSONID, when mapped)
wo.csv  ORIGRECORDID ──► sr.csv TICKETID          (follow-up WOs only)
worklog.csv  RECORDKEY ──► sr.csv TICKETID or wo.csv WONUM  (by CLASS)
qalert/activity.json  requestId ──► qalert/requests.json id
answer-key.csv  TICKETID ──► sr.csv;  RELATED_RECORDS ──► sr.csv / wo.csv
answer-key.csv  REQUIRED_INFO_GAP ──► reference/required-information.csv  RULE_ID
```

ID ranges are distinct from real Sarasota ranges:

| Record | ID range |
|---|---|
| SR | `SR810001` and up |
| WO | `WO2910001` and up |
| QAlert request | `710001` and up |
| Work log | `3010001` and up |
| Draft WO | `WO2915001` and up |
| Address point | `AP00001` and up |

The pilot was first loaded under `SR800001`, `WO2900001`, QAlert `700001`, work log `3000001` and drafts `WO2950001`, in the text-only shape. Those records stay in TechZone, closed, as the "before" copies. [`scripts/id_map.py`](../scripts/id_map.py) maps each old ID to its new one by a fixed offset. The training history keeps its own ranges (`SR600001`, `WO2700001`, QAlert `500001`, work log `3500001`) and the text-only shape.

## Maximo SRs: fields

Today's integration writes everything it knows about a request into the long description, and stamps the integration account on every SR. The County's sample records look like that, and so do the training history and the pilot's first load. The pilot SRs now carry the same information in Maximo fields too, by the mapping proposed to the County in [qalert-integration-proposal.md](qalert-integration-proposal.md). `maximo_sr_fields` in `scripts/generate_pilot_dataset.py` implements it.

| Value | Before: text only | Now: field |
|---|---|---|
| Channel | Not in Maximo. Look up the QAlert request's `origin`. | `SOURCE`: `APP-IOS`, `APP-ANDROID`, `WEB`, `PHONE` or `EMAIL` |
| Priority | Not in Maximo | `REPORTEDPRIORITY`, the request type's QAlert priority (1 Urgent to 4 Low) |
| Who entered it | `REPORTEDBY` is `MWQSCINT` on every SR; staff-entered SRs have an "Entered by" line | `REPORTEDBY` is the employee's PERSONID when they have an active Maximo person record, and Maximo copies it into `AFFECTEDPERSON`; blank otherwise |
| Reporter's contact | `REPORTEDEMAIL` is the integration account's; `REPORTEDPHONE` is empty | `REPORTEDPHONE` and `REPORTEDEMAIL` are whoever entered it: the resident, or the employee's QAlert phone and email |
| Resident's contact | The `Customer` line | `AFFECTEDPHONE` and `AFFECTEDEMAIL` |
| Resident's name | The `Customer` line | Still only the `Customer` line: Maximo has no field for a free-text name |
| Address | The `Address` line | The SR's service address: `SADDRESSCODE` (only when it matches an address point), `STADDRNUMBER`, `STADDRSTREET`, `STREETADDRESS`, `CITY`, `STATEPROVINCE`, `POSTALCODE`, `COUNTRY` |
| Coordinates | The Maps link | `LATITUDEY` and `LONGITUDEX` on the service address |

- The long description is unchanged, so the AI reads the same text as before.
- A missing or invalid address stays missing or invalid in the fields. It has no address code and no ZIP. A street-only address has no house number, and an SR with no usable address has only its city. Of the 65 SRs, 58 have an address code.
- `SOURCE`: 32 app (17 Android, 15 iOS), 19 web, 11 phone, 3 email. 7 staff-entered SRs name a person in `REPORTEDBY`. The employee who has left (SR810005) has an inactive person record, so she isn't named there; her QAlert phone and email are the reported contact.
- `CREATEDBY` stays `MWQSCINT`, the account that writes the record. `EXTERNALSYSTEM` is `QAlert`, and `EXTERNALSYSTEM_TICKETID` holds the QAlert request ID.
- `DESCRIPTION` is `<request type>, <street address>`.
- `DESCRIPTION_LONGDESCRIPTION` follows the observed HTML pattern. Staff-entered SRs add one line, **"Entered by"**, which shows how the QAlert employee ID could reach Maximo:

```html
<div>Customer: NAME EMAIL PHONE</div>
<div>Address: 123 Street, City, FL <a target="_blank" href="https://www.google.com/maps/search/LAT,LON">Map</a></div>
<div>What the resident or the Contact Center reported</div>
<div>Entered by: 0820533</div>
```

Other details of the long description:
- The real file has no line breaks between the `div` elements.
- App and web requests have no "Entered by" line, and their text reads as written by the resident ("I", "my house").
- The `Customer` line lists only the contact details the resident gave. One web request is anonymous (`Customer: Anonymous`).
- When there is no usable address, the map link is omitted.

Dates are ISO 8601 with the Eastern offset (for example `2026-10-19T14:52:36-04:00`). SR report dates run from 2026-08-03 to 2026-10-27.

SR statuses use Sarasota's values:

| Status | SRs | Meaning |
|---|---|---|
| `NEW` | 3 | Just arrived, not reviewed yet (no work log) |
| `QUEUED` | 38 | Waiting for review or for a crew |
| `PENDING` | 3 | Held while staff wait for the requester |
| `INPRG` | 1 | Its follow-up WO is in progress |
| `RESOLVED` | 16 | Its follow-up WO is complete, or a planner settled it by phone |
| `CLOSED` | 4 | Its follow-up WO is closed or cancelled, or a planner sent it to another department |

`CLASSSTRUCTUREID` holds a synthetic classification for the request type as submitted. A misclassified SR keeps the wrong one, which is what the AI should catch.

## Teams: on the work order, not the request

In Sarasota, the team that does the work is set on the work order, not the service request. A planner reads the request and applies a job plan, and the job plan fills in the team (`PERSONGROUP`), `SUPERVISOR` and `LEAD`. The planner often changes the lead afterwards. The County's real SRs leave `OWNERGROUP` blank, so ours do too.

What the dataset holds:
- **New requests** have no team. Suggesting one is part of what MAS AI is tested on.
- **Work orders** that were assigned, including closed ones, keep their team. That history is what the AI learns from.
- **The answer key** holds the correct team for each SR (`EXPECTED_PERSONGROUP`). A misclassified request's expected team is the team for its correct type. It is blank for requests that are not County Utilities work: the two stormwater requests, the private backflow device, and the two addresses served by city utilities.

## Maximo WOs

Each WO has `PERSONGROUP` (copied to `OWNERGROUP`), `SUPERVISOR`, `LEAD`, `CLASSSTRUCTUREID`, and, except for planned capital work, `JPNUM`, `FAILURECODE` and `PROBLEMCODE`. A follow-up WO keeps the classification and team it was actually given, even when its SR was misclassified, so the record shows how routing really went.

| Field | Values |
|---|---|
| `STATUS` | `WCONT` (waiting for a contract), `SCHED`, `INPRG`, `COMP`, `CLOSE`, `CAN` |
| `WORKTYPE` | `CM` corrective maintenance (23), `CS` customer service (8), `IN` inspection (2), `CP` planned capital project (8) |

The job plan decides the team:

| Job plan | Team | Request types |
|---|---|---|
| `LEAK` | `WTRPIPE` | Water Line Leak, Water Main Break, Curb Stop |
| `PRESSURE` | `WTRPIPE` | Low Water Pressure |
| `NOWATER` | `WTRPIPE` | No Water |
| `METER` | `WTRMETER` | Water Meter Issue |
| `SAN INSP` | `SANCLINSP` | Sewer Issue, Sewer Odor |
| `FORCEMAIN` | `SANCLINSP` | Force Main Break |
| `LSALARM` | `LSCENT` | Lift Station Alarm |
| `RECLAIM` | `RECLAIM` | Reclaimed Water Issue |

Backflow Device Issue, a County request type, has no job plan or team: backflow devices belong to the property owner.

`scripts/pilot_catalog.py` holds these tables, the failure and problem codes, and the classifications. Each entry is marked as a real County code or our own illustrative value.

### Service address

The pilot and draft WOs carry the SR's address columns without `SADDRESSCODE`: `STADDRNUMBER`, `STADDRSTREET`, `STREETADDRESS`, `CITY`, `STATEPROVINCE`, `POSTALCODE`, `COUNTRY`, `LATITUDEY` and `LONGITUDEX`. Maximo keeps them on the WO's service address, which is how a reviewer finds other work at the same place.

| WO | Address |
|---|---|
| Follow-up or draft | Its SR's address, as written. An SR with no usable address gives its WO only the city and no coordinates (drafts WO2915005 and WO2915014). |
| Past work | Its address point: number, street, city, ZIP and coordinates |
| Planned or street-wide work | The street's centroid, with no house number or ZIP |

The validators check each rule. The training history keeps the text-only WO shape, with no address columns.

## Mock QAlert data

`requests.json` is a top-level array, matching the documented `requests/get` response. Field names follow the public QAlert v1 evidence: the City of Haverhill and City of Somerville QAlert client code and test fixtures.

| Field(s) | Basis |
|---|---|
| `id`, `status`, `createDate`, `createDateUnix`, `lastAction`, `lastActionUnix`, `typeId`, `typeName`, `priorityToDisplay`, `hasLinks`, `comments`, `streetNum`, `streetName`, `crossName`, `cityName`, `latitude`, `longitude` | Confirmed in public QAlert client code and fixtures |
| `origin` | Confirmed field. `Control Panel` and `QAlert Mobile iOS` appear in public QAlert client code. `QAlert Mobile Android` and `Web Portal` are **assumed**. |
| `name`, `email` (resident) | Seen in a public test fixture only. Empty when the resident did not give one. |
| `phone` (resident), `intakeMethod`, `employeeId` | **Provisional.** These are our assumption and are not in any public source. `intakeMethod` (`Phone` or `Email`) and `employeeId` are set only on `Control Panel` requests, and are `null` otherwise. |

Other conventions:

- `status` uses `0` for open, `1` for closed, and `3` for in progress (from public Somerville configuration).
- Dates use QAlert's `M/D/YYYY h:mm AM` format.
- Requests with no usable address have `latitude` and `longitude` set to `0`.
- `streetName` is uppercase, as in the public fixture.

`activity.json` uses the confirmed fields `id`, `requestId`, `displayDate`, `code`, `codeDesc`, and `routeId`.
- On the "Created" entry, `routeId` is the employee's username for staff-entered requests, and empty for resident-submitted ones.
- On "Assigned" and "Closed" entries, `routeId` is a department route such as `PUWater`.
- The numeric `code` values (1, 4, and 15) are illustrative.

`employees.json` is **provisional**: no public QAlert employee schema exists. Each record has `id`, `username`, `firstName`, `lastName`, `email`, `phone`, `department`, and `active`.
- The `id` uses the same 7-digit format as Maximo PERSONID. This reflects the pilot assumption that employee IDs are shared across QAlert and Maximo.
- Six of the 15 employees have no Maximo PERSON record. This reproduces the "requester does not map to a Maximo person" gap.
- Two employees are inactive.
- Fourteen SRs are staff-entered. Thirteen name their employee; one records no employee anywhere. The other 51 have no employee.

## Scenarios

| Use case | Scenario | SRs | What the AI should notice |
|---|---|---|---|
| Missing-Information Detection | Missing location | 4 | No house number, or no address at all |
| | Invalid location | 3 | A house number that is not in the GIS file, a misspelled street, or an address outside the County |
| | Insufficient problem detail | 4 | For example "Customer has a question about the meter." |
| | Unclear request | 3 | The device or problem is never identified |
| | Incorrect classification | 5 | For example stormwater flooding filed as a water leak or as a sewer issue, or a force main filed as a water main |
| | Multiple issues in one request | 3 | Two problems combined in one SR |
| | County responsibility review | 6 | The request may not be the County's job: private plumbing inside the home (3), a private backflow device (1), or an address that the City of North Port or City of Venice utility serves (2) |
| Duplicate Identification | Duplicate clusters A–E | 12 | 5 clusters of 2–3 SRs: same problem, same or neighboring address, within hours to days, sometimes under a different request type. In one cluster, the resident who used the app calls 311 about the same problem. |
| | Look-alike (not a duplicate) | 4 | The same street or the same night as a cluster, but a different problem; or the same address and problem after the earlier repair was finished |
| Historical / Planned Work Context | Related past work | 5 | Earlier WOs at the same address or on the same street |
| | Related planned work | 4 | A scheduled or in-progress project on the same street |
| Control | Complete request | 12 | Nothing to flag |

Several missing-information SRs also have a follow-up WO in which the crew found nothing, or could not find the address. These illustrate the unnecessary dispatches the pilot aims to avoid.

Two misrouted requests show the two ways the County handles them. One had a crew sent before anyone noticed, and that WO was cancelled. The other, like the County's "Misrouted" examples, never got a WO: a planner closed it with a `RESOLUTION` work log that sends routing instructions to the Contact Center.

### How our scenarios match the County's example tabs

The County's workbook, *MAS AI Pilot Data Examples Sarasota County*, groups its real examples into five tabs. IBM's updated review of that workbook, the tab "Pilot Data Review - Updated", asks the County to confirm each label. Our scenarios map onto those tabs like this:

| County tab | Our scenarios | Notes |
|---|---|---|
| Duplicates | Duplicate clusters A–E | The County's examples include the same address years apart. We keep duplicates to the same open problem, as agreed, and put repeats after a repair under look-alikes or related past work. IBM asks the County to confirm where that line falls. |
| Similar but not duplicate | Look-alikes; Related past work | The County's examples are the same address a week or two apart, after the first repair was done. Our same-address look-alike follows that pattern. |
| Incomplete requests | Missing location, Invalid location, Insufficient problem detail, Unclear request, Multiple issues | The County's "Incomplete SR Data" tab holds work log columns instead of SR rows, as IBM's review points out. Our cases follow the County's *Incomplete and Missing Data Examples* workbook instead. |
| Misrouted | Incorrect classification | Includes the no-WO, `RESOLUTION`-note pattern above. |
| Non County | County responsibility review | Covers private plumbing, a private backflow device, and city utility service areas. |

IBM's review also asks the County which outside sources are part of triage: UMAX, Outlook crew schedules, GIS, Badger Beacon, and the restoration Smartsheet. The dataset models none of them, apart from the GIS stand-in.

## Required information by request type

IBM's review rates missing-information detection as only partly covered until the County says what each request type must contain. `data/reference/required-information.csv` is our proposal for that list, for the County to confirm.

- Three rules apply to every type: a findable address (`ADDR`), an address that exists in the County (`ADDR-VALID`), and one problem per request (`ONE-ISSUE`).
- Each Utilities request type has one rule of its own. For example, `SEWER-SYMPTOM` says a Sewer Issue must give the symptom (backup, overflow or odor) and whether it is inside or outside the house.

The answer key's `REQUIRED_INFO_GAP` lists the rules each missing-information SR breaks. For example, the lift station alarm with no address breaks both `ADDR` and `LS-ID`. It is blank for misclassified and non-County requests, which are about the wrong type or the wrong owner, not missing details.

## Answer key

`answer-key.csv` has one row per SR with these columns:
- `USE_CASE`, `SCENARIO`, and `EXPECTED_ALERT`. The alert is `Missing or incorrect information`, `Possibly not County responsibility`, `Possible duplicate`, `Related past work`, `Related planned work`, or `None`.
- `ISSUE_SUMMARY` and `MISSING_INFORMATION`.
- `REQUIRED_INFO_GAP`: the required-information rules the request breaks, separated by `;`.
- `QALERT_ORIGIN` and `SUBMITTED_VIA`: the channel the request came in through.
- For staff-entered requests, the QAlert employee who entered the request: ID, name, department, phone, email, active flag, and whether that employee has a Maximo PERSON record. These columns are empty for app and web requests.
- `FOLLOW_UP_CONTACT_TYPE`, `FOLLOW_UP_CONTACT_NAME`, `FOLLOW_UP_CONTACT_PHONE`, and `FOLLOW_UP_CONTACT_EMAIL`: who to ask if the request needs clarification. The type is `Resident`, `Entered-by employee`, `Department supervisor`, `Contact Center`, or `Owning group supervisor`.
- `SUGGESTED_CLARIFICATION_QUESTION`.
- `EXPECTED_CLASSSTRUCTUREID`: the classification the request should have. It differs from the SR's own classification only for the five misclassified requests, where it is the class of the correct type, for example 9401 (stormwater) for a flooding report filed as a water leak.
- `EXPECTED_PERSONGROUP`: the team that should handle the request. It is blank for the two stormwater requests, which belong to Public Works, and for the three requests that are another party's job.
- `RELATED_RECORDS` and `EXPECTED_RECOMMENDATION`.

Here is an example of the expected output for a missing-location SR submitted through the app:

> Flag before dispatch: Street only; no house number. The resident submitted this through the 311Connect mobile app; contact THERESA SHEFFIELD directly (941-555-0123 or tsheffield81@example.com). Ask: "Can you give the house number or describe the closest house to the leak?"

And for one that came in by phone:

> Flag before dispatch: No house number or cross street, so the crew cannot find the break. Contact Daniel Okafor (Contact Center, 941-555-0101, daniel.okafor@example.org), who took the phone call to 311 and entered it in QAlert as employee 0820533; this employee has no Maximo person record, so the contact details come from QAlert. Ask: "Can you call the customer back and get the nearest house number or cross street where the water is coming up?"

Special cases:
- When the employee who entered the request is inactive, the question goes to the department supervisor.
- When the employee has no Maximo person record, the recommendation notes that the contact details came from QAlert.
- When a resident gave no phone or email, the question goes to the supervisor of the group that owns the work.
- When a staff-entered request records no employee, the question goes to the Contact Center.

A request that may not be the County's job gets the same follow-up contact. Its recommendation starts "Check responsibility before dispatch" and ends with who to refer the customer to once that's confirmed: a plumber, or the City of North Port or City of Venice utility.

Of the 28 flagged SRs (22 missing or incorrect information, 6 possibly not County responsibility):
- 19 go to the resident;
- 5 go to the staff member who entered the request;
- 1 goes to the Contact Center, because nobody recorded who took the call;
- 2 go to a department supervisor, because that staff member is inactive;
- 1 goes to the owning group's supervisor, because the request was anonymous.

The recommendations encode the team's assumptions. Stakeholders should review them; this is the Sprint 2 "refine based on feedback" step.

## Training history for MAS AI

MAS AI's field value recommendations learn from past records before they can recommend a classification or a team. The 65 pilot SRs are the test set, so the model learns from a separate history instead.

```bash
python3 scripts/generate_training_history.py   # writes data/maximo/history/
python3 scripts/validate_training_history.py   # exits 1 if any check fails
```

| File | Rows | What it represents |
|---|---|---|
| `data/maximo/history/sr.csv` | 1,170 | Past requests, 90 for each of the 13 classifications, all closed or resolved |
| `data/maximo/history/wo.csv` | 990 | One closed follow-up WO for each request that needed a crew, with the right job plan and team |
| `data/maximo/history/worklog.csv` | 2,160 | Crew notes on the WOs, and the note that closed each request with no crew |

- **Same columns as the pilot files**, so the loader handles them with `--dataset history`.
- **Dates:** everything happens between 2024-08-01 and 2026-07-31, and every pilot SR is reported on or after 2026-08-03.
  - A `reportdate` filter can therefore separate history SRs from pilot SRs.
  - It cannot separate WOs, because the pilot's past work goes back to 2025. The AI configuration filters on external IDs instead.
- **IDs:** SR600001 onward, QAlert request 500001 onward, WO2700001 onward, and work log 3500001 onward. None of them overlaps the pilot.
  - Records are numbered round by round, and each one is built from its own seed.
  - Raising the size only adds records at the end. Records already loaded into Maximo never change.
- **Kept apart from the pilot:** the history uses its own streets, resident names and wording. The validator checks that no history request repeats a pilot request's text. Residents give only an email, because the pilot uses up the fictional phone range.
- **Labels are what the planner settled on:** `CLASSSTRUCTUREID` is the correct classification.
  - 12% of the Utilities requests were filed under a nearby QAlert type. Their `DESCRIPTION` still starts with the type the resident picked, so the model has to read the request, not copy the type name.
  - Every stormwater request was filed under a Utilities type, as they are in real life. Each was closed with a `RESOLUTION` note that refers it to Public Works.
  - Backflow requests are resolved with a note that the device belongs to the property owner. Neither stormwater nor backflow requests get a work order.
- **Size:** `PER_CLASS` in `scripts/history_catalog.py` sets the count per classification. Raise it if Maximo's **Check data requirement** asks for more data, then load the history again; only the new records are created.
- **Coverage:** the misfiled pairs are general confusions (leak and main break, sewer issue and odor, and so on). They do not include every confusion in the pilot. For example, no history leak is filed as Sewer Issue, as SR810018 is. Read that SR's result with this in mind.

See [mas-ai-configuration.md](mas-ai-configuration.md) for how the AI uses it.

## Draft work orders for MAS AI

Team recommendations and similar work orders show on a work order, but most pilot SRs are still waiting for review and have none. The drafts are the work orders a planner opens before deciding who goes:

```bash
python3 scripts/generate_draft_work_orders.py   # writes data/maximo/drafts/, after the pilot files
python3 scripts/validate_draft_work_orders.py   # exits 1 if any check fails
```

| File | Rows | What it holds |
|---|---|---|
| `data/maximo/drafts/wo.csv` | 35 | One WAPPR work order for each open pilot SR that names a team and has no work order |
| `data/maximo/drafts/sr.csv`, `worklog.csv` | 0 | Header only, so the loader reads every dataset the same way |

- **Duplicate reports get no draft.** Several residents reporting one problem should end up on one work order: the one their cluster's first report already has, or that report's draft (WO2915024 for SR810044). Grouping them is what similar service requests suggest.
- **Nothing is decided yet.** A draft has the SR's text and classification, and no team, job plan, crew, codes or field dates. The validator checks this.
- **Created by the planner.** `REPORTEDBY` is the planner for the request type. The draft is dated within the hour after the SR, and never after the as-of time.
- **The pilot files are not changed**, so its 65 SRs and 41 WOs stay as reviewed. The drafts are WO2915001 onward and load with `--dataset drafts`, after the pilot.

## Assumptions to revisit

- The channel mix (51 resident-submitted, 14 staff-entered) reflects the County's statement that only a small share of requests comes through the Contact Center. The real proportions are unknown.
- The City of North Port and the City of Venice run their own water utilities. Which streets they serve is illustrative: two invented streets are marked in the GIS stand-in's `UTILITY` column, and every other address is County-served, whatever its mailing city. The real boundaries come from County GIS.
- The required-information rules are our proposal. The County has not yet said what each request type must contain.
- The `RESOLUTION` work log type is used in the County's samples. The TechZone instance may not have it; `python -m loader inventory` reports whether it does.
- The QAlert API returns each request's `origin` and, for staff-entered requests, the employee ID. The `origin` labels other than `Control Panel` and `QAlert Mobile iOS` are assumed.
- App users always have an email on file; web, phone, and email requests may lack one.
- QAlert employee IDs equal Maximo PERSONIDs.
- For staff-entered requests, the employee ID reaches Maximo as `REPORTEDBY` (when the employee has an active Maximo person record) and as an "Entered by" line in the long description.
- The resident's name stays in the long description only, because standard Maximo stores a name only on a person record. The County integration proposal asks the County to choose: the text, a custom field, or a person record per resident.
- The structured fields assume the County adopts the integration mapping in [qalert-integration-proposal.md](qalert-integration-proposal.md). The `SOURCE` codes are our convention, because `SOURCE` has no domain.
- The QAlert `employees.json` schema and the fields `phone`, `intakeMethod`, and `employeeId` are provisional until Sarasota confirms what the QAlert API returns.
- These Maximo values come from the County's sample records: the SR statuses, `WCONT` and `SCHED`; the work types `CM`, `CS` and `IN`; the teams `WTRPIPE`, `SANCLINSP` and `LSCENT`; the job plans `LEAK`, `PRESSURE` and `SAN INSP`; the failure codes `SERVLINE` and `SERVICELATERAL`; and the problem codes `LEAKBROKEN`, `LOWPRESSURE`, `CURBSTOP` and `CUSTCOMPLAINT`. The meanings of `SANCLINSP`, `LSCENT` and `WCONT` are read from the code names and are unconfirmed.
- These Maximo values are illustrative, not Sarasota's actual configuration:
  - the teams `WTRMETER` and `RECLAIM`, and the job plans `NOWATER`, `METER`, `FORCEMAIN`, `LSALARM` and `RECLAIM`;
  - the other failure and problem codes;
  - the `CP` work type for planned capital projects (we assume the County tracks this work as its own type);
  - all classification IDs (`9101`–`9401`, including `9107` for backflow devices); the County's numeric IDs only mean something on its own instance;
  - `COMMODITY` values other than `WATER_PIPE`, `WATER_SERV`, `COLLECTION`, and `BACKFLOW`.
- Street names were invented and checked only by eye. Rename any that match a real Sarasota County street.
- The CSVs use Maximo attribute names. Loading them into the TechZone environment may require column mapping for MXLoader or the REST API.
