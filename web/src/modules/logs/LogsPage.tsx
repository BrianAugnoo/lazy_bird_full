import { useState } from 'react';
import { logs, type LogQuery } from '@/api/endpoints/system';
import type { LogEntry } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
/** Debug lines (HTTP and socket chatter) are hidden until asked for. */
const DEFAULT_LEVELS = LEVELS.slice(1);
const LEVEL_CHIPS: Record<string, string> = { WARNING: 'chip-warning', ERROR: 'chip-error', CRITICAL: 'chip-error', DEBUG: 'chip-muted' };

interface TraceNode {
  call: LogEntry;
  return: LogEntry | null;
  parent_missing: boolean;
  children: TraceNode[];
}

function TraceTree({ node }: { node: TraceNode }) {
  const call = node.call.payload ?? {};
  const result = node.return?.payload ?? {};
  return (
    <details className="trace-node" open>
      <summary>
        <span className="mono">
          {String(call.module ?? '')}.{String(call.function ?? '?')}
        </span>
        {result.duration_ms !== undefined && <span className="muted small"> {String(result.duration_ms)} ms</span>}
        {typeof result.status === "string" && result.status !== "success" && <span className="chip chip-error">{result.status}</span>}
      </summary>
      <pre className="code">{JSON.stringify({ args: call.args, result: result.result ?? result.error }, null, 2)}</pre>
      {node.children.map((child, index) => (
        <TraceTree key={index} node={child} />
      ))}
    </details>
  );
}

function Tracing() {
  const toast = useToast();
  const tracing = useResource(logs.tracing, []);
  const [fn, setFn] = useState('');
  const [module, setModule] = useState('');
  const [trees, setTrees] = useState<TraceNode[] | null>(null);

  const toggle = async () => {
    try {
      tracing.setData(await logs.setTracing(!tracing.data?.enabled));
    } catch (reason) {
      toast.error(reason);
    }
  };

  const find = async () => {
    try {
      setTrees((await logs.trace(fn.trim(), module.trim() || undefined)) as unknown as TraceNode[]);
    } catch (reason) {
      toast.error(reason);
      setTrees(null);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Call tracing</h2>
          <p className="card-description">Records every lazy_bird call with its arguments and result. Useful to debug, but slows the server down.</p>
        </div>
        <label className="switch">
          <input type="checkbox" checked={tracing.data?.enabled ?? false} onChange={toggle} disabled={!tracing.data} />
          <span>{tracing.data?.enabled ? 'On' : 'Off'}</span>
        </label>
      </div>
      <div className="card-body stack">
        <form
          className="form-row"
          onSubmit={(event) => {
            event.preventDefault();
            if (fn.trim()) void find();
          }}
        >
          <input className="form-input form-mono" value={fn} onChange={(event) => setFn(event.target.value)} placeholder="function, e.g. agentic_loop" aria-label="Function" />
          <input className="form-input form-mono" value={module} onChange={(event) => setModule(event.target.value)} placeholder="module (optional)" aria-label="Module" />
          <button type="submit" className="btn btn-secondary" disabled={!fn.trim()}>
            Show its calls
          </button>
        </form>
        {trees && (trees.length === 0 ? <p className="muted">No traced call of this function.</p> : trees.map((tree, index) => <TraceTree key={index} node={tree} />))}
      </div>
    </div>
  );
}

export function LogsPage() {
  const [query, setQuery] = useState<LogQuery>({ lastN: 200, levels: DEFAULT_LEVELS });
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'bm25' | 'regex'>('bm25');
  const [levels, setLevels] = useState<string[]>(DEFAULT_LEVELS);
  const entries = useResource(() => logs.search(query), [JSON.stringify(query)]);
  const [open, setOpen] = useState<number | null>(null);

  const apply = (changes: Partial<LogQuery>) => setQuery({ ...query, query: text.trim() || undefined, mode, levels, ...changes });

  return (
    <>
      <PageHeader
        title="Logs"
        description="What the server did, most recent first."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void entries.reload()}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />
      <form
        className="log-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply({});
        }}
      >
        <input className="form-input grow" value={text} onChange={(event) => setText(event.target.value)} placeholder={mode === 'regex' ? 'Regular expression' : 'Words to look for'} aria-label="Search the logs" />
        <select className="form-input" value={mode} onChange={(event) => setMode(event.target.value as 'bm25' | 'regex')} aria-label="Search mode">
          <option value="bm25">Words</option>
          <option value="regex">Regex</option>
        </select>
        <button type="submit" className="btn btn-primary">
          Search
        </button>
      </form>
      <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
        {LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            className={`chip chip-button ${levels.includes(level) ? 'chip-accent' : 'chip-outline'}`}
            aria-pressed={levels.includes(level)}
            onClick={() => {
              const next = levels.includes(level) ? levels.filter((item) => item !== level) : [...levels, level];
              setLevels(next);
              apply({ levels: next });
            }}
          >
            {level.toLowerCase()}
          </button>
        ))}
      </div>
      <AsyncState {...entries} onRetry={entries.reload} empty={<span className="muted">No log entry matches.</span>}>
        {(list) => (
          <div className="log-list">
            {list.map((entry) => (
              <div key={`${entry.start_line}-${entry.end_line}`} className="log-entry">
                <button type="button" className="log-head" onClick={() => setOpen(open === entry.start_line ? null : entry.start_line)} aria-expanded={open === entry.start_line}>
                  <span className="log-time mono">{entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : ''}</span>
                  <span className={`chip ${LEVEL_CHIPS[entry.level ?? ''] ?? 'chip-outline'}`}>{(entry.level ?? '').toLowerCase()}</span>
                  <span className="log-message">{entry.message}</span>
                </button>
                {open === entry.start_line && (
                  <div className="log-details">
                    <div className="muted small mono">
                      {entry.timestamp} · {entry.location} · lines {entry.start_line}–{entry.end_line}
                    </div>
                    <pre className="code">{entry.payload ? JSON.stringify(entry.payload, null, 2) : entry.message}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </AsyncState>
      <Tracing />
    </>
  );
}
