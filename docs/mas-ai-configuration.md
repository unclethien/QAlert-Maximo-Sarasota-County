# Setting up MAS AI for AI-assisted vetting and classification

This guide sets up use case 1 from the Workshop Playback on the TechZone Maximo instance. It uses the AI that is built into Maximo Manage:

| What the reviewer needs | Maximo feature | Where it shows |
|---|---|---|
| The right classification for a new request | Field value recommendation on the SR's `CLASSSTRUCTUREID` | A recommendation option on the Classification field of a service request |
| The right team | Field value recommendation on the WO's `PERSONGROUP` | A recommendation option on the Person Group field of a work order |
| Several residents reporting one problem (duplicates) | Similar service requests (`similarity` template on `MXAPISR`), then a Global Issue groups them onto one work order | **Select Action > Similar service requests from AI** on a service request. We build this dialog; see configuration 4 |
| Related past or planned work | Similar work orders (`WOSIMILARITY`) | **Actions > View similar work orders** on a work order |
| Questions in plain language during reviews | Maximo Assistant | The AI icon in Service Requests and Work Order Tracking |
| Missing information | No built-in AI feature on 9.1 or 9.2 | A rule script flags gaps as `MISSINFO` work log entries, and a Work Queue lists them. A watsonx.ai check outside Maximo reads the request for the rest and drafts the question to the resident. See "Missing information" below |

The AI only recommends. A person accepts or ignores each recommendation, and no configuration here changes a record by itself. That is the pilot guardrail from the Playback.

Status: **draft**. The steps come from IBM's documentation, listed under Sources at the end. The "Observed on TechZone" notes are filled in as each step is run. Notes marked "before the reload" come from the records loaded before the SRs carried structured fields, so they cite the old numbers (SR800001+, WO2900001+, drafts WO2950001+). Each old number maps to the new one by a fixed offset: SR800044 is now SR810044.

## Before you start

1. **The pilot data is loaded.** See [maximo-import-guide.md](maximo-import-guide.md).
2. **The training history is loaded.** Step 7b of the same guide covers this: 1,170 closed or resolved SRs and 990 closed WOs that the AI learns from. The 65 pilot SRs are what it is tested on. See [sample-dataset.md](sample-dataset.md#training-history-for-mas-ai).
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
| We have cluster-admin on the OpenShift cluster (only needed to install AI Service ourselves) | `oc auth can-i '*' '*' --all-namespaces` | Yes, for the reservation's IBMid (2026-11-12). The cluster is Red Hat OpenShift on IBM Cloud in `us-south`. Sign in with an IBM Cloud one-time passcode, as `oc login -s <cluster service endpoint> -u passcode -p <passcode>`. |
| AI Service is installed, and which catalog the cluster runs | `oc get aiserviceapp -A`, or `mas must-gather --collectors mas,aiservice --no-logs` for a full version summary | Installed: `aiserviceapp` `inst1` in namespace `aiservice-inst1`, tenant `aiservice-inst1-user`, licensed 2026-09-25 to 2027-09-25 (2026-11-12). Catalog not checked. |
| Which watsonx.ai AI Service uses | `oc get aiservicetenant -n aiservice-inst1-user -o yaml`, under `settings.watsonxai` | watsonx.ai on IBM Cloud, `https://us-south.ml.cloud.ibm.com`, project `16f0743c-0dfc-4223-8047-047c0a3b7232`. The key is in secret `aiservice-inst1-user----wx-secret` (`wx_apikey`). No watsonx.ai runs on the cluster itself. |
| Which tools the Assistant can call | **AI configuration** > `ASSISTANT` > **Tools** | None. All 14 tools, our `SRQ-SR-CLASS` and `SRSIMILARITY` included, show **Available in assistant: Not supported yet** (2026-11-12). Tool use needs the agentic Assistant, which the instance owner turns on. |
| A RESOLVED SR can be made a Global Issue, and a QUEUED SR can be linked to it | Try SR810030 and SR810031 | _pending_ |

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
| Pilot (test) | `siteid='SRQSITE' and externalrecid like '71%'` | `siteid='SRQSITE' and externalrefid like 'WO291%'` |

- **Alternative, for SRs only:** a date split. Every history SR is reported before 2026-08-01, and every pilot SR on or after 2026-08-03.
  - Use it only if the ID filters are refused. The date syntax depends on the database.
  - It does not work for WOs: 12 pilot WOs (the past work, WO2910001 to WO2910012) are reported before August 2026. WOs must use the `externalrefid` filters.
- **Why `siteid` in every filter:** the instance also holds an earlier demo dataset. Without it, the model trains on that.

## Configuration 1: SR classification

IBM's examples classify work orders only. On TechZone, its `WOPROBLEMCODE` configuration (template `pcc`, on `MXAPIWODETAIL`) shows the setup a classification needs: two filters, two query templates and two invocation channels, the same pattern as configuration 4. We copy it onto `MXAPISR`. Check first that **Create** in **AI configuration** offers the `mcc` template. If it does not, stop and record that as a pilot finding.

1. **Filters.** In **Object Structures**, open `MXAPISR` and click **More actions > Query definition**. Add these with **Query Type** `osclause` and **Is Public?** ticked:

   | Query Clause Name | Query Clause | What it picks |
   |---|---|---|
   | `SRCLASSTRAINFILTER` | `siteid='SRQSITE' and externalrecid like '5%'` | The 1,170 history SRs the model learns from (13 classes, 90 each) |
   | `SRCLASSINFFILTER` | `siteid='SRQSITE' and externalrecid like '71%'` | The 65 pilot SRs that get a recommendation |

   - Change these clauses here. The REST API cannot change them: `MXAPIOSLCQUERY` is read only (BMXAA0031E), and `MXAPIINTOBJECT` does not include them.

2. **Query templates.** Still in `MXAPISR`, click **More actions > Query Template**. Tick **Public?** and leave **Default Projection?** clear on both.

   | Template name | Description | Page Size | Attributes |
   |---|---|---|---|
   | `SRCLASSTRAIN` | SR classification training request content | 1000 | `ticketuid`, `description`, `description_longdescription`, `classstructureid`, `classstructure.description--classstructureid_description` |
   | `SRCLASSINF` | SR classification inference request content | 10 | `ticketuid`, `description`, `description_longdescription` |

   - This mirrors IBM's `WOPROBLEMTRAIN` and `WOPROBLEMINF` on `MXAPIWODETAIL`. Training sends the answer (`classstructureid`) and its description. Inference sends only the text.
   - The `--` in the last attribute names the alias the AI sees, as IBM's `problem.description--problemcode_description` does.

3. **Invocation channels.** In **Invocation Channels**, copy IBM's problem code channels with **More actions > Duplicate Invocation Channel**:

   | Copy this channel | New name | Request and response object structure | Request template (`templatename`) |
   |---|---|---|---|
   | `AITRAINWOPROBLEMCODE` | `AITRAINSRCLASS` | `MXAPISR` | `SRCLASSTRAIN` |
   | `AIINFWOPROBLEMCODE` | `AIINFSRCLASS` | `MXAPISR` | `SRCLASSINF` |

   - Keep the endpoint `AIBROKERAPI` and the exit classes the copy brings (`AITrainReqExit` and `AITrainRespExit`, `AIInferenceReqExit` and `AIInferenceRespExit`).
   - On TechZone (Manage 9.2.3) the screen lets you change only the **Request Object Structure**. The **Response Object Structure** stays locked at `MXAPIWODETAIL`, and there is no **Request Template** field. Set `replyintobjname` = `MXAPISR` and `templatename` through the `MXIFACEINVOKE` object structure in the REST API. Otherwise the copy keeps IBM's `MXAPIWODETAIL` response and its `WOPROBLEMTRAIN` or `WOPROBLEMINF` template.

4. **Description relationship.** Maximo reads the target description on its AI result object, `MAXAIINFERENCEDET`, not on the SR. IBM's `WOPROBLEMCODE` uses its `PROBLEMCODEDESC` relationship there; classifications have none. In **Database Configuration**, open `MAXAIINFERENCEDET` and add one relationship:

   | Relationship | Child object | Where clause |
   |---|---|---|
   | `CLASSSTRUCTUREDESC` | `CLASSSTRUCTURE` | `classstructureid = :inference` |

   - Without it, leave Target description empty. The recommendation then shows the class ID (for example `1024`) instead of "Utilities \ Water \ Line leak".

5. **The AI configuration.** In **AI configuration**, click **Add configuration**:

   | Field | Value |
   |---|---|
   | Name | `SRQ-SR-CLASS` |
   | Description | Recommend the classification of a Sarasota pilot service request |
   | Template | the `mcc` template, latest version |
   | Object structure | `MXAPISR` |
   | Attribute | `classstructureid` |
   | Target description | `CLASSSTRUCTUREDESC.DESCRIPTION` |
   | Training and inference channels | `AITRAINSRCLASS` and `AIINFSRCLASS` |
   | Training and inference filters | `SRCLASSTRAINFILTER` and `SRCLASSINFFILTER` |

   Then, in order:
   1. **Actions > Set arguments**:
      - `features` = `description,description_longdescription`
      - `score_threshold` = `0.5`
   2. **Actions > Check data requirement.** If it fails:
      - raise `PER_CLASS` in `scripts/history_catalog.py` (for example to 60)
      - regenerate and validate the history
      - load it again with `--dataset history --apply`. Raising the size only appends records (SR601171 onward at the next step), so the records already loaded do not change and are skipped.
      - run the check again
   3. **Actions > Activate**, then **Actions > Create model** (some versions call it **Train model**). Watch **Actions > Check model status**; the training log only records the start.
   4. Results come from the AIINFJOB cron task's `DFLTINF` instance, already set to every 5 minutes for configuration 4. Each run handles 10 SRs (the inference template's page size), so the 65 pilot SRs take about 35 minutes.
   5. Leave **Auto apply** off. The AI recommends, and a person accepts.

6. **Check it:** open a pilot SR, for example `SR810001` (expected **WATER-LEAK**), and make it editable. The Classification field should offer a recommendation.

**Fallback if `MXAPISR` is refused:** IBM's examples all use work orders. If the SR structure is not accepted, set this configuration up on `MXAPIWODETAIL` with attribute `classstructureid` and the WO filters. Record the refusal as a pilot finding.

**Second run, worth doing:** a pilot SR's `DESCRIPTION` starts with the QAlert type the resident picked, so a model can score well just by copying it. The five misclassified pilot SRs show whether it reads the request instead.
- Run a copy of this configuration with `features` = `description_longdescription` only.
- Compare the two runs on those five SRs with the scoring script.

Observed on TechZone (2026-11-09, before the reload):
- `mcc` is offered, as version 1.7.1-gpt. Its arguments are `features` (a string list) and `score_threshold` (default 0.5).
- **Create** with `classstructure.description` as Target description fails with BMXAA4187E: the relationship does not exist for `MAXAIINFERENCEDET`. The `CLASSSTRUCTUREDESC` relationship in step 4 fixes it.
- With 30 SRs per class, training reads all 390 history SRs and the model is created, but the model status ends in **Error** at step 3 of 4 (Training), with "unknown error". Maximo's training log stops at "Training initiated".
  - The payload matches IBM's data preparation rules for `mcc`: 390 unique records, 13 values with 30 records each, features `description` and `description_longdescription`, the unique ID `ticketuid`, the target `classstructureid`, and `classstructureid_description` filled in on every record.
  - No classification model has trained on this instance before. IBM's own `WOPROBLEMCODE` (`pcc`) has never been trained, and the models that work (similarity, Assistant, docs search) do not train a classifier.
  - **Cause, from the training pod's log** (pod `s3-<model id>-pipeline-…` in OpenShift project `aiservice-inst1-user`; it is deleted soon after it ends, so watch it during a run):
    - `mcc` 1.7.1-gpt makes extra training examples with watsonx.ai (`openai/gpt-oss-120b`) for every value with fewer than 50 training records (`expansions.min_samples: 50`). Its training split is about two thirds of the records, so 30 per class gave 20 each, and all 13 values were sent for expansion: 261 calls, one at a time.
    - On the re-train (2026-11-09 14:38 UTC) the first watsonx chat call got no answer for 10 minutes. IBM's own 10-minute timeout then failed with `TypeError: handle_timeout() missing 1 required positional argument: 'frame'`. That bug in the template turns a slow call into a failed training run, reported in Maximo as "unknown error".
    - Report to IBM: the `handle_timeout` signature in `/mcc/common/utils/augment.py`, `mcc` 1.7.1-gpt.
  - **Workaround:** give every value at least 50 training records, so the watsonx step is skipped. `PER_CLASS` is now 90 (about 60 training records per value): 1,170 history SRs and 990 WOs. The first 390 SRs are unchanged, so only the new ones are loaded. This also means the training text no longer goes to watsonx.ai, which avoids sending residents' names and addresses to IBM Cloud.
- With 90 per class, the re-train (2026-11-09 15:18 UTC) skipped the watsonx step ("No expansion will be performed", 0 watsonx tokens) and trained on CPU. Inference ran at 16:31 UTC on all 65 pilot SRs.
- **Result against the answer key** (top recommendation per SR):
  - It agrees on 56 of 65 SRs. The classifications as loaded agree on 60 of 65.
  - It corrects 4 of the 5 misfiled SRs.
  - It disagrees with 8 SRs that were already filed correctly. 6 of those are at confidence 50, the lowest the default threshold shows.
  - Most of its misses send a water line leak to Water Main, Storm Flooding, Pressure or No Water: the neighbouring water classes.
  - SR800027 (Pressure instead of Meter) reports both problems, so Pressure is defensible.
- **After the reload (2026-11-11):** the inference filter was changed to `'71%'`, the configuration was reactivated with the same model, and inference ran on the 65 reloaded SRs (SR810001 onward). The result is unchanged: 56 of 65 agree with the answer key, and 4 of the 5 misfiled SRs are corrected. This was expected, because the model reads only the description text, and the reload did not change it.

  | `score_threshold` | Shown | Right | Wrong |
  |---|---|---|---|
  | 0.50 (default) | 63 | 54 | 9 |
  | 0.51 | 48 | 46 | 2 |
  | 0.55 | 36 | 34 | 2 |

## Configuration 2: WO team

The same setup as configuration 1, on `MXAPIWODETAIL`. IBM's work order channels already answer with `MXAPIWODETAIL`, so only the request template needs the API.

1. **Filters** on `MXAPIWODETAIL` (**Object Structures > Query definition**, `osclause`, **Is Public?**):

   | Query Clause Name | Query Clause | What it picks |
   |---|---|---|
   | `WOTEAMTRAINFILTER` | `siteid='SRQSITE' and externalrefid like 'WO27%'` | The 990 history WOs |
   | `WOTEAMINFFILTER` | `siteid='SRQSITE' and externalrefid like 'WO291%'` | The 76 pilot WOs, drafts included |

2. **Query templates** on `MXAPIWODETAIL` (**Public?** ticked, **Default Projection?** clear):

   | Template name | Description | Page Size | Attributes |
   |---|---|---|---|
   | `WOTEAMTRAIN` | WO team training request content | 1000 | `workorderid`, `description`, `description_longdescription`, `persongroup` |
   | `WOTEAMINF` | WO team inference request content | 10 | `workorderid`, `description`, `description_longdescription` |

   - `WORKORDER` has no `PERSONGROUP` relationship (BMXAA4187E), so the training template sends the team code only. The codes (`WTRPIPE`, `SANCLINS` and so on) are readable.

3. **Invocation channels.** Duplicate `AITRAINWOPROBLEMCODE` as `AITRAINWOTEAM` and `AIINFWOPROBLEMCODE` as `AIINFWOTEAM`. Keep `MXAPIWODETAIL` for request and response. Set `templatename` through `MXIFACEINVOKE` in the REST API: `WOTEAMTRAIN` and `WOTEAMINF`.

4. **Description relationship** on `MAXAIINFERENCEDET`: `PERSONGROUPDESC`, child `PERSONGROUP`, where clause `persongroup = :inference`.

5. **The AI configuration:**

   | Field | Value |
   |---|---|
   | Name | `SRQ-WO-TEAM` |
   | Description | Recommend the team for a Sarasota pilot work order |
   | Template | `mcc`, latest version |
   | Object structure | `MXAPIWODETAIL` |
   | Attribute | `persongroup` |
   | Target description | `PERSONGROUPDESC.DESCRIPTION` |
   | Training and inference channels | `AITRAINWOTEAM` and `AIINFWOTEAM` |
   | Training and inference filters | `WOTEAMTRAINFILTER` and `WOTEAMINFFILTER` |
   | `features` | `description,description_longdescription` |
   | `score_threshold` | `0.5` |

   Then **Activate** and **Create model**, as in configuration 1.

- A follow-up WO's long description repeats the resident's request, so the model sees the same words the planner saw.
- **Where to test it:** 53 pilot SRs name an expected team and are not duplicates. 18 have a follow-up WO and the other 35 have a draft WO (WO2915001 onward). The pilot filter `externalrefid like 'WO291%'` covers both.
- **Prefer the drafts.** The 18 follow-up WOs already have their team filled in, so the reviewer sees the answer before judging the recommendation. A draft has no team yet.
- Duplicate reports have no WO of their own and get no team recommendation. They join their cluster's work order (configuration 4).

Observed on TechZone: _pending_

## Configuration 3: Similar work orders

`WOSIMILARITY` needs no training. In the pilot it answers "has a crew worked on this before, or is work already planned?" Run it from the draft WO of a related-work SR, for example SR810036's draft, which should list WO2910007 and WO2910012. Duplicate reports are found with similar service requests instead (configuration 4).

1. Open the `WOSIMILARITY` configuration and click **Actions > Edit**.
   - Set **Related Records** to `siteid='SRQSITE' and externalrefid like 'WO291%'`, so only pilot WOs are compared.
     - Leaving it empty brings in the earlier demo data on the instance.
     - It would also bring in the 990 closed history WOs, which are worded like the pilot's and would crowd the top 10.
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

Do not use the IBM-shipped `TICKETSIMILARITY` instead. It reads the generic `TICKET` object through `MXAPITKSRVAD`, and on TechZone (2026-11-08) Maximo refuses to read `TICKET`, `INCIDENT` and `PROBLEM` for every user, with BMXAA0024E. Its training stops after preparing the data, even with every `MXAPITKSRVAD` option granted. The Incidents and Problems applications are not in any security group there, so the Service Desk parts that `TICKET` spans appear not to be installed. Configuration 4 reads `SR` through `MXAPISR`, which works. Steps 1 to 5 below set up the data side, step 6 adds a duplicate score that also counts place and time, and steps 7 and 8 add the screen.

Keep IBM's name `SRSIMILARITY` for the AI configuration. The relationship in step 1 names it.

1. **Relationships.** In **Database Configuration**, add one relationship on each of two objects (**Relationships** tab):

   | Object | Relationship | Child object | Where clause | Remarks |
   |---|---|---|---|---|
   | `SR` | `AISIMSRPAIR` | `MAXAISIMILAROBJ` | `objectname='SR' and objectid=:ticketuid and aicfgname='SRSIMILARITY' and skipinf=0` | AI similarity results for this service request, one row per similar SR, with its scores. Used by the AISIMSR dialog. |
   | `MAXAISIMILAROBJ` | `AISIMSRTICKET` | `SR` | `ticketuid=:similartoobjectid` | The similar service request a similarity result points to. Used by the AISIMSR dialog. |

   - `MAXAISIMILAROBJ` holds one row per pair: `objectid` is the open SR that was checked, `similartoobjectid` the SR found, and `score` their text similarity. Step 6 adds `dupscore`.
   - The relationship has no score cut. The dialog lists every stored pair, ranked by the duplicate score from step 6, so a reviewer sees a report at another address low in the list with a low score instead of not at all. To hide pairs, add `and dupscore>=85`. The first pilot cut, `and score>=93` on the AI score alone, showed a report 6 km away at 93 and hid two real duplicates (see "Observed on TechZone" below).
   - Save. If Maximo asks to apply configuration changes, do so.
   - IBM's sample uses a relationship from `SR` to `SR` with the score read by the listed SR alone (`objectname='SR' and similartoobjectid=:ticketuid`). On TechZone that showed another pair's score (89 instead of 96) and could not sort by score, so the dialog reads the pairs directly.

2. **Filters.** In **Object Structures**, open `MXAPISR` and click **More actions > Query definition**. For each row below, click **+**, choose **Query Type** `osclause`, tick **Is Public?**, and click **OK**.

   | Query Clause Name | Query Clause | What it picks |
   |---|---|---|
   | `SRSIMILARITYCFGFILTER` | `siteid='SRQSITE' and historyflag = 0` | The reports a new one is compared with: every SR that is not closed or cancelled, whatever its source, including the resolved first reports of each cluster |
   | `SRSIMILARITYINFFILTER` | `siteid='SRQSITE' and status in (select value from synonymdomain where domainid='SRSTATUS' and maxvalue in ('NEW','QUEUED','PENDING','INPROG'))` | The reports that get suggestions: every open SR, whether loaded from QAlert or entered in Maximo |

   - The filters do not test the external ID, so an SR entered in Maximo, including with **Duplicate** (which does not copy the external ID), is covered like a loaded one.
   - Maximo marks an SR as history (`historyflag = 1`) when it is closed or cancelled. Leaving those out keeps retired copies, test SRs and cancelled reports from topping a live SR's list at 100, without naming any ID range.
   - On TechZone (2026-11-11) the filter matches 152 SRs: 61 pilot SRs, the 90 resolved SRs of the training history and one SR entered in Maximo. The four closed pilot SRs (SR810006, SR810016, SR810033, SR810061) are left out; none of them is in a duplicate pair.
   - Training also applies `retention_days` (step 5) to `reportdate`, so the model compares against 84 of them: the 61 pilot SRs, the 22 history SRs reported in the last 365 days, and the one entered in Maximo.
   - Until 2026-11-11 both filters were limited to `externalrecid like '71%' or externalrecid is null`. That took in the closed test SRs and the retired hand-made copy SR700046, which have no external ID.

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
   | `similarity_threshold` | 70 | keep 70 | Every pilot pair scores 81 to 97, so nothing is cut here. The dialog ranks by the duplicate score from step 6. |
   | `max_similarity_records` | 10 | keep | Stores the 10 closest per open SR. |

   - Optional: in **Additional details for AI explained**, enter "Suggests other reports of the same problem. A reviewer decides which ones to group. Nothing is linked or closed automatically." Users see it behind the AI icon.
   - Click **Save**, then **Actions > Activate**, then **Actions > Create model**.
   - Training starts at once and the configuration list shows **Model status Ready** when it ends. The log only records the start; use **Actions > Check model status** for progress.
   - Results come from the AIINFJOB cron task, whose `DFLTINF` instance runs hourly by default (training is AITRAINJOB's `WOAI` instance, every 5 minutes). For the pilot, in **Cron Task Setup**, set `DFLTINF` to every 5 minutes and use **Reload Request** there so the new schedule takes effect. (The AI configuration screen has no Reload Request.) Each run handles 10 open SRs (the inferencing template's page size), so the 45 open pilot SRs take about 25 minutes.
   - **The cron task scores each SR once.** Once an SR has its inference record (`MAXAIINFERENCE`), no later run scores it again. None of these makes it score again: a retrain, a filter change, Deactivate and Activate, or a later save of the SR. All four were tried on TechZone on 2026-11-11. A new SR gets its suggestions within about 5 minutes of being created inside the filter.
   - **To refresh SRs that already have suggestions,** for example after a retrain or a reload, send IBM's regenerate request once for each SR:
     - `POST <MAXIMO_URL>/api/aicfg_srsimilarity`, with header `content-type: application/json` and body `{"href": "<MAXIMO_URL>/api/os/mxapisr/<the SR's resource ID>", "usecache": false}`.
     - On TechZone, Manage answers with a 400 error (BMXAA9757E), but within a few seconds it still replaces the SR's inference record and its 10 pairs. Check the result by reading the new pairs, not the reply.
     - The `SRQDUPSCORE` escalation scores the new pairs within 5 minutes.
     - On 2026-11-11 this refreshed all 45 open pilot SRs. Their stored pairs had been made before the filter change, and 342 of them pointed at retired copies.

6. **The duplicate score.** The AI's score is text only. Pilot SRs all read "*Type*, *address*" over the same Customer, Address and Map layout, so two sewer odor reports 6 km apart score 93 against 97 for the true duplicate. The duplicate score adds place and time:

   `dupscore = AI score × location factor × time factor`

   | Factor | Value |
   |---|---|
   | Location, from each SR's service address coordinates, or the Maps link in its long description when the address has none | 1.0 up to 150 m apart, falling in a straight line to 0.5 at 1 km and beyond; 0.75 if either SR has no coordinates |
   | Time, days between the two report dates | 1.0 up to 3 days, 0.85 up to 14 days, 0.7 beyond |

   The dialog also shows the points each factor took off: distance first, then time, so `dupscore + distance deduction + time deduction` is the AI score. For SR810044 against SR810025 (6.1 km and 25 days apart) that is 33 + 46 + 14 = 93.

   A duplicate score of 85 or more marks a likely duplicate. The pilot's duplicates sit within 78 m and 2.1 days of the first report; wrong matches are 1.3 km or more apart, and look-alikes at the same place come 6 to 42 days later. The coordinates come from the SR's service address (`LATITUDEY`, `LONGITUDEX`). An SR without them, such as one from the text-only history, falls back to the Maps link in its long description. The script reads the address row through a set scoped to the SR by ticket and class, because on TechZone the row's org is not the SR's. The factors are in `scripts/autoscript/srqdupscore.py` and tested in `tests/test_duplicate_score.py`.

   1. **Back up.** Save the current `MAXAISIMILAROBJ` rows, for example through the API with the `MAXAISIMILARSR` relationship on `MXAPISR`. They are AI output, so the next AIINFJOB run would also rebuild them.
   2. **Add the columns.** In **Database Configuration**, open `MAXAISIMILAROBJ` and add three attributes, each type `INTEGER`, not required: `DUPSCORE` (Duplicate score), `DUPDISTPTS` (Distance deduction) and `DUPTIMEPTS` (Time deduction). Save. Applying it is a structural change, so it needs admin mode:
      - Admin mode needs `mail.smtp.host` and `mxe.adminEmail` set in **System Properties** (Live Refresh after each). It e-mails the administrator and, with no mail server, logs "BMXAA0259E - The e-mail cannot be sent", but it still turns on after its countdown. Everyone is signed out when the countdown ends, so warn other users first.
      - Every admin mode and structural step asks for an electronic signature. The password is your Manage **e-signature key**, not your sign-in password. Set it first from your profile menu (**Set or Modify E-signature**). Your sign-in password fails with BMXAA3840E and counts as a failed login.
      - With admin mode on, use **Apply Configuration Changes**, tick the backup box and click **Start Configuring the Database**. Use **Refresh Status** until it reads "ConfigDB completed without errors". Then turn admin mode off; escalations do not run while it is on.
   3. **The script.** In **Automation Scripts**, click **More Actions > Create > Script with Action Launch Point**. Launch point `SRQDUPSCORE` on object `MAXAISIMILAROBJ`, active; the action `SRQDUPSCORE` fills in. Script `SRQDUPSCORE`, language `python`, log level `ERROR`, no variables. Paste the source of `scripts/autoscript/srqdupscore.py` and click **Create**.
   4. **The escalation.** In **Escalations**, create `SRQDUPSCORE`, applies to `MAXAISIMILAROBJ`, condition `aicfgname='SRSIMILARITY' and (dupscore is null or duptimepts is null)`, schedule every 5 minutes. Add one escalation point with no elapsed time and no condition, tick its **Repeat?** box, and add action `SRQDUPSCORE` on its **Actions** tab. Without **Repeat?**, Maximo acts on each row only once, so rows scored before a change to the script or condition are never scored again; the condition alone stops a filled row from being processed twice. Save, then **More Actions > Activate/Deactivate Escalation**. Maximo creates cron task instance `ESCSRQDUPSCORE` under `ESCALATION`.
   - Each run scores every pair that has none, so new AI results are scored within 5 minutes. The `duptimepts is null` part also re-scores rows from before the deduction columns were added. On TechZone the first run scored all 450 pairs in one pass.

7. **The dialog.** In **Application Designer**, open the **Service Requests** application (`SR`).
   1. Click **Export Application Definition** and keep the file. It is the way back.
      The TechZone exports are in [maximo/app-designer](../maximo/app-designer): `sr-original.xml` is the SR application before any change, and `sr-aisimsr-v1.xml` to `v4` are each version imported since, and v4 added the duplicate score and the two deduction columns. `sr-source-v5.xml` is the one in use (2026-11-11): v4 plus a **Source** field (`SOURCE`, no lookup) under the class description in Service Request Details. Build any later change on v5.
   2. Add this dialog at the end of the XML, just before `</presentation>`, then import it with **Import Application Definition**:

      ```xml
      <dialog id="AISIMSR" label="Similar service requests from AI" datasrc="MAINRECORD">
        <section id="aisimsr_head">
          <textbox id="aisimsr_ticketid" dataattribute="ticketid" inputmode="readonly"/>
          <textbox id="aisimsr_desc" dataattribute="description" inputmode="readonly"/>
        </section>
        <table id="aisimsr_tbl" relationship="AISIMSRPAIR" orderby="dupscore desc" label="Similar requests, most likely duplicate first (duplicate score 85 or more: likely duplicate)" inputmode="readonly">
          <tablebody id="aisimsr_tbl_body" displayrowsperpage="10">
            <tablecol id="aisimsr_c1" dataattribute="AISIMSRTICKET.ticketid" label="Service Request"/>
            <tablecol id="aisimsr_c2" dataattribute="AISIMSRTICKET.status" label="Status"/>
            <tablecol id="aisimsr_c3" dataattribute="AISIMSRTICKET.reportdate" label="Reported Date"/>
            <tablecol id="aisimsr_c4" dataattribute="AISIMSRTICKET.description" label="Summary"/>
            <tablecol id="aisimsr_c6" dataattribute="dupscore" label="Duplicate score"/>
            <tablecol id="aisimsr_c7" dataattribute="dupdistpts" label="Distance deduction"/>
            <tablecol id="aisimsr_c8" dataattribute="duptimepts" label="Time deduction"/>
          </tablebody>
        </table>
        <buttongroup id="aisimsr_buttons">
          <pushbutton id="aisimsr_ok" label="OK" default="true" mxevent="dialogok"/>
        </buttongroup>
      </dialog>
      ```

   - This is IBM's sample dialog cut down to a read-only list. IBM's version also has a **Generate/Re-generate similarity** button and a **Close selected SRs** button. Both need custom Java or a script.
     - We leave out regenerate. The cron task does not refresh the list, so after a retrain or a reload, refresh the SRs with the request in step 5.
     - We leave out close because the County wants duplicates grouped onto one work order, not closed. Grouping is the next section.
   - Add the columns from step 6 before importing; the table sorts on `DUPSCORE`.
   - The AI's own text match (`score`) is not shown. The duplicate score and the two deductions add up to it.
   - If the import is refused, add the same dialog with the **Create Dialogs** toolbar button instead.

8. **The menu entry and access.**
   1. Still in Application Designer, click **Select Action > Add/Modify Signature Options**. Add option `AISIMSR`, with description "Similar service requests from AI".
   2. Click **Select Action > Add/Modify Select Action Menu**. Add a row with element type `OPTION` and key value `AISIMSR`, then save. Maximo opens the dialog whose ID matches the option name.
   3. In **Security Groups**, open each reviewer group. Under **Applications > Service Requests**, grant **Similar service requests from AI**. Sign out and back in.

**Check it:** open SR810019 in classic **Service Requests** (Service Desk > Service Requests) and click **Select Action > Similar service requests from AI**. SR810017 should be first, with a duplicate score of 96, and every other row below 50. Then try SR810044: SR810046 first at 97, and SR810025 (the same problem 6 km away) at 33, with 46 points taken off for distance and 14 for time (its AI text match is 93). Before the reload, the old SR800044 was cancelled by mistake on 2026-11-10, and its copy SR700044 (external ID 799044) showed the same list.

Expected matches in the pilot:

| Cluster | First report: becomes the Global Issue | Duplicate reports | The one work order |
|---|---|---|---|
| A, main break, Corvina Bay Dr | SR810030 | SR810031, SR810032 | WO2910028 (complete) |
| B, sewer odor, 6546 Gulfwren Ave | SR810044 | SR810046 (the same resident, calling two days later) | WO2915024 (draft) |
| C, no water, Bramblewick Ln | SR810053 | SR810054, SR810055 | WO2910040 (complete) |
| D, lift station alarm, Eldergrove Ct | SR810040 | SR810041 | WO2910035 (complete) |
| E, water line leak, 5948 Thistlewood Dr | SR810017 | SR810019 | WO2910018 (complete) |

Look-alikes that must **not** be grouped, even if listed:
- SR810042 resembles SR810040: a lift station alarm the same night, but at a different station in another city.
- SR810059 resembles SR810030: a small meter leak six weeks after the repair.
- SR810060 resembles SR810053: an account lock on the meter.
- SR810065 resembles SR810053: water coming up again after the repair.

The AI compares words only. It cannot tell that 1370 and 1364 Corvina Bay Dr are neighbors, or that two lift stations are different. The duplicate score (step 6) adds distance and time between reports, so a look-alike weeks later ranks below a same-day report next door. The reviewer still judges what the list shows, and the look-alikes test exactly that.

Observed on TechZone, AI score only (2026-11-08, `history_days` 365, all 8 open duplicates checked, before the reload):

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

Observed on TechZone with the duplicate score (2026-11-10, all 450 stored pairs scored, before the reload):

| Open duplicate | Likely duplicates (duplicate score 85 or more) | Highest other row |
|---|---|---|
| SR800019 | SR800017, 96 ✅ | 38 |
| SR800031 | SR800030, 95 ✅; SR800032, 91 (same cluster) | SR800059, 64 (look-alike) |
| SR800032 | SR800030, 92 ✅; SR800031, 91 (same cluster) | SR800059, 67 (look-alike) |
| SR800041 | SR800040, 93 ✅ | 49 |
| SR800044 | SR800046, 97 ✅ | 48; SR800025 at 33 |
| SR800046 | SR800044, 97 ✅ | 48 |
| SR800054 | SR800053, 96 ✅; SR800055, 92 (same cluster) | SR800060, 81 (look-alike) |
| SR800055 | SR800053, 92 ✅; SR800054, 92 (same cluster) | SR800060 and SR800065, 77 (look-alikes) |

- The first report now leads for all 8 duplicates, including SR800032 and SR800055, which the AI score alone missed.
- 14 of the 450 pairs reach 85: the 12 duplicate pairs and SR800060 with SR800065. Those two are look-alikes of cluster C, but against each other they are 12 m and 4 hours apart, so they may be one new problem reported twice. With the AI score alone, 34 pairs reached 93, 22 of them at another address.
- Look-alikes against the cluster they resemble score 64 to 82, so they stay visible, below the true duplicates. SR800042's closest row scores 47.
- The factors were tuned on these pilot pairs, so expect some drift on real data, especially SRs without a Maps link.

Observed after the reload (2026-11-11). The model was retrained on the ID-free filters, and all 45 open pilot SRs (SR810xxx) were refreshed:
- The likely duplicates (score 85 or more) are the same as in the table above, with the same scores and SR810xxx in place of SR800xxx.
  - 14 of the 450 pairs reach 85: the 12 duplicate pairs and SR810060 with SR810065.
  - The scorer reports 8 of 8 duplicates matched to their group, and 7 of 7 shown their first report.
  - No look-alike is matched to the group it resembles, and no control SR gets a match.
- 27 pairs now point at resolved history SRs. Their highest duplicate score is 47, because the history SRs are at other streets and dates, so they never reach the cut.
- No pair points at a retired SR800xxx copy, because closed SRs are out of the corpus.

## Group duplicate reports under one work order

This uses standard Manage features, no AI. Do it after the reviewer agrees with a suggestion from configuration 4.

1. **Make the first report the Global Issue.** Open the cluster's first report, for example SR810030. Tick **Global Issue** on its main tab and save.
2. **Link each duplicate.** Open SR810031. In **Related to Global ID**, select SR810030 and save. Do the same for SR810032. Or, on SR810030, use **Show Similar Tickets**, select the duplicates and press **Relate Records to Global Issue**.
   - Link duplicates this way only. A plain related-record link made earlier does not follow the Global Issue's status, even after the first report becomes global. Delete it and link again.
   - Once reports are linked, you cannot untick **Global Issue** (BMXAA4272E). Remove the links first.
3. **Only the first report's work order is dispatched.** For cluster A that is WO2910028. For cluster B, approve the draft WO2915024. The duplicates never get a work order of their own.
4. **Status follows the Global Issue.** When the first report's status changes, Maximo changes every report linked to it. Its work order drives it: when the work order completes, its SR is resolved, and so is every linked report. The communication template `SRTGTEMP` can email everyone who reported the problem.
   - In clusters A, C, D and E the first report is already RESOLVED, so the linked reports follow its next change, to CLOSED.
   - Or resolve a duplicate directly, with a note such as "Duplicate of SR810030".

Labels may differ by version. Step 0 checks that the fields are there. If SRs on TechZone have no Global Issue fields, use the **Related Records** tab instead: relate each duplicate to the first report. This links them, but status does not follow, so resolve each duplicate by hand.

Observed on TechZone (2026-11-08, cluster B, before the reload):
- The fields are on the **Service Request** tab of classic Service Requests (Service Desk > Service Requests), in the **Global Issues** section next to **Dates**: the **Global Issue** check box, the global ID field with a lookup, and **Global Class**.
- SR800044 ticked as Global Issue, then SR800046 linked to it: SR800046 shows global ID SR800044, class SR, related to global = yes. The AI dialog on SR800046 had listed SR800044 first, at 97.
- Status follows: WO2950024 approved (APPR), then SR800044 moved to INPROG. SR800046 changed to INPROG at the same second, with no edit of its own. Only WO2950024 is dispatched for the cluster.
- Cluster A: a RESOLVED first report can be a Global Issue. SR800030 (RESOLVED) was ticked, and SR800031 and SR800032 linked to it; SR800032 was linked by the reviewer although the AI did not suggest it. Linking does not change a duplicate's status: they stay QUEUED until SR800030's next change, to CLOSED. That was not tested, because a closed SR cannot be changed again.

## Missing information

No Maximo version has a built-in AI check for missing details, on service requests or work orders. The pilot splits the check by what it takes to decide a gap:
- **Rules that plain text can decide:** an automation script, [scripts/autoscript/srqmissinfo.py](../scripts/autoscript/srqmissinfo.py), runs when an SR is saved. It never blocks the save, so a report from QAlert is never lost. Each gap becomes a work log entry of type `MISSINFO` on the SR, and a Work Queue lists the open SRs that have one.
- **Rules that need the request to be read and understood:** for example, what the meter problem is, or two problems in one request. A script outside Maximo asks watsonx.ai, and the reviewer decides. See "AI check with watsonx.ai" below.

What the script checks, from [required-information.csv](../data/reference/required-information.csv):

| Rule | The script flags | Pilot SRs flagged |
|---|---|---|
| `ADDR` | No house number in the address | SR810001, SR810005, SR810008, SR810020 |
| `LS-ID` | A lift station alarm with no street and no station name or number | SR810020 |
| `ADDR-VALID` | An address in a city outside Sarasota County, or a house number and street with no address code, meaning it matched nothing in the County address file | SR810002, SR810012 (Bradenton), SR810033 |

- Against the answer key, the script finds every `ADDR` and `LS-ID` gap and flags nothing that is complete, in the pilot or the training history. `tests/test_missing_info_rules.py` checks this.
- It catches the misspelled or unknown streets, SR810002 and SR810033, from the service address: each has a house number and a street but no address code. The text alone can't tell, so an SR without a service address would miss them.
- The other 10 gaps in the answer key break only rules that need the text to be understood. The script catches 8 of the 18 gaps, against 6 from the text alone.
- The script reads the SR's service address first. When the address is empty, as on the text-only history or an SR typed into Maximo without one, it falls back to the `Address:` line of the long description. On an SR being added, it reads the row Maximo holds in memory. Otherwise it reads a set scoped to the SR by ticket and class.

### Set it up

1. **Log type.** In **Domains**, open `LOGTYPE` (a synonym domain) and add a row:

   | Value | Internal Value | Description |
   |---|---|---|
   | `MISSINFO` | `UPDATE` | Missing information |

2. **The script.** In **Automation Scripts**, click **More actions > Create > Script with Object Launch Point**:

   | Field | Value |
   |---|---|
   | Launch Point | `SRQMISSINFO` |
   | Object | `SR` |
   | Events | **Save**, with **Add** and **Update** ticked, **Before Save** |
   | Script | `SRQMISSINFO` |
   | Script Language | `python` |
   | Source | the whole of `scripts/autoscript/srqmissinfo.py` |

   Make sure both the script and the launch point are **Active**.

   - The wizard leaves the script's **status** at `Draft` even with **Active?** ticked, and a Draft script does not run. Use **Change Status > Active**.
   - To replace the source later without the UI, merge `{"source": "<the file>"}` into the script's `MXAPIAUTOSCRIPT` record. The API accepts `source` but does not return it on a read.
   - The script must import nothing. Maximo's Jython has no standard library, so `import re` fails, and a failing Before Save script blocks **every** SR save. If a new version fails, switch the launch point off first (merge `{"scriptlaunchpoint": [{"launchpointname": "SRQMISSINFO", "active": false}]}`), then fix it.
   - **Deploy it before loading SRs.** The loader closes some pilot SRs, and a closed SR refuses new work logs. With the script live, each SR is noted when it is created. On 2026-11-11 the reload noted all 7 expected SRs this way, SR810033 included, although it ends up Closed.
   - **How the script reads the service address.**
     - A new SR's address row is still only in memory, so the script reads it through the SR's relationship `SERVICEADDRESS`. That is the relationship `MXAPISR` uses for its `TKSERVICEADDRESS` child. There is no relationship named `TKSERVICEADDRESS` on SR.
     - A saved SR is read through a set the script scopes itself, by ticket and class.
     - If either lookup fails, the script falls back to the text without an error. So test a new version on a canary SR whose flag depends on the address row, such as SR810002 (`ADDR-VALID`).

3. **Check the SRs already loaded.** The launch point only runs on saves from now on. Run [scripts/flag_missing_info.py](../scripts/flag_missing_info.py) once. It reads the 65 pilot SRs through the REST API, applies the same rules, and adds the missing notes. Without `--apply` it only previews. A second run adds nothing, because gaps already noted are skipped.
   - The SR's `worklog` child in `MXAPISR` lists only client-viewable notes, and `MISSINFO` notes are internal. Read them through `MXAPIWORKLOG` instead.
   - Calling the script itself through `/maximo/api/script/SRQMISSINFO` returns BMXAA4216E "Unknown Object" on TechZone, so the backfill runs from outside.

4. **The reviewer's list.** A Work Queue lists the results of a saved query, so the query comes first.
   1. In **Service Requests**, open **Advanced Search > Where Clause**, paste this clause and run it. It should list the open flagged SRs: on TechZone SR810001, SR810002, SR810005, SR810012 and SR810020. SR810008 is also flagged, but it is Resolved, and SR810033 is Closed.

      ```sql
      siteid='SRQSITE'
      and status in (select value from synonymdomain where domainid='SRSTATUS' and maxvalue in ('NEW','QUEUED','PENDING','INPROG'))
      and exists (select 1 from worklog w where w.recordkey=ticketid and w.class='SR' and w.siteid='SRQSITE' and w.logtype='MISSINFO')
      ```

      - `ticketid` is unqualified on purpose: the application queries the `SR` view, so a `ticket.` prefix may not resolve. Inside the subquery it still means the SR's ticket, because `WORKLOG` has no `TICKETID` column.
   2. **Save Query** as `SRQMISSINFO`, with description "Missing information", and tick **Public**.
      - The API cannot create saved queries: `MXAPIQUERY` refuses ADD (BMXAA0024E).
   3. In **Work Queue Manager**, create a queue named `SRQ MISSING INFO`:
      - application **Service Requests** (`SR`), object structure `MXAPISR`
      - query `SRQMISSINFO`, unique column `TICKETUID`
      - columns `TICKETID`, `DESCRIPTION`, `STATUS` and `REPORTDATE`
      - the reviewers' security group
   4. **Activate** the queue. New queues start inactive.

   - The public query on its own is the fallback if a Work Queue cannot be used.
   - When the resident answers, the reviewer updates the SR and closes the gap by adding a CLIENTNOTE. The MISSINFO note stays as the record of what was asked.

5. **Check it:** open SR810020 in Service Requests. Its **Log** tab should show two `MISSINFO` entries, `ADDR` and `LS-ID`.

Observed on TechZone (2026-11-09, before the reload):
- The `MISSINFO` log type, the script and its launch point are in place. The backfill added 6 notes to 5 SRs, exactly the local test's result: SR800001, SR800005 and SR800008 (`ADDR`), SR800012 (`ADDR-VALID`) and SR800020 (`ADDR` and `LS-ID`). A second run added none.
- The launch point works on new and updated SRs. Tested with five test SRs, which were then closed:
  - A new lift station alarm with only "North Port, FL" got `ADDR` and `LS-ID`.
  - A new SR with a full address got nothing.
  - An existing SR with no house number got `ADDR` when it was updated. Saving it again added nothing.
- The first version deployed did nothing, for two reasons:
  - It never ran. It imported `re`, which fails in Maximo, yet SR saves still succeeded. It started running only after the script record was saved again through the API.
    - The status had been set to Active through the API, which may not have reloaded Maximo's script cache. This is not proven.
    - If a script seems to do nothing, save its record again.
  - SR's `WORKLOG` relationship returns every SR's work logs (2,333 rows), not just this SR's. The duplicate check found the backfill's notes and skipped every gap.
  - The script now uses a relationship scoped to the SR (`recordkey=:ticketid and class=:class and siteid=:siteid`).
- While those were being fixed, a version with `import re` blocked SR saves for about two minutes (15:44 to 15:46 UTC), until its launch point was switched off.

### AI check with watsonx.ai

[scripts/ai_missing_info.py](../scripts/ai_missing_info.py) runs outside Maximo. It reads the open pilot SRs through the REST API and handles each one in three steps:
1. **The rules above** find the gaps the record shows.
2. **An address lookup** in the County address file runs for an address the file does not have. It finds the resident's own house number on a similarly spelled street, as with SR810002's "Glenn" for Glen, or it says which house numbers the street has, as with SR810033. It never proposes a house number the resident did not give.
3. **One watsonx.ai chat call** checks the rules that need the text read: one problem per request, and the rule for the request type. It also drafts one question to the resident covering every gap.

Guardrails:
- **What is sent.** The resident's name, phone and email line is removed before the text is sent.
- **What the reply must show.** A gap must quote its evidence word for word from the request, or it is dropped.
- **Only gaps that block dispatch count.** The model marks each gap as blocking or not, and gaps that only lack a second detail are set aside.
- **No invented values.** A question with a number that is not in the request or the address lookup is reported, and never written.
- **Nothing changes without `--apply`.** Without it, the script writes only `evaluation/ai-missing-info-<model>.csv` and prints the score. With `--apply`, each open SR with a gap gets one internal `MISSINFO` work log, "AI check: missing information", holding the gaps, the evidence and the question. A reviewer decides what to send.
- **Credentials.** The script uses AI Service's own watsonx.ai connection (Step 0). The URL, project ID and key go in `WATSONX_URL`, `WATSONX_PROJECT_ID` and `WATSONX_API_KEY` in `.env`.

```bash
uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py   # preview
uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py --model ibm/granite-4-h-small
```

Observed on TechZone (2026-11-12, all 65 pilot SRs, scored against the answer key):

| Prompt version | `openai/gpt-oss-120b`: gaps found | Complete SRs flagged | `ibm/granite-4-h-small`: gaps found | Complete SRs flagged |
|---|---|---|---|---|
| The rules alone | 8 of 18 | 0 of 48 | 8 of 18 | 0 of 48 |
| Flag a rule the request clearly fails | 18 of 18 | 22 of 48 | 13 of 18 | 40 of 48 |
| Plus: do not flag a missing second detail | 18 of 18 | 23 of 48 | 13 of 18 | 20 of 48 |
| Grade each gap as blocking dispatch or not (kept) | **18 of 18** | **12 of 48** | 17 of 18 | 27 of 48 |

- **Use `openai/gpt-oss-120b`.** It finds every gap, including all 10 the rules cannot see. No drafted question had an invented number in any run, and in the kept version every street named in a question comes from the request or the address file. It used about 940 tokens per SR, or 61,000 for the 65.
- **Granite is not reliable enough.** It flags far more complete SRs, and its results swing between prompt versions.
- **The 12 complete SRs gpt-oss flags:**
  - 3 are fair to raise on reading. SR810004 reports low pressure and brown water. SR810029 describes a leak under a kitchen sink, which is the owner's side. SR810018, clear water bubbling up near the meter, is filed as a sewer issue.
  - 8 ask for the second half of a two-part rule, such as a meter lock (`NOWATER-SCOPE`, three SRs), the exact source of an odor (`ODOR-SOURCE`, two SRs), or how much water is flowing (`MAIN-WHERE`). Whether those halves are required is the County's call. If they are not, shorter rule wording in `required-information.csv` would remove these flags.
  - 1 is a plain misreading: SR810051 says the meter spins with every fixture off, which names the problem.
- On SRs that do have a gap, it adds a second gap to two: SR810005 (the odor's source) and SR810027 (which meter problem).
- The model only reads the description text, so it misses nothing the service address shows. The rules and the address lookup cover that.
- The prompt was changed twice, both times with general wording and never for a particular SR. The third version is the one in the script.

### AI test: can the 9.2 Assistant judge the gaps that need reading?

Ask the Maximo Assistant (the AI icon in Service Requests) about three SRs whose gaps the script cannot see. Compare its answer with the answer key:

| SR | Ask | The answer key says is missing |
|---|---|---|
| SR810048 | "Read service request SR810048. What information is missing for a crew to act on it, and what should we ask the resident?" | What the meter problem is: high bill, leak, damage or reading |
| SR810027 | Same question for SR810027 | It reports two problems (high pressure and meter accuracy); they need separate requests |
| SR810021 | Same question for SR810021 | The symptom (backup, overflow or odor) and whether it is inside or outside the house |

- If it names the gap in at least two of the three, the 9.2 route (an agent that calls this script and explains the rest) is worth building.
- If it only restates the request, the reviewer judges these gaps until IBM says how to call the `almwatsonx` template.
- On TechZone the agent route is blocked for now: the Assistant can call no tools (Step 0). The watsonx.ai check above covers these gaps without it.

Observed on TechZone: _pending_

The research is in `plans/reports/research-synthesis-261106-1307-maximo-ai-duplicates-and-missing-info.md`.

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
- They are numbered WO2915001 onward, so the pilot WO filters (`externalrefid like 'WO291%'`) already include them.
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
| The similar SR dialog is empty | The SR is not open, so it is not in `SRSIMILARITYINFFILTER`. Or AIINFJOB has not run since activation. Or the AI configuration is not named `SRSIMILARITY`, which the `AISIMSRPAIR` relationship expects. |
| A duplicate is missing from the dialog | It is not among the 10 closest stored for that SR (`max_similarity_records`), or its report date is outside `history_days`. If you added a `dupscore` cut to `AISIMSRPAIR`, it may score below it. |
| The Duplicate score column is empty | The `SRQDUPSCORE` escalation has not run yet (every 5 minutes), is not active, or admin mode is still on. Check the `ESCSRQDUPSCORE` instance under `ESCALATION` in **Cron Task Setup** and its **History** tab. |
| The escalation runs but leaves the deduction columns empty | The condition was not saved, or escalation point 1 has **Repeat?** clear, so rows already processed once are skipped. Deactivate the escalation, set the condition from step 6, tick **Repeat?**, save and activate. A condition naming a column that does not exist yet fails with BMXAA3056E: add the columns first. |
| A duplicate score looks too low for a real duplicate | One SR has no coordinates in its service address or its text (factor 0.75), the reports are more than 150 m apart, or they came more than 3 days apart. The factors are at the top of `srqdupscore.py`. |
| A similarity score looks wrong, or the list is not sorted by score | The dialog still uses IBM's `SR`-to-`SR` relationship, which reads the score by the listed SR only. Use `AISIMSRPAIR` and `AISIMSRTICKET` from step 1 and the dialog in step 7. |
| The similar SR dialog lists 10 reports every time | Expected: it stores the 10 closest per SR and lists them all. Read the duplicate score; 85 or more is a likely duplicate. |
| BMXAA3840E, the electronic signature is not valid, with the right password | The signature wants your Manage e-signature key, not your sign-in password. Set it from the profile menu (**Set or Modify E-signature**). Each failure counts as a failed login. |
| Admin mode logs "BMXAA0259E - The e-mail cannot be sent" | No mail server. Admin mode still turns on after the countdown; check with **Manage Admin Mode**. Everyone is signed out when it does. |
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
