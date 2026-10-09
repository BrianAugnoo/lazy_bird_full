import type { LoadedModel, ResourceSnapshot } from '@/core/types/api';
import { amount, modelMemory, resourceLabel } from './format';

/** The local models in memory: in use or idle, where, and how much they take. */
export function LoadedModels({ models }: { models: LoadedModel[] }) {
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

export function Resources({ resources }: { resources: ResourceSnapshot }) {
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
              <span className="resource-name">{resourceLabel(name)}</span>
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
