# Loading the dataset into Maximo

The `loader/` package puts the sample dataset into a Maximo Manage instance over the REST API: 65 service requests, 41 work orders, their work logs, and the setup records they point to. It writes everything to its own organization `SRQ` and site `SRQSITE`, so it can share an instance with other data.

**Safety rules built into the loader:**

- Every command is a dry run unless you pass `--apply`. A dry run reads from Maximo but never writes.
- It never deletes anything, and there's no code to do so.
- Before it creates a record, it checks whether that record is already there. Running it again creates nothing new.
- It never changes a record it didn't create. When an existing record differs from our data, it reports the difference and leaves the record alone. For example:
  - a work order with one of our numbers but a different external reference is someone else's, so it's left alone;
  - a job plan that's already there is never activated.
- It doesn't follow redirects, so the API key is only ever sent to `MAXIMO_URL`.

## Setup

You need Python 3.11 or later.

```bash
uv venv && uv pip install -r requirements.txt   # or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                           # then fill in .env
```

`.env` is gitignored. It holds:

| Variable | What |
|---|---|
| `MAXIMO_URL` | The Manage base URL, ending in `/maximo`. Use the public Manage route, not the MAS admin route. |
| `MAXIMO_API_KEY` | An API key for a Maximo user who can create organizations, people, person groups, domains, classifications, job plans, service requests and work orders. |
| `MAXIMO_API_PATH` | Optional. Defaults to `api`. |
| `MAXIMO_ITEMSETID` | The item set for the new `SRQ` organization. It must already exist. Either reuse one the inventory lists as in use, or create a new one (for example `SRQSET`, type `ITEM`) in the Sets application first. The company set and currency are copied from an organization that shares the item set, or, for a new item set, from an active USD organization. |
| `MAXIMO_VERIFY_TLS` | Optional. Set to `false` only for an instance with a self-signed certificate. |

The loader never prints the API key or writes it to a file. Its state goes in `loader-state/`, which is also gitignored. `loader-state/manifest.json` records what was loaded and which instance it went to. If `MAXIMO_URL` later points somewhere else, the loader refuses to use that manifest. Move the file aside, and the loader finds its own records again by their natural keys.

## Run order

Run each command with `.venv/bin/python -m loader` (or `uv run --no-project python -m loader`).

| Step | Command | Writes? |
|---|---|---|
| 1. See what the instance holds | `inventory` | No. It saves a report to `loader-state/inventory-<time>.json`. |
| 2. Preview the setup records | `provision` | No |
| 3. Create the setup records | `provision --apply` | Yes |
| 4. Load one chain (the canary) | `load --only SR800008`, then `load --only SR800008 --apply` | Yes, with `--apply` |
| 5. Check the canary | `verify --only SR800008` | No |
| 6. Load everything | `load`, then `load --apply` | Yes, with `--apply` |
| 7. Check everything | `verify` | No |
| 8. Confirm a re-run creates nothing | `load --apply` | Should create 0 records |

The canary, `SR800008`, is a water leak that has an SR work log and a follow-up WO, `WO2900014`, with crew notes.

Options:

- `--only ID,ID`: load or verify only these SRs or WOs. Each SR brings its follow-up WOs and all their work logs.
- `--limit N`: only the first N chains. A chain is an SR with its WOs, or a WO with no SR.
- `provision --only org,site,...`: only some setup steps.

## What `provision` creates

These steps run in order:

1. the organization;
2. the site, as a child of the organization;
3. 18 people;
4. 5 person groups, each with its supervisors and leads as members;
5. the status values our data uses;
6. work types;
7. 13 classifications;
8. 8 job plans, which are then set to `ACTIVE`.

`WCONT` is added as a synonym of `WAPPR`, and `SCHED` as a synonym of `WSCH`. On standard SR statuses, `INPRG` becomes a synonym of `INPROG`. If the instance doesn't have the internal value a status needs, the step fails and asks you to choose a mapping. It doesn't guess.

## Manual steps in the Maximo UI

`provision` prints these steps with a `MANUAL` tag:

- **Give the API user access to the site.** In Security Groups, give the API key user's group access to `SRQSITE`. Until you do, Maximo refuses every SR and WO for that site.
- **Activate the organization.** A new organization stays inactive until someone sets its clearing account. In Organizations, open `SRQ`, set the clearing account, activate it, then run `provision --apply` again.
- **Work log types.** One SR work log uses the County's `LOGTYPE` `RESOLUTION`, from the misrouted samples. Standard Maximo has no such type, so the loader writes it as `UPDATE`. `inventory` lists any work log type the instance lacks.
- **Work types.** Standard Maximo has no REST object structure for work types. Under Organizations > `SRQ` > Work Order Options > Work Type, make sure `CM`, `CS`, `IN` and `CP` exist.
- **Job plans that were already there.** `provision` only activates job plans it created itself. A plan that was already there and isn't `ACTIVE` is listed for you to activate by hand.
- **Teams, status values and work types, when the API is refused.** On the TechZone MAS 9 instance, Maximo refuses REST writes to person groups, domains and work types with `BMXAA0024E` ("The action ADD is not allowed"), even for a `MAXADMIN` user. `provision` then reports them as `FAILED`. Add them in the UI:
  - **Person Groups:** create each team and add its supervisors and leads. `provision --only person_groups` lists them.
  - **Domains:** add `INPRG` (internal `INPROG`) to `SRSTATUS`, and `WCONT` (internal `WAPPR`) and `SCHED` (internal `WSCH`) to `WOSTATUS`, each for organization `SRQ` only.
  - **Organizations > `SRQ` > Work Order Options > Work Type:** add any missing work type.

  Then run `provision --apply` again. It sees them as existing and creates the job plans, which need the teams.
- **Failure codes.** The loader doesn't write the failure hierarchy. `provision` prints the failure classes and problem codes to add in Failure Codes. Until they exist, `load` sends work orders without `FAILURECODE` and `PROBLEMCODE`. Once they exist, pass `--keep-failure-codes` to `load` and `verify`.
- **Service groups and services.** `load` doesn't send `COMMODITYGROUP` and `COMMODITY` by default. Two reasons: they must exist in Maximo first, and the County's codes (`WATER_PIPE`, `WATER_SERV`) are longer than standard Maximo's 8-character `COMMODITY`. Once they're set up, pass `--keep-commodities` to `load` and `verify`.

## What the load does with each column

- **Not sent, because Maximo sets them:**
  - SR `CLASS`, `CREATEDBY` and `CREATIONDATE`;
  - SR `REPORTEDNAME` and `AFFECTEDNAME`: Maximo clears them when `REPORTEDBY` and `AFFECTEDPERSON` are people, and shows those people's names instead;
  - work log `WORKLOGID`;
  - every `STATUSDATE`.
- **Status.** Applied after create with `changeStatus`, through the usual steps. For example, a closed WO goes `INPRG`, then `COMP`, then `CLOSE`. The loader passes the dataset's status date. If Maximo refuses a back-dated status, the loader sets the status without the date and lists it under *Known limitations*.
  - **SR "in progress".** The dataset uses `INPRG` for SRs, but Maximo's `changeStatus` refuses the `SRSTATUS` synonym `INPRG` ("not in the value list") even when the domain lists it. The loader therefore sends Maximo's standard `INPROG`, which is the same internal status. `verify` expects `INPROG`. WOs keep `INPRG`, which is standard on `WOSTATUS`.
  - **Order.** When a follow-up WO starts, Maximo also moves its SR to in progress, and it refuses the WO's change while the SR is still queued. So the loader applies statuses in the order work happens: SRs go to in progress first, then the WOs run, then the SRs are resolved or closed. Maximo resolves some SRs itself when their WO completes.
  - **Closing.** `CLOSED`, `CLOSE` and `CAN` put a record in history, and Maximo then refuses every change, new work logs included. If any of a record's work logs failed to load, the loader stops it one step short, reports the status as `FAILED`, and closes it on the run after the work log loads.
- **Keys.** The loader sends our own `TICKETID` and `WONUM`. Each WO also gets `EXTERNALREFID` set to our WO number. If Maximo renumbers a record, `loader-state/manifest.json` records its number. `loader-state/answer-key-maximo.csv` then repeats the answer key with Maximo's numbers.
- **Team codes.** Standard Maximo team codes (`PERSONGROUP`) hold 8 characters. The County's own code `SANCLINSP` has 9, so the loader writes it as `SANCLINS`. The dataset keeps `SANCLINSP`. `verify` uses the same mapping, and `loader-state/answer-key-maximo.csv` shows `SANCLINS`.
- **Classification.** Maximo numbers classifications itself. The loader finds each classification by name, for example `WATER-LEAK`, and sends Maximo's number.

The run report starts with the full list of columns it didn't send, with the reason for each.

## Known limitations

- A `STATUSDATE` that Maximo stamps with the load time is reported by `verify` as a limitation, not a failure. The history use case reads `REPORTDATE`, `ACTSTART`, `ACTFINISH`, `SCHEDSTART` and the work log `CREATEDATE`, which are set directly.
- If a run stops partway, run it again. The manifest is saved after every record, so the next run picks up where the last one stopped.
  - **Status changes:** before each one, the loader reads the record's live status, so a change whose answer was lost isn't sent twice.
  - **Follow-up WOs:** a follow-up WO is only created once its SR is in Maximo. If the SR failed, the WO waits for the next run.
- Standard Maximo has no `EXTERNALSYSTEM` or `EXTERNALSYSTEM_TICKETID` on tickets. The loader puts the QAlert request ID from `EXTERNALSYSTEM_TICKETID` into the standard `EXTERNALRECID`, and doesn't send `EXTERNALSYSTEM`, which is always `QAlert`. To find a request's QAlert record in Maximo, read the SR's `EXTERNALRECID`.
- The natural keys are `EXTERNALRECID` at site `SRQSITE` for SRs, and `EXTERNALREFID` for WOs. The inventory checks that SRs can be queried by `EXTERNALRECID`. The canary shows whether Maximo keeps the work log `CREATEDATE` we send, which the work log check depends on.
- To remove loaded records, do it by hand in the Maximo UI. The loader can't delete.
- **One work log is missing on the TechZone instance.** Work log `3000126` on `SR800061` is missing there, and `verify` reports it as the one difference. The first full load closed `SR800061` before the loader held back closing a record with a missing work log. At that point the work log had failed on its `RESOLUTION` type. A closed SR is in history, so Maximo now refuses the work log both through the SR and through `mxapiworklog` (`commlog#ownerNull`). A fresh load on another instance loads it.

## Tests

```bash
uv run --no-project python -m pytest -q tests
```

The tests run offline against an in-memory fake Maximo. They cover:

- URL rebasing and error parsing;
- making sure the key never appears in output;
- that the inventory is read only;
- dry runs;
- that a second run creates nothing;
- renumbered keys;
- resuming after a failure;
- the read-back check.
