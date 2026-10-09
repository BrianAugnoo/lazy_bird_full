import { useMemo, useState, type DragEvent } from 'react';
import { tasks as tasksApi } from '@/api/endpoints/tasks';
import { DEFAULT_PRIORITY, PRIORITY_NOW, isScheduled, moveTask, taskAction, useTaskStore, type TaskAction } from '@/core/tasks/store';
import type { LoadedModel, ResourceSnapshot, Task } from '@/core/types/api';
import { Icon } from '@/ui/Icon';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';
import { duration } from './format';

const RESOURCE_LABELS: Record<string, { label: string; unit?: string; scale?: number }> = {
  cpu: { label: 'Worker slots' },
  vram_mb: { label: 'GPU memory', unit: 'GB', scale: 1024 },
  ram_mb: { label: 'Memory', unit: 'GB', scale: 1024 },
};

const STATUS_CHIPS: Record<Task['status'], string> = {
  running: 'chip-live',
  queued: 'chip-outline',
  paused: 'chip-warning',
  completed: 'chip-success',
  failed: 'chip-error',
  cancelled: 'chip-muted',
};

function amount(name: string, value: number): string {
  const spec = RESOURCE_LABELS[name];
  if (spec?.scale) return `${(value / spec.scale).toFixed(1)} ${spec.unit}`;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function modelMemory(model: LoadedModel): string {
  const reserved = Object.entries(model.needs)
    .map(([name, value]) => `${amount(name, value)} ${name === 'vram_mb' ? 'of GPU memory' : 'of memory'}`)
    .join(', ');
  const really = model.memory ? ` (really using ${(model.memory.rss_mb / 1024).toFixed(1)} GB memory${model.memory.vram_mb ? `, ${(model.memory.vram_mb / 1024).toFixed(1)} GB GPU` : ''})` : '';
  return reserved + really;
}

function LoadedModels({ models }: { models: LoadedModel[] }) {
  if (models.length === 0) return null;
  return (
    <section>
      <h2 className="section-title">
        Models in memory <span className="muted">{models.length}</span>
      </h2>
      <div className="task-list">
        {models.map((model) => (
          <div key={`${model.engine}:${model.model}:${model.device}`} className="task-row">
            <div className="task-main">
              <div className="task-title">
                <span className="task-title-text">{model.model}</span>
                <span className={`chip ${model.idle ? 'chip-outline' : 'chip-live'}`}>{model.idle ? 'idle' : 'in use'}</span>
                {model.device && <span className="chip chip-outline">{model.device}</span>}
                {model.pid !== null && (
                  <span className="chip chip-outline" title="It runs in a process of its own: unloading it gives all its memory back">
                    own process
                  </span>
                )}
              </div>
              <div className="task-meta">
                <span>{modelMemory(model) || 'no memory declared'}</span>
                {model.idle && <span>Unloaded when its memory is needed.</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Resources({ resources }: { resources: ResourceSnapshot }) {
  const names = Object.keys(resources.capacity ?? {});
  if (names.length === 0) return null;
  return (
    <div className="resource-grid">
      {names.map((name) => {
        const capacity = resources.capacity[name] ?? 0;
        const used = resources.used?.[name] ?? 0;
        const ratio = capacity > 0 ? Math.min(1, used / capacity) : 0;
        return (
          <div key={name} className="resource">
            <div className="row-between small">
              <span className="resource-name">{RESOURCE_LABELS[name]?.label ?? name}</span>
              <span className="muted">
                {amount(name, used)} / {amount(name, capacity)}
              </span>
            </div>
            <div className="progress">
              <div className={`progress-bar ${used > 0 ? 'progress-live' : ''}`} style={{ width: `${ratio * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface RowProps {
  task: Task;
  waiting?: string[];
  unresponsive?: boolean;
  onAction: (action: TaskAction, task: Task) => void;
  drag?: {
    onDragStart: (event: DragEvent) => void;
    onDragOver: (event: DragEvent) => void;
    onDrop: (event: DragEvent) => void;
    onDragEnd: () => void;
    indicator: 'before' | 'after' | null;
    onMoveUp?: () => void;
    onMoveDown?: () => void;
  };
}

function TaskRow({ task, waiting, unresponsive, onAction, drag }: RowProps) {
  const [open, setOpen] = useState(false);
  const progress = task.progress ?? null;
  const finished = ['completed', 'failed', 'cancelled'].includes(task.status);
  return (
    <div
      className={`task-row is-${task.status} ${drag?.indicator ? `drop-${drag.indicator}` : ''}`}
      draggable={Boolean(drag)}
      onDragStart={drag?.onDragStart}
      onDragOver={drag?.onDragOver}
      onDrop={drag?.onDrop}
      onDragEnd={drag?.onDragEnd}
    >
      {drag && (
        <span className="task-grip" title="Drag to reorder" aria-hidden>
          <Icon name="grip" size={16} />
        </span>
      )}
      <div className="task-main">
        <div className="task-title">
          <button type="button" className="task-title-text" onClick={() => setOpen(!open)} aria-expanded={open}>
            {task.title}
          </button>
          <span className={`chip ${isScheduled(task) ? 'chip-outline' : STATUS_CHIPS[task.status]}`}>{isScheduled(task) ? 'scheduled' : task.status}</span>
          {task.control && <span className="chip chip-warning">{task.control === 'pause' ? 'pausing…' : 'cancelling…'}</span>}
          {unresponsive && task.status === 'running' && (
            <span className="chip chip-warning" title="It was asked to make room for a more urgent task but has not stopped yet">
              not responding
            </span>
          )}
          {task.priority !== DEFAULT_PRIORITY && !finished && (
            <span className="chip chip-outline" title="Lower numbers run first">
              {task.priority === PRIORITY_NOW ? 'run now' : `priority ${task.priority}`}
            </span>
          )}
          {task.attempts > 1 && (
            <span className="chip chip-outline">
              attempt {task.attempts}/{task.max_attempts}
            </span>
          )}
        </div>
        {task.status === 'running' && (
          <div className="task-progress">
            <div className="progress">
              <div className="progress-bar progress-live" style={{ width: progress === null ? '100%' : `${Math.round(progress * 100)}%`, opacity: progress === null ? 0.35 : 1 }} />
            </div>
            <span className="small muted">{progress === null ? duration(task.started_at, null) : `${Math.round(progress * 100)}%`}</span>
          </div>
        )}
        <div className="task-meta">
          {task.message && <span>{task.message}</span>}
          {waiting && waiting.length > 0 && <span className="text-warning">Waiting for {waiting.map((name) => RESOURCE_LABELS[name]?.label.toLowerCase() ?? name).join(', ')}</span>}
          {isScheduled(task) && <span>Starts {new Date(task.run_at!).toLocaleString()}</span>}
          {finished && <span>{duration(task.started_at, task.finished_at)}</span>}
          {task.error && <span className="text-error">{task.error.message}</span>}
        </div>
        {open && (
          <div className="task-details">
            <div>
              <span className="muted">Kind</span> <span className="mono">{task.kind}</span> · <span className="muted">Created</span>{' '}
              {new Date(task.created_at).toLocaleString()}
            </div>
            {Object.keys(task.resources).length > 0 && (
              <div>
                <span className="muted">Needs</span>{' '}
                {Object.entries(task.resources)
                  .map(([name, value]) => `${RESOURCE_LABELS[name]?.label ?? name}: ${amount(name, value)}`)
                  .join(', ')}
              </div>
            )}
            <pre className="code">{JSON.stringify({ params: task.params, result: task.result ?? undefined, error: task.error ?? undefined }, null, 2)}</pre>
          </div>
        )}
      </div>
      <div className="task-actions">
        {drag?.onMoveUp && (
          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={drag.onMoveUp} aria-label="Move up" title="Move up">
            ↑
          </button>
        )}
        {drag?.onMoveDown && (
          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={drag.onMoveDown} aria-label="Move down" title="Move down">
            ↓
          </button>
        )}
        {(task.status === 'running' || task.status === 'queued') && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAction('pause', task)} disabled={task.control !== null}>
            <Icon name="pause" /> Pause
          </button>
        )}
        {task.status === 'queued' && task.priority !== PRIORITY_NOW && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onAction('run_now', task)}
            title="Start it before everything else, even if other tasks have to step aside"
          >
            Run now
          </button>
        )}
        {task.status === 'paused' && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => onAction('resume', task)}>
            <Icon name="play" /> Resume
          </button>
        )}
        {!finished && (
          <button type="button" className="btn btn-ghost btn-sm btn-danger-text" onClick={() => onAction('cancel', task)} disabled={task.control === 'cancel'}>
            Cancel
          </button>
        )}
        {(task.status === 'failed' || task.status === 'cancelled') && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => onAction('retry', task)}>
            <Icon name="refresh" /> Retry
          </button>
        )}
        {finished && (
          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => onAction('delete', task)} aria-label="Remove from the list" title="Remove from the list">
            <Icon name="trash" />
          </button>
        )}
      </div>
    </div>
  );
}

export function TasksPage() {
  const { tasks, resources, waiting, unresponsive, kinds, status } = useTaskStore();
  const toast = useToast();
  const [kind, setKind] = useState('');
  const [dragged, setDragged] = useState<number | null>(null);
  const [target, setTarget] = useState<{ id: number; side: 'before' | 'after' } | null>(null);

  const shown = useMemo(() => (kind ? tasks.filter((task) => task.kind === kind) : tasks), [tasks, kind]);
  const running = shown.filter((task) => task.status === 'running');
  const queue = shown.filter((task) => task.status === 'queued' || task.status === 'paused');
  const finished = shown.filter((task) => !['running', 'queued', 'paused'].includes(task.status));

  const act = (action: TaskAction, task: Task) => {
    taskAction(action, task.id).catch((reason) => toast.error(reason));
  };

  const move = (id: number, anchor: { before_id?: number; after_id?: number }) => {
    moveTask(id, anchor).catch((reason) => toast.error(reason));
  };

  const clearFinished = async () => {
    try {
      const { deleted } = await tasksApi.clearFinished();
      toast.show(`${deleted} finished task${deleted === 1 ? '' : 's'} removed`);
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="Tasks"
        description="Background work: model downloads, chunking, embedding and file scans. Drag waiting tasks to change their order."
        actions={
          <>
            {kinds.length > 1 && (
              <select className="form-input" value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Filter by kind">
                <option value="">All kinds</option>
                {kinds.map((item) => (
                  <option key={item.kind} value={item.kind} title={item.description}>
                    {item.title}
                  </option>
                ))}
              </select>
            )}
            <button type="button" className="btn btn-secondary" onClick={clearFinished} disabled={finished.length === 0}>
              Clear finished
            </button>
          </>
        }
      />
      {status !== 'open' && <div className="alert alert-warning">{status === 'connecting' ? 'Connecting to the task queue…' : 'Disconnected from the task queue, reconnecting…'}</div>}
      <Resources resources={resources} />
      <LoadedModels models={resources.models ?? []} />

      <section>
        <h2 className="section-title">
          Running <span className="muted">{running.length}</span>
        </h2>
        {running.length === 0 ? (
          <div className="state-empty small">Nothing is running.</div>
        ) : (
          <div className="task-list">
            {running.map((task) => (
              <TaskRow key={task.id} task={task} unresponsive={unresponsive.includes(task.id)} onAction={act} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="section-title">
          Waiting <span className="muted">{queue.length}</span>
        </h2>
        {queue.length === 0 ? (
          <div className="state-empty small">The queue is empty.</div>
        ) : (
          <div className="task-list">
            {queue.map((task, index) => (
              <TaskRow
                key={task.id}
                task={task}
                waiting={waiting[String(task.id)]}
                onAction={act}
                drag={{
                  indicator: target?.id === task.id && dragged !== task.id ? target.side : null,
                  onDragStart: (event) => {
                    setDragged(task.id);
                    event.dataTransfer.effectAllowed = 'move';
                  },
                  onDragOver: (event) => {
                    if (dragged === null) return;
                    event.preventDefault();
                    const box = event.currentTarget.getBoundingClientRect();
                    setTarget({ id: task.id, side: event.clientY < box.top + box.height / 2 ? 'before' : 'after' });
                  },
                  onDrop: (event) => {
                    event.preventDefault();
                    if (dragged !== null && target && dragged !== target.id) {
                      move(dragged, target.side === 'before' ? { before_id: target.id } : { after_id: target.id });
                    }
                    setDragged(null);
                    setTarget(null);
                  },
                  onDragEnd: () => {
                    setDragged(null);
                    setTarget(null);
                  },
                  onMoveUp: index > 0 ? () => move(task.id, { before_id: queue[index - 1].id }) : undefined,
                  onMoveDown: index < queue.length - 1 ? () => move(task.id, { after_id: queue[index + 1].id }) : undefined,
                }}
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="section-title">
          Finished <span className="muted">{finished.length}</span>
        </h2>
        {finished.length === 0 ? (
          <div className="state-empty small">No finished task.</div>
        ) : (
          <div className="task-list">
            {finished.map((task) => (
              <TaskRow key={task.id} task={task} onAction={act} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
