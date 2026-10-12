import { useEffect, useRef } from 'react';
import type { SelectionState } from './catalog';

interface GroupCheckboxProps {
  state: SelectionState;
  /** true: select the whole group; false: deselect it. */
  onChange: (on: boolean) => void;
  label: string;
}

/** Checks or unchecks a whole group: ticked when all are chosen, dashed when some are. */
export function GroupCheckbox({ state, onChange, label }: GroupCheckboxProps) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) input.current.indeterminate = state === 'some';
  }, [state]);
  return <input ref={input} type="checkbox" aria-label={label} checked={state === 'all'} onChange={() => onChange(state !== 'all')} />;
}
