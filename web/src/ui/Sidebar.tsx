import { useEffect, useState } from 'react';
import { health } from '@/api/endpoints/system';
import { pagesByGroup } from '@/core/navigation';
import { buildHash } from '@/core/router';
import { isScheduled, useTaskStore } from '@/core/tasks/store';
import { Icon } from './Icon';

const HEALTH_INTERVAL_MS = 15000;

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
export function Sidebar({ current, open, onNavigate }: { current: string; open: boolean; onNavigate: () => void }) {
  const server = useServerHealth();
  const { tasks } = useTaskStore();
  const running = tasks.filter((task) => task.status === 'running').length;
  const waiting = tasks.filter((task) => task.status === 'queued' && !isScheduled(task)).length;
  const failed = tasks.filter((task) => task.status === 'failed').length;

  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`} aria-label="Main navigation">
      <div className="sidebar-brand">
        <Icon name="bird" className="sidebar-logo" size={28} />
        <span className="sidebar-title">lazy_bird</span>
      </div>
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
                onClick={onNavigate}
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
    </aside>
  );
}
