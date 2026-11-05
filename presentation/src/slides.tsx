import type { ReactElement } from 'react'
import {
  answerSamples,
  channelGroups,
  countWord,
  duplicateExample,
  missingPatterns,
  missingTotal,
  missingWithCrewSent,
  pastExample,
  plannedExample,
  requestExample,
  residentSubmitted,
  reviewChanges,
  staffEntered,
  staffExample,
  statusLists,
  teamExample,
  teamList,
  teamTotals,
  totals,
  useCaseGroups,
} from './deck-data'

const REPO_URL = 'https://github.com/unclethien/QAlert-Maximo-Sarasota-County'

// Utility locate-marking colors (APWA): blue for drinking water, green for sewer, purple for reclaimed.
function discipline(requestType: string): 'water' | 'sewer' | 'reclaimed' | 'other' {
  if (/reclaimed/i.test(requestType)) return 'reclaimed'
  if (/sewer|lift station/i.test(requestType)) return 'sewer'
  if (/water|meter|curb stop/i.test(requestType)) return 'water'
  return 'other'
}

function TypeTag({ type }: { type: string }) {
  return <span className={`type-tag type-${discipline(type)}`}>{type}</span>
}

// One bar split into labeled groups, with a legend underneath. Used for channels and use cases.
function StackedBar({ groups }: { groups: readonly { key: string; label: string; note: string; count: number }[] }) {
  const total = groups.reduce((sum, g) => sum + g.count, 0)
  return (
    <>
      <div className="stack-bar" role="img" aria-label={groups.map((g) => `${g.label}: ${g.count}`).join(', ')}>
        {groups.map((g, i) => (
          <div key={g.key} className={`stack-seg seg-${i}`} style={{ flexGrow: g.count / total }}>
            <span className="stack-count">{g.count}</span>
          </div>
        ))}
      </div>
      <div className="stack-legend">
        {groups.map((g, i) => (
          <div key={g.key} className="legend-item" style={{ flexGrow: Math.max(g.count / total, 0.18) }}>
            <span className={`legend-swatch seg-${i}`} />
            <span className="legend-label">{g.label}</span>
            <span className="legend-note">{g.note}</span>
          </div>
        ))}
      </div>
    </>
  )
}

/* 1 */
function TitleSlide() {
  return (
    <div className="layout-title">
      <div className="title-copy">
        <h1 className="display-xl">A practice dataset for the Sarasota AI pilot</h1>
        <p className="lede">
          Sprint 2 sample data to test how MAS AI spots missing information, duplicates, and related past or planned
          work.
        </p>
        <p className="byline">Thien Nguyen, IBM · Sprint 2 review</p>
      </div>
      <div className="title-stub" aria-hidden="true">
        <span className="stub-id">{requestExample.id}</span>
        <span className="stub-summary">{requestExample.summary}</span>
        <mark className="flag-mark">Came in through the {requestExample.via}</mark>
      </div>
    </div>
  )
}

/* 2 */
function TodaySlide() {
  const r = requestExample
  return (
    <div className="layout-split">
      <div>
        <h2 className="display-lg">Today, Maximo can’t tell who to ask</h2>
        <figure className="record bracketed">
          <figcaption className="record-head">
            <span>Service request {r.id}</span>
            <span className="record-status">{r.status}</span>
          </figcaption>
          <dl className="record-fields">
            <dt>Summary</dt>
            <dd>{r.summary}</dd>
            <dt>Reported by</dt>
            <dd>
              {r.reportedName} <span className="muted">({r.reportedBy})</span>
            </dd>
            <dt>Phone</dt>
            <dd className="muted">{r.reportedPhone || 'Blank'}</dd>
            <dt>Details</dt>
            <dd>
              {r.detailLines.map((line) => (
                <span key={line} className="detail-line">
                  {line}
                </span>
              ))}
            </dd>
          </dl>
        </figure>
      </div>
      <ul className="callouts">
        <li>
          <strong>Reported by</strong> is always the integration account, never the resident or the staff member who
          entered it.
        </li>
        <li>Nothing says whether it came from the app, the web portal, or a 311 call.</li>
        <li>To follow up, staff have to find the same request again in QAlert.</li>
      </ul>
    </div>
  )
}

/* 3 */
function ChannelsSlide() {
  return (
    <div className="layout-band channels">
      <h2 className="display-lg">Most requests come from residents</h2>
      <p className="lede narrow">
        Sarasota’s 311 has four ways in. In the dataset, {residentSubmitted} of {totals.serviceRequests} requests come
        from residents and {staffEntered} from the Contact Center. The mix is our assumption.
      </p>
      <StackedBar groups={channelGroups} />
    </div>
  )
}

/* 4 */
function UseCasesSlide() {
  return (
    <div className="layout-band">
      <h2 className="display-lg">
        {totals.serviceRequests} requests, four kinds of test
      </h2>
      <p className="lede narrow">Each request was written to test one thing the AI should notice, or to have nothing to notice.</p>
      <StackedBar groups={useCaseGroups} />
    </div>
  )
}

/* 5 */
function DatasetSlide() {
  const maximo = [
    [totals.serviceRequests, 'service requests'],
    [totals.workOrders, 'work orders'],
    [totals.workLogs, 'work log notes'],
    [totals.people, 'person records'],
  ] as const
  const qalert = [
    [totals.qalertRequests, 'requests, one behind each Maximo request'],
    [totals.qalertHistory, 'history entries'],
    [totals.qalertStaff, 'Contact Center staff who enter phone and email requests'],
  ] as const
  const extras = [
    [totals.addressPoints, 'address points, a stand-in for the County address list'],
    [totals.answerKeyRows, 'answer key rows, what the AI should say for each request'],
  ] as const

  const Ledger = ({ title, rows }: { title: string; rows: readonly (readonly [number, string])[] }) => (
    <div className="ledger">
      <h3 className="ledger-title">{title}</h3>
      {rows.map(([n, label]) => (
        <div key={label} className="ledger-row">
          <span className="ledger-num">{n}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  )

  return (
    <div className="layout-ledgers">
      <h2 className="display-lg">Two systems, linked like the real ones</h2>
      <div className="ledgers">
        <Ledger title="Maximo" rows={maximo} />
        <Ledger title="QAlert (mock)" rows={qalert} />
        <Ledger title="Also included" rows={extras} />
      </div>
      <p className="footnote">
        Everything is made up: people, phone numbers (941-555-01XX), emails (example.com), and street names. Cities and
        ZIP codes are real so addresses look local.
      </p>
    </div>
  )
}

/* 6 */
function BridgeArrow() {
  return (
    <svg className="bridge-link" viewBox="0 0 160 40" aria-hidden="true">
      <line x1="0" y1="20" x2="148" y2="20" />
      <polyline points="138 10 150 20 138 30" />
    </svg>
  )
}

function BridgeSlide() {
  const resident = requestExample
  const staffed = staffExample
  const staff = staffed.staff
  return (
    <div className="layout-bridge">
      <h2 className="display-lg">Where it came from decides who to ask</h2>
      <div className="bridge-rows">
        <div className="bridge">
          <figure className="record bracketed">
            <figcaption className="record-head">
              <span>{resident.id} in Maximo</span>
              <span className="record-status">QAlert origin: {resident.origin}</span>
            </figcaption>
            <div className="record-body">
              <mark className="flag-mark bridge-source">{resident.customerLine}</mark>
              <span className="muted">No “Entered by” line: the resident used the {resident.via}.</span>
            </div>
          </figure>
          <BridgeArrow />
          <figure className="contact-card">
            <figcaption className="contact-source">Ask the resident</figcaption>
            <p className="contact-name">{resident.contact.name}</p>
            {resident.contact.phone && <p className="tabular">{resident.contact.phone}</p>}
            {resident.contact.email && <p>{resident.contact.email}</p>}
          </figure>
        </div>
        {staff && (
          <div className="bridge">
            <figure className="record bracketed">
              <figcaption className="record-head">
                <span>{staffed.id} in Maximo</span>
                <span className="record-status">QAlert origin: {staffed.origin}</span>
              </figcaption>
              <div className="record-body">
                <mark className="flag-mark bridge-source">{staffed.enteredByLine}</mark>
                <span className="muted">Added for staff-entered requests: this one was a {staffed.via}.</span>
              </div>
            </figure>
            <BridgeArrow />
            <figure className="contact-card">
              <figcaption className="contact-source">Ask the staff member who took the call</figcaption>
              <p className="contact-name">{staff.name}</p>
              <p className="tabular">
                {staff.department} · {staff.phone}
              </p>
              {!staff.inMaximo && <p className="muted">From QAlert: no Maximo person record</p>}
            </figure>
          </div>
        )}
      </div>
      <p className="lede">
        Also included: {totals.staffWithoutMaximoRecord} staff not in Maximo, {totals.inactiveStaff} no longer active, and
        one anonymous web request.
      </p>
    </div>
  )
}

/* 7 */
function MissingSlide() {
  const max = Math.max(...missingPatterns.map((p) => p.count))
  return (
    <div className="layout-bars">
      <div>
        <h2 className="display-lg">{missingTotal} requests are missing something or may not be ours</h2>
        <p className="aside-stat">
          <span className="aside-num">{missingWithCrewSent}</span> of these already had a crew sent out. Asking first
          could have saved the trip.
        </p>
      </div>
      <ol className="bars" aria-label="Missing information patterns">
        {missingPatterns.map((p) => (
          <li key={p.label} className="bar-row">
            <span className="bar-label">{p.label}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ transform: `scaleX(${p.count / max})` }} />
            </span>
            <span className="bar-count">{p.count}</span>
            <span className="bar-example">{p.example}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

/* 8 */
function StepsSlide() {
  const r = requestExample
  const steps = [
    { verb: 'Spot the gap', body: r.gap },
    { verb: 'Check the source', body: `QAlert says the ${r.via}, so the resident can be asked directly.` },
    { verb: 'Ask one question', body: `“${r.question}”` },
    { verb: 'Then dispatch', body: 'Send a crew once the address is confirmed.' },
  ]
  return (
    <div className="layout-steps">
      <h2 className="display-lg">What the AI should do with {r.id}</h2>
      <ol className="steps">
        {steps.map((s, i) => (
          <li key={s.verb} className={i === 0 ? 'step step-flag' : 'step'}>
            <span className="step-num">{i + 1}</span>
            <h3 className="step-verb">{s.verb}</h3>
            <p>{s.body}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}

/* 9 */
function DuplicatesSlide() {
  const { members, groups, lookAlikes } = duplicateExample
  const times = members.map((m) => new Date(m.reportedAt).getTime())
  const hour = 3_600_000
  const start = Math.floor(Math.min(...times) / hour) * hour
  const end = Math.ceil(Math.max(...times) / hour) * hour
  const ticks = Array.from({ length: (end - start) / hour + 1 }, (_, i) => start + i * hour)
  const pos = (t: number) => `${((t - start) / (end - start)) * 100}%`
  const primary = members.find((m) => m.primary)
  const others = members.filter((m) => !m.primary).map((m) => m.id)

  return (
    <div className="layout-timeline">
      <h2 className="display-lg">
        <span className="capitalize">{countWord(members.length)}</span> reports, one outage
      </h2>
      <p className="lede narrow">{members[0]?.date}</p>
      <div className="timeline">
        <div className="timeline-axis" />
        {ticks.map((t) => (
          <span key={t} className="timeline-tick" style={{ left: pos(t) }}>
            {new Intl.DateTimeFormat('en-US', { hour: 'numeric', timeZone: 'America/New_York' }).format(t)}
          </span>
        ))}
        {members.map((m, i) => (
          <div key={m.id} className="timeline-event" style={{ left: pos(times[i]) }}>
            <span className={m.primary ? 'event-dot event-primary' : 'event-dot'} />
            <span className="event-time">{m.time}</span>
            <span className="event-id">{m.id}</span>
            <span>{m.address}</span>
            <TypeTag type={m.type} />
          </div>
        ))}
      </div>
      <div className="timeline-foot">
        <p>
          <strong>Expected:</strong> link {others.join(' and ')} to {primary?.id} instead of sending {countWord(members.length)} crews.
        </p>
        <p className="muted">
          The dataset has {countWord(groups)} duplicate groups, plus {countWord(lookAlikes)} look-alikes that should not
          be linked.
        </p>
      </div>
    </div>
  )
}

/* 10 */
function HistorySlide() {
  const past = pastExample
  const plan = plannedExample
  const planWo = plan.workOrders[0]
  return (
    <div className="layout-history">
      <h2 className="display-lg">Some places already have history</h2>
      <div className="history">
        <article className="history-case">
          <h3 className="case-title">Past work: {past.address}</h3>
          <p className="case-summary">{past.summary}</p>
          <ol className="history-list">
            {past.workOrders.map((w) => (
              <li key={w.id}>
                <span className="history-date">{w.reportedOn}</span>
                <span>
                  {w.id} · {w.title}
                </span>
              </li>
            ))}
            <li className="history-now">
              <span className="history-date">{past.reportedOn}</span>
              <span>
                {past.id} · {past.type}
              </span>
            </li>
          </ol>
        </article>
        <article className="history-case">
          <h3 className="case-title">Planned work: {plan.address.replace(/^\d+\s/, '')}</h3>
          {planWo && (
            <dl className="plan-facts">
              <dt>Project</dt>
              <dd>
                {planWo.id} · {planWo.title}
              </dd>
              <dt>Dates</dt>
              <dd>
                {planWo.start} to {planWo.finish}
              </dd>
              <dt>Status</dt>
              <dd>{planWo.status}</dd>
              <dt>New request</dt>
              <dd>
                {plan.id} on {plan.reportedOn}
              </dd>
            </dl>
          )}
        </article>
      </div>
      <p className="history-foot">The AI should point to the related work order, not open new work.</p>
    </div>
  )
}

/* 11 */
function TeamSlide() {
  const t = teamExample
  return (
    <div className="layout-bridge">
      <h2 className="display-lg">Requests arrive with no team</h2>
      <div className="bridge-rows">
        <div className="bridge">
          <figure className="record bracketed">
            <figcaption className="record-head">
              <span>{t.srId} in Maximo</span>
              <span className="record-status">
                <TypeTag type={t.type} />
              </span>
            </figcaption>
            <div className="record-body">
              <span>{t.address}</span>
              <mark className="flag-mark bridge-source">Team: {t.srTeam || 'blank'}</mark>
              <span className="muted">Someone has to decide which crew gets the work.</span>
            </div>
          </figure>
          <BridgeArrow />
          <figure className="contact-card">
            <figcaption className="contact-source">The AI suggests</figcaption>
            <p className="contact-name">{t.suggestedTeam}</p>
            <p>{t.suggestedLabel}</p>
            <p className="muted">A planner approves it</p>
          </figure>
        </div>
        <div className="bridge">
          <figure className="record bracketed">
            <figcaption className="record-head">
              <span>{t.woId} in Maximo</span>
              <span className="record-status">Job plan {t.jobPlan}</span>
            </figcaption>
            <div className="record-body">
              <mark className="flag-mark bridge-source">Team: {t.team}</mark>
              <span className="muted">The planner applies a job plan, and the job plan sets the team on the work order.</span>
            </div>
          </figure>
          <BridgeArrow />
          <figure className="contact-card">
            <figcaption className="contact-source">Who goes out</figcaption>
            <p className="contact-name">{t.lead}</p>
            <p>Crew lead</p>
            <p className="muted">Supervisor: {t.supervisor}</p>
          </figure>
        </div>
      </div>
      <p className="lede">
        The answer key gives the right team for {teamTotals.withSuggestedTeam} of {teamTotals.requestsWithoutTeam}{' '}
        requests. The other {countWord(teamTotals.requestsWithoutTeam - teamTotals.withSuggestedTeam)} aren’t County
        Utilities work.
      </p>
    </div>
  )
}

/* 12 */
function StatusList({ title, rows }: { title: string; rows: typeof statusLists.requests }) {
  return (
    <div className="status-col">
      <h3 className="ledger-title">{title}</h3>
      <table className="ref-table">
        <tbody>
          {rows.map((s) => (
            <tr key={s.code}>
              <td className="tabular ref-code">{s.code}</td>
              <td>
                {s.label}
                {s.maximo && <span className="muted ref-note">Maximo {s.maximo}</span>}
              </td>
              <td className="tabular ref-count">{s.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReferenceSlide() {
  return (
    <div className="layout-reference">
      <h2 className="display-lg">Teams and status values</h2>
      <div className="reference-grid">
        <div>
          <h3 className="ledger-title">Teams</h3>
          <table className="ref-table">
            <thead>
              <tr>
                <th scope="col">Team</th>
                <th scope="col">Job plans</th>
                <th scope="col" className="ref-count">
                  Work orders
                </th>
                <th scope="col" className="ref-count">
                  Requests
                </th>
              </tr>
            </thead>
            <tbody>
              {teamList.map((t) => (
                <tr key={t.code}>
                  <td>
                    <span className="tabular ref-code">{t.code}</span>
                    {t.fromCounty && <span className="ref-badge">County</span>}
                    <span className="ref-sub">{t.label}</span>
                  </td>
                  <td className="tabular">{t.jobPlans.join(', ')}</td>
                  <td className="tabular ref-count">{t.workOrders}</td>
                  <td className="tabular ref-count">{t.requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <StatusList title="Request statuses" rows={statusLists.requests} />
        <StatusList title="Work order statuses" rows={statusLists.workOrders} />
      </div>
      <p className="footnote">
        Numbers are records in the dataset. “County” marks team codes from the County’s sample records; the other two
        are ours. Requests is how many requests the answer key sends to that team. “Maximo” is the standard status a
        County value stands for.
      </p>
    </div>
  )
}

/* 13 */
const CONTACT_LABELS: Record<string, string> = {
  Resident: 'resident',
  'Entered-by employee': 'took the call',
  'Department supervisor': 'supervisor',
  'Owning group supervisor': 'supervisor',
  'Contact Center': 'unknown employee',
}

function AnswerKeySlide() {
  return (
    <div className="layout-table">
      <h2 className="display-lg">An answer key for every request</h2>
      <p className="lede narrow">
        {totals.answerKeyRows} rows, one per request. We compare what the AI says against this file.
      </p>
      <table className="answer-table">
        <thead>
          <tr>
            <th scope="col">Request</th>
            <th scope="col">What the AI should flag</th>
            <th scope="col">Who to contact</th>
            <th scope="col">Related records</th>
          </tr>
        </thead>
        <tbody>
          {answerSamples.map((a) => (
            <tr key={a.id}>
              <td className="tabular">{a.id}</td>
              <td>{a.alert === 'None' ? <span className="muted">Nothing</span> : a.alert}</td>
              <td>
                {a.contact} <span className="muted">({CONTACT_LABELS[a.contactType] ?? a.contactType})</span>
              </td>
              <td className="tabular">{a.related || <span className="muted">None</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* 14 */
function ChangesSlide() {
  const c = reviewChanges
  const changes = [
    {
      count: c.notCounty,
      title: 'May not be the County’s job',
      body: `Private plumbing, a private backflow device, and ${countWord(c.cityUtility)} addresses that the City of North Port or City of Venice utility serves. The AI should check responsibility, then say who to refer the customer to.`,
    },
    {
      count: c.reroutedByNote,
      title: 'Rerouted without a crew',
      body: 'A “sewer issue” that is really clogged storm drains. As in the County’s misrouted examples, a note sends it back to the Contact Center and no work order is opened.',
    },
    {
      count: c.requiredInfoRules,
      title: 'Required-information rules',
      body: `What each request type must include before a crew goes out. The ${c.requestsWithGaps} incomplete requests now name the rules they break. These rules are our proposal for you to confirm.`,
    },
    {
      count: c.sameAddressLookAlikes,
      title: 'Same address, not a duplicate',
      body: 'Water comes back at an address six days after the repair was finished. That is new work, not another report of an open problem.',
    },
  ]
  return (
    <div className="layout-changes">
      <h2 className="display-lg">What changed after IBM’s data review</h2>
      <p className="lede narrow">
        IBM’s updated review of the County’s examples showed four gaps. Each one now has test requests and an expected
        answer.
      </p>
      <ul className="changes">
        {changes.map((ch) => (
          <li key={ch.title} className="change">
            <span className="change-num">{ch.count}</span>
            <h3 className="change-title">{ch.title}</h3>
            <p className="change-body">{ch.body}</p>
          </li>
        ))}
      </ul>
      <p className="footnote">
        Our scenarios now match the County’s five example groups: duplicates, similar but not duplicate, incomplete,
        misrouted, and not the County’s job.
      </p>
    </div>
  )
}

/* 15 */
function NextSlide() {
  const assumptions = [
    'Most requests come from residents through 311Connect; about one in five through the Contact Center.',
    'QAlert records where each request came from, and who entered phone and email requests.',
    'QAlert and Maximo share the employee ID, and it can come across as an “Entered by” line.',
    'The QAlert origin labels in the data are placeholders until we see real ones.',
    'The city utility areas and the required-information rules are our placeholders.',
  ]
  return (
    <div className="layout-close">
      <div>
        <h2 className="display-lg">Please check these assumptions</h2>
        <ul className="checklist">
          {assumptions.map((a) => (
            <li key={a}>
              <span className="checkbox" aria-hidden="true" />
              {a}
            </li>
          ))}
        </ul>
      </div>
      <aside className="next">
        <h3 className="next-title">Next</h3>
        <p>Build a mock QAlert service and its API guide for the MCP server.</p>
        <h3 className="next-title">Open questions</h3>
        <p>Where should the mock service run?</p>
        <p>What can the real QAlert API return, and how do we get access?</p>
        <p className="repo">{REPO_URL.replace('https://', '')}</p>
      </aside>
    </div>
  )
}

export const slides: { title: string; Component: () => ReactElement }[] = [
  { title: 'A practice dataset for the Sarasota AI pilot', Component: TitleSlide },
  { title: 'Today, Maximo can’t tell who to ask', Component: TodaySlide },
  { title: 'Where requests come from', Component: ChannelsSlide },
  { title: 'Four kinds of test', Component: UseCasesSlide },
  { title: 'Two systems, linked like the real ones', Component: DatasetSlide },
  { title: 'Where it came from decides who to ask', Component: BridgeSlide },
  { title: 'Missing information', Component: MissingSlide },
  { title: 'What the AI should do with one request', Component: StepsSlide },
  { title: 'Duplicates', Component: DuplicatesSlide },
  { title: 'Past and planned work', Component: HistorySlide },
  { title: 'Who does the work', Component: TeamSlide },
  { title: 'Teams and status values', Component: ReferenceSlide },
  { title: 'The answer key', Component: AnswerKeySlide },
  { title: 'What changed after IBM’s data review', Component: ChangesSlide },
  { title: 'Assumptions and next steps', Component: NextSlide },
]
