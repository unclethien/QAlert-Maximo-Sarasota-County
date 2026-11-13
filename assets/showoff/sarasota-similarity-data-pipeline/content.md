# Finding related work, and the data it depends on

A 13-slide deck and speaker script for the IBM team and Sarasota County staff, 2026-11-13. It runs about 15 minutes, plus two optional live demos of about a minute each. Read the script as written, or use it as talking points.

Every record on the slides is the pilot's synthetic data on the TechZone Maximo instance. No real resident details appear. The County workbook was used only for counts and structure.

## Before you present

- **Open the deck:** `assets/showoff/sarasota-similarity-data-pipeline/index.html` in Chrome, then press **F** for full screen. It works offline.
- **Keys:**
  - Next slide: right arrow, down arrow, Space or Page Down (most clickers send Page Down).
  - Previous slide: left arrow, up arrow or Page Up.
  - First and last slides: Home and End.
  - **N** shows the time budget and the demo cue for the current slide.
- **For the demos,** sign in to TechZone Maximo before the meeting, in a second browser tab:
  - one tab on classic **Service Requests** (Service Desk > Service Requests);
  - one tab on classic **Work Order Tracking**.
  - Your security group needs **Similar service requests from AI**, **Similar work orders from AI** and **Nearby work**.
- **Backup images:** if the demo fails, every slide also exists as an image in `images/`.

---

## 1. Finding related work, and the data it depends on (about 30 seconds)

**On screen:** the title over a street map. Three pins on Corvina Bay Dr light up one after another and join into one work order.

**Say:**

> Thanks for joining. I have three things today.
>
> Two are results from the pilot instance: how Maximo's AI finds other reports of the same problem, and how it finds past or planned work at the same place.
>
> The third is a request. Both results turned out to depend on one thing: whether the address and the reporter's details reach Maximo as fields, or as one block of text. Today it's the text.
>
> Everything you'll see is the pilot's practice data. No real resident appears on any slide.

## 2. Three questions a reviewer asks about every new request (about 30 seconds)

**On screen:** three numbered questions, each with the feature that answers it.

**Say:**

> When a new request comes in, a reviewer asks three questions.
>
> One: has someone already reported this? That's similar service requests.
>
> Two: has a crew been here before, or is work already planned here? That's similar work orders.
>
> Three, the one underneath both: can Maximo answer those from its fields, or only by reading text? That's the data pipeline.

## 3. Three neighbors, one main break (about 1 minute)

**On screen:** September 14 on Corvina Bay Dr. Three reports at 6:55 AM, 9:33 AM and 12:19 PM, from 1364, 1370 and 1376. The third was filed as a water line leak. All three lead to one work order, WO2910028. Below, four steps: the AI finds them, a reviewer checks, the reviewer links them, one crew goes.

**Say:**

> Here's the duplicate case in one picture. On the morning of September 14, three neighbors on Corvina Bay Drive reported the same main break within about five and a half hours. The third filed it as a water line leak, a different request type, but it's the same break.
>
> What we want is one work order and one crew, not three.
>
> That takes two parts. The AI finds the other reports. Then a reviewer links them to the first one, using Maximo's standard Global Issue. Only the first report's work order goes out, and when it's done, every linked report follows its status.
>
> One note: Maximo ships AI for similar work orders, but not for service requests. We set up IBM's documented similarity template on service requests and added a screen for it, **Select Action, Similar service requests from AI**.

## 4. Text alone ranks a break across town second (about 1 minute 15 seconds)

**On screen:** the AI's list for SR810031, ranked by the AI's score alone. SR810030 is first at 95. Second is a main break on Bramblewick Ln, six weeks later, at 93. The real neighbor, SR810032, is fifth at 91. On the right, why the scores bunch together.

**Say:**

> This is the AI's own list for the middle report, SR810031, sorted by its score.
>
> First place is right: the first report, at 95.
>
> But second is a main break on Bramblewick Lane, across town and six weeks later, at 93. Then a leak on the same street six weeks later, and another main break elsewhere. The real neighbor, SR810032, is fifth.
>
> Why? The AI compares words. Every request arrives in the same layout: "type, address", then customer, address and a map link. So almost everything scores between 83 and 97, and the address is just more words.
>
> No cut-off fixes that. At 93, a reviewer keeps half of the true duplicate pairs and gets 20 wrong ones.

## 5. Add place and time: duplicates rise, look-alikes fall (about 1 minute 30 seconds)

**On screen:** the formula, AI score × place × time. The same list re-sorted by the duplicate score: SR810030 at 95 and SR810032 at 91, both with no deductions. The look-alike on the same street drops to 64 and other streets to the 30s. Each row's bar shows the points taken off for distance and for time.

**Say:**

> So we kept the AI's score and added two things it can't see: how far apart the reports are, and how many days apart.
>
> Within 150 meters, nothing comes off; at a kilometer or more, half comes off. Within three days, nothing; after two weeks, 30 percent.
>
> Same list, re-sorted. The two real duplicates are now first and second, with nothing taken off. The leak on the same street six weeks later drops to 64. It stays on the list, below the line, because a reviewer should still see it. Everything on other streets drops to the 30s, and the bar shows exactly where the points went.
>
> Across the pilot: for all 8 open duplicates, the first report is now on top. With text alone, it was 6 of 8. And 85 or more marks a likely duplicate. Of 450 stored pairs, 14 reach it: all 12 true duplicate pairs, and one pair 12 meters and 4 hours apart that may well be one new problem reported twice.
>
> Then the reviewer ticks Global Issue on the first report and links the others. We tested that on the pilot instance: the linked reports change status with it, and only one work order is dispatched.

**Demo (optional, about 1 minute):** in classic Service Requests, open **SR810031** and click **Select Action > Similar service requests from AI**. SR810030 is first at 95 and SR810032 second at 91. Point to the Distance deduction and Time deduction columns on the rows below.

## 6. Similar work orders: text finds repeats, not places (about 1 minute 15 seconds)

**On screen:** what Maximo's built-in similar work orders found on the 22 pilot requests that have a work order to check: 6 of the 12 related work orders, none of the 4 planned projects, and 10 matches on every one of the 12 control requests. On the right, an example of how a capital project and a resident's report use different words.

**Say:**

> Now work orders. The question here is: has a crew been here before, or is work already planned?
>
> Maximo's similar work orders feature is built in and needs no training. We checked the work orders of 22 pilot requests: 10 with related past or planned work, and 12 controls with nothing related.
>
> It found 6 of the 12 related work orders, the ones worded the same way: "1382 Larkspur Bay Dr: service line leak" next to "water line leak" at the same address.
>
> It found none of the 4 planned projects. A capital project reads "Starling Cove Dr water main replacement"; a resident writes "low water pressure". Different words, so it doesn't match.
>
> And every control request still got 10 matches, at 83 to 93. Related work scored 88 to 95. The score alone doesn't separate them, and Maximo keeps at most 10 results per work order.

## 7. Two fixes on the work order (about 1 minute 30 seconds)

**On screen:** left, Similar work orders from AI for WO2915021 at 1382 Larkspur Bay Dr. With the AI score alone, the two earlier leaks at the same address rank third and fourth; by match score they rank first and second at 64, and other streets drop to 33. Right, Nearby work: other work orders within about 150 meters, found from the service address with no AI.

**Say:**

> We added two things to the work order.
>
> On the left, the same place-and-time score, on the AI's list. This is WO2915021, a new leak at 1382 Larkspur Bay Drive. By the AI's score, the two earlier leaks at that address are third and fourth, behind leaks on other streets. By match score, they're first and second.
>
> They score 64, not 90, because they're months old: past work loses 30 percent for age. That's deliberate. 60 or more marks likely related work. Every related work order the AI found is above 60. Nothing on a control request reaches it.
>
> On the right, Nearby work. It isn't AI at all. It lists every other work order within about 150 meters, from the work order's service address. That finds the work text can't: the planned projects, and work at the same place written in different words.

**Demo (optional, about 1 minute):** in classic Work Order Tracking, open **WO2915021**.
- Click **Select Action > Similar work orders from AI**. WO2910007 and WO2910012 are first at 64, each with 0 distance and 28 time deduction. Rows below are on other streets, at 31 to 33.
- Then **Select Action > Nearby work**. It lists WO2910012 and WO2910007, the closed service line leaks at the same address.
- If time allows, open **WO2915004** and its Nearby work: the planned Starling Cove Dr water main replacement, WO2910037.

## 8. Side by side (about 50 seconds)

**On screen:** a scoreboard for the 22 requests: related work orders listed, related work ranked first, and control requests with a likely match. Columns: AI score only, match score, and Nearby work.

**Say:**

> Side by side.
>
> The AI's list finds 6 of 12 related work orders. By the AI's score, related work is first on 3 of the 5 requests where it found any; by match score, on 4 of 5. The fifth is a different request 78 meters away in the same week, which place and time can't tell apart.
>
> Nearby work finds all 12, including the planned projects, and lists nothing for any control request.
>
> So a reviewer gets both on the work order: Nearby work for the place, and similar work orders for the same problem worded the same way.
>
> And here's the link to the next part. Both fixes needed one thing the AI never had: the location as a field.

## 9. What reaches Maximo today (about 1 minute 20 seconds)

**On screen:** left, the QAlert record behind SR810031, with each detail as its own value. In the middle, the integration. Right, what Maximo holds today: service address, source, priority and reporter phone empty; reported by "QAlert Integration"; everything in one text block. Below, three numbers: 51 of 116 columns filled on the County's sample requests, 0 of 1,243 requests on the pilot instance with a priority or a source, and IBM's review asking why location, priority and source are blank.

**Say:**

> Here's the same request, SR810031, on its way in.
>
> On the left is QAlert. It already keeps every detail separately: the house number, the street, the city, the map coordinates, how the request came in, the priority, and the resident's name, email and phone.
>
> On the right is what arrives in Maximo today. The service address is empty. The source and priority are empty. Reported by says "QAlert Integration" on every request. Everything QAlert knew is in one block of text: the customer, the address, a map link, and the problem.
>
> This isn't only our test data. On the County's sample requests, 51 of 116 columns have a value, and the address, source and priority aren't among them. When we checked the pilot instance before the reload, none of its 1,243 requests had a priority or a source.
>
> IBM's review of your sample asks the same question: why location, priority and source are blank, and which parts should be fields rather than text.

**Demo (optional):** open **SR800031**, the closed "before" copy loaded in today's shape, next to **SR810031**. The Service Address section is empty on the first and filled on the second.

## 10. Why one text block holds everyone back (about 1 minute 20 seconds)

**On screen:** five tiles: search and reports, follow-up, AI, upkeep, and privacy. Below, what the pilot could read back out of the text in the best case.

**Say:**

> Keeping it all in one text block costs something in five places.
>
> Search and reports: Maximo can't list all requests on a street, or the ones that came in by phone, or the urgent ones this week. There's no field to filter on.
>
> Follow-up: the phone number is inside the text, and Reported by names the integration. Every callback starts with reading and copying.
>
> The AI: similarity reads a layout that's the same on every request. That's how two reports 6 kilometers apart scored 93 against 97. And the Maximo Assistant searches fields, so address questions have nothing to search.
>
> Upkeep: to make the pilot work, we wrote scripts that pick the address back out of the text. A planner's edit, or a change in the text layout, breaks them.
>
> Privacy: the resident's name and phone are copied into free text on the request and again on its work order, and from there into anything that reads the text, including AI. IBM's review asks to keep personal details out where they aren't needed.
>
> And reading it back has a ceiling. In the best case, our clean test text, the address and contact details come back for all 65 requests. But how the request came in, its priority, and whether the address is real come back for none of them, because they're not in the text.

## 11. What we changed in the pilot data (about 1 minute 15 seconds)

**On screen:** SR810031 before and after: service address with coordinates and the County address point, source APP-ANDROID, priority 1, the resident's phone and email in the reporter and affected-person fields, and the text kept as it was. Below, what each change made possible.

**Say:**

> So we rebuilt the pilot's data as if the integration sent fields. Same requests, same text, plus the fields.
>
> SR810031 now has its service address with coordinates, matched to the County address point. Its source says it came from the Android app, its priority is 1, and the resident's phone and email sit in the contact fields. The text is unchanged, so nothing staff read today goes away.
>
> The work orders carry the request's address too.
>
> That's what made today's results possible. The duplicate score uses the coordinates: 8 of 8. Nearby work exists only because work orders have an address: 12 of 12. The missing-information rules catch 8 of the 18 gaps in our answer key instead of 6. And 58 of the 65 requests match an address point; the other 7 are exactly the missing or invalid addresses the AI should flag.
>
> Every improvement today came from a field, not from a bigger model.

## 12. Our proposal: send QAlert's values to Maximo's fields (about 1 minute 15 seconds)

**On screen:** the pipeline: QAlert's four channels into QAlert, then the integration mapping into Maximo fields, with the text kept, and the County GIS address list into Maximo service addresses. On the right, what uses each field, and how the Open311 standard for 311 requests keeps the same values separate.

**Say:**

> Our proposal is three steps.
>
> One: the integration maps each QAlert value to its Maximo field. Street, city and coordinates to the service address. How it came in to Source. Priority to Reported Priority. The resident's phone and email to the contact fields. And it keeps writing the text as today. It's a mapping change by the integration's owner, not new software, and it improves every request from the day it goes live.
>
> Two: load the County's address list from GIS into Maximo, so each request is matched to a known address when it arrives, and one that matches nothing is flagged before a crew is sent to look for it.
>
> Three: use AI only for what rules can't do, like reading an unclear description, as a suggestion a reviewer accepts. Not to rebuild values QAlert already has.
>
> This is also how 311 systems are usually built. The Open311 standard for 311 requests keeps the location and the reporter's name, email and phone as separate values from the description.

## 13. What we need from the County (about 1 minute 30 seconds)

**On screen:** six questions for the County, and the next step.

**Say:**

> To move forward, we need six answers from you.
>
> One: who owns the QAlert-to-Maximo integration? It could be the QAlert connector, County middleware, or a Maximo job. That decides how the mapping changes and how soon.
>
> Two: which values does the County's QAlert actually send? We assumed it has the channel, how a call or email was taken, who entered it, and the resident's phone.
>
> Three: where should the resident's name live: only in the text, in a custom field, or as a person record?
>
> Four: can we load the County's address list from GIS?
>
> Five: how do QAlert's priority levels match Maximo's one to four?
>
> And six: do our lines match how your staff judge? 85 or more for a likely duplicate, and 60 or more for likely related work.
>
> With those answers, we'll rerun the same checks and show you the difference. Thank you. Questions?

---

**Total:** about 15 minutes, plus up to 3 minutes of live demos.

## Numbers on the slides and where they come from

| Number | Source |
|---|---|
| SR810031's list, AI and duplicate scores | TechZone, read live on 2026-11-12 (`rel.aisimsrpair` on `MXAPISR`) |
| 6 of 8 and 8 of 8 first reports on top; 12 of 12 duplicate pairs and 14 of 450 pairs at 85 or more; 6 of 12 pairs and 20 wrong at 93 | `docs/mas-ai-configuration.md`, configuration 4, "Observed on TechZone" |
| 6 of 12 related WOs; 0 of 4 planned; controls 12 of 12; AI ranges 88–95, 83–95, 83–93 | `docs/mas-ai-configuration.md`, configuration 3, "Observed on TechZone" |
| Match score ranges 62–80, 29–92, 29–56; cut at 60; WO2915021's list | `docs/mas-ai-configuration.md`, "Match score (place and time)", and the dialog checked on 2026-11-12 |
| Nearby work 12 of 12, 10 of 10, controls 0 of 12 | `docs/mas-ai-configuration.md`, "Nearby work orders" |
| 51 of 116 SR columns filled; reported by the integration account; source and priority blank | The County workbook `Sarasota_County_Pilot_Data_Review.xlsx`, tab SR (counted only; no values copied) |
| 1,243 SRs with no priority or source | `docs/qalert-integration-proposal.md` |
| Parser recovery 65 of 65 and 0 of 65; missing-information 8 versus 6 of 18 | `docs/qalert-integration-proposal.md` (`tests/test_parser_recovery.py`, `tests/test_missing_info_rules.py`) |
| 58 of 65 SRs with an address code | `docs/sample-dataset.md` |

## References

1. IBM, Enabling locating of similar work orders (the `features` default of description and long description, at most 10 results, threshold 70, no training): https://www.ibm.com/docs/SSRHPA_cd/appsuite/admin/t_ai_config_similarity.html
2. IBM, Finding other types of similar data (service request similarity): https://www.ibm.com/docs/en/masv-and-l/cd?topic=orders-finding-other-types-data
3. IBM, Service request related records and global issues: https://www.ibm.com/support/pages/service-request-related-records
4. Open311, GeoReport v2 (a service request carries `lat`, `long`, `address_string`, `address_id`, `email`, `first_name`, `last_name` and `phone` apart from `description`): https://webarchive.library.unt.edu/web/20170118233000mp_/http://wiki.open311.org/GeoReport_v2
5. FGDC, United States Thoroughfare, Landmark, and Postal Address Data Standard (FGDC-STD-016-2011): https://fgdc.gov/standards/projects/address-data
6. IBM, Sarasota County Pilot Data Review (in the County workbook, tab "Pilot Data Review"): the questions on blank location, priority and source fields, and on data minimization.
