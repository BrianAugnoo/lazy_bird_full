import type { ReactNode } from 'react';
import type { CallableExtension } from './catalog';

interface ExtensionNavProps {
  extensions: CallableExtension[];
  active: string;
  onSelect: (extension: string) => void;
  /** Shown after each name, e.g. how many items it has. */
  badge: (extension: CallableExtension) => ReactNode;
  label: string;
}

/** The extensions of the Tools and Hooks pages and pickers: one entry per folder. */
export function ExtensionNav({ extensions, active, onSelect, badge, label }: ExtensionNavProps) {
  return (
    <nav className="extension-nav" aria-label={label}>
      {extensions.map((entry) => {
        const selected = entry.extension === active;
        return (
          <button
            key={entry.extension}
            type="button"
            className={`extension-nav-item ${selected ? 'is-active' : ''}`}
            aria-current={selected ? 'page' : undefined}
            onClick={() => onSelect(entry.extension)}
          >
            <span className="truncate">{entry.extension}</span>
            <span className="extension-nav-badge">{badge(entry)}</span>
          </button>
        );
      })}
    </nav>
  );
}
