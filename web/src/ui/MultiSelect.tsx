import { useMemo, useState } from 'react';

export interface Option {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface MultiSelectProps {
  options: Option[];
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  /** Values that are selected but no longer offered (e.g. an uninstalled tool). */
  emptyText?: string;
  id?: string;
}

/** Searchable checkbox list; keeps the order in which items were selected. */
export function MultiSelect({ options, value, onChange, placeholder = 'Filter…', emptyText = 'Nothing to choose from.', id }: MultiSelectProps) {
  const [filter, setFilter] = useState('');
  const known = useMemo(() => new Set(options.map((option) => option.value)), [options]);
  const missing = value.filter((item) => !known.has(item));
  const shown = options.filter((option) =>
    `${option.label} ${option.value} ${option.description ?? ''}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  const toggle = (item: string) => onChange(value.includes(item) ? value.filter((entry) => entry !== item) : [...value, item]);

  return (
    <div className="multi-select" id={id}>
      {options.length > 6 && (
        <input className="form-input multi-select-search" placeholder={placeholder} value={filter} onChange={(event) => setFilter(event.target.value)} />
      )}
      <div className="multi-select-options">
        {options.length === 0 && missing.length === 0 && <div className="muted small" style={{ padding: 8 }}>{emptyText}</div>}
        {missing.map((item) => (
          <label key={item} className="multi-select-option" title="Not installed anymore">
            <input type="checkbox" checked onChange={() => toggle(item)} />
            <span>
              <span className="mono">{item}</span> <span className="chip chip-error">missing</span>
            </span>
          </label>
        ))}
        {shown.map((option) => (
          <label key={option.value} className="multi-select-option">
            <input type="checkbox" checked={value.includes(option.value)} disabled={option.disabled} onChange={() => toggle(option.value)} />
            <span>
              {option.label}
              {option.description && <small>{option.description}</small>}
            </span>
          </label>
        ))}
      </div>
      {value.length > 0 && <div className="multi-select-summary">{value.length} selected</div>}
    </div>
  );
}
