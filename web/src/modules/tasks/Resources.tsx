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
  const names = [...new Set([...Object.keys(resources.capacity ?? {}), ...Object.keys(resources.system ?? {})])];
  if (names.length === 0) return null;
  return (
    <div className="resource-grid">
      {names.map((name) => {
        const memory = name === 'ram_mb' || name === 'vram_mb';
        const measured = resources.system?.[name];
        const capacity = measured?.total_mb ?? resources.capacity[name] ?? 0;
        const reserved = resources.used?.[name] ?? 0;
        const used = measured?.used_mb ?? 0;
        const displayed = memory ? used : reserved;
        const ratio = capacity > 0 ? Math.max(0, Math.min(1, displayed / capacity)) : 0;
        return (
          <div key={name} className="resource" role="group" aria-label={resourceLabel(name)}>
            <div className="row-between small">
              <span className="resource-name">{resourceLabel(name)}</span>
              <span className="muted">
                {memory && !measured ? 'Usage unavailable' : `${amount(name, displayed)} / ${amount(name, capacity)}`}
              </span>
            </div>
            {(!memory || measured) && (
              <div className="progress" role="progressbar" aria-label={`${resourceLabel(name)} ${memory ? 'usage' : 'reserved slots'}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(ratio * 100)}>
                <div className={`progress-bar ${displayed > 0 ? 'progress-live' : ''}`} style={{ width: `${ratio * 100}%` }} />
              </div>
            )}
            <div className="small muted">
              {measured && <div>Whole PC · {amount(name, measured.available_mb)} available</div>}
              <div>{amount(name, reserved)} reserved by lazy_bird (limit {amount(name, resources.capacity[name] ?? 0)})</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
