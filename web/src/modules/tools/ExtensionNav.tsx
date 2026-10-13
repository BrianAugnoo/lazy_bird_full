import { useState, type ReactNode } from 'react';
import { Icon } from '@/ui/Icon';
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
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className={`extension-nav ${collapsed ? 'is-collapsed' : ''}`}>
      <button type="button" className="btn btn-ghost btn-sm panel-toggle" onClick={() => setCollapsed(!collapsed)} aria-expanded={!collapsed} title={collapsed ? 'Show extensions' : 'Hide extensions'}><Icon name="panel" size={16} /><span>{collapsed ? 'Show' : 'Extensions'}</span></button>
      {!collapsed && <nav aria-label={label}>{extensions.map((entry) => {
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
      })}</nav>}
    </div>
  );
}
