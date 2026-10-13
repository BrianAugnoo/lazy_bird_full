import { useState, type ReactNode } from 'react';
import { Icon } from './Icon';

export interface LibraryExtension { extension: string; count: number }
export function LibraryBrowser({ extensions, active, onSelect, children, label = 'Extensions' }: { extensions: LibraryExtension[]; active: string; onSelect: (extension: string) => void; children: ReactNode; label?: string }) {
  const [collapsed, setCollapsed] = useState(false);
  return <div className={`library-browser ${collapsed ? 'is-collapsed' : ''}`}>
    <aside className="library-sidebar" aria-label={label}>
      <button type="button" className="btn btn-ghost btn-sm panel-toggle" aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)} title={collapsed ? `Show ${label.toLowerCase()}` : `Hide ${label.toLowerCase()}`}><Icon name="panel" /><span>{collapsed ? 'Show' : label}</span></button>
      {!collapsed && <nav>{extensions.map(entry => <button key={entry.extension} type="button" className={`extension-nav-item ${entry.extension === active ? 'is-active' : ''}`} aria-current={entry.extension === active ? 'page' : undefined} onClick={() => onSelect(entry.extension)}><Icon name="extension" size={15} /><span className="truncate">{entry.extension}</span><span className="extension-nav-badge">{entry.count}</span></button>)}</nav>}
    </aside>
    <div className="library-content">{children}</div>
  </div>;
}
