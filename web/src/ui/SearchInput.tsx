import { useId } from 'react';
import { Icon } from './Icon';

export function SearchInput({ value, onChange, label, autoFocus = false }: { value: string; onChange: (value: string) => void; label: string; autoFocus?: boolean }) {
  const id = useId();
  return <div className="filter-input"><Icon name="search" size={16} /><input id={id} type="search" value={value} onChange={event => onChange(event.target.value)} placeholder={label} aria-label={label} autoFocus={autoFocus} />{value && <button type="button" onClick={() => onChange('')} aria-label={`Clear ${label.toLowerCase()}`}><Icon name="close" size={14} /></button>}</div>;
}
