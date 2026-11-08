# How to import the sample data into Maximo

This guide walks you through loading the Sarasota County sample data into a Maximo Manage instance, step by step. When you finish, Maximo has:

- 65 service requests (SRs);
- 41 work orders (WOs);
- their work logs;
- the people, teams, statuses, classifications and job plans they use.

Everything goes into its own organization, `SRQ`, and site, `SRQSITE`, so it doesn't mix with other data on the instance.

The import script is the `loader/` folder in this repository. For how it maps each column and why, see [maximo-load.md](maximo-load.md).

## Before you start: it's safe to run

- **Nothing is written unless you add `--apply`.** Every command without it is a preview.
- **It never deletes anything.** To remove loaded records, use the Maximo UI.
- **Running it again is safe.** It checks for each record before creating it, and skips any that are already there.
- **It never changes records it didn't create.** If it finds one that differs from our data, it reports the difference and leaves the record alone.

## What you need

- A Maximo Manage instance you can sign in to as an administrator, for example a TechZone MAS 9 instance.
- An **API key** for a Maximo user who can create organizations, people, person groups, domains, classifications, job plans, service requests and work orders.
  - To create one, search for **API Keys** in Maximo's application search.
  - Treat the key like a password: don't paste it into chat, email or a commit.
- **Python 3.11 or later.**
- **[uv](https://docs.astral.sh/uv/)**, which is recommended. Plain `python3 -m venv` works too.
- **git**, to get the code.

## Step 1: Get the code and install

```bash
git clone https://github.com/unclethien/QAlert-Maximo-Sarasota-County.git
cd QAlert-Maximo-Sarasota-County
uv venv && uv pip install -r requirements.txt
```

Without uv, use these instead:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Then type `.venv/bin/python -m loader` wherever this guide says `uv run --no-project python -m loader`.

## Step 2: Tell the script which Maximo to use

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill it in:

| Setting | What to put |
|---|---|
| `MAXIMO_URL` | The Manage address, ending in `/maximo`. For example: `https://main.manage.<your-instance>.techzone.ibm.com/maximo`. Use the Manage address, not the MAS admin address. |
| `MAXIMO_API_KEY` | Your API key. |
| `MAXIMO_ITEMSETID` | The item set for the new `SRQ` organization. If you don't know which one to use yet, leave it blank: step 3 lists the item sets already in use. |
| `MAXIMO_VERIFY_TLS` | Leave this as `true`. Set it to `false` only if the instance has a self-signed certificate. |

`.env` is never committed, and the script never prints the key.

## Step 3: Check what the instance already has

```bash
uv run --no-project python -m loader inventory
```

This only reads from Maximo. It prints a report and saves a copy to `loader-state/inventory-<time>.json`. Check three things in it:

- **The connection works.** If it doesn't, check `MAXIMO_URL` and the API key.
- **Which item sets are in use.** Either put one of them in `MAXIMO_ITEMSETID`, or create a new one, such as `SRQSET` of type `ITEM`, in the **Sets** application and use that.
- **Anything listed as missing.** Step 4 creates most of it.

## Step 4: Create the setup records

First preview, then create:

```bash
uv run --no-project python -m loader provision            # preview only
uv run --no-project python -m loader provision --apply    # creates them
```

This creates, in order:

1. the `SRQ` organization and `SRQSITE` site;
2. 18 people;
3. 5 teams (person groups);
4. the status values the data uses;
5. work types;
6. 13 classifications;
7. 8 job plans.

Each line of output starts with a tag:

- **`CREATED`**: made in this run.
- **`EXISTS`**: already there.
- **`MANUAL`**: you need to do this in the Maximo UI.
- **`FAILED`**: Maximo refused it. Read the message.

### Finish the setup in the Maximo UI

Some instances, including TechZone, refuse some of these writes even for an administrator. `provision` lists each one under **Manual steps**. Do the ones it lists, then run `provision --apply` again, until it reports `failed 0`.

- **Give the API user access to the site.** In **Security Groups**, open the API user's group and give it access to site `SRQSITE`. Until you do, Maximo refuses every SR and WO.
- **Activate the organization.** In **Organizations**, open `SRQ`, set its clearing account, and make it active.
  - A new organization stays inactive until it has a clearing account.
  - An inactive organization doesn't appear in the list until you clear the **Active** filter.
- **Teams.** In **Person Groups**, create each team and add its people in this order. The people come from step 4's people step. Each team lists its supervisors first, then its leads.

  | Team | Members, in order |
  |---|---|
  | `WTRPIPE` | 0830144 (Raymond Castillo), 0831460 (Owen Price), 0831027 (Marcus Bell), 0832236 (Tanya Greer) |
  | `WTRMETER` | 0830144 (Raymond Castillo), 0833015 (Sandra Ortiz), 0832236 (Tanya Greer) |
  | `SANCLINS` | 0830581 (Denise Holloway), 0831893 (Felix Romero), 0832671 (Victor Lindqvist) |
  | `LSCENT` | 0830581 (Denise Holloway), 0831893 (Felix Romero), 0832671 (Victor Lindqvist) |
  | `RECLAIM` | 0830144 (Raymond Castillo), 0831027 (Marcus Bell), 0832236 (Tanya Greer) |

  - Maximo asks for a **Sequence** for each member. Number them 1, 2, 3 in the order shown.
  - Make the first person the group default.
  - The County's own code for `SANCLINS` is `SANCLINSP`. Maximo team codes hold only 8 characters, so the loader uses `SANCLINS`.
- **Status values.** In **Domains**, add these values, each for organization `SRQ` only:

  | Domain | Value | Internal value |
  |---|---|---|
  | `SRSTATUS` | `INPRG` | `INPROG` |
  | `WOSTATUS` | `WCONT` | `WAPPR` |
  | `WOSTATUS` | `SCHED` | `WSCH` |
- **Work types.** In **Organizations**, open `SRQ` and go to **Work Order Options > Work Type**. Make sure `CM`, `CS`, `IN` and `CP` exist.
- **Job plans.** Work orders need job plans that are **Active**, and the API user may not be allowed to activate them.
  1. In **Job Plans**, filter Organization = `SRQ`.
  2. Turn on **Select Records** and select all 8 plans.
  3. Choose **More Actions > Change Status > Active**.
- **Failure codes** are optional. `provision` prints the hierarchy to add in **Failure Codes**. Until they exist, the load leaves failure codes off the work orders.

## Step 5: Load one record first

Try one chain before loading everything. SR800008 is a water leak, with a follow-up work order and crew notes.

```bash
uv run --no-project python -m loader load --only SR800008            # preview
uv run --no-project python -m loader load --only SR800008 --apply    # load it
uv run --no-project python -m loader verify --only SR800008          # check it
```

`verify` should print `OK` for SR800008 and for WO2900014. If it doesn't, fix the problem before step 6. The *Troubleshooting* section below covers the errors we've seen.

## Step 6: Load everything

```bash
uv run --no-project python -m loader load            # preview
uv run --no-project python -m loader load --apply    # load it
```

The run ends with a summary:

```
Done:
  sr       created 64, planned 0, existing 1, failed 0
  wo       created 41, planned 0, existing 0, failed 0
  worklog  created 124, planned 0, existing 3, failed 0
  status   created ..., planned 0, existing 0, failed 0
```

Your numbers may differ. The `existing` count is whatever loaded before, such as the record from step 5. What matters is `failed 0`.

You'll also see a long list under **Known limitations hit**: "historical date refused … Maximo used the load time". This is expected, not an error. Maximo won't back-date a status change, so each record's status date is the time of the load. The report dates, actual start and finish dates, and work log dates all keep their historical values.

If the run stops partway, for example on a timeout, just run `load --apply` again. It picks up where it stopped.

## Step 7: Check the result

```bash
uv run --no-project python -m loader verify
uv run --no-project python -m loader load --apply    # should create 0
```

- `verify` reads every record back and compares it with the data. It should end with `match 106, differ 0, not loaded 0`.
- It also lists status dates under *Known limitation*. That is the limitation from step 6, not a failure.
- The second `load --apply` should report `created 0` on every line. That shows a re-run is safe.

## Step 7b: Load the training history (for MAS AI)

MAS AI learns classification and team from past records. These are in a separate set of 390 closed or resolved SRs and 330 closed WOs: see [sample-dataset.md](sample-dataset.md#training-history-for-mas-ai). Load them the same way, with `--dataset history`:

```bash
uv run --no-project python -m loader load --dataset history --limit 3            # preview
uv run --no-project python -m loader load --dataset history --limit 3 --apply    # load a few
uv run --no-project python -m loader load --dataset history --apply              # load the rest
uv run --no-project python -m loader verify --dataset history
```

- This is about 6,000 calls, 3,600 of them writes, so expect it to take a while. If it stops partway, run the same command again; it resumes.
- History records are SR600001 to SR600390 and WO2700001 to WO2700330.
- No answer key is written for the history, because only the pilot is scored.

## Step 7c: Load the draft work orders (for MAS AI)

Team recommendations and similar work orders show on a work order. Most pilot SRs are still waiting for review and have none, so `data/maximo/drafts/` holds 35 draft work orders, one for each open pilot SR that names a team. Duplicate reports get none, because they join their cluster's work order. Load the drafts **after the pilot**, because each one links to a pilot SR:

```bash
uv run --no-project python -m loader load --dataset drafts --limit 3            # preview
uv run --no-project python -m loader load --dataset drafts --apply              # load all 35
uv run --no-project python -m loader verify --dataset drafts
```

- The drafts are WO2950001 to WO2950035. They stay in status WAPPR, with no team, job plan or crew.
- If a draft's SR is not loaded yet, the loader reports "is not loaded yet; re-run after it is" and creates nothing for it.
- See [mas-ai-configuration.md](mas-ai-configuration.md#draft-work-orders).

## Step 8: Find the data in Maximo

- **Service requests:** open **Service Requests** and filter Site = `SRQSITE`. You'll see SR800001 to SR800065.
  - The QAlert request number is in the **External Record ID** field.
  - Follow-up work orders are on the **Related Records** tab.
- **Work orders:** open **Work Order Tracking** and filter Site = `SRQSITE`. You'll see WO2900001 to WO2900041.
  - Crew notes are on the **Work Log** tab.

Maximo may give a record a different number from ours. If it does, `loader-state/answer-key-maximo.csv` lists the answer key with Maximo's numbers.

## Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `BMXAA0024E` "The action ADD is not allowed" on person groups, domains or work types | The instance refuses REST writes to that application. | Add them in the UI (step 4), then run `provision --apply` again. |
| `BMXAA7385E` "The person … is not a member of the … Person Group" on a work order | The work order's lead is not on its team. Teams set up before the training history was added may lack a lead it uses. | Run `provision --only person_groups`. It lists any missing member as a manual step. Add them in **Person Groups**, then run the same `load` again. |
| `BMXAA0029E` "You are not authorized" when activating job plans | The API user can't change job plan status. | Activate them in **Job Plans** (step 4). |
| Every SR or WO fails, mentioning the site | The API user's group has no access to `SRQSITE`. | Give the group access to the site in **Security Groups**. |
| `SRQ` doesn't appear in **Organizations** | It's inactive, and the list shows only active organizations. | Clear the **Active** filter. Then set the clearing account and activate it. |
| "historical date refused", `BMXAA4295E` or `BMXAA4673E` | Maximo won't back-date a status change. | Nothing. The status is set with the load time instead. |
| `BMXAA4190E` "… is not in the value list" | A status value or work log type is missing from its domain. | Run `inventory`, add what it lists as missing in **Domains**, then run `load --apply` again. |
| `BMXAA4301E` "Ticket … is in history" | The record is closed, and Maximo doesn't allow changes to closed records. | Nothing can be added to it now. The loader avoids this by not closing a record until all its work logs have loaded. |
| `ReadTimeout` or a gateway error | The instance was slow to answer. | Run the same command again. |

## Command reference

| Command | Writes? | What it does |
|---|---|---|
| `inventory` | No | Reports what the instance holds. |
| `provision` | With `--apply` | Creates the setup records. `--only org,site,persons,person_groups,statuses,work_types,classifications,job_plans,failure_codes` runs only some steps. |
| `load` | With `--apply` | Loads the SRs, WOs and work logs, then sets their statuses. |
| `verify` | No | Compares what's in Maximo with the data. |

Options for `load` and `verify`:

- `--dataset history`: the AI training history instead of the 65 pilot SRs (the default is `pilot`).
- `--dataset drafts`: the 35 draft work orders for open pilot SRs. Load them after the pilot.
- `--only SR800008,WO2900001`: only these records. Each brings its linked records.
- `--limit 5`: only the first 5 chains.
- `--keep-failure-codes`: send failure codes, once they exist in Maximo.
- `--keep-commodities`: send service groups, once they exist in Maximo with codes of 8 characters or fewer.

Add `--help` to any command to see its options.
