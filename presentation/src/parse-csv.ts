export type Row = Record<string, string>

// Minimal RFC 4180 parser: quoted fields may contain commas, newlines, and "" escapes.
export function parseCsv(text: string): Row[] {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let quoted = false

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"'
        i++
      } else if (ch === '"') {
        quoted = false
      } else {
        field += ch
      }
    } else if (ch === '"') {
      quoted = true
    } else if (ch === ',') {
      record.push(field)
      field = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      record.push(field)
      records.push(record)
      record = []
      field = ''
    } else {
      field += ch
    }
  }
  if (field !== '' || record.length > 0) {
    record.push(field)
    records.push(record)
  }

  const [header, ...rows] = records.filter((r) => r.length > 1 || r[0] !== '')
  return rows.map((r) => Object.fromEntries(header.map((name, i) => [name, r[i] ?? ''])))
}
