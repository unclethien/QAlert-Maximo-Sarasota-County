import type { ReactElement } from 'react'
import {
  answerSamples,
  countWord,
  duplicateExample,
  missingPatterns,
  missingTotal,
  missingWithCrewSent,
  pastExample,
  plannedExample,
  requestExample,
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
        <mark className="flag-mark">{requestExample.enteredByLine}</mark>
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
        <h2 className="display-lg">Today, Maximo loses who took the call</h2>
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
          <strong>Reported by</strong> is always the integration account, never the staff member who took the call.
        </li>
        <li>The caller, the address, and the problem all sit in one text field.</li>
        <li>To follow up, staff have to find the same request again in QAlert.</li>
      </ul>
    </div>
  )
}

/* 3 */
function UseCasesSlide() {
  const total = useCaseGroups.reduce((sum, g) => sum + g.count, 0)
  return (
    <div className="layout-band">
      <h2 className="display-lg">
        {totals.serviceRequests} requests, four kinds of test
      </h2>
      <p className="lede narrow">Each request was written to test one thing the AI should notice, or to have nothing to notice.</p>
      <div className="stack-bar" role="img" aria-label={useCaseGroups.map((g) => `${g.label}: ${g.count}`).join(', ')}>
        {useCaseGroups.map((g, i) => (
          <div key={g.key} className={`stack-seg seg-${i}`} style={{ flexGrow: g.count / total }}>
            <span className="stack-count">{g.count}</span>
          </div>
        ))}
      </div>
      <div className="stack-legend">
        {useCaseGroups.map((g, i) => (
          <div key={g.key} className="legend-item" style={{ flexGrow: Math.max(g.count / total, 0.18) }}>
            <span className={`legend-swatch seg-${i}`} />
            <span className="legend-label">{g.label}</span>
            <span className="legend-note">{g.note}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* 4 */
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
    [totals.qalertStaff, 'staff who enter requests'],
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

/* 5 */
function BridgeSlide() {
  const r = requestExample
  return (
    <div className="layout-bridge">
      <h2 className="display-lg">One extra line connects the two</h2>
      <div className="bridge">
        <figure className="record bracketed">
          <figcaption className="record-head">
            <span>{r.id} details in Maximo</span>
          </figcaption>
          <div className="record-body">
            {r.detailLines.map((line) => (
              <span key={line} className="detail-line">
                {line}
              </span>
            ))}
            <mark className="flag-mark bridge-source">{r.enteredByLine}</mark>
          </div>
        </figure>
        <svg className="bridge-link" viewBox="0 0 160 40" aria-hidden="true">
          <line x1="0" y1="20" x2="148" y2="20" />
          <polyline points="138 10 150 20 138 30" />
        </svg>
        <figure className="contact-card">
          <figcaption className="contact-source">QAlert staff record {r.staff.id}</figcaption>
          <p className="contact-name">{r.staff.name}</p>
          <p>{r.staff.department}</p>
          <p className="tabular">{r.staff.phone}</p>
          <p>{r.staff.email}</p>
          <p className="muted">{r.staff.active ? 'Active' : 'No longer active'}</p>
        </figure>
      </div>
      <p className="lede narrow">
        {totals.staffWithoutMaximoRecord} of {totals.qalertStaff} QAlert staff have no Maximo person record, and{' '}
        {totals.inactiveStaff} are no longer active. The dataset includes both cases on purpose.
      </p>
    </div>
  )
}

/* 6 */
function MissingSlide() {
  const max = Math.max(...missingPatterns.map((p) => p.count))
  return (
    <div className="layout-bars">
      <div>
        <h2 className="display-lg">{missingTotal} requests are missing something</h2>
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

/* 7 */
function StepsSlide() {
  const r = requestExample
  const steps = [
    { verb: 'Spot the gap', body: r.gap },
    { verb: 'Find who entered it', body: `${r.enteredByLine}, which is ${r.staff.name} in the ${r.staff.department}.` },
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

/* 8 */
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
        <span className="capitalize">{countWord(members.length)}</span> calls, one outage
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

/* 9 */
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

/* 10 */
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
              <td>{a.contact}</td>
              <td className="tabular">{a.related || <span className="muted">None</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* 11 */
function NextSlide() {
  const assumptions = [
    'QAlert and Maximo use the same employee ID.',
    'Only County staff enter requests in QAlert.',
    'The employee ID can come across as an “Entered by” line.',
    'QAlert can return each staff member’s name, phone, email, and department.',
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
  { title: 'Today, Maximo loses who took the call', Component: TodaySlide },
  { title: 'Four kinds of test', Component: UseCasesSlide },
  { title: 'Two systems, linked like the real ones', Component: DatasetSlide },
  { title: 'One extra line connects the two', Component: BridgeSlide },
  { title: 'Missing information', Component: MissingSlide },
  { title: 'What the AI should do with one request', Component: StepsSlide },
  { title: 'Duplicates', Component: DuplicatesSlide },
  { title: 'Past and planned work', Component: HistorySlide },
  { title: 'The answer key', Component: AnswerKeySlide },
  { title: 'Assumptions and next steps', Component: NextSlide },
]
