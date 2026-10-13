import { useMemo, useState } from 'react';
import { ApiError } from '@/api/client';
import { complete, engineApi } from '@/api/endpoints/engines';
import type { SettingsValues } from '@/core/fields/types';
import type { CompletionOut, EngineKind, EngineOut, PresetOut } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';
import { useDialogs } from '@/ui/dialogContext';
import { SearchInput } from '@/ui/SearchInput';

const TEXT: Record<EngineKind, { title: string; description: string }> = {
  embedding: {
    title: 'Embedding',
    description: 'Embedding turns files into vectors for semantic search. The default preset embeds every file; changing it embeds them again.',
  },
  cross_encoder: {
    title: 'Cross-encoder',
    description: 'Cross-encoders rerank search results: they read the question together with each candidate passage and score how well it answers. Search uses the default preset unless you choose another.',
  },
  inference: {
    title: 'Inference',
    description: 'Inference presets are the language models agents answer with. Agents use the default preset unless they choose another one.',
  },
};

interface Draft {
  id: number | null;
  name: string;
  engineId: number | null;
  kwargs: SettingsValues;
  formKey: number;
}

function PresetEditor({
  kind,
  draft,
  engines,
  initialErrors,
  onClose,
  onSaved,
}: {
  kind: EngineKind;
  draft: Draft;
  engines: EngineOut[];
  initialErrors: Record<string, string>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const api = useMemo(() => engineApi(kind), [kind]);
  const toast = useToast();
  const [current, setCurrent] = useState(draft);
  const [errors, setErrors] = useState(initialErrors);
  const [saving, setSaving] = useState(false);
  const engine = engines.find((item) => item.id === current.engineId);

  const save = async () => {
    if (current.engineId == null) return;
    setSaving(true);
    setErrors({});
    try {
      const changes = { name: current.name.trim(), engine_id: current.engineId, kwargs: current.kwargs };
      if (current.id == null) await api.createPreset(changes);
      else await api.updatePreset(current.id, changes);
      toast.show(current.id == null ? 'Preset created' : 'Preset saved');
      onSaved();
    } catch (reason) {
      if (reason instanceof ApiError && Object.keys(reason.fieldErrors).length > 0) setErrors(reason.fieldErrors);
      else toast.error(reason);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      title={current.id == null ? 'New preset' : `Edit “${draft.name}”`}
      subtitle="A preset is a named configuration of an engine."
      onClose={onClose}
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !current.name.trim() || current.engineId == null}>
            {saving ? 'Saving…' : 'Save preset'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label" htmlFor="preset-name">
          Name
        </label>
        <input id="preset-name" className="form-input" value={current.name} onChange={(event) => setCurrent({ ...current, name: event.target.value })} autoFocus />
        {errors.name && <div className="form-error">{errors.name}</div>}
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor="preset-engine">
          Engine
        </label>
        <select
          id="preset-engine"
          className="form-input"
          value={current.engineId ?? ''}
          onChange={(event) => setCurrent({ ...current, engineId: Number(event.target.value), kwargs: {}, formKey: Date.now() })}
        >
          {engines.map((item) => (
            <option key={item.id} value={item.id} disabled={!item.available}>
              {item.name}
              {item.available ? '' : ' (unavailable)'}
            </option>
          ))}
        </select>
        {engine && engine.formats.length > 0 && <div className="form-hint">Works with models in {engine.formats.join(', ')} format.</div>}
        {engine?.local && <div className="form-hint">Runs the model on this computer: it is loaded into memory while it is used.</div>}
      </div>
      {engine && (
        <section className="form-section">
          <h3 className="form-section-title">Settings</h3>
          <SettingsForm
            key={`${current.formKey}-${engine.id}`}
            kwargsKey={engine.kwargs_key}
            values={current.kwargs}
            errors={errors}
            onChange={(kwargs) => setCurrent((value) => ({ ...value, kwargs }))}
          />
        </section>
      )}
    </Drawer>
  );
}

function TryInference({ presets }: { presets: PresetOut[] }) {
  const [presetId, setPresetId] = useState<number | ''>('');
  const [prompt, setPrompt] = useState('Say hello in one sentence.');
  const [result, setResult] = useState<CompletionOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await complete(prompt, presetId === '' ? undefined : presetId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Try a preset</h2>
          <p className="card-description">Send one prompt to check that a model answers.</p>
        </div>
      </div>
      <div className="card-body stack">
        <div className="form-row">
          <select className="form-input" value={presetId} onChange={(event) => setPresetId(event.target.value ? Number(event.target.value) : '')} aria-label="Preset to try">
            <option value="">Default preset</option>
            {presets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.name}
              </option>
            ))}
          </select>
        </div>
        <textarea className="form-textarea" rows={2} value={prompt} onChange={(event) => setPrompt(event.target.value)} aria-label="Prompt" />
        <div>
          <button type="button" className="btn btn-secondary" onClick={run} disabled={busy || !prompt.trim()}>
            {busy ? <span className="spinner" /> : <Icon name="play" />} {busy ? 'Waiting for the model…' : 'Send'}
          </button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        {result && (
          <div className="try-result">
            <div className="try-result-text">{result.content}</div>
            <div className="muted small">{[result.model, result.usage?.total_tokens ? `${String(result.usage.total_tokens)} tokens` : null].filter(Boolean).join(' · ')}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export function EnginePresets({ kind }: { kind: EngineKind }) {
  const dialogs = useDialogs();
  const [search, setSearch] = useState('');
  const api = useMemo(() => engineApi(kind), [kind]);
  const toast = useToast();
  const data = useResource(() => Promise.all([api.listEngines(), api.listPresets()]).then(([engines, presets]) => ({ engines, presets })), [kind]);
  const [editing, setEditing] = useState<{ draft: Draft; errors: Record<string, string> } | null>(null);
  const engines = data.data?.engines ?? [];
  const text = TEXT[kind];

  const act = async (action: () => Promise<unknown>, done?: string) => {
    try {
      await action();
      if (done) toast.show(done);
      await data.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const create = () => {
    const engine = engines.find((item) => item.available) ?? engines[0];
    setEditing({ draft: { id: null, name: '', engineId: engine?.id ?? null, kwargs: {}, formKey: Date.now() }, errors: {} });
  };
  const remove = async (preset: PresetOut) => {
    if (await dialogs.confirm({ title: `Delete ${preset.name}?`, message: 'Agents using this preset will need another one.', confirmLabel: 'Delete', danger: true })) await act(() => api.deletePreset(preset.id), 'Preset deleted');
  };

  return (
    <>
      <PageHeader
        title={text.title}
        description={text.description}
        actions={
          <button type="button" className="btn btn-primary" onClick={create} disabled={engines.length === 0}>
            <Icon name="plus" /> New preset
          </button>
        }
      />
      <SearchInput label={`Search ${text.title.toLowerCase()} presets`} value={search} onChange={setSearch} />
      <AsyncState
        {...data}
        onRetry={data.reload}
        isEmpty={(value) => value.presets.length === 0}
        empty={
          <>
            <div className="state-title">No preset yet</div>
            <p className="state-desc">
              {engines.length === 0 ? `No ${kind.replace('_', '-')} engine is installed.` : 'Create a preset to get started. The first one becomes the default.'}
            </p>
            {engines.length > 0 && (
              <button type="button" className="btn btn-primary btn-sm" onClick={create}>
                <Icon name="plus" /> New preset
              </button>
            )}
          </>
        }
      >
        {({ presets }) => (
          <div className="list">
            {presets.filter(preset => preset.name.toLowerCase().includes(search.toLowerCase())).map((preset) => {
              const engine = engines.find((item) => item.id === api.engineIdOf(preset));
              return (
                <div key={preset.id} className={`list-row ${preset.default ? 'is-highlighted' : ''}`}>
                  <div className="list-row-main">
                    <div className="list-row-title">
                      {preset.name}
                      {preset.default && <span className="chip chip-accent">default</span>}
                      {!preset.valid && <span className="chip chip-error">needs attention</span>}
                    </div>
                    <div className="list-row-meta">{engine?.name ?? 'Unknown engine'}</div>
                    {!preset.valid && (
                      <ul className="error-list">
                        {Object.entries(preset.errors).map(([field, message]) => (
                          <li key={field}>{field === '__root__' ? message : `${engine?.kwargs_key[field]?.title ?? field}: ${message}`}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="list-row-actions">
                    {!preset.default && (
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => act(() => api.updatePreset(preset.id, { default: true }), `${preset.name} is now the default`)}>
                        Make default
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() =>
                        setEditing({
                          draft: { id: preset.id, name: preset.name, engineId: api.engineIdOf(preset), kwargs: { ...preset.kwargs }, formKey: Date.now() },
                          errors: preset.errors,
                        })
                      }
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-icon btn-sm"
                      aria-label={`Delete ${preset.name}`}
                      onClick={() => void remove(preset)}
                    >
                      <Icon name="trash" />
                    </button>
                  </div>
                </div>
              );
            })}
            {search && !presets.some(preset => preset.name.toLowerCase().includes(search.toLowerCase())) && <div className="state-empty">No matching presets.</div>}
          </div>
        )}
      </AsyncState>
      {kind === 'inference' && (data.data?.presets.length ?? 0) > 0 && <TryInference presets={data.data!.presets} />}
      {editing && (
        <PresetEditor
          kind={kind}
          draft={editing.draft}
          engines={engines}
          initialErrors={editing.errors}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void data.reload();
          }}
        />
      )}
    </>
  );
}
