# Setting up MAS AI for AI-assisted vetting and classification

This guide sets up use case 1 from the Workshop Playback on the TechZone Maximo instance. It uses the AI that is built into Maximo Manage:

| What the reviewer needs | Maximo feature | Where it shows |
|---|---|---|
| The right classification for a new request | Field value recommendation on the SR's `CLASSSTRUCTUREID` | A recommendation option on the Classification field of a service request |
| The right team | Field value recommendation on the WO's `PERSONGROUP` | A recommendation option on the Person Group field of a work order |
| Several residents reporting one problem (duplicates) | Similar service requests (`similarity` template on `MXAPISR`), then a Global Issue groups them onto one work order | **Select Action > Similar service requests from AI** on a service request. We build this dialog; see configuration 4 |
| Related past or planned work | Similar work orders (`WOSIMILARITY`) | **Actions > View similar work orders** on a work order |
| Questions in plain language during reviews | Maximo Assistant | The AI icon in Service Requests and Work Order Tracking |
| Missing information | No built-in AI feature on 9.1 or 9.2 | Planned: a rule script now, and an AI agent on 9.2. See "Missing information" below |

The AI only recommends. A person accepts or ignores each recommendation, and no configuration here changes a record by itself. That is the pilot guardrail from the Playback.

Status: **draft**. The steps come from IBM's documentation, listed under Sources at the end. The "Observed on TechZone" notes are filled in as each step is run.

## Before you start

1. **The pilot data is loaded.** See [maximo-import-guide.md](maximo-import-guide.md).
2. **The training history is loaded.** Step 7b of the same guide covers this: 390 closed or resolved SRs and 330 closed WOs that the AI learns from. The 65 pilot SRs are what it is tested on. See [sample-dataset.md](sample-dataset.md#training-history-for-mas-ai).
3. **The draft work orders are loaded**, after the pilot. Step 7c of the same guide covers this. See "Draft work orders" below.
4. You can sign in to Manage with a user that can open **AI configuration**. Configuration 4 also needs **Database Configuration**, **Object Structures**, **Invocation Channels**, **Application Designer** and **Security Groups**.
5. The reviewer's security group has the Service Requests options **Show Related Record** and **show isglobal**. Without them, the **Relate Records to Global Issue** button does not appear.
6. Reviewers use the classic **Service Requests** application. The MAS 9.2 **Tickets** application cannot work with Global Issues, ticket templates or classification specifications.

## Step 0: Check what the instance offers

Do this first. If AI Service is not there, nothing else in this guide works.

| Check | Where | Observed on TechZone |
|---|---|---|
| MAS and Manage version | Help menu > **About** in Manage | MAS 9.2.6, Manage 9.2.3 (2026-11-06). Not 9.1 as first assumed. |
| AI Service is installed and running | Suite administration > **AI Service**, or ask the instance owner | Yes: three configurations are active with Ready models (2026-11-06) |
| The **AI configuration** application opens | Search "AI configuration" in Manage | Yes |
| Configurations already listed (look for the `mcc`, `pcc`, `similarity`, `nl2oslc` templates, and on 9.2 the agentic tools) | AI configuration list | Active and Ready: `ASSISTANT` (`nl2oslc`), `WOSIMILARITY`, `IBMDOCS` (`docsearch`). Inactive: `WOPROBLEMCODE` (`pcc`), **`TICKETSIMILARITY`** (`similarity` on `MXAPITKSRVAD`, IBM-shipped), `MREF_LEASE_ABSTRACT` (`fieldextractor`), and our own tests `SR-MISSING-INFO` (`insightsgenerator`) and `SR-MISSINGINFO-TEST` (`almwatsonx`). No `mcc` configuration yet; check that the template is offered under **Create**. |
| `WOSIMILARITY` is listed | AI configuration list | Yes, active, model Ready |
| The AITRAINJOB and AIINFJOB cron tasks exist | **Cron Task Setup** | _pending_ |
| The invocation channels `AIWOSIMILARITYCFG` and `AIWOSIMILARITYINF` exist (configuration 4 copies them) | **Invocation Channels** | _pending_ |
| A service request shows the **Global Issue** check box and a **Related to Global ID** field on its main tab | Open any SR in **Service Requests** | _pending_ |
| We have cluster-admin on the OpenShift cluster (only needed to install AI Service ourselves) | `oc auth can-i '*' '*' --all-namespaces` | _pending_ |
| AI Service is installed, and which catalog the cluster runs | `oc get aiserviceapp -A`, or `mas must-gather --collectors mas,aiservice --no-logs` for a full version summary | _pending_ |
| A RESOLVED SR can be made a Global Issue, and a QUEUED SR can be linked to it | Try SR800030 and SR800031 | _pending_ |

- **If AI Service is missing or not licensed:** stop. Escalate to the instance owner, Joseph Haney, or the IBM MAS AI contact, Divya. AI Service costs AppPoints, so ask before anyone installs it.
  - If the owner agrees, the MAS CLI adds it to an existing install with `mas aiservice-install` (see the AI Service install guide under Sources). It needs cluster-admin, a catalog of `v9-250828` or newer already on the cluster (`mas update` changes it), an IBM entitlement key, and a watsonx.ai API key, URL and project ID. It installs Db2, MinIO and Red Hat OpenShift AI in the cluster.
  - In that guide the scheduling flag is really `--tenant-scheduling-config-file`, and the example's tenant end date has already passed.
  - After the install, connect Manage to AI Service in Manage. The URL is the `aibroker` route in namespace `aiservice-<id>`, and the API key is the `AIBROKER_APIKEY` value in secret `aiservice-<id>-<tenant>----apikey-secret`.
- **If you need 9.2:** the CLI upgrade is `mas update -c <catalog>`, then `mas upgrade --mas-instance-id <id> --next-channel 9.2.x`, then `mas aiservice-upgrade`. Always pass `--next-channel`, or the CLI may pick a preview channel. This is the instance owner's call.
- **If the version is 9.2 or later (TechZone is):** the agentic Assistant and the Maximo MCP server may also be available, so the 9.2 route for missing information needs no upgrade. Reviewers still group duplicates in the classic **Service Requests** application, because the 9.2 **Tickets** application has no Global Issues.

## How training and testing records are separated

Every AI configuration needs two filters. The **training filter** picks the records the model learns from. The **inference filter** picks the records it recommends on.

We filter on the external IDs the loader always preserves. Maximo may renumber `TICKETID` and `WONUM`, but not these:

| Records | SR filter (`MXAPISR`) | WO filter (`MXAPIWODETAIL`) |
|---|---|---|
| Training history | `siteid='SRQSITE' and externalrecid like '5%'` | `siteid='SRQSITE' and externalrefid like 'WO27%'` |
| Pilot (test) | `siteid='SRQSITE' and externalrecid like '7%'` | `siteid='SRQSITE' and externalrefid like 'WO29%'` |

- **Alternative, for SRs only:** a date split. Every history SR is reported before 2026-08-01, and every pilot SR on or after 2026-08-03.
  - Use it only if the ID filters are refused. The date syntax depends on the database.
  - It does not work for WOs: 12 pilot WOs (the past work, WO2900001 to WO2900012) are reported before August 2026. WOs must use the `externalrefid` filters.
- **Why `siteid` in every filter:** the instance also holds an earlier demo dataset. Without it, the model trains on that.

## Configuration 1: SR classification

In **AI configuration**, click **Add configuration**:

| Field | Value |
|---|---|
| Name | `SRQ-SR-CLASS` |
| Description | Recommend the classification of a Sarasota pilot service request |
| Template | the `mcc` template, latest version |
| Object structure | `MXAPISR` |
| Target object path | leave empty |
| Attribute | `classstructureid` |
| Target description | `classstructure.description`, if offered |
| Training filter | the SR training filter above |
| Inference filter | the SR pilot filter above |

Then, in order:

1. **Actions > Set arguments**:
   - `features` = `description,description_longdescription`
   - `score_threshold` = `0.5`
2. **Actions > Check data requirement.** If it fails:
   - raise `PER_CLASS` in `scripts/history_catalog.py` (for example to 60)
   - regenerate and validate the history
   - load it again with `--dataset history --apply`. Raising the size only appends records (SR600391 onward), so the records already loaded do not change and are skipped.
   - run the check again
3. **Actions > Activate.**
4. **Optional, for the pilot only:** in **Cron Task Setup**, set the `WOAI` instance of `AITRAINJOB` and of `AIINFJOB` to run every 5 minutes. By default inference runs hourly.
5. **Actions > Train model.** Training can take a few hours. Watch the **Model training log**, or **Actions > Check model status**. It is ready when **Ready to inference** shows Ready.
6. **Check it:** open a pilot SR, for example `SR800001`, and make it editable. The Classification field should offer a recommendation.

**Fallback if `MXAPISR` is refused:** IBM's examples all use work orders. If the SR structure is not accepted, set this configuration up on `MXAPIWODETAIL` with attribute `classstructureid` and the WO filters. Record the refusal as a pilot finding.

**Second run, worth doing:** a pilot SR's `DESCRIPTION` starts with the QAlert type the resident picked, so a model can score well just by copying it. The five misclassified pilot SRs show whether it reads the request instead.
- Run a copy of this configuration with `features` = `description_longdescription` only.
- Compare the two runs on those five SRs with the scoring script.

Observed on TechZone: _pending_

## Configuration 2: WO team

Same steps as configuration 1, with these values:

| Field | Value |
|---|---|
| Name | `SRQ-WO-TEAM` |
| Object structure | `MXAPIWODETAIL` |
| Attribute | `persongroup` |
| Target description | `persongroup.description`, if offered |
| Training filter | the WO training filter above |
| Inference filter | the WO pilot filter above |
| `features` | `description,description_longdescription` |

- A follow-up WO's long description repeats the resident's request, so the model sees the same words the planner saw.
- **Where to test it:** 53 pilot SRs name an expected team and are not duplicates. 18 have a follow-up WO and the other 35 have a draft WO (WO2950001 onward). The pilot filter `externalrefid like 'WO29%'` covers both.
- **Prefer the drafts.** The 18 follow-up WOs already have their team filled in, so the reviewer sees the answer before judging the recommendation. A draft has no team yet.
- Duplicate reports have no WO of their own and get no team recommendation. They join their cluster's work order (configuration 4).

Observed on TechZone: _pending_

## Configuration 3: Similar work orders

`WOSIMILARITY` needs no training. In the pilot it answers "has a crew worked on this before, or is work already planned?" Run it from the draft WO of a related-work SR, for example SR800036's draft, which should list WO2900007 and WO2900012. Duplicate reports are found with similar service requests instead (configuration 4).

1. Open the `WOSIMILARITY` configuration and click **Actions > Edit**.
   - Set **Related Records** to `siteid='SRQSITE' and externalrefid like 'WO29%'`, so only pilot WOs are compared.
     - Leaving it empty brings in the earlier demo data on the instance.
     - It would also bring in the 330 closed history WOs, which are worded like the pilot's and would crowd the top 10.
   - Pick the latest template version.
   - Save.
2. **Actions > Set arguments:**

   | Argument | Default | Pilot value | Why |
   |---|---|---|---|
   | `date_field` | `changedate` | `reportdate` | Maximo stamps `changedate` at load time, so every loaded record would look new. |
   | `history_days` | 30 | 1000 | The related past work in the pilot goes back to July 2025. |
   | `features` | `description, description_longdescription` | keep | |
   | `similarity_threshold` | 70 | 70; try 60 if nothing comes back | |
   | `max_similarity_records` | 10 | keep | |
   | `retention_days` | 90 | 1000 (IBM's limit) | It counts back from today, so at 90 the past work from 2025 and early 2026 is left out and can never be listed. |

3. **Include finished work.**
   - By default only WOs that are not closed or cancelled, and not PM work, are compared.
   - Our related past work is closed, so edit the similarity inference query definition for `MXAPIWODETAIL` to include `CLOSE` and `COMP`.
   - If `date_field` or `features` change, the similarity query templates in `MXAPIWODETAIL` need the same change.
4. **Actions > Activate**, wait a few minutes, then **Actions > Create model**. **Actions > Check model status** shows Ready when it is done.
5. **Grant access:**
   - In **Security Groups**, open your group, then **Object Structures** > `MXAPIWODETAIL`.
   - Under **Options**, tick **View similar work order**.
   - Repeat this for each reviewer group.
6. **Check it:** open a pilot WO and click **Actions > View similar work orders**.

Observed on TechZone: _pending_

## Configuration 4: Similar service requests (duplicate reports)

The County's duplicate case is several residents reporting one problem, for example three neighbors on Corvina Bay Dr reporting one main break within hours. The goal is one work order for all of them. That takes two parts:
1. **Find them:** the AI lists other reports that read like this one. That is this configuration.
2. **Group them:** a reviewer links the duplicates to the first report with a Global Issue. Only the first report's work order goes to a crew. See the next section.

Maximo has no AI for this on service requests out of the box. "View similar work orders" works on work orders only. The non-AI **Show Similar Tickets** action does work on SRs, but it lists every unrelated ticket with the same classification, with no place or date filter. It is the fallback if AI Service is not available. IBM documents the same `similarity` template on service requests, with service request similarity as its worked example ("Finding other types of similar data", under Sources). The AI part is configuration only. The screen that shows the results is a dialog we add in Application Designer.

Do not use the IBM-shipped `TICKETSIMILARITY` instead. It reads the generic `TICKET` object through `MXAPITKSRVAD`, and on TechZone (2026-11-08) Maximo refuses to read `TICKET`, `INCIDENT` and `PROBLEM` for every user, with BMXAA0024E. Its training stops after preparing the data, even with every `MXAPITKSRVAD` option granted. The Incidents and Problems applications are not in any security group there, so the Service Desk parts that `TICKET` spans appear not to be installed. Configuration 4 reads `SR` through `MXAPISR`, which works. Steps 1 to 4 below set up the data side, and steps 5 to 7 add the screen.

Keep IBM's name `SRSIMILARITY` for the AI configuration. The relationship in step 1 names it.

1. **Relationships.** In **Database Configuration**, add one relationship on each of two objects (**Relationships** tab):

   | Object | Relationship | Child object | Where clause | Remarks |
   |---|---|---|---|---|
   | `SR` | `AISIMSRPAIR` | `MAXAISIMILAROBJ` | `objectname='SR' and objectid=:ticketuid and aicfgname='SRSIMILARITY' and skipinf=0 and score>=93` | AI similarity results for this service request, one row per similar SR, with its score. Used by the AISIMSR dialog. Change 93 to adjust the threshold shown to reviewers. |
   | `MAXAISIMILAROBJ` | `AISIMSRTICKET` | `SR` | `ticketuid=:similartoobjectid` | The similar service request a similarity result points to. Used by the AISIMSR dialog. |

   - `MAXAISIMILAROBJ` holds one row per pair: `objectid` is the open SR that was checked, `similartoobjectid` the SR found, and `score` their similarity.
   - The `score>=93` cut is where reviewers see the threshold. The AI's own `similarity_threshold` (step 5) stays low, so every candidate is stored and the cut can change without retraining. See "Observed on TechZone" below for why 93.
   - Save. If Maximo asks to apply configuration changes, do so.
   - IBM's sample uses a relationship from `SR` to `SR` with the score read by the listed SR alone (`objectname='SR' and similartoobjectid=:ticketuid`). On TechZone that showed another pair's score (89 instead of 96) and could not sort by score, so the dialog reads the pairs directly.

2. **Filters.** In **Object Structures**, open `MXAPISR` and click **More actions > Query definition**. For each row below, click **+**, choose **Query Type** `osclause`, tick **Is Public?**, and click **OK**.

   | Query Clause Name | Query Clause | What it picks |
   |---|---|---|
   | `SRSIMILARITYCFGFILTER` | `siteid='SRQSITE' and externalrecid like '7%'` | The reports a new one is compared with: all 65 pilot SRs, including the resolved first reports of each cluster |
   | `SRSIMILARITYINFFILTER` | `siteid='SRQSITE' and externalrecid like '7%' and status in (select value from synonymdomain where domainid='SRSTATUS' and maxvalue in ('NEW','QUEUED','PENDING','INPROG'))` | The reports that get suggestions: the open ones a reviewer is still vetting (45) |

   - The training history is left out on purpose. It is all closed, and its streets differ from the pilot's, so it would only slow the comparison.

3. **Query templates.** Still in `MXAPISR`, click **More actions > Query Template** and add two templates. Add the same four attributes to both: `ticketuid`, `description`, `description_longdescription`, `reportdate`.

   | Template name | Description | Page Size |
   |---|---|---|
   | `SRSIMILARITY` | SR similarity configuration | 1000 |
   | `SRSIMILARITYINF` | SR similarity inferencing | 10 |

   - Tick **Public?** and leave **Default Projection?** clear on both. The attributes need no sort, visible or searchable flags. This matches IBM's `WOSIMILARITYCFG` and `WOSIMILARITYINF` templates on `MXAPIWODETAIL`.

   - `ticketuid` is the unique ID the filters use, the two descriptions are what gets compared, and `reportdate` is the date the arguments in step 5 use.

4. **Invocation channels.** In **Invocation Channels**, copy IBM's work order channels:

   | Copy this channel | New name | Request object structure | Request template |
   |---|---|---|---|
   | `AIWOSIMILARITYCFG` | `SRSIMILARITYCFG` | `MXAPISR` | the configuration template from step 3 |
   | `AIWOSIMILARITYINF` | `SRSIMILARITYINF` | `MXAPISR` | the inferencing template from step 3 |

   - For each: open the channel, click **More actions > Duplicate Invocation Channel**, enter the new name, and set both the **Request** and the **Response Object Structure** to `MXAPISR`. The copy keeps `MXAPIWODETAIL` as the response structure until you change it.
   - Keep the endpoint `AIBROKERAPI` and the processing classes that come with the copy.
   - On TechZone (Manage 9.2.3) the Invocation Channels screen has no **Request Template** field, although IBM's steps name one. The value lives in the channel's `templatename` (`MAXIFACEINVOKE.TEMPLATENAME`). IBM's `AIWOSIMILARITYCFG` holds `WOSIMILARITYCFG` there. Set it on each saved channel through the `MXIFACEINVOKE` object structure in the REST API: `SRSIMILARITY` on `SRSIMILARITYCFG`, `SRSIMILARITYINF` on `SRSIMILARITYINF`. A duplicated channel may still hold IBM's work order template until you do.

5. **The AI configuration.** In **AI configuration**, click **Add configuration**:

   | Field | Value |
   |---|---|
   | Name | `SRSIMILARITY` |
   | Description | Suggest other reports of the same problem |
   | Template | the `similarity` template, latest version |
   | Object structure | `MXAPISR` |
   | Configuration and inference channels | `SRSIMILARITYCFG` and `SRSIMILARITYINF` |
   | Configuration and inference filters | `SRSIMILARITYCFGFILTER` and `SRSIMILARITYINFFILTER` |

   Click **Create**, then **Actions > Set arguments**:

   | Argument | Default | Pilot value | Why |
   |---|---|---|---|
   | `date_field` | `changedate` | `reportdate` | Maximo stamps `changedate` at load time, so every loaded record would look new. |
   | `features` | `description, description_longdescription` | keep | The long description holds the address and the resident's words. |
   | `history_days` | 30 | 365 | Tested at 365 so the window cannot hide a duplicate. IBM does not say whether it counts back from today or from each report; if from today, a small value drops the whole pilot (August to October). Trying 7 is the next test: if it counts from each report, it would drop look-alikes weeks apart. |
   | `retention_days` | 90 | 365 | It counts back from today. The pilot starts on 2026-08-03, so 90 days would drop August. The limit is 1000. Raise it if the pilot runs past July 2027. |
   | `similarity_threshold` | 70 | keep 70 | Every pilot pair scores 83 to 97, so nothing is cut here. The reviewer's cut is the `score>=93` in step 1. |
   | `max_similarity_records` | 10 | keep | Stores the 10 closest per open SR. |

   - Optional: in **Additional details for AI explained**, enter "Suggests other reports of the same problem. A reviewer decides which ones to group. Nothing is linked or closed automatically." Users see it behind the AI icon.
   - Click **Save**, then **Actions > Activate**, then **Actions > Create model**.
   - Training starts at once and the configuration list shows **Model status Ready** when it ends. The log only records the start; use **Actions > Check model status** for progress.
   - Results come from the AIINFJOB cron task, whose `DFLTINF` instance runs hourly by default (training is AITRAINJOB's `WOAI` instance, every 5 minutes). For the pilot, set `DFLTINF` to every 5 minutes and use **Reload Request**. Each run handles 10 open SRs (the inferencing template's page size), so the 45 open pilot SRs take about 25 minutes.

6. **The dialog.** In **Application Designer**, open the **Service Requests** application (`SR`).
   1. Click **Export Application Definition** and keep the file. It is the way back.
   2. Add this dialog at the end of the XML, just before `</presentation>`, then import it with **Import Application Definition**:

      ```xml
      <dialog id="AISIMSR" label="Similar service requests from AI" datasrc="MAINRECORD">
        <section id="aisimsr_head">
          <textbox id="aisimsr_ticketid" dataattribute="ticketid" inputmode="readonly"/>
          <textbox id="aisimsr_desc" dataattribute="description" inputmode="readonly"/>
        </section>
        <table id="aisimsr_tbl" relationship="AISIMSRPAIR" orderby="score desc" label="Reports that read like this one, closest first" inputmode="readonly">
          <tablebody id="aisimsr_tbl_body" displayrowsperpage="10">
            <tablecol id="aisimsr_c1" dataattribute="AISIMSRTICKET.ticketid" label="Service Request"/>
            <tablecol id="aisimsr_c2" dataattribute="AISIMSRTICKET.status" label="Status"/>
            <tablecol id="aisimsr_c3" dataattribute="AISIMSRTICKET.reportdate" label="Reported Date"/>
            <tablecol id="aisimsr_c4" dataattribute="AISIMSRTICKET.description" label="Summary"/>
            <tablecol id="aisimsr_c5" dataattribute="score" label="Similarity score"/>
          </tablebody>
        </table>
        <buttongroup id="aisimsr_buttons">
          <pushbutton id="aisimsr_ok" label="OK" default="true" mxevent="dialogok"/>
        </buttongroup>
      </dialog>
      ```

   - This is IBM's sample dialog cut down to a read-only list. IBM's version also has a **Generate/Re-generate similarity** button and a **Close selected SRs** button. Both need custom Java or a script.
     - We leave out regenerate because the cron task refreshes the list.
     - We leave out close because the County wants duplicates grouped onto one work order, not closed. Grouping is the next section.
   - If the import is refused, add the same dialog with the **Create Dialogs** toolbar button instead.

7. **The menu entry and access.**
   1. Still in Application Designer, click **Select Action > Add/Modify Signature Options**. Add option `AISIMSR`, with description "Similar service requests from AI".
   2. Click **Select Action > Add/Modify Select Action Menu**. Add a row with element type `OPTION` and key value `AISIMSR`, then save. Maximo opens the dialog whose ID matches the option name.
   3. In **Security Groups**, open each reviewer group. Under **Applications > Service Requests**, grant **Similar service requests from AI**. Sign out and back in.

**Check it:** open SR800019 in classic **Service Requests** (Service Desk > Service Requests) and click **Select Action > Similar service requests from AI**. SR800017 should be the only row, at 96. Then try SR800031: SR800030 first, at 95.

Expected matches in the pilot:

| Cluster | First report: becomes the Global Issue | Duplicate reports | The one work order |
|---|---|---|---|
| A, main break, Corvina Bay Dr | SR800030 | SR800031, SR800032 | WO2900028 (complete) |
| B, sewer odor, 6546 Gulfwren Ave | SR800044 | SR800046 (the same resident, calling two days later) | WO2950024 (draft) |
| C, no water, Bramblewick Ln | SR800053 | SR800054, SR800055 | WO2900040 (complete) |
| D, lift station alarm, Eldergrove Ct | SR800040 | SR800041 | WO2900035 (complete) |
| E, water line leak, 5948 Thistlewood Dr | SR800017 | SR800019 | WO2900018 (complete) |

Look-alikes that must **not** be grouped, even if listed:
- SR800042 resembles SR800040: a lift station alarm the same night, but at a different station in another city.
- SR800059 resembles SR800030: a small meter leak six weeks after the repair.
- SR800060 resembles SR800053: an account lock on the meter.
- SR800065 resembles SR800053: water coming up again after the repair.

The AI compares words only. It cannot tell that 1370 and 1364 Corvina Bay Dr are neighbors, or that two lift stations are different. Time only counts through the `history_days` window. The reviewer judges the rest, and the look-alikes test exactly that.

Observed on TechZone (2026-11-08, `history_days` 365, all 8 open duplicates checked):

| Open duplicate | Top match | At `score>=93` the reviewer sees |
|---|---|---|
| SR800019 | SR800017, 96 ✅ | SR800017 only |
| SR800031 | SR800030, 95 ✅ | SR800030, plus SR800065 (93) |
| SR800032 | SR800006, 95 ❌ | SR800006, SR800059 (look-alike), SR800049, SR800036; not SR800030 |
| SR800041 | SR800040, 93 ✅ | SR800040 only |
| SR800044 | SR800046, 97 ✅ | SR800046, plus SR800025 (93) |
| SR800046 | SR800044, 97 ✅ | SR800044 only |
| SR800054 | SR800053, 96 ✅ | SR800053, plus SR800060 (look-alike, 95) |
| SR800055 | SR800004, 94 ❌ | SR800004 only; SR800053 and SR800054 score 92 |

- The first report is the top match for 6 of the 8 duplicates.
- Scores bunch between 83 and 97 because the pilot summaries share one pattern ("Water Line Leak, *address*"). Across 40 open SRs, a cut at 93 keeps 6 of 12 duplicate pairs with 20 wrong pairs (about one in two SRs shows one). At 96 there are no wrong pairs but only 4 duplicates.
- Two look-alikes (SR800059, SR800060) score as high as true duplicates, so the reviewer's judgement stays essential, as planned.

## Group duplicate reports under one work order

This uses standard Manage features, no AI. Do it after the reviewer agrees with a suggestion from configuration 4.

1. **Make the first report the Global Issue.** Open the cluster's first report, for example SR800030. Tick **Global Issue** on its main tab and save.
2. **Link each duplicate.** Open SR800031. In **Related to Global ID**, select SR800030 and save. Do the same for SR800032. Or, on SR800030, use **Show Similar Tickets**, select the duplicates and press **Relate Records to Global Issue**.
   - Link duplicates this way only. A plain related-record link made earlier does not follow the Global Issue's status, even after the first report becomes global. Delete it and link again.
   - Once reports are linked, you cannot untick **Global Issue** (BMXAA4272E). Remove the links first.
3. **Only the first report's work order is dispatched.** For cluster A that is WO2900028. For cluster B, approve the draft WO2950024. The duplicates never get a work order of their own.
4. **Status follows the Global Issue.** When the first report's status changes, Maximo changes every report linked to it. Its work order drives it: when the work order completes, its SR is resolved, and so is every linked report. The communication template `SRTGTEMP` can email everyone who reported the problem.
   - In clusters A, C, D and E the first report is already RESOLVED, so the linked reports follow its next change, to CLOSED.
   - Or resolve a duplicate directly, with a note such as "Duplicate of SR800030".

Labels may differ by version. Step 0 checks that the fields are there. If SRs on TechZone have no Global Issue fields, use the **Related Records** tab instead: relate each duplicate to the first report. This links them, but status does not follow, so resolve each duplicate by hand.

Observed on TechZone (2026-11-08, cluster B):
- The fields are on the **Service Request** tab of classic Service Requests (Service Desk > Service Requests), in the **Global Issues** section next to **Dates**: the **Global Issue** check box, the global ID field with a lookup, and **Global Class**.
- SR800044 ticked as Global Issue, then SR800046 linked to it: SR800046 shows global ID SR800044, class SR, related to global = yes. The AI dialog on SR800046 had listed SR800044 first, at 97.
- Status follows: WO2950024 approved (APPR), then SR800044 moved to INPROG. SR800046 changed to INPROG at the same second, with no edit of its own. Only WO2950024 is dispatched for the cluster.
- Cluster A: a RESOLVED first report can be a Global Issue. SR800030 (RESOLVED) was ticked, and SR800031 and SR800032 linked to it; SR800032 was linked by the reviewer although the AI did not suggest it. Linking does not change a duplicate's status: they stay QUEUED until SR800030's next change, to CLOSED. That was not tested, because a closed SR cannot be changed again.

## Missing information (planned)

No Maximo version has a built-in AI check for missing details, on service requests or work orders. The decision for the pilot:
- **Now, on any version:** an automation script that runs when an SR is saved. It flags gaps such as no house number or no lift station number. It does not block the save, so a report from QAlert is never lost.
  - A Work Queue only shows the results of a saved query; nothing can be pushed into one. So the script sets a flag on the SR, and a Work Queue on `MXAPISR` lists the flagged SRs. New Work Queues start inactive, so activate it.
  - If an SR has a structured service address, "no house number" is a plain empty-field check on its House Number field. Free text needs the script.
  - An escalation can run the same check on a schedule without a script, but it is not immediate.
- **On 9.2:** the same script becomes a custom tool on the Maximo MCP server. An AI agent, watsonx Orchestrate for certain and the Maximo Assistant if TechZone shows it can call custom tools, uses it to explain the gap and draft the question for the resident.

The research is in `plans/reports/research-synthesis-261106-1307-maximo-ai-duplicates-and-missing-info.md`. This is not built yet.

## Maximo Assistant (talk track)

- In **Object Structures**, confirm that **Use for assistant** is ticked on `MXAPISR` and `MXAPIWODETAIL`.
- As documented for 9.1, the Assistant finds records. It does not judge them. TechZone runs 9.2, where the Assistant can also act as an agent, so check what it can do there. Use it at reviews with the tested questions in [mas-ai-assistant-prompts.md](mas-ai-assistant-prompts.md).
- On 11/04 a broad question ran until Maximo logged the session out. Keep questions narrow: one address, one request, one week.

## Measure the result

The Playback's measure is "agreement between AI recommendations and reviewer decisions". For each pilot record, write down what Maximo recommended and what the reviewer decided, then score it:

```bash
python3 scripts/score_ai_results.py --template evaluation/ai-results.csv   # a blank sheet, one row per record and feature
# fill in AI_VALUE, AI_SCORE, REVIEWER_DECISION (accept, override, skip) and OVERRIDE_REASON
python3 scripts/score_ai_results.py evaluation/ai-results.csv
```

- **Classification:** record the classification **name** Maximo shows, for example `WATER-LEAK`. Maximo numbers classifications itself, so a numeric ID is refused with a hint.
- **Team:** `SANCLINS` and `SANCLINSP` both count.
- **Similar work orders:** list the WO numbers Maximo showed, separated by `;`.
- **Similar service requests:** list the SR numbers the dialog showed, separated by `;`. Use `accept` when the reviewer grouped them under the Global Issue, and `override` when the reviewer kept them apart.
- **Which rows the template asks for:**
  - classification on all 65 SRs
  - team on the 53 SRs that name a team and are not duplicates
  - similar work orders where related WOs are expected, and on controls
  - similar service requests on the 18 open SRs that are in a duplicate cluster, are look-alikes, or are controls
- **Special values for `AI_VALUE`:**
  - leave it blank: not tried yet, left out of the score
  - `n/a`: the feature was not available on this record, for example the SR has no work order; left out
  - `none`: Maximo was asked and recommended nothing; counts against the AI
- **If Maximo renumbered the SRs or WOs:** score with `--answer-key loader-state/answer-key-maximo.csv`. On TechZone our numbers were kept, so this is not needed there. If that file was written before this change, run the pilot `load --apply` once to rewrite it.
- **What it reports:**
  - classification agreement, plus the share of misclassified SRs the AI corrected
  - team agreement
  - how many of the related WOs the similarity search surfaced
  - how many reports in a duplicate cluster were matched to it, and how many duplicates were shown their first report, the one they are grouped under
  - how many look-alikes were wrongly matched to the cluster they resemble (lower is better)
  - how often a control SR got a match
  - reviewer decisions and override reasons

## Draft work orders

Team recommendations and similar work orders appear on a **work order**, but most pilot SRs had none. `data/maximo/drafts/` holds 35 draft work orders, one for each open pilot SR that names a team and has no work order. Duplicate reports are left out: they join their cluster's work order.

- Each draft is WAPPR and linked to its SR. It carries the SR's text and classification, and no team, job plan or crew yet. That is what a planner sees before deciding who goes.
- They are numbered WO2950001 onward, so the pilot WO filters (`externalrefid like 'WO29%'`) already include them.
- Load them after the pilot (step 7c of the import guide). The loader refuses a draft whose SR is not loaded yet.
- Regenerate and check them with `scripts/generate_draft_work_orders.py` and `scripts/validate_draft_work_orders.py`.

## After the pilot

Deactivate the four configurations (**Actions > Deactivate**). This stops the training and inference cron work and the AppPoint use. Set the AITRAINJOB and AIINFJOB schedules back if you changed them. The `AISIMSR` dialog and menu entry can stay; without `SRSIMILARITY` running they show an empty list. To remove them, import the application definition you exported in configuration 4.

## Troubleshooting

| What you see | What to do |
|---|---|
| **Check data requirement** fails | Add history: raise `PER_CLASS`, regenerate, load with `--dataset history --apply`, then check again. |
| No recommendation option on a record | The record is not in the inference filter, the record is not editable, or inference has not run yet (AIINFJOB). |
| Training never starts | AITRAINJOB is inactive, or its `WOAI` instance schedule is long. |
| **View similar work orders** is missing from Actions | The security group lacks the **View similar work order** option on `MXAPIWODETAIL`. Sign out and back in after granting it. |
| Similar work orders list nothing for a related-work SR | Closed work is still excluded (step 3), `history_days` is too small, or the threshold is too high. |
| **Similar service requests from AI** is missing from Select Action | The `AISIMSR` option is not granted to your group, or you have not signed out and back in. |
| The similar SR dialog is empty | The SR is not open, so it is not in `SRSIMILARITYINFFILTER`. Or AIINFJOB has not run since activation. Or the AI configuration is not named `SRSIMILARITY`, which the `AISIMSRPAIR` relationship expects. Or it has no pair scoring 93 or more. |
| A duplicate is missing from the dialog | It scored below the `score>=93` cut in `AISIMSRPAIR` (SR800055 and SR800032 do), or its report date is outside `history_days`. Lower the cut to see more, at the cost of more wrong suggestions. |
| A similarity score looks wrong, or the list is not sorted by score | The dialog still uses IBM's `SR`-to-`SR` relationship, which reads the score by the listed SR only. Use `AISIMSRPAIR` and `AISIMSRTICKET` from step 1 and the dialog in step 6. |
| The similar SR dialog lists 10 reports every time | The cut is missing: every pilot pair scores above 83. Check `score>=93` in `AISIMSRPAIR`. |
| No Global Issue fields on the SR | Check you are in the classic Service Requests application, not the 9.2 Tickets application. If they are still missing, use the Related Records tab instead, and resolve each duplicate by hand. |
| **Relate Records to Global Issue** is missing | The SR is not ticked as a Global Issue, or your group lacks the **show isglobal** option. |
| A linked report did not change status | It was linked as a plain related record, not through **Related to Global ID**. Delete the link and relate it to the Global Issue again. |
| BMXAA4272E when unticking Global Issue | Other reports are still linked to it. Remove those links first. |
| A similarity log shows "BMXAA0024E - The action READ is not allowed on object TICKET" | The configuration reads the generic `TICKET` object, which this instance refuses for every user; granting `MXAPITKSRVAD` does not help. Use configuration 4 on `MXAPISR` instead, and deactivate `TICKETSIMILARITY`. |
| The Assistant spins and logs you out | Ask a narrower question. Note the time taken in the prompt pack. |

## Sources

- IBM, AI Service feature list: https://www.ibm.com/docs/en/masv-and-l/cd?topic=ons-ai-service
- IBM, Enabling field value recommendations: https://www.ibm.com/docs/en/SSRHPA_cd/appsuite/admin/t_ai_config_field_rec.html
- IBM, Enabling locating of similar work orders: https://www.ibm.com/docs/en/SSRHPA_cd/appsuite/admin/t_ai_config_similarity.html
- IBM, Enabling the assistant to retrieve data: https://www.ibm.com/docs/en/SSRHPA_cd/appsuite/admin/t_ai_config_assistant.html
- IBM, Finding other types of similar data (service request similarity, `SRSIMILARITY`, the `AISIMSR` dialog): https://www.ibm.com/docs/en/masv-and-l/cd?topic=orders-finding-other-types-data
- IBM, AI features in Maximo Manage: https://www.ibm.com/docs/SSRHPA_cd/appsuite/admin/c_ctr_ai_integrattion_manage.html
- IBM, Service request related records and global issues: https://www.ibm.com/support/pages/service-request-related-records
- IBM, Custom tools for the Maximo MCP server (9.2): https://www.ibm.com/docs/en/masv-and-l/cd?topic=developing-custom-tools
- IBM MAS CLI, AI Service install guide: https://ibm-mas.github.io/cli/guides/aiservice-install/
- Maximo Secrets (Andrew Jeffery), related tickets and Global Issues: https://maximosecrets.com/2021/10/26/service-request-related-tickets/
- Maximo Secrets, status inheritance on tickets: https://maximosecrets.com/2021/11/16/status-inheritance-on-tickets/
- Maximo Secrets, MAS 9.2 Work Queue Manager: https://maximosecrets.com/2026/08/10/mas-9-2-work-queue-manager/
- Maximo Secrets, MAS 9.2 Tickets application: https://maximosecrets.com/2026/11/02/mas-9-2-tickets/
