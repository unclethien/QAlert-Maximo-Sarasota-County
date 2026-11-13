# Missing-information check for service requests

This guide sets up the check that finds service requests (SRs) a crew cannot act on yet, because information is missing. It also lists everything the setup creates, so it can be rebuilt on another instance or removed. It runs on the TechZone Maximo instance (MAS 9.2.6, Manage 9.2.3) and the OpenShift cluster that hosts it.

| Part | What it does | Where it runs | Source |
|---|---|---|---|
| Rule check | Flags the gaps a record shows when an SR is saved: no house number, an address outside the county or not in the County address file, a lift station alarm with no station named | Inside Maximo, as the automation script `SRQMISSINFO` | [scripts/autoscript/srqmissinfo.py](../scripts/autoscript/srqmissinfo.py) |
| AI check | Reads each new open SR for the gaps that need the text understood, such as two problems in one request, and drafts one question to the resident | A CronJob every 15 minutes on the OpenShift cluster, calling watsonx.ai | [scripts/ai_missing_info.py](../scripts/ai_missing_info.py), [deploy/missinfo-job/](../deploy/missinfo-job/) |
| Notes on the SR | One internal work log entry per gap, plus one AI summary entry | The SR's **Log** tab | Written by both checks |
| Missing Information tab | Counts the open SRs by type of gap, and lists the SRs behind each count. A row opens the SR | A Start Center tab for every user | [scripts/setup_missinfo_start_center.py](../scripts/setup_missinfo_start_center.py) |

No Maximo version has a built-in AI check for missing details, so this is built from Maximo's own pieces and one external job. The checks only add internal notes: nothing is sent to the resident, no field changes, and a reviewer decides what to ask.

Status: **running on TechZone** since 2026-11-12. The repository changes for the scheduled job and the Start Center are on the branch `feat/missinfo-start-center` until it is merged.

## How it works

1. A request arrives from QAlert and is saved in Maximo as an SR.
2. On the save, the rule check adds a `MISSINFO` work log entry for each gap it can see in the record. It never blocks the save.
3. Every 15 minutes, the cluster job reads the open SRs that have no AI check yet, up to 25 a run. For each one it:
   1. applies the same rules;
   2. looks up an address the County address file does not have, to suggest the likely match;
   3. sends the request text, without the resident's contact line, to watsonx.ai, which lists the gaps that need reading and drafts one question;
   4. keeps a gap only if the model quotes words from the request that show it, and holds back a question with an invented number;
   5. writes one `MISSINFO` entry per new gap and one summary entry, "AI check: missing information".
4. The Missing Information tab counts the `MISSINFO` entries on open SRs. A reviewer opens an SR from a list, reads its **Log** tab, and contacts the resident if needed.

The resident's name, phone and email stay on the SR, in its contact fields and its long description; the reviewer uses them to call back. Only the copy of the text sent to watsonx.ai leaves out the contact line.

## Before you start

1. **The pilot data is loaded**, as in [maximo-import-guide.md](maximo-import-guide.md). The rule check should be live before SRs are loaded; see Step 1.
2. **A Maximo administrator** that can open **Domains**, **Automation Scripts**, **Work Queue Manager** and **Security Groups**.
3. **watsonx.ai access.** The check uses AI Service's own watsonx.ai connection; see [Step 0 in mas-ai-configuration.md](mas-ai-configuration.md#step-0-check-what-the-instance-offers).
4. **The settings in `.env`** (never committed):

   | Setting | Used for |
   |---|---|
   | `MAXIMO_URL`, `MAXIMO_API_KEY`, `MAXIMO_API_PATH`, `MAXIMO_VERIFY_TLS` | The Maximo REST API, as in [maximo-import-guide.md](maximo-import-guide.md) |
   | `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_API_KEY` | The watsonx.ai chat call |

5. **Cluster access**, for Step 3: `kubectl`, or `oc`, logged in to the OpenShift cluster with a user that can create a namespace. In the OpenShift console, use your name's menu, **Copy login command**, and run the `oc login --token=... --server=...` it shows. A kubeconfig holding the same token also works.
6. **Tools:** `uv` for the Python scripts, run from the repository root.

## What the setup creates

Everything below can be rebuilt from this guide and removed with "Pause, roll back or remove" at the end.

**In Maximo:**

| Object | Name | Created by | Step |
|---|---|---|---|
| Log type (synonym domain `LOGTYPE`) | `MISSINFO`, internal value `UPDATE` | Hand, in **Domains** | 1 |
| Automation script and launch point | `SRQMISSINFO`, on SR, Before Save, Add and Update | Hand, in **Automation Scripts** | 1 |
| Public saved query and Work Queue | `SRQMISSINFO` and `SRQ MISSING INFO` | Hand, in Service Requests and **Work Queue Manager** | 1 |
| Internal work log entries on SRs | `MISSINFO` "Missing information: <rule>", and `UPDATE` "AI check: missing information" | The rule check, `flag_missing_info.py` and the AI check | 1 to 3 |
| Automation script, no launch point | `SRQMKQUERY` | `setup_missinfo_start_center.py` | 4 |
| Public saved queries in Service Requests | `SRQMI-ALL`, `SRQMI-ADDR`, `SRQMI-ADDRVALID`, `SRQMI-LSID`, `SRQMI-ONEISSUE`, `SRQMI-DETAIL` | `setup_missinfo_start_center.py`, through `SRQMKQUERY` | 4 |
| Public real-time KPIs | The six above plus `SRQMI-WAITING` | `setup_missinfo_start_center.py` | 4 |
| Start Center template | "Missing Information" (template 43 on TechZone) | `setup_missinfo_start_center.py` | 4 |
| Security group setting | `EVERYONE`: **Start Center Template** = "Missing Information" | Hand, in **Security Groups** | 4 |

**On the OpenShift cluster**, all in the namespace `srq-missinfo`:

| Object | Name | Created by |
|---|---|---|
| Namespace, ImageStream, BuildConfig, CronJob | `srq-missinfo`, `missinfo-check` | [deploy/missinfo-job/openshift.yaml](../deploy/missinfo-job/openshift.yaml) |
| Secret with the Maximo and watsonx.ai settings | `srq-missinfo` | [deploy/missinfo-job/create_secret.py](../deploy/missinfo-job/create_secret.py) |

**In this repository:**

| File | What it is |
|---|---|
| [scripts/autoscript/srqmissinfo.py](../scripts/autoscript/srqmissinfo.py) | The rule check, pasted into Maximo |
| [scripts/flag_missing_info.py](../scripts/flag_missing_info.py) | Adds the rule check's notes to SRs loaded before it was live |
| [scripts/ai_missing_info.py](../scripts/ai_missing_info.py) | The AI check. `--new` reads every open SR not checked yet, `--limit` caps a run, `--apply` writes the notes |
| [tests/test_ai_missing_info.py](../tests/test_ai_missing_info.py) | Its tests, run with the rest of the suite |
| [deploy/missinfo-job/](../deploy/missinfo-job/) | The image (`Dockerfile`), the cluster objects (`openshift.yaml`) and the secret helper (`create_secret.py`) |
| [scripts/setup_missinfo_start_center.py](../scripts/setup_missinfo_start_center.py) | Creates the KPIs, the saved queries and the Start Center template |
| [scripts/autoscript/srqmkquery.py](../scripts/autoscript/srqmkquery.py) | The `SRQMKQUERY` script that creates the saved queries |

## Step 1: The rule check on save

The pilot splits the check by what it takes to decide a gap:
- **Rules that plain text can decide:** an automation script, [scripts/autoscript/srqmissinfo.py](../scripts/autoscript/srqmissinfo.py), runs when an SR is saved. It never blocks the save, so a report from QAlert is never lost. Each gap becomes a work log entry of type `MISSINFO` on the SR, and a Work Queue lists the open SRs that have one.
- **Rules that need the request to be read and understood:** for example, what the meter problem is, or two problems in one request. A script outside Maximo asks watsonx.ai, and the reviewer decides. See Step 2.

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

## Step 2: The AI check with watsonx.ai

[scripts/ai_missing_info.py](../scripts/ai_missing_info.py) runs outside Maximo: by hand for the scored pilot run, and every 15 minutes on the cluster for new SRs (see Step 3). It reads SRs through the REST API and handles each one in three steps:
1. **The rules above** find the gaps the record shows.
2. **An address lookup** in the County address file runs for an address the file does not have. It finds the resident's own house number on a similarly spelled street, as with SR810002's "Glenn" for Glen, or it says which house numbers the street has, as with SR810033. It never proposes a house number the resident did not give.
3. **One watsonx.ai chat call** checks the rules that need the text read: one problem per request, and the rule for the request type. It also drafts one question to the resident covering every gap.

Guardrails:
- **What is sent.** The long description's contact line (the resident's name, phone and email) and its "Entered by" line are left out of the text sent to watsonx.ai. The SR itself keeps them, so the reviewer can still call the resident back.
- **What the reply must show.** A gap must quote its evidence word for word from the request, or it is dropped.
- **Only gaps that block dispatch count.** The model marks each gap as blocking or not, and gaps that only lack a second detail are set aside.
- **No invented values.** A question with a number that is not in the request or the address lookup is reported, and never written.
- **Nothing changes without `--apply`.** Without it, the script writes only `evaluation/ai-missing-info-<model>.csv` and prints the score. With `--apply`, each open SR checked without an error gets internal work logs. Nothing is client-viewable, no field changes and nothing is sent; a reviewer decides what to send.
  - One `MISSINFO` entry per gap, "Missing information: <rule>", the same entry the `SRQMISSINFO` launch point writes. A gap the launch point already noted is not written twice. The model's entries begin "Suggested by watsonx.ai".
  - One `UPDATE` entry, "AI check: missing information", with the gaps, their evidence, the address hint and the question, or "No missing information found". It is not a `MISSINFO` entry, so the Work Queue and the Start Center count only gaps. It also marks the SR as checked.
  - A question with an invented number is withheld; the gaps are still noted.
- **Credentials.** The script uses AI Service's own watsonx.ai connection ([Step 0 in mas-ai-configuration.md](mas-ai-configuration.md#step-0-check-what-the-instance-offers)). The URL, project ID and key go in `WATSONX_URL`, `WATSONX_PROJECT_ID` and `WATSONX_API_KEY` in `.env`.

```bash
uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py   # preview
uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py --model ibm/granite-4-h-small
uv run -q --no-project --with-requirements requirements.txt python scripts/ai_missing_info.py --new --apply --limit 25   # what the scheduled job runs
```

With `--new`, the script reads every open SR at `SRQSITE`, not only the pilot ones, and skips an SR that already has the "AI check: missing information" entry. `--limit` caps how many SRs one run sends to watsonx.ai. An SR whose model call fails gets no entry, so the next run tries it again.

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

## Step 3: The scheduled job

Every 15 minutes a cluster job runs the watsonx.ai check on the open SRs not checked yet and writes its notes. A "Missing Information" Start Center then shows every user how many open SRs lack each type of information.

[deploy/missinfo-job/](../deploy/missinfo-job/) holds a Dockerfile and [openshift.yaml](../deploy/missinfo-job/openshift.yaml). The YAML creates the `srq-missinfo` namespace, an image build from this repository's `main` branch, and a CronJob that runs `scripts/ai_missing_info.py --new --apply --limit 25` every 15 minutes, never two at a time.
1. Log in to the cluster (`oc login`, or a kubeconfig with the same token).
2. `kubectl apply -f deploy/missinfo-job/openshift.yaml`. The build starts by itself.
3. Create the secret from `.env`. Only the Maximo and watsonx.ai settings are copied, and no value is printed:
   ```bash
   uv run -q --no-project --with-requirements requirements.txt python deploy/missinfo-job/create_secret.py
   ```
4. Run it once by hand and read the log: `kubectl -n srq-missinfo create job first --from=cronjob/missinfo-check`, then `kubectl -n srq-missinfo logs job/first`.

- After a change to the script, rebuild by creating a build from `main`. With `oc`, run `oc -n srq-missinfo start-build missinfo-check`. Without `oc`, post a `BuildRequest` to the BuildConfig's `instantiate` endpoint.
- `oc start-build --from-dir` builds from local files instead. The raw `instantiatebinary` endpoint takes a plain tar archive. On macOS, create it with `COPYFILE_DISABLE=1 tar --no-xattrs --format ustar`; a gzipped archive from macOS `tar` failed with "unable to extract binary build input".
- To pause the job, run `kubectl -n srq-missinfo patch cronjob missinfo-check -p '{"spec":{"suspend":true}}'`. To remove it, run `kubectl delete namespace srq-missinfo`. The notes already written stay on the SRs.

## Step 4: The Start Center

[scripts/setup_missinfo_start_center.py](../scripts/setup_missinfo_start_center.py) sets it up through the REST API. It previews by default, `--apply` creates or updates, and `--remove` undoes.
- **Seven public KPIs** (`MXAPIKPIMAIN`), each counting open SRs at `SRQSITE`:

  | KPI | Counts open SRs with |
  |---|---|
  | `SRQMI-ALL` | any `MISSINFO` entry |
  | `SRQMI-ADDR` | no house number (`ADDR`) |
  | `SRQMI-ADDRVALID` | an address not in the County file, or outside the county (`ADDR-VALID`) |
  | `SRQMI-LSID` | a lift station not named (`LS-ID`) |
  | `SRQMI-ONEISSUE` | more than one problem in one request (`ONE-ISSUE`) |
  | `SRQMI-DETAIL` | the problem not described well enough (the request type's rule) |
  | `SRQMI-WAITING` | no AI check yet |

  The target is 0, with caution at 1 and alert at 5. A row in the KPI List cannot open the SRs behind it; the lists below do that.
- **Six public saved queries in Service Requests**, named like the KPIs (`SRQMI-ADDR`, `SRQMI-ADDRVALID`, `SRQMI-LSID`, `SRQMI-ONEISSUE`, `SRQMI-DETAIL`, `SRQMI-ALL`), with the same conditions.
  - The REST API cannot create saved queries: `MXAPIQUERY` and `MXAPIUSERQUERY` refuse ADD (BMXAA0024E), and so does `MXAPIINTOBJECT` for a new object structure. A script called directly can. The setup deploys [scripts/autoscript/srqmkquery.py](../scripts/autoscript/srqmkquery.py) as the automation script `SRQMKQUERY`, with no launch point, and calls it through `/maximo/api/script/SRQMKQUERY`. The queries are owned by the API key's user (`MAXADMIN` on TechZone).
  - In Service Requests they also appear under **Saved Queries**, for example "Missing information: No house number".
- **A Start Center template**, "Missing Information" (`MXAPISTARTCNTR`), in two columns. The left one holds the KPI List, then the lists for more than one problem and for the problem not described well enough. The right one holds the lists for an address not in the County file, no house number, and a lift station not named. Each list is a Result Set portlet on its saved query, and a row opens the SR; its **Log** tab shows the gaps and the question for the resident.
- **Give the template to the `EVERYONE` security group, in the UI.** `MXAPIGROUP` accepts a change to `sctemplateid` without an error but does not save it, so the script reads it back and tells you when to do this by hand:
  1. Open **Security Groups** and the group `EVERYONE`.
  2. On the **Group** tab, set **Start Center Template** to "Missing Information" (template 43 on TechZone) and save. `EVERYONE` had no template before.
  3. Sign out and back in. The Start Center (the home icon) gets a "Missing Information" tab next to the user's other Start Centers.

  A group has one template, so the script refuses to replace another template there. A user who is not a member of `EVERYONE` does not get the tab; add the template to one of that user's groups instead.
- **When the counts refresh.** The KPIs are real-time, so Maximo calculates them when the Start Center shows them. It also calculates a KPI once, when it is created.
  - The value stored on the KPI is not recalculated when it is saved again through the API, even with a changed where clause. So `MXAPIKPIMAIN` can return an old count.
  - A `KPICronTask` instance does not help. The built-in instance's description says it runs "KPI that are not real time". A 5-minute instance added for these KPIs changed nothing in 13 minutes, so it was removed.

Notes:
- A user who is already signed in sees the new tab after signing in again.
- An SR leaves the counts when it is resolved, closed or cancelled. A gap the resident has answered still counts while the SR stays open, as in the Work Queue.

Observed on TechZone (2026-11-12):
- **The job.** The first run, started by hand, checked 25 of the 46 open SRs at `SRQSITE`, and the first scheduled run checked the other 21. Each run took about 2 minutes and used about 950 tokens per SR. There were no model errors, no failed writes and no invented numbers.
  - The 46 include SR 1181, an open SR that is not part of the pilot. It was flagged for `ODOR-SOURCE`.
  - Of the open pilot SRs in the answer key, the two runs found all 12 expected gaps and flagged 6 of the 34 complete ones.
  - A backup of the 114 existing `MISSINFO` and `UPDATE` work logs on SRs was taken before the first run. All the job's entries came after it.
- **The Start Center.** The setup created the seven KPIs and template 43. Its write of template 43 to `EVERYONE` reported success, but reading the group back showed no template; that is why the group step is now done in the UI. At creation, before the job ran, the KPIs read 5 SRs in all: 3 with no house number, 2 with an address not in the County file, 1 with no lift station name, and 46 waiting for the AI check.
- **After both runs,** with template 43 set on `EVERYONE` in Security Groups, the tab showed exactly the counts the work logs give, recalculated when it opened ("Last Run" was the time the page opened): 18 open SRs missing information, 3 with no house number, 2 with an address not in the County file, 1 with no lift station name, 3 with more than one problem, 13 with the problem not described well enough, and 0 waiting.

## Optional: can the 9.2 Assistant judge the gaps that need reading?

Ask the Maximo Assistant (the AI icon in Service Requests) about three SRs whose gaps the script cannot see. Compare its answer with the answer key:

| SR | Ask | The answer key says is missing |
|---|---|---|
| SR810048 | "Read service request SR810048. What information is missing for a crew to act on it, and what should we ask the resident?" | What the meter problem is: high bill, leak, damage or reading |
| SR810027 | Same question for SR810027 | It reports two problems (high pressure and meter accuracy); they need separate requests |
| SR810021 | Same question for SR810021 | The symptom (backup, overflow or odor) and whether it is inside or outside the house |

- If it names the gap in at least two of the three, the 9.2 route (an agent that calls this script and explains the rest) is worth building.
- If it only restates the request, the reviewer judges these gaps until IBM says how to call the `almwatsonx` template.
- On TechZone the agent route is blocked for now: the Assistant can call no tools ([Step 0 in mas-ai-configuration.md](mas-ai-configuration.md#step-0-check-what-the-instance-offers)). The watsonx.ai check above covers these gaps without it.

Observed on TechZone: _pending_

The research is in `plans/reports/research-synthesis-261106-1307-maximo-ai-duplicates-and-missing-info.md`.

## Check that it works

1. In Service Requests, create a test SR for a lift station alarm with only "North Port, FL" as the address, and save it. Its **Log** tab shows two `MISSINFO` entries, `ADDR` and `LS-ID`, at once. This is the rule check.
2. Wait for the next quarter hour, or start the job by hand: `kubectl -n srq-missinfo create job check-now --from=cronjob/missinfo-check`. Its log (`kubectl -n srq-missinfo logs job/check-now`) names the SRs it checked. The test SR now also has an "AI check: missing information" entry.
3. Open the Start Center's Missing Information tab. "Open SRs waiting for the AI check" is 0, and the test SR is in the "No house number" and "Lift station not named" lists.
4. Close the test SR, so it leaves the counts.

## Running on TechZone (2026-11-13)

- **The job.** It runs every 15 minutes. With every open SR already checked, a run finds nothing new and ends in about 5 seconds.
- **The image** is build 2, made from local files of the branch `feat/missinfo-start-center`, because the branch is not merged yet. Build 1 failed on a gzipped macOS archive (see Step 3).
- **The BuildConfig** points at `main`, but has no `ConfigChange` trigger, so applying it did not build from `main` before the code was there. After the branch is merged:
  1. run `kubectl apply -f deploy/missinfo-job/openshift.yaml`, which adds the trigger;
  2. start a build from `main` (`oc -n srq-missinfo start-build missinfo-check`), so the image matches the repository.
- **The Start Center** is template 43, set on `EVERYONE` in Security Groups.

## Pause, roll back or remove

Each part can be undone on its own. The notes already written stay on the SRs in every case, because they are the record of what was asked.

| To | Do this |
|---|---|
| Pause the AI check | `kubectl -n srq-missinfo patch cronjob missinfo-check -p '{"spec":{"suspend":true}}'`. Set `suspend` back to `false` to resume |
| Remove the AI check | `kubectl delete namespace srq-missinfo`. This removes the job, its image and its secret |
| Remove the Start Center, its KPIs and saved queries, and `SRQMKQUERY` | `uv run -q --no-project --with-requirements requirements.txt python scripts/setup_missinfo_start_center.py --remove`. Then clear **Start Center Template** on `EVERYONE` in Security Groups, because the API cannot |
| Stop the rule check | In **Automation Scripts**, make the `SRQMISSINFO` launch point inactive |
| Remove the reviewer list | Delete the `SRQ MISSING INFO` Work Queue, then the `SRQMISSINFO` saved query |

Before a run that writes notes to many SRs, back up the existing work logs: read the `MISSINFO` and `UPDATE` entries on SRs through `MXAPIWORKLOG` and save them to a file. On TechZone, the 114 entries that existed before the first job run were backed up this way. Every entry the job wrote came after them.

## Known limits

- **The county check is a list of place names, not a map.** `ADDR-VALID` flags a city on the list in `srqmissinfo.py` (Bradenton, Palmetto, Ellenton, Parrish, Myakka City, Port Charlotte, Punta Gorda, Arcadia, Charlotte County, Manatee County). A place outside the county that is not on the list is not flagged.
- **A valid address can be flagged.** An address with a house number and a street but no County address code is flagged `ADDR-VALID`, even when it is correct but was typed in without the code.
- **The drafted question can ask for more than the gaps found.** On SR810012 it also asked whether the water meter has a lock, which was not flagged.
- **Two-part rules flag complete SRs.** 6 of the 34 complete open pilot SRs were flagged, mostly for the second half of a rule, such as a meter lock or the exact source of an odor. Whether those halves are required is the County's call.
- **No SR without contact details is flagged.** SR810020, a web request with no phone or email, gets a question for the resident that nobody can be asked.
- **Notes are written as `MAXADMIN`**, the API key's user, and the rule check's notes as the user who saved the SR.
- **A gap stays counted while the SR is open,** even after the resident has answered.
- **The job checks every open SR at `SRQSITE`,** not only the pilot ones. SR 1181, which is not part of the pilot, was checked and flagged.

## Proposed next steps (not built)

These came out of a review of the reviewer's experience on 2026-11-12. None of them is built.

1. **One self-contained note per gap, in plain words.** The title says the problem, and the rule code becomes a tag. The body says the problem, the words in the request that show it, the next step, and the question for the resident. Both checks would write the same format. For SR810012:

   > **Address outside Sarasota County: Bradenton [ADDR-VALID]**
   > - Problem: the address is in Bradenton, which is outside Sarasota County.
   > - Found in the request: "4410 Riverbluff Ln, Bradenton"
   > - Next step: confirm the address with the resident. If Bradenton is correct, this is probably not a County utility customer: refer them and close the SR. If the city was typed wrong, correct it and save.
   > - Ask the resident: "We have 4410 Riverbluff Ln in Bradenton, which is outside Sarasota County. Can you confirm the address?"
   > - Source: rule check on save

   - The question would be built from the gaps kept, one fixed question per rule, instead of being drafted by the model. That removes questions about gaps that were not flagged.
   - The KPIs, the saved queries and the "already noted" check match the title "Missing information: <rule>" exactly. They would have to match on the `[RULE]` tag instead, and still find the old titles.
2. **A "no way to contact the resident" check (`NO-CONTACT`).** It flags an SR whose Affected Phone and Affected Email are both empty. It reads the fields directly, so no contact details go to watsonx.ai. On such an SR, the other notes say the resident cannot be reached instead of offering a question. The reviewer's next step, as decided on 2026-11-12 and not yet confirmed by the County:
   1. investigate from what is in the request;
   2. if that is not enough, find help resources;
   3. if it still cannot be resolved, close the SR as "not enough information".
3. **Later:**
   - mark a gap resolved when a save shows it fixed, and let the reviewer mark "not a gap";
   - check the county against a County GIS boundary or address service instead of the list of names.

Questions for the County:
1. What does a reviewer do with an address outside the county: refer, close or transfer?
2. Are the second halves of the two-part rules required?
3. Is a one-line review note field on the SR's main tab wanted?
4. Should notes already written be rewritten in a new format?
5. Can the check call a County GIS boundary or address service?

## Troubleshooting

| What you see | What to do |
|---|---|
| Every SR save fails after a change to `SRQMISSINFO` | The script imports something, which Maximo's Jython cannot do. Make the launch point inactive first, then fix the script (Step 1). |
| A change to `SRQMISSINFO` seems to do nothing | Save the script record again, through the UI or by merging its `source` through `MXAPIAUTOSCRIPT`. |
| The Missing Information tab does not appear | `EVERYONE` has no Start Center template (the API cannot set it; use Security Groups), the user is not in `EVERYONE`, or the user has not signed out and back in. |
| A count read through the API is old | Expected. The KPIs are real-time, so Maximo recalculates them only when a Start Center shows them. Open the tab. |
| Clicking a row in the counts opens nothing | Expected. A KPI List row cannot open records. Use the lists on the same tab. |
| A list on the tab is empty or reports a missing query | The saved query is gone or has another owner. Run `setup_missinfo_start_center.py --apply` again. |
| BMXAA0024E when creating a saved query through the API | `MXAPIQUERY`, `MXAPIUSERQUERY` and `MXAPIINTOBJECT` refuse ADD. The setup creates the queries through the `SRQMKQUERY` script instead. |
| "Open SRs waiting for the AI check" stays above 0 | The job is suspended, the run limit (25) has not caught up yet, or the model call failed for those SRs. Read the latest job log; a failed SR is tried again on the next run. |
| The job log shows a 401 or 403 from Maximo or watsonx.ai | A key changed. Update `.env`, run `create_secret.py` again, and start the job by hand to check. |
| A build fails with "unable to extract binary build input" | The archive was gzipped by macOS `tar`. Send a plain one: `COPYFILE_DISABLE=1 tar --no-xattrs --format ustar`. |
| An SR is never checked | It is resolved, closed or cancelled, or it is not at `SRQSITE`. The job reads only open SRs. |

## Sources

- The research behind this design: `plans/reports/research-synthesis-261106-1307-maximo-ai-duplicates-and-missing-info.md`.
- Maximo Secrets, MAS 9.2 Work Queue Manager: https://maximosecrets.com/2026/08/10/mas-9-2-work-queue-manager/
- The IBM sources for AI Service and the Maximo Assistant are listed in [mas-ai-configuration.md](mas-ai-configuration.md#sources).
