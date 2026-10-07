import { useState } from 'react';
import { Icon } from './Icon';
import { rowsToObject, toRows, type Row } from './keyValue';

interface KeyValueEditorProps {
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  /** Keys suggested to the user (e.g. what tools need), shown as one-click additions. */
  suggestions?: string[];
  keyPlaceholder?: string;
}

/** Editable list of key/value pairs (session meta, preset meta). */
export function KeyValueEditor({ value, onChange, suggestions = [], keyPlaceholder = 'key' }: KeyValueEditorProps) {
  const [rows, setRows] = useState<Row[]>(() => toRows(value));
  const update = (next: Row[]) => {
    setRows(next);
    onChange(rowsToObject(next));
  };
  const missing = suggestions.filter((key) => !rows.some((row) => row.key.trim() === key));

  return (
    <div className="kv-editor">
      {rows.map((row, index) => (
        <div key={index} className="kv-row">
          <input
            className="form-input form-mono"
            value={row.key}
            placeholder={keyPlaceholder}
            aria-label="Key"
            onChange={(event) => update(rows.map((item, i) => (i === index ? { ...item, key: event.target.value } : item)))}
          />
          <input
            className="form-input"
            value={row.value}
            placeholder="value"
            aria-label={`Value of ${row.key || 'new key'}`}
            onChange={(event) => update(rows.map((item, i) => (i === index ? { ...item, value: event.target.value } : item)))}
          />
          <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label="Remove" onClick={() => update(rows.filter((_, i) => i !== index))}>
            <Icon name="close" />
          </button>
        </div>
      ))}
      <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setRows([...rows, { key: '', value: '' }])}>
          <Icon name="plus" /> Add a value
        </button>
        {missing.map((key) => (
          <button key={key} type="button" className="chip chip-warning chip-button" onClick={() => setRows([...rows, { key, value: '' }])} title="Needed by a tool">
            + {key}
          </button>
        ))}
      </div>
    </div>
  );
}
