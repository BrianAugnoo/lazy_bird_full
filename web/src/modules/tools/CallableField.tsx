import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { CallableItem } from '@/core/types/api';
import { Icon } from '@/ui/Icon';
import { CallablePicker } from './CallablePicker';
import type { CallableKind } from './catalog';

interface CallableFieldProps {
  kind: CallableKind;
  /** The installed tools or hooks. */
  items: CallableItem[];
  value: string[];
  /** Without it the field is read only. */
  onChange?: (value: string[]) => void;
  /** Shown when nothing is installed. */
  emptyText: string;
}

/** The tools or hooks of an agent or preset, in the order chosen; edited in a picker. */
export function CallableField({ kind, items, value, onChange, emptyText }: CallableFieldProps) {
  const [picking, setPicking] = useState(false);
  const byId = new Map(items.map((item) => [item.id, item]));

  return (
    <div className="callable-field">
      {value.length > 0 ? (
        <div className="row">
          {value.map((id) => {
            const item = byId.get(id);
            return (
              <span key={id} className={`chip ${item ? 'chip-outline' : 'chip-error'}`} title={item ? [id, item.description].filter(Boolean).join('\n') : 'Not installed anymore'}>
                <span className="mono">{item?.name ?? id}</span>
                {!item && ' · missing'}
                {onChange && (
                  <button type="button" className="chip-remove" aria-label={`Remove ${item?.name ?? id}`} onClick={() => onChange(value.filter((entry) => entry !== id))}>
                    <Icon name="close" size={12} />
                  </button>
                )}
              </span>
            );
          })}
        </div>
      ) : (
        <span className="muted small">{items.length === 0 ? emptyText : `No ${kind}.`}</span>
      )}
      {onChange && items.length > 0 && (
        <div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPicking(true)}>
            Choose {kind}…
          </button>
        </div>
      )}
      {picking &&
        onChange &&
        // Above the drawer holding the field, not inside it.
        createPortal(
          <CallablePicker
            kind={kind}
            items={items}
            value={value}
            onClose={() => setPicking(false)}
            onConfirm={(next) => {
              onChange(next);
              setPicking(false);
            }}
          />,
          document.body,
        )}
    </div>
  );
}
