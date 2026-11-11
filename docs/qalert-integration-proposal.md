# Proposal: send QAlert's details to Maximo as fields

*Executive summary for Sarasota County Public Utilities and County IT. Prepared by the MAS AI Pilot team, 2026-11-10.*

## In one paragraph

When a resident reports a problem through 311, QAlert records the address, the map location, the resident's phone and email, how the request came in, and its priority, each as a separate value. The integration that copies the request into Maximo turns all of that into one block of text. The address, contact, channel and priority fields in Maximo are left empty, and every request is shown as reported by the integration account. That makes each request harder for staff, reports and Maximo's AI to use. **We propose that the County ask the integration's owner to send these details into Maximo's own fields as well.** It is a mapping change on the County's side. It needs no new software, and it improves every request from the day it goes live.

## What we see today

A typical service request in Maximo, as the integration delivers it, shows this. The example is SR800060, a "No Water" report from the pilot's first load. The pilot's reload replaces it with SR810060, which carries these details in their fields.

| Maximo field | What it holds today |
|---|---|
| Service Address, Street, City, ZIP | Empty |
| Reported By and Affected Person | The integration account, "QAlert Integration" |
| Reporter phone | Empty |
| Reporter email | The integration account's address |
| Reported Priority | Empty |
| Source (how the request came in) | Empty |
| Details (long description) | Everything: the resident's name, email and phone, the address, a Google Maps link, and the problem |

The County's sample records follow the same pattern. When we checked the pilot instance on 2026-11-10, before the pilot was reloaded, none of its 1,243 service requests had a priority or a source.

## Why it matters

- **Staff search and reports.** Maximo cannot answer "all requests on this street", "requests that came in by phone", or "urgent requests this week", because those values are not in fields. Staff read the text instead.
- **Contacting the resident.** The phone number is buried in the text, and the reporter fields name the integration account, so follow-up starts with reading and copying.
- **Maximo's AI.** The Maximo Assistant searches fields. Address, channel and priority questions have nothing to search. The AI's similarity check compares text, and every request shares the same Customer, Address and Map layout, so two reports several kilometres apart can look nearly identical to it.
- **Pilot workarounds.** To make the AI usable, the pilot had to write scripts that pick the address and the map location back out of the text. A planner's edit to the text, or a change to the integration's text layout, breaks them.
- **What text parsing can and cannot recover.** We ran the pilot's text parsers over the 65 pilot requests and compared each value with QAlert. In this best case, with synthetic text in one fixed layout:
  - the house number, street, city, coordinates, phone and email came back for 65 of 65;
  - the channel and the priority came back for 0 of 65, because they are not in the text;
  - whether the address is in the County address file came back for 0 of 65, because that needs a lookup.

  Real QAlert text varies more, so the first figure would fall. With the address in fields, the missing-information check catches 8 of the 18 gaps in the pilot's answer key, against 6 from the text. (`tests/test_parser_recovery.py`, `tests/test_missing_info_rules.py`)

## Root cause

The information is not missing; it is lost on the way. QAlert already holds each value separately, and the integration uses those values to build the text, so it could put them into Maximo's fields at the same moment. No parsing and no AI is needed for data the source system already has.

## What we propose

**1. Map each QAlert value to its Maximo field.** Keep writing the current text as well, so nothing staff rely on today goes away.

| QAlert value | Maximo field | Note |
|---|---|---|
| Street number, street, city | Service address: number, street, city | Copied as sent |
| Latitude and longitude | Service address: latitude and longitude | Copied as sent; replaces the Maps link as the location source |
| Resident's phone and email | Reporter and affected-person phone and email | The reporter itself stays blank for residents; see decision 3 |
| How the request came in (`origin`, intake method) | Source | Short codes: `APP-IOS`, `APP-ANDROID`, `WEB`, `PHONE`, `EMAIL` |
| Priority | Reported Priority | After the County confirms how QAlert's levels match Maximo's (1 Urgent to 4 Low) |
| Employee who entered a phone or email request | Reported By | Only when that employee has an active Maximo person record; otherwise their phone and email are the reported contact |
| QAlert request number | External record ID | Already sent today |

**2. Keep the County's address list in Maximo** as service address records, from County GIS. Maximo can then link each request to a known address automatically. A request whose address matches nothing is flagged for review instead of sending a crew to look for it. On the pilot data, this one change lets the missing-information check catch two wrong addresses it misses today.

**3. Use Maximo's AI only for what rules cannot do.** AI can suggest an address when the text is unclear, or point out that a request is missing a detail. Those stay suggestions that a reviewer accepts. We do not recommend AI as the main fix: it would pay a model to rebuild values QAlert already sent, it can get a house number wrong, and it would send residents' details to a cloud service.

## Options we considered

| Option | Fixes the cause? | What it takes | Main limitation |
|---|---|---|---|
| **Fix the integration mapping (recommended)** | Yes, for every new request | A mapping change by the integration's owner, and the address list in Maximo | Depends on the owner's schedule |
| Rebuild the fields in Maximo from the text when a request is saved | Partly | A Maximo script | Cannot recover the channel or priority, which are not in the text. It breaks if the text layout changes. Useful only for the existing backlog. |
| Extract the fields with AI (watsonx.ai) | No | AI service setup, review of every suggestion, and approval for cloud processing of resident data | Variable results, possible wrong addresses, cost per request |
| Leave it as is | No | Nothing | Staff and AI keep working from text |

## Decisions and information we need from the County

1. **Who owns the integration?** It may be Catalis's QAlert connector, County middleware, or a Maximo job. The owner decides how the mapping is changed and how soon.
2. **Which values does the County's QAlert send?** We assumed QAlert has the channel, the intake method, the entering employee and the resident's phone, based on public QAlert evidence. These need confirming.
3. **Where does the resident's name go?** Standard Maximo stores a name only on a person record. The choices are: the text only (our default), a new custom field, or a person record per resident.
4. **Is the County address list available for Maximo?** The County's attribute list already maps GIS address columns to Maximo service addresses.
5. **How do QAlert's priority levels map to Maximo's?**
6. **Is cloud AI processing of resident data acceptable?** This matters only for the AI option.

## What the pilot does in the meantime

- **The target shape.** The pilot's sample data is being rebuilt so every request carries these fields, as if the mapping were already fixed. The County can then see the difference in Maximo and in the AI's results.
- **The current shape.** The current-shape copies stay on the pilot instance, closed, as the "before" example.
- **The stopgap.** The pilot's scripts read the fields first and fall back to the text, so they keep working on requests in today's shape.

How the sample data models today's records is described in [sample-dataset.md](sample-dataset.md). The AI setup is in [mas-ai-configuration.md](mas-ai-configuration.md).
