// Every number and example in the deck is derived here from the generated
// dataset in ../data, so the slides stay correct after the data is regenerated.
import srCsv from '../../data/maximo/sr.csv?raw'
import woCsv from '../../data/maximo/wo.csv?raw'
import worklogCsv from '../../data/maximo/worklog.csv?raw'
import personCsv from '../../data/maximo/person.csv?raw'
import answerKeyCsv from '../../data/answer-key.csv?raw'
import addressPointsCsv from '../../data/reference/address-points.csv?raw'
import requiredInfoCsv from '../../data/reference/required-information.csv?raw'
import qalertRequests from '../../data/qalert/requests.json'
import qalertActivity from '../../data/qalert/activity.json'
import qalertEmployees from '../../data/qalert/employees.json'
import { parseCsv, type Row } from './parse-csv'

interface QalertRequest {
  id: number
  origin: string
}

interface Employee {
  id: string
  username: string
  firstName: string
  lastName: string
  email: string
  phone: string
  department: string
  active: boolean
}

const srRows = parseCsv(srCsv)
const woRows = parseCsv(woCsv)
const personRows = parseCsv(personCsv)
const answerRows = parseCsv(answerKeyCsv)
const worklogRows = parseCsv(worklogCsv)
const staffList = qalertEmployees as Employee[]

function indexBy<T>(rows: T[], key: (row: T) => string): Map<string, T> {
  return new Map(rows.map((row) => [key(row), row]))
}

const srById = indexBy(srRows, (r) => r.TICKETID)
const woById = indexBy(woRows, (r) => r.WONUM)
const answerById = indexBy(answerRows, (r) => r.TICKETID)
const staffById = indexBy(staffList, (e) => e.id)
const requestById = indexBy(qalertRequests as QalertRequest[], (r) => String(r.id))

function need<T>(map: Map<string, T>, id: string): T {
  const value = map.get(id)
  if (!value) throw new Error(`Record ${id} is missing from data/. Regenerate the dataset or update the deck examples.`)
  return value
}

const TZ = 'America/New_York'
const timeFmt = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: TZ })
const dateFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: TZ })
const shortDateFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: TZ })

export const formatTime = (iso: string) => timeFmt.format(new Date(iso))
export const formatDate = (iso: string) => dateFmt.format(new Date(iso))
export const formatShortDate = (iso: string) => shortDateFmt.format(new Date(iso))

// "No Water, 3912 Bramblewick Ln" -> type and address
function splitSummary(description: string) {
  const cut = description.indexOf(', ')
  return cut < 0
    ? { type: description, address: '' }
    : { type: description.slice(0, cut), address: description.slice(cut + 2) }
}

// "1382 Larkspur Bay Dr:  SERVICE LINE LEAK" -> "Service line leak".
// Titles that are already in mixed case, such as project names, are kept as written.
function workOrderTitle(description: string) {
  const text = (description.split(':').pop() ?? description).trim()
  if (text !== text.toUpperCase()) return text
  const lower = text.toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']

// Small counts read better as words on a slide: 3 -> "three".
export function countWord(n: number): string {
  return NUMBER_WORDS[n] ?? String(n)
}

// The long description is a run of <div> lines; drop the map link and tags.
function descriptionLines(html: string): string[] {
  return html
    .replace(/<a\b[^>]*>.*?<\/a>/g, '')
    .split(/<\/div>\s*<div>/)
    .map((part) => part.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim())
    // Non-breaking hyphens keep phone numbers on one line.
    .map((line) => line.replace(/\b(\d{3})-(\d{3})-(\d{4})\b/g, '$1\u2011$2\u2011$3'))
    .filter(Boolean)
}

const WO_STATUS: Record<string, string> = {
  SCHED: 'Scheduled',
  WCONT: 'Waiting for a contract',
  INPRG: 'In progress',
  COMP: 'Completed',
  CLOSE: 'Closed',
}

/* ---------- Totals ---------- */

const mappedPersonIds = new Set(personRows.map((p) => p.PERSONID))

export const totals = {
  serviceRequests: srRows.length,
  workOrders: woRows.length,
  followUpWorkOrders: woRows.filter((w) => w.ORIGRECORDCLASS === 'SR').length,
  pastWorkOrders: woRows.filter((w) => !w.ORIGRECORDID && w.WORKTYPE !== 'CP').length,
  plannedWorkOrders: woRows.filter((w) => w.WORKTYPE === 'CP').length,
  workLogs: worklogRows.length,
  people: personRows.length,
  qalertRequests: (qalertRequests as unknown[]).length,
  qalertHistory: (qalertActivity as unknown[]).length,
  qalertStaff: staffList.length,
  staffWithoutMaximoRecord: staffList.filter((e) => !mappedPersonIds.has(e.id)).length,
  inactiveStaff: staffList.filter((e) => !e.active).length,
  addressPoints: parseCsv(addressPointsCsv).length,
  answerKeyRows: answerRows.length,
}

/* ---------- Channels ---------- */

// How requests reach QAlert. Residents submit app and web requests; Contact Center staff
// enter phone calls and emails.
const CHANNELS = [
  { key: '311Connect mobile app', label: '311Connect app', note: 'The resident submits it', staff: false },
  { key: '311 web portal', label: '311 web portal', note: 'The resident submits it', staff: false },
  { key: 'phone call to 311', label: 'Phone call to 311', note: 'Contact Center staff enter it', staff: true },
  { key: 'email to the Contact Center', label: 'Email', note: 'Contact Center staff enter it', staff: true },
] as const

export const channelGroups = CHANNELS.map((c) => ({
  ...c,
  count: answerRows.filter((r) => r.SUBMITTED_VIA === c.key).length,
}))

export const residentSubmitted = channelGroups.filter((c) => !c.staff).reduce((sum, c) => sum + c.count, 0)
export const staffEntered = channelGroups.filter((c) => c.staff).reduce((sum, c) => sum + c.count, 0)

/* ---------- Use cases ---------- */

const USE_CASES = [
  { key: 'Missing-Information Detection', label: 'Missing information', note: 'No address, too little detail, wrong type, not ours' },
  { key: 'Duplicate Identification', label: 'Duplicates', note: 'Several calls about one problem' },
  { key: 'Historical / Planned Work Context', label: 'Past or planned work', note: 'Earlier repairs or a project nearby' },
  { key: 'Control (no issue)', label: 'Nothing to flag', note: 'Complete requests, as a baseline' },
] as const

export const useCaseGroups = USE_CASES.map((u) => ({
  ...u,
  count: answerRows.filter((r) => r.USE_CASE === u.key).length,
}))

/* ---------- Missing information ---------- */

const PATTERN_LABELS: Record<string, string> = {
  'Missing location': 'No usable address',
  'Invalid location': 'Address that does not exist',
  'Insufficient problem detail': 'Too little detail',
  'Unclear request': 'Unclear what is wrong',
  'Incorrect classification': 'Wrong request type',
  'Multiple issues in one request': 'Two problems in one request',
  'County responsibility review': 'May not be the County’s job',
}

const missingRows = answerRows.filter((r) => r.USE_CASE === USE_CASES[0].key)

export const missingPatterns = Object.entries(PATTERN_LABELS)
  .map(([scenario, label]) => {
    const rows = missingRows.filter((r) => r.SCENARIO === scenario)
    return { label, count: rows.length, example: rows[0]?.ISSUE_SUMMARY ?? '' }
  })
  .sort((a, b) => b.count - a.count)

const relatedIds = (row: Row) => row.RELATED_RECORDS.split(';').filter(Boolean)

export const missingTotal = missingRows.length
export const missingWithCrewSent = missingRows.filter((r) => relatedIds(r).some((id) => id.startsWith('WO'))).length

/* ---------- Worked examples: one resident request, one staff-entered request ---------- */

function buildRequestExample(ticketId: string) {
  const sr = need(srById, ticketId)
  const answer = need(answerById, ticketId)
  const lines = descriptionLines(sr.DESCRIPTION_LONGDESCRIPTION)
  const enteredByLine = lines.find((l) => l.startsWith('Entered by:')) ?? ''
  const staff = staffById.get(answer.ENTERED_BY_EMPLOYEE_ID)
  return {
    id: sr.TICKETID,
    qalertId: sr.EXTERNALSYSTEM_TICKETID,
    summary: sr.DESCRIPTION,
    status: sr.STATUS,
    reportedOn: formatDate(sr.REPORTDATE),
    reportedName: sr.REPORTEDNAME,
    reportedBy: sr.REPORTEDBY,
    reportedPhone: sr.REPORTEDPHONE,
    detailLines: lines.filter((l) => l !== enteredByLine),
    customerLine: lines.find((l) => l.startsWith('Customer:')) ?? '',
    enteredByLine,
    origin: need(requestById, sr.EXTERNALSYSTEM_TICKETID).origin,
    via: answer.SUBMITTED_VIA,
    staff: staff && { ...staff, name: `${staff.firstName} ${staff.lastName}`, inMaximo: mappedPersonIds.has(staff.id) },
    contact: {
      type: answer.FOLLOW_UP_CONTACT_TYPE,
      name: answer.FOLLOW_UP_CONTACT_NAME,
      phone: answer.FOLLOW_UP_CONTACT_PHONE,
      email: answer.FOLLOW_UP_CONTACT_EMAIL,
    },
    gap: answer.ISSUE_SUMMARY,
    question: answer.SUGGESTED_CLARIFICATION_QUESTION,
  }
}

const firstMissing = (contactType: string) =>
  missingRows.find((r) => r.FOLLOW_UP_CONTACT_TYPE === contactType)?.TICKETID ?? ''

export const requestExample = buildRequestExample('SR800001')
export const staffExample = buildRequestExample(firstMissing('Entered-by employee'))

/* ---------- Duplicates ---------- */

const DUPLICATE_EXAMPLE_CLUSTER = 'C'
const clusterOf = (scenario: string) => scenario.match(/^Duplicate cluster (\w)/)?.[1]

const duplicateRows = answerRows.filter((r) => clusterOf(r.SCENARIO))

export const duplicateExample = {
  groups: new Set(duplicateRows.map((r) => clusterOf(r.SCENARIO))).size,
  lookAlikes: answerRows.filter((r) => r.SCENARIO.startsWith('Look-alike')).length,
  members: duplicateRows
    .filter((r) => clusterOf(r.SCENARIO) === DUPLICATE_EXAMPLE_CLUSTER)
    .map((r) => {
      const sr = need(srById, r.TICKETID)
      return {
        id: r.TICKETID,
        primary: r.SCENARIO.endsWith('(primary)'),
        reportedAt: sr.REPORTDATE,
        time: formatTime(sr.REPORTDATE),
        date: formatDate(sr.REPORTDATE),
        summary: r.ISSUE_SUMMARY,
        ...splitSummary(sr.DESCRIPTION),
      }
    })
    .sort((a, b) => a.reportedAt.localeCompare(b.reportedAt)),
}

/* ---------- Past and planned work ---------- */

function buildContextExample(ticketId: string) {
  const sr = need(srById, ticketId)
  const answer = need(answerById, ticketId)
  const workOrders = relatedIds(answer)
    .filter((id) => id.startsWith('WO'))
    .map((id) => {
      const wo = need(woById, id)
      return {
        id,
        title: workOrderTitle(wo.DESCRIPTION),
        status: WO_STATUS[wo.STATUS] ?? wo.STATUS,
        reportedOn: formatShortDate(wo.REPORTDATE),
        start: wo.SCHEDSTART ? formatShortDate(wo.SCHEDSTART) : '',
        finish: wo.SCHEDFINISH ? formatShortDate(wo.SCHEDFINISH) : '',
      }
    })
  return {
    id: sr.TICKETID,
    reportedOn: formatShortDate(sr.REPORTDATE),
    summary: answer.ISSUE_SUMMARY,
    ...splitSummary(sr.DESCRIPTION),
    workOrders,
  }
}

export const pastExample = buildContextExample('SR800036')
export const plannedExample = buildContextExample('SR800004')

/* ---------- Teams ---------- */

// Descriptions of the person groups in the dataset (WTRPIPE, SANCLINSP and LSCENT appear in the
// County's sample records; WTRMETER and RECLAIM are illustrative).
const TEAM_LABELS: Record<string, string> = {
  WTRPIPE: 'Water distribution pipe crew',
  SANCLINSP: 'Sanitary collection and inspection crew',
  LSCENT: 'Lift station crew',
  WTRMETER: 'Meter services crew',
  RECLAIM: 'Reclaimed water crew',
}

// Each team's job plans, as provisioned in Maximo (FORCEMAIN has no work order in the dataset yet).
const JOB_PLANS_BY_TEAM: Record<string, string[]> = {
  WTRPIPE: ['LEAK', 'PRESSURE', 'NOWATER'],
  SANCLINSP: ['SAN INSP', 'FORCEMAIN'],
  LSCENT: ['LSALARM'],
  WTRMETER: ['METER'],
  RECLAIM: ['RECLAIM'],
}

const personById = indexBy(personRows, (p) => p.PERSONID)

function buildTeamExample(workOrderId: string) {
  const wo = need(woById, workOrderId)
  const sr = need(srById, wo.ORIGRECORDID)
  const answer = need(answerById, sr.TICKETID)
  return {
    srId: sr.TICKETID,
    ...splitSummary(sr.DESCRIPTION),
    srTeam: sr.OWNERGROUP,
    suggestedTeam: answer.EXPECTED_PERSONGROUP,
    suggestedLabel: TEAM_LABELS[answer.EXPECTED_PERSONGROUP] ?? '',
    woId: wo.WONUM,
    jobPlan: wo.JPNUM,
    team: wo.PERSONGROUP,
    supervisor: need(personById, wo.SUPERVISOR).DISPLAYNAME,
    lead: need(personById, wo.LEAD).DISPLAYNAME,
  }
}

export const teamExample = buildTeamExample('WO2900020')
export const teamTotals = {
  requestsWithoutTeam: srRows.filter((r) => !r.OWNERGROUP).length,
  withSuggestedTeam: answerRows.filter((r) => r.EXPECTED_PERSONGROUP).length,
}

/* ---------- Teams and status values ---------- */

const COUNTY_TEAMS = new Set(['WTRPIPE', 'SANCLINSP', 'LSCENT'])

export const teamList = Object.entries(TEAM_LABELS).map(([code, label]) => {
  const orders = woRows.filter((w) => w.PERSONGROUP === code)
  return {
    code,
    label,
    fromCounty: COUNTY_TEAMS.has(code),
    jobPlans: JOB_PLANS_BY_TEAM[code] ?? [],
    workOrders: orders.length,
    requests: answerRows.filter((r) => r.EXPECTED_PERSONGROUP === code).length,
  }
})

// In lifecycle order. `maximo` is the standard internal status a County value is a synonym of.
const SR_STATUSES = [
  { code: 'NEW', label: 'New' },
  { code: 'QUEUED', label: 'Queued' },
  { code: 'INPRG', label: 'In progress', maximo: 'INPROG' },
  { code: 'PENDING', label: 'Pending' },
  { code: 'RESOLVED', label: 'Resolved' },
  { code: 'CLOSED', label: 'Closed' },
]
const WO_STATUSES = [
  { code: 'WCONT', label: 'Waiting for a contract', maximo: 'WAPPR' },
  { code: 'SCHED', label: 'Scheduled', maximo: 'WSCH' },
  { code: 'INPRG', label: 'In progress' },
  { code: 'COMP', label: 'Completed' },
  { code: 'CLOSE', label: 'Closed' },
  { code: 'CAN', label: 'Canceled' },
]

const withCounts = (statuses: typeof SR_STATUSES, rows: Row[]) =>
  statuses.map((s) => ({ ...s, count: rows.filter((r) => r.STATUS === s.code).length }))

export const statusLists = {
  requests: withCounts(SR_STATUSES, srRows),
  workOrders: withCounts(WO_STATUSES, woRows),
}

/* ---------- Answer key ---------- */

const firstControl = answerRows.find((r) => r.USE_CASE === USE_CASES[3].key)

export const answerSamples = [requestExample.id, staffExample.id, 'SR800054', 'SR800004', firstControl?.TICKETID ?? '']
  .filter(Boolean)
  .map((id) => {
    const r = need(answerById, id)
    return {
      id,
      alert: r.EXPECTED_ALERT,
      contact: r.FOLLOW_UP_CONTACT_NAME,
      contactType: r.FOLLOW_UP_CONTACT_TYPE,
      related: relatedIds(r).join(', '),
    }
  })

/* ---------- What changed after IBM's data review ---------- */

const notCountyRows = answerRows.filter((r) => r.EXPECTED_ALERT === 'Possibly not County responsibility')

export const reviewChanges = {
  notCounty: notCountyRows.length,
  cityUtility: notCountyRows.filter((r) => /refer the customer to City of /.test(r.EXPECTED_RECOMMENDATION)).length,
  reroutedByNote: worklogRows.filter((w) => w.LOGTYPE === 'RESOLUTION').length,
  requiredInfoRules: parseCsv(requiredInfoCsv).length,
  requestsWithGaps: answerRows.filter((r) => r.REQUIRED_INFO_GAP).length,
  sameAddressLookAlikes: answerRows.filter(
    (r) => r.SCENARIO.startsWith('Look-alike') && relatedIds(r).some((id) => id.startsWith('WO')),
  ).length,
}
