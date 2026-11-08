# Maximo Assistant: questions for pilot reviews

These questions walk Sarasota reviewers through the pilot scenarios with the Maximo Assistant. The Assistant runs alongside the recommendations set up in [mas-ai-configuration.md](mas-ai-configuration.md).

Each question has:
- the answer the data should give
- what the question shows
- the result on TechZone, filled in when it is tried

The expected answers come from `data/maximo/` and `data/answer-key.csv`.

**What the Assistant can and cannot do (as documented for 9.1; TechZone runs 9.2, so re-check there).** It finds records and summarizes them. It does not judge them: it cannot say that a request is missing a house number or is not the County's job. The reviewer makes that call from what it finds. That gap is what the classification recommendations, and on 9.2 the agentic Assistant, are meant to close.

**How to ask.**
- Ask about one request, one street or one month at a time. On 11/04 a broad question ran until Maximo logged the session out.
- Add "reported after August 1, 2026" when a question could also match the training history. The history is at the same site, SRQSITE, so the site does not separate them. It uses different streets, so street questions are safe.
- Record the time each answer took.

Result codes: **Pass** (the expected records, nothing wrong), **Partial** (some records, or extra ones), **Fail**, **Pending** (not tried yet).

## 1. Missing information

| # | Question | Expected answer | What it shows | TechZone result |
|---|---|---|---|---|
| 1.1 | Show service request SR800001. | Water Line Leak at "Fennimore Pines Blvd, North Port", with no house number. The resident is a landscaper who is "not sure of the address". Status QUEUED. | The reviewer sees at once that the crew cannot find the leak. The answer key flags rule `ADDR` and suggests asking for the closest house. | Pending |
| 1.2 | Show service request SR800020. | Lift Station Alarm, address "North Port" only, submitted anonymously, "pump station behind our neighborhood". | No station number and no street (rules `ADDR` and `LS-ID`). It came anonymously through the web portal, with no phone or email, so the answer key sends the question to the wastewater supervisor. | Pending |
| 1.3 | List queued service requests at site SRQSITE reported in August 2026. | 14 SRs, including SR800001, SR800002, SR800005, SR800013, SR800014, SR800018 and SR800020. | A planner's morning queue. In the answer key, eight of the 14 are flagged for missing or wrong information and one may not be the County's job. | Pending |
| 1.4 | Show service request SR800006 and its work orders. | Filed as Water Line Leak at 4950 Marlowe Cove Ave. The text describes street flooding after rain. WO2900013 was cancelled. | A stormwater problem routed to Utilities. A crew was sent for nothing. The classification recommendation should suggest Stormwater (9401). | Pending |

## 2. Possible duplicates

| # | Question | Expected answer | What it shows | TechZone result |
|---|---|---|---|---|
| 2.1 | Show service requests on Corvina Bay Dr. | SR800030 (main break, 1364, RESOLVED), SR800031 (1370), SR800032 (1376), all on 2026-09-14, and SR800059 (1382, NEW, 2026-10-26). | Three neighbors reporting one main break within hours. SR800059 is a look-alike: a small meter leak six weeks after the repair, so it is a new request, not a duplicate. | Pending |
| 2.2 | Show work orders on Corvina Bay Dr. | WO2900028, 1364 Corvina Bay Dr, MAIN BREAK, COMP. | The crew already fixed it. Link SR800031 and SR800032 to SR800030 instead of dispatching again. | Pending |
| 2.3 | Show service requests on Bramblewick Ln reported in October 2026. | SR800053 (No Water, 3912), SR800054 (3918) and SR800055 (Low Water Pressure, 3930) on 10-21, plus SR800060 and SR800065 on 10-27. | One outage reported under two request types. SR800060 and SR800065 are look-alikes, not duplicates: an account lock on the meter, and water coming up again after the repair. | Pending |
| 2.4 | Show service requests at 6546 Gulfwren Ave. | SR800044 (10-05) and SR800046 (10-07), both Sewer Odor, both QUEUED. | The same resident called the Contact Center two days after submitting the request in the app. Only SR800044 has a work order, the draft WO2950024. SR800046 should join it. | Pending |

## 3. Related past and planned work

| # | Question | Expected answer | What it shows | TechZone result |
|---|---|---|---|---|
| 3.1 | Show closed work orders at 1382 Larkspur Bay Dr. | WO2900007 (2026-02-16) and WO2900012 (2026-07-17), both SERVICE LINE LEAK. | A third leak in eight months (SR800036). The reviewer should consider replacing the service line instead of patching it again. | Pending |
| 3.2 | Show work orders on Oakhallow Cir. | WO2900015 (MAIN LINE STOPPAGE, 08-16) and WO2900022 (CCTV INSPECTION, 09-10), both for team SANCLINS (our SANCLINSP, shortened to Maximo's 8 characters). | The main line was jetted for root intrusion two months earlier and then inspected. SR800056 is likely the roots coming back. | Pending |
| 3.3 | Show work orders at 1834 Rushmere Ave. | WO2900002, CURB STOP REPLACEMENT, closed 2025-08-30. | The curb stop was replaced a year before SR800034, so this is a possible warranty issue. | Pending |
| 3.4 | Show scheduled work orders on Starling Cove Dr. | WO2900037, water main replacement, SCHED, work starting 2026-11-16. | Low pressure there (SR800004) may be fixed by the planned project. Tell the resident instead of sending a crew. | Pending |
| 3.5 | List work orders at site SRQSITE with status SCHED, WCONT or INPRG. | 9 WOs: 8 planned (CP) projects plus WO2900041, an in-progress main break on Glimmerton Ave. | The planned-work picture a reviewer checks before dispatch. | Pending |

## 4. Classification, team and responsibility

| # | Question | Expected answer | What it shows | TechZone result |
|---|---|---|---|---|
| 4.1 | How many service requests at SRQSITE reported after August 1, 2026 are classified WATER-LEAK? | 14. Without the date, 44, because the training history adds 30. | The Assistant counts what is recorded. Five pilot SRs are filed under the wrong class, which is what the recommendations are for. | Pending |
| 4.2 | Show work orders for person group WTRMETER. | 5 pilot WOs (WO2900004, WO2900011, WO2900024, WO2900025, WO2900031), plus history WOs from WO2700001 onward. Add "reported after August 1, 2026" to get only the pilot's 3. | How team routing looks in Maximo: it is on the work order, not the SR. | Pending |
| 4.3 | Show service request SR800063. | Water Line Leak at 4500 Zinnia Crest Ln, North Port. | Maximo cannot tell that the City of North Port, not the County, serves this street. That comes from GIS. The answer key says to refer the customer to the city. | Pending |
| 4.4 | Show service requests at 4908 Dovetail Pl. | SR800062, Backflow Device Issue, RESOLVED. | Backflow devices belong to the property owner. The work log shows the planner's referral note. | Pending |

## Talk track

1. **Open with section 1.** Missing information is the County's most time-consuming check. The Assistant brings the request to the reviewer in seconds; deciding that it is incomplete is still the reviewer's call. That is why the next step is recommendations, or the 9.2 agent.
2. **Section 2: a street search finds neighbors reporting one problem.** This is the County's duplicate example: several residents, one problem, one work order.
   - Then show the AI doing it without a search. Open SR800031 and click **Select Action > Similar service requests from AI** (configuration 4 in the configuration guide). SR800030 should be listed.
   - Group them: link SR800031 and SR800032 to SR800030 as its Global Issue. Only WO2900028 goes to a crew.
   - Point out a look-alike: open SR800042, a lift station alarm the same night as SR800040 and SR800041. The AI may list them, yet it is a different station in another city. The reviewer decides.
3. **Section 3 is the "institutional knowledge" story.** Past and planned work at the address, without asking the one person who remembers.
4. **Close on 4.1 and 4.3.** Show the classification recommendation on SR800006. Point out what still needs GIS: whether the County serves the address.

## Results log

| Date | Who | Questions tried | Notes (time taken, odd answers) |
|---|---|---|---|
| | | | |
