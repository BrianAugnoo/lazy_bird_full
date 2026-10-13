import { useEffect, useState, useSyncExternalStore } from 'react';
import { health, profile } from '@/api/endpoints/system';
import { useResource } from '@/core/useResource';
import { pagesByGroup } from '@/core/navigation';
import { buildHash } from '@/core/router';
import { isScheduled, useTaskStore } from '@/core/tasks/store';
import { Icon } from './Icon';
import { Popover } from './Popover';

const HEALTH_INTERVAL_MS = 15000;
const narrowSnapshot = () => window.matchMedia('(max-width: 860px)').matches;
function subscribeNarrow(listener: () => void) {
  const media = window.matchMedia('(max-width: 860px)');
  media.addEventListener('change', listener);
  return () => media.removeEventListener('change', listener);
}

type ServerState = { state: 'checking' | 'up' | 'down'; detail?: string };

function useServerHealth(): ServerState {
  const [state, setState] = useState<ServerState>({ state: 'checking' });
  useEffect(() => {
    let active = true;
    const check = () =>
      health()
        .then((response) => active && setState(response.ready ? { state: 'up', detail: `lazy_bird ${response.version}` } : { state: 'down', detail: response.error?.message }))
        .catch((reason) => active && setState({ state: 'down', detail: reason instanceof Error ? reason.message : undefined }));
    void check();
    const timer = window.setInterval(check, HEALTH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);
  return state;
}

/** Navigation built from the page registry, with server and task activity at the bottom. */
export function Sidebar({ current, open, onNavigate, onOpen, onCollapse, onSearch }: { current: string; open: boolean; onNavigate: () => void; onOpen: (page: string, extra?: boolean) => void; onCollapse: () => void; onSearch: () => void }) {
  const server = useServerHealth();
  const narrow = useSyncExternalStore(subscribeNarrow, narrowSnapshot, () => false);
  const user = useResource(profile.get, []);
  const { reload: reloadProfile } = user;
  const [profileOpen, setProfileOpen] = useState(false);
  useEffect(() => {
    const refresh = () => { void reloadProfile(); };
    window.addEventListener('focus', refresh);
    window.addEventListener('profile-changed', refresh);
    return () => { window.removeEventListener('focus', refresh); window.removeEventListener('profile-changed', refresh); };
  }, [reloadProfile]);
  const { tasks } = useTaskStore();
  const running = tasks.filter((task) => task.status === 'running').length;
  const waiting = tasks.filter((task) => task.status === 'queued' && !isScheduled(task)).length;
  const failed = tasks.filter((task) => task.status === 'failed').length;

  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`} aria-label="Main navigation" inert={narrow && !open} aria-hidden={narrow && !open ? true : undefined}>
      <div className="sidebar-brand">
        <Icon name="bird" className="sidebar-logo" size={28} />
        <span className="sidebar-title">lazy_bird</span>
        <button type="button" className="btn btn-ghost btn-icon" onClick={onCollapse} aria-label="Collapse navigation" title="Collapse navigation"><Icon name="panel" size={16} /></button>
      </div>
      <button type="button" className="sidebar-search" onClick={onSearch}><Icon name="search" size={16} /><span>Go to…</span><kbd>Ctrl K</kbd></button>
      <nav className="sidebar-nav">
        {pagesByGroup().map(({ group, pages }) => (
          <div key={group} className="nav-group">
            <div className="nav-group-title">{group}</div>
            {pages.map((page) => (
              <a
                key={page.id}
                href={buildHash(page.id)}
                className={`nav-item ${current === page.id ? 'active' : ''}`}
                aria-current={current === page.id ? 'page' : undefined}
                onClick={event => { event.preventDefault(); onOpen(page.id, event.ctrlKey || event.metaKey || event.shiftKey); onNavigate(); }}
                onAuxClick={event => { if (event.button === 1) { event.preventDefault(); onOpen(page.id, true); } }}
              >
                <Icon name={page.icon} className="nav-icon" />
                <span>{page.label}</span>
                {page.id === 'tasks' && running + waiting > 0 && (
                  <span className="chip chip-live nav-badge" title={`${running} running, ${waiting} waiting`}>
                    {running + waiting}
                  </span>
                )}
                {page.id === 'tasks' && running + waiting === 0 && failed > 0 && (
                  <span className="chip chip-error nav-badge" title={`${failed} failed`}>
                    {failed}
                  </span>
                )}
              </a>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className={`dot ${server.state === 'up' ? 'dot-success' : server.state === 'down' ? 'dot-error' : 'dot-muted'}`} />
        <span title={server.detail}>{server.state === 'up' ? 'Server connected' : server.state === 'down' ? 'Server unavailable' : 'Connecting…'}</span>
        {running > 0 && (
          <a className="sidebar-activity" href={buildHash('tasks')} onClick={onNavigate}>
            <span className="dot dot-live" />
            {running} running
          </a>
        )}
      </div>
      <div className="sidebar-profile">
        <button type="button" className="profile-trigger" aria-expanded={profileOpen} aria-haspopup="dialog" onClick={() => setProfileOpen(!profileOpen)}>
          <span className="profile-avatar"><Icon name="user" size={16} /></span>
          <span className="profile-copy"><strong className="truncate">{user.data?.user?.name || 'Personal workspace'}</strong><small>{user.loading ? 'Loading profile…' : user.error ? 'Profile unavailable' : user.data?.user ? 'Your workspace' : 'No default profile'}</small></span>
          <Icon name="chevronDown" size={15} />
        </button>
        {profileOpen && <Popover label="Workspace settings" onClose={() => setProfileOpen(false)} className="profile-menu">
          {[{ page: 'users', label: 'Users', icon: 'user' as const }, { page: 'databases', label: 'Database', icon: 'database' as const }, { page: 'preferences', label: 'Preferences', icon: 'settings' as const }].map(item => <button key={item.page} type="button" className="popover-item" onClick={() => { onOpen(item.page); setProfileOpen(false); }}><Icon name={item.icon} size={17} />{item.label}</button>)}
          {user.error && <button type="button" className="popover-item" title={user.error.message} onClick={() => void user.reload()}><Icon name="refresh" size={16} />Retry profile</button>}
        </Popover>}
      </div>
    </aside>
  );
}
