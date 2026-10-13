import { useEffect, useRef, useState } from 'react';
import { models as modelsApi } from '@/api/endpoints/models';
import { useTaskStore } from '@/core/tasks/store';
import type { LLMModel } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { SearchInput } from '@/ui/SearchInput';
import { useToast } from '@/ui/toastContext';
import { AddModel } from './AddModel';

function ModelSettings({ model, onClose, onSaved }: { model: LLMModel; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(model.name);
  const [format, setFormat] = useState(model.selected_format ?? model.formats[0] ?? '');
  const [file, setFile] = useState(model.selected_file ?? '');
  const [context, setContext] = useState(model.selected_context?.toString() ?? '');
  const candidates = model.files[format] ?? [];

  const save = async () => {
    try {
      await modelsApi.update(model.id, {
        name: name.trim() || model.name,
        selected_format: format || undefined,
        selected_file: candidates.length > 1 && file ? file : undefined,
        selected_context: context ? Number(context) : null,
      });
      toast.show('Model saved');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title={model.name}
      subtitle={model.hf_path}
      onClose={onClose}
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={save}>
            Save
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label" htmlFor="model-name">
          Name
        </label>
        <input id="model-name" className="form-input" value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      {model.formats.length > 0 && (
        <div className="form-group">
          <label className="form-label" htmlFor="model-format">
            Weight format
          </label>
          <select id="model-format" className="form-input" value={format} onChange={(event) => setFormat(event.target.value)}>
            {model.formats.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <div className="form-hint">Engines only load the formats they support.</div>
        </div>
      )}
      {candidates.length > 1 && (
        <div className="form-group">
          <label className="form-label" htmlFor="model-file">
            Weight file
          </label>
          <select id="model-file" className="form-input form-mono" value={file} onChange={(event) => setFile(event.target.value)}>
            <option value="">Choose…</option>
            {candidates.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="form-group">
        <label className="form-label" htmlFor="model-context">
          Context length
        </label>
        <input
          id="model-context"
          type="number"
          min={1}
          max={model.max_context_length ?? undefined}
          className="form-input"
          value={context}
          placeholder={model.max_context_length ? `Up to ${model.max_context_length}` : 'Model default'}
          onChange={(event) => setContext(event.target.value)}
        />
        <div className="form-hint">Lower values use less memory.</div>
      </div>
      <dl className="facts">
        <dt>Source</dt>
        <dd>{model.source}</dd>
        <dt>Stored in</dt>
        <dd className="mono small" style={{ wordBreak: 'break-all' }}>
          {model.local_path}
        </dd>
        {model.dimension && (
          <>
            <dt>Vector size</dt>
            <dd>{model.dimension}</dd>
          </>
        )}
      </dl>
    </Drawer>
  );
}

function HubAccount() {
  const toast = useToast();
  const status = useResource(modelsApi.hubStatus, []);
  if (!status.data) return null;
  return (
    <div className={`account-strip ${status.data.authenticated ? '' : 'is-anonymous'}`}>
      <span className={`dot ${status.data.authenticated ? 'dot-success' : 'dot-muted'}`} />
      <span>{status.data.authenticated ? `Hugging Face: logged in as ${status.data.user}` : 'Hugging Face: not logged in (public models only)'}</span>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={() =>
          modelsApi
            .hubLogin()
            .then((next) => {
              status.setData(next);
              toast.show(next.authenticated ? `Logged in as ${next.user}` : 'Still not logged in: add a key named HuggingFace on the API keys page', next.authenticated ? 'success' : 'error');
            })
            .catch(toast.error)
        }
      >
        Log in again
      </button>
    </div>
  );
}

export function ModelsPage() {
  const [search, setSearch] = useState('');
  const toast = useToast();
  const dialogs = useDialogs();
  const list = useResource(() => modelsApi.list(), []);
  const { tasks } = useTaskStore();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<LLMModel | null>(null);
  const transfers = tasks.filter((task) => task.kind.startsWith('models.') && ['running', 'queued', 'paused'].includes(task.status));

  // Show models as soon as their download ends.
  const activeCount = useRef(transfers.length);
  useEffect(() => {
    if (transfers.length < activeCount.current) void list.reload();
    activeCount.current = transfers.length;
  }, [transfers.length, list]);

  const sync = async () => {
    try {
      const result = await modelsApi.sync();
      toast.show(`${result.added.length} added, ${result.refreshed.length} refreshed`);
      await list.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const remove = async (model: LLMModel) => {
    const choice = await dialogs.prompt({
      title: `Remove ${model.name}?`,
      label: 'What should be removed',
      confirmLabel: 'Remove',
      options: [
        { value: 'entry', label: 'Only the entry (keep the files in the cache)' },
        { value: 'files', label: 'The entry and its files' },
      ],
    });
    if (!choice) return;
    try {
      await modelsApi.remove(model.id, choice === 'files');
      toast.show('Model removed');
      await list.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="Models"
        description="Model weights used by the embedding and inference engines."
        actions={
          <>
            <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
              <Icon name="plus" /> Add a model
            </button>
            <button type="button" className="btn btn-ghost" onClick={sync} title="Register models already present in the Hugging Face cache">
              <Icon name="refresh" /> Rescan the cache
            </button>
          </>
        }
      />
      <HubAccount />
      <SearchInput label="Search models" value={search} onChange={setSearch} />
      {transfers.length > 0 && (
        <div className="list">
          {transfers.map((task) => (
            <div key={task.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  <span className="dot dot-live" /> {task.title}
                </div>
                <div className="task-progress">
                  <div className="progress">
                    <div className="progress-bar progress-live" style={{ width: `${Math.round((task.progress ?? 0) * 100)}%` }} />
                  </div>
                  <span className="small muted">{task.status === 'running' ? `${Math.round((task.progress ?? 0) * 100)}%` : task.status}</span>
                </div>
                {task.message && <div className="list-row-meta">{task.message}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
      <AsyncState
        {...list}
        onRetry={list.reload}
        empty={
          <>
            <div className="state-title">No model yet</div>
            <p className="state-desc">Add one from Hugging Face, e.g. sentence-transformers/all-MiniLM-L6-v2 for embedding.</p>
          </>
        }
      >
        {(models) => (
          <div className="list">
            {models.filter(model => `${model.name} ${model.hf_path} ${model.formats.join(' ')}`.toLowerCase().includes(search.toLowerCase())).map((model) => (
              <div key={model.id} className="list-row">
                <div className="list-row-main">
                  <div className="list-row-title">
                    {model.name}
                    {!model.available && <span className="chip chip-error">files missing</span>}
                    {model.source === 'local' && <span className="chip chip-outline">imported</span>}
                  </div>
                  <div className="list-row-meta">
                    <span className="mono">{model.hf_path}</span>
                    {model.size_mb !== null && ` · ${model.size_mb >= 1024 ? `${(model.size_mb / 1024).toFixed(1)} GB` : `${Math.round(model.size_mb)} MB`}`}
                    {model.selected_context && ` · context ${model.selected_context}`}
                  </div>
                  <div className="row" style={{ flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {model.formats.map((format) => (
                      <span key={format} className={`chip ${format === model.selected_format ? 'chip-accent' : 'chip-outline'}`} title={format === model.selected_format ? 'Selected format' : undefined}>
                        {format}
                      </span>
                    ))}
                    {model.selected_file && <span className="chip chip-outline mono">{model.selected_file}</span>}
                  </div>
                </div>
                <div className="list-row-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(model)}>
                    Settings
                  </button>
                  <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => remove(model)} aria-label={`Remove ${model.name}`}>
                    <Icon name="trash" />
                  </button>
                </div>
              </div>
            ))}
            {search && !models.some(model => `${model.name} ${model.hf_path} ${model.formats.join(' ')}`.toLowerCase().includes(search.toLowerCase())) && <div className="state-empty">No matching models.</div>}
          </div>
        )}
      </AsyncState>
      {adding && <AddModel onClose={() => setAdding(false)} onQueued={() => setAdding(false)} />}
      {editing && (
        <ModelSettings
          model={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void list.reload();
          }}
        />
      )}
    </>
  );
}
