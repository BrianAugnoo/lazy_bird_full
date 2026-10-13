import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { firstPage, getPage, pagesByGroup } from '@/core/navigation';
import { buildHash, parseHash, RouteContext, type Route, type RouteChanges } from '@/core/router';
import { duplicateTab, navigateWorkspace, removeTab, restoreWorkspace, selectTab, toggleSplit, updateTabParams, WORKSPACE_KEY, type Workspace } from '@/core/workspace';
import { Icon } from '@/ui/Icon';
import { DialogProvider } from '@/ui/Dialogs';
import { useDialogs } from '@/ui/dialogContext';
import { Sidebar } from '@/ui/Sidebar';
import { ToastProvider } from '@/ui/Toasts';
import { Modal } from '@/ui/Modal';
import { SearchInput } from '@/ui/SearchInput';
import { SplitDivider } from '@/ui/SplitDivider';

import.meta.glob('./modules/*/index.ts', { eager: true });
const writeHash = (route: Route) => window.history.replaceState(null, '', buildHash(route.page, route.params));

function TabRoute({ id, route, active, onParams, children }: { id: string; route: Route; active: boolean; onParams: (id: string, page: string, changes: RouteChanges) => void; children: ReactNode }) {
  const setParams = useCallback((changes: RouteChanges) => onParams(id, route.page, changes), [id, route.page, onParams]);
  return <RouteContext.Provider value={{ route, active, setParams }}>{children}</RouteContext.Provider>;
}

function WorkspaceShell() {
  const [workspace, setWorkspace] = useState<Workspace>(() => restoreWorkspace(window.location.hash, id => Boolean(getPage(id)), firstPage()?.id ?? 'chat'));
  const workspaceRef = useRef(workspace);
  useLayoutEffect(() => { workspaceRef.current = workspace; }, [workspace]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem('lazy-bird.sidebar') === 'collapsed'; } catch { return false; } });
  const [picker, setPicker] = useState(false);
  const [query, setQuery] = useState('');
  const panels = useRef(new Map<string, HTMLElement>());
  const dialogs = useDialogs();
  const activeTab = workspace.tabs.find(tab => tab.id === workspace.active) ?? workspace.tabs[0];
  const activate = useCallback((id: string) => {
    const tab = workspaceRef.current.tabs.find(item => item.id === id);
    if (!tab) return;
    writeHash(tab.route);
    setWorkspace(current => selectTab(current, id));
  }, []);
  const openPage = useCallback((page: string, extra = false, params?: Record<string, string>) => {
    if (!getPage(page)) return;
    setWorkspace(current => navigateWorkspace(current, page, params, extra));
    setMenuOpen(false); setPicker(false); setQuery('');
  }, []);
  const updateParams = useCallback((id: string, page: string, changes: RouteChanges) => {
    setWorkspace(current => updateTabParams(current, id, page, changes));
  }, []);
  useEffect(() => {
    const hashChanged = () => {
      const route = parseHash(window.location.hash);
      if (!getPage(route.page)) return;
      openPage(route.page, false, route.params);
    };
    window.addEventListener('hashchange', hashChanged);
    return () => window.removeEventListener('hashchange', hashChanged);
  }, [openPage]);
  useEffect(() => {
    try { sessionStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspace)); } catch { /* Optional persistence. */ }
    const tab = workspace.tabs.find(item => item.id === workspace.active);
    if (tab) { writeHash(tab.route); document.title = `${getPage(tab.route.page)?.label ?? tab.route.page} · lazy_bird`; }
  }, [workspace]);
  useEffect(() => { try { localStorage.setItem('lazy-bird.sidebar', collapsed ? 'collapsed' : 'expanded'); } catch { /* Optional persistence. */ } }, [collapsed]);
  const closeTab = async (id: string) => {
    const panel = panels.current.get(id);
    const hasDraft = Boolean(panel?.querySelector('[data-unsaved="true"]')) || [...(panel?.querySelectorAll<HTMLTextAreaElement>('.composer-input') ?? [])].some(area => area.value.trim());
    if (hasDraft && !await dialogs.confirm({ title: 'Close this tab?', message: 'Unsaved drafts in this tab will be lost. Background tasks will continue.', confirmLabel: 'Close tab', danger: true })) return;
    setWorkspace(current => removeTab(current, id, firstPage()?.id ?? 'chat'));
  };
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && menuOpen && window.matchMedia('(max-width: 860px)').matches && ![...document.querySelectorAll('[role="dialog"]')].some(dialog => !dialog.closest('[hidden]'))) { event.preventDefault(); event.stopPropagation(); setMenuOpen(false); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPicker(value => !value); }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 't') {
        event.preventDefault(); setWorkspace(current => duplicateTab(current));
      }
      if ((event.ctrlKey || event.metaKey) && event.code === 'Backslash') { event.preventDefault(); setWorkspace(current => toggleSplit(current)); }
      if (event.altKey && (event.key === '[' || event.key === ']')) {
        event.preventDefault(); const value = workspaceRef.current; const index = value.tabs.findIndex(tab => tab.id === value.active);
        activate(value.tabs[(index + (event.key === '[' ? -1 : 1) + value.tabs.length) % value.tabs.length].id);
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [activate, openPage, menuOpen]);
  const routes = pagesByGroup().flatMap(group => group.pages).filter(page => `${page.label} ${page.group}`.toLowerCase().includes(query.toLowerCase()));
  return <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#workspace-main" onClick={event => { event.preventDefault(); panels.current.get(workspace.active)?.focus(); }}>Skip to content</a>
    <Sidebar current={activeTab.route.page} open={menuOpen} onNavigate={() => setMenuOpen(false)} onOpen={openPage} onCollapse={() => { setCollapsed(true); setMenuOpen(false); window.requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.sidebar-reopen')?.focus()); }} onSearch={() => setPicker(true)} />
    {menuOpen && <button type="button" className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
    <div className="main-wrapper">
      <header className="workspace-bar">
        <button type="button" className={`btn btn-ghost btn-icon sidebar-reopen ${collapsed ? 'is-visible' : ''}`} onClick={() => { setCollapsed(false); setMenuOpen(true); }} title="Show navigation" aria-label="Show navigation"><Icon name="panel" /></button>
        <div className="workspace-tabs" role="tablist" aria-label="Workspace tabs">
          {workspace.tabs.map(tab => { const page = getPage(tab.route.page); return <button key={tab.id} type="button" id={`tab-${tab.id}`} role="tab" className={`workspace-tab ${tab.id === workspace.active ? 'is-active' : ''} ${workspace.split && (tab.id === workspace.split.left || tab.id === workspace.split.right) ? 'is-visible-pane' : ''}`} aria-selected={tab.id === workspace.active} aria-controls={`panel-${tab.id}`} tabIndex={tab.id === workspace.active ? 0 : -1} onClick={() => activate(tab.id)} onKeyDown={event => {
              const index = workspace.tabs.findIndex(item => item.id === tab.id);
              const next = event.key === 'ArrowRight' ? (index + 1) % workspace.tabs.length : event.key === 'ArrowLeft' ? (index - 1 + workspace.tabs.length) % workspace.tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? workspace.tabs.length - 1 : null;
              if (next !== null) { event.preventDefault(); activate(workspace.tabs[next].id); document.getElementById(`tab-${workspace.tabs[next].id}`)?.focus(); }
              if (event.key === 'Delete') void closeTab(tab.id);
            }}><Icon name={page?.icon ?? 'file'} size={15} /><span className="tab-label">{page?.label ?? tab.route.page}{tab.route.params.file ? ` · ${tab.route.params.file}` : tab.route.params.session ? ` · ${tab.route.params.session}` : ''}</span>
            <span className="tab-close" aria-hidden="true" onClick={event => { event.stopPropagation(); void closeTab(tab.id); }} title="Close tab (Delete)"><Icon name="close" size={13} /></span>
          </button>; })}
        </div>
        <button type="button" className="btn btn-ghost btn-icon" onClick={() => setWorkspace(current => duplicateTab(current))} title="New tab at this location (Ctrl+Shift+T)" aria-label="Open a new tab"><Icon name="plus" size={16} /></button>
        <button type="button" className="btn btn-ghost btn-icon split-toggle" onClick={() => setWorkspace(current => toggleSplit(current))} aria-pressed={Boolean(workspace.split)} title="Toggle split view (Ctrl+\)" aria-label={workspace.split ? 'Close split view' : 'Split view'}><Icon name="split" size={17} /></button>
        <button type="button" className="btn btn-ghost btn-icon close-active-tab" onClick={() => void closeTab(workspace.active)} aria-label={`Close ${getPage(activeTab.route.page)?.label ?? activeTab.route.page} tab`} title="Close active tab (Delete)"><Icon name="close" size={14} /></button>
      </header>
      <div className={`workspace-panes ${workspace.split ? 'is-split' : ''}`} style={workspace.split ? { gridTemplateColumns: `${workspace.split.ratio}fr 6px ${100 - workspace.split.ratio}fr`, '--split-ratio': `${workspace.split.ratio}fr`, '--split-rest': `${100 - workspace.split.ratio}fr` } as React.CSSProperties : undefined}>
        {workspace.tabs.map(tab => {
          const focused = tab.id === workspace.active;
          const visible = workspace.split ? tab.id === workspace.split.left || tab.id === workspace.split.right : focused;
          const right = tab.id === workspace.split?.right;
          return <main key={tab.id} ref={node => { if (node) panels.current.set(tab.id, node); else panels.current.delete(tab.id); }} id={`panel-${tab.id}`} role="tabpanel" aria-labelledby={`tab-${tab.id}`} tabIndex={-1} hidden={!visible} inert={!visible} onPointerDownCapture={() => { if (!focused) activate(tab.id); }} onFocusCapture={() => { if (!focused) activate(tab.id); }} className={`workspace-window ${focused ? 'is-focused' : ''} ${right ? 'is-right' : ''}`}>
            {Object.values(tab.views).map(route => {
              const page = getPage(route.page); const Page = page?.component; const current = route.page === tab.route.page;
              return <TabRoute key={route.page} id={tab.id} route={route} active={focused && current} onParams={updateParams}>
                <div hidden={!current} inert={!current} className={`content-viewport ${page?.flush ? 'is-flush' : ''} ${route.page === 'files' && route.params.file ? 'is-editor' : ''}`}>
                  {Page && (page?.flush ? <Page /> : <div className="content-container"><Page /></div>)}
                </div>
              </TabRoute>;
            })}
          </main>;
        })}
        {workspace.split && <SplitDivider ratio={workspace.split.ratio} onChange={ratio => setWorkspace(current => current.split ? { ...current, split: { ...current.split, ratio } } : current)} />}
      </div>
    </div>
    {picker && <Modal title="Go to…" subtitle="Navigate in the focused tab." onClose={() => { setPicker(false); setQuery(''); }} width={520}>
      <SearchInput label="Search pages" value={query} onChange={setQuery} autoFocus />
      <div className="command-results">{routes.map(page => <button type="button" key={page.id} className="command-item" onClick={() => openPage(page.id)}><Icon name={page.icon} /><span>{page.label}</span><small>{page.group}</small><Icon name="external" size={14} /></button>)}{routes.length === 0 && <p className="state-empty">No page matches “{query}”.</p>}</div>
      <p className="form-hint">Ctrl+K to search · Alt+[ / Alt+] to switch tabs</p>
    </Modal>}
  </div>;
}
export default function App() { return <ToastProvider><DialogProvider><WorkspaceShell /></DialogProvider></ToastProvider>; }
