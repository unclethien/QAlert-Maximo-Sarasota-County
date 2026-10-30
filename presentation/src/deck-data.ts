// Every number and example in the deck is derived here from the generated
// dataset in ../data, so the slides stay correct after the data is regenerated.
import srCsv from '../../data/maximo/sr.csv?raw'
import woCsv from '../../data/maximo/wo.csv?raw'
import worklogCsv from '../../data/maximo/worklog.csv?raw'
import personCsv from '../../data/maximo/person.csv?raw'
import answerKeyCsv from '../../data/answer-key.csv?raw'
import addressPointsCsv from '../../data/reference/address-points.csv?raw'
import qalertRequests from '../../data/qalert/requests.json'
import qalertActivity from '../../data/qalert/activity.json'
import qalertEmployees from '../../data/qalert/employees.json'
import { parseCsv, type Row } from './parse-csv'

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
const staffList = qalertEmployees as Employee[]

function indexBy<T>(rows: T[], key: (row: T) => string): Map<string, T> {
  return new Map(rows.map((row) => [key(row), row]))
}

const srById = indexBy(srRows, (r) => r.TICKETID)
const woById = indexBy(woRows, (r) => r.WONUM)
const answerById = indexBy(answerRows, (r) => r.TICKETID)
const staffById = indexBy(staffList, (e) => e.id)

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
  WSCH: 'Scheduled',
  APPR: 'Approved',
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
  workLogs: parseCsv(worklogCsv).length,
  people: personRows.length,
  qalertRequests: (qalertRequests as unknown[]).length,
  qalertHistory: (qalertActivity as unknown[]).length,
  qalertStaff: staffList.length,
  staffWithoutMaximoRecord: staffList.filter((e) => !mappedPersonIds.has(e.id)).length,
  inactiveStaff: staffList.filter((e) => !e.active).length,
  addressPoints: parseCsv(addressPointsCsv).length,
  answerKeyRows: answerRows.length,
}

/* ---------- Use cases ---------- */

const USE_CASES = [
  { key: 'Missing-Information Detection', label: 'Missing information', note: 'No address, too little detail, wrong type' },
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
  'County responsibility review': 'Likely private plumbing',
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

/* ---------- Worked example: one request ---------- */

function buildRequestExample(ticketId: string) {
  const sr = need(srById, ticketId)
  const answer = need(answerById, ticketId)
  const lines = descriptionLines(sr.DESCRIPTION_LONGDESCRIPTION)
  const enteredByLine = lines.find((l) => l.startsWith('Entered by:')) ?? ''
  const enteredById = enteredByLine.replace('Entered by:', '').trim()
  const staff = need(staffById, enteredById)
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
    enteredByLine,
    enteredById,
    staff: { ...staff, name: `${staff.firstName} ${staff.lastName}` },
    gap: answer.ISSUE_SUMMARY,
    question: answer.SUGGESTED_CLARIFICATION_QUESTION,
  }
}

export const requestExample = buildRequestExample('SR800001')

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

/* ---------- Answer key ---------- */

const firstControl = answerRows.find((r) => r.USE_CASE === USE_CASES[3].key)

export const answerSamples = ['SR800001', 'SR800054', 'SR800036', 'SR800004', firstControl?.TICKETID ?? '']
  .filter(Boolean)
  .map((id) => {
    const r = need(answerById, id)
    return {
      id,
      alert: r.EXPECTED_ALERT,
      contact: r.ENTERED_BY_NAME,
      related: relatedIds(r).join(', '),
    }
  })
