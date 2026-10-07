/** Conversions between key/value rows and objects (session meta, preset meta). */

/** Text shown for a value: strings as-is, anything else as JSON. */
export function formatValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** Numbers, booleans, null, lists and objects typed as JSON keep their type; anything else is text. */
export function parseValue(text: string): unknown {
  const trimmed = text.trim();
  if (/^(-?\d+(\.\d+)?|true|false|null)$/.test(trimmed) || /^[[{]/.test(trimmed)) {
    try {
      return JSON.parse(trimmed);
    } catch {
      return text;
    }
  }
  return text;
}

export interface Row {
  key: string;
  value: string;
}

export const toRows = (values: Record<string, unknown>): Row[] => Object.entries(values).map(([key, value]) => ({ key, value: formatValue(value) }));

export function rowsToObject(rows: Row[]): Record<string, unknown> {
  return Object.fromEntries(rows.filter((row) => row.key.trim()).map((row) => [row.key.trim(), parseValue(row.value)]));
}
