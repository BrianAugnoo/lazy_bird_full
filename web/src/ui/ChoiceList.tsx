import type { ReactNode } from 'react';
import { Icon } from './Icon';

export interface Choice {
  value: string;
  title: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

interface ChoiceListProps {
  choices: Choice[];
  value: string | null;
  onChange: (value: string) => void;
  label: string;
  /** Double-click: choose and confirm at once. */
  onConfirm?: (value: string) => void;
}

/** One option to pick among cards; the choice is confirmed elsewhere (a dialog button). */
export function ChoiceList({ choices, value, onChange, label, onConfirm }: ChoiceListProps) {
  return (
    <div className="choice-list" role="radiogroup" aria-label={label}>
      {choices.map((choice) => {
        const selected = choice.value === value;
        return (
          <button
            key={choice.value}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`choice ${selected ? 'is-selected' : ''}`}
            disabled={choice.disabled}
            onClick={() => onChange(choice.value)}
            onDoubleClick={() => onConfirm?.(choice.value)}
          >
            <span className="choice-title">
              {choice.title}
              {selected && <Icon name="check" size={16} className="choice-check" />}
            </span>
            {choice.description && <span className="choice-desc">{choice.description}</span>}
          </button>
        );
      })}
    </div>
  );
}
