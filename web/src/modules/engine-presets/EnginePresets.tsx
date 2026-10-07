import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError } from '@/api/client';
import { engineApi } from '@/api/endpoints/engines';
import type { SettingsValues } from '@/core/fields/types';
import type { EngineKind, EngineOut, PresetOut } from '@/core/types/api';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';

const DESCRIPTIONS: Record<EngineKind, string> = {
  embedding: 'The default preset embeds uploaded files and answers semantic searches.',
  inference: 'The default preset answers chats of agents that do not choose their own preset.',
};

interface Draft {
  id: number | null;
  name: string;
  engineId: number | null;
  kwargs: SettingsValues;
  /** Changes when another preset is loaded, to rebuild the settings form. */
  formKey: number;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function EnginePresets({ kind }: { kind: EngineKind }) {
  const api = useMemo(() => engineApi(kind), [kind]);
  const [engines, setEngines] = useState<EngineOut[]>([]);
  const [presets, setPresets] = useState<PresetOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [engineList, presetList] = await Promise.all([api.listEngines(), api.listPresets()]);
      setEngines(engineList);
      setPresets(presetList);
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const engineById = useMemo(() => new Map(engines.map((engine) => [engine.id, engine])), [engines]);
  const draftEngine = draft?.engineId != null ? engineById.get(draft.engineId) : undefined;

  const startCreate = () => {
    const firstAvailable = engines.find((engine) => engine.available);
    setFieldErrors({});
    setDraft({ id: null, name: '', engineId: firstAvailable?.id ?? null, kwargs: {}, formKey: Date.now() });
  };

  const startEdit = (preset: PresetOut) => {
    setFieldErrors(preset.errors);
    setDraft({ id: preset.id, name: preset.name, engineId: api.engineIdOf(preset), kwargs: { ...preset.kwargs }, formKey: Date.now() });
  };

  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  };

  const save = async () => {
    if (!draft || draft.engineId == null) return;
    setSaving(true);
    setFieldErrors({});
    try {
      if (draft.id == null) {
        await api.createPreset({ name: draft.name.trim(), engine_id: draft.engineId, kwargs: draft.kwargs });
      } else {
        await api.updatePreset(draft.id, { name: draft.name.trim(), engine_id: draft.engineId, kwargs: draft.kwargs });
      }
      setDraft(null);
      await reload();
    } catch (reason) {
      if (reason instanceof ApiError && Object.keys(reason.fieldErrors).length > 0) {
        setFieldErrors(reason.fieldErrors);
      } else {
        setError(errorMessage(reason));
      }
    } finally {
      setSaving(false);
    }
  };

  const title = kind === 'embedding' ? 'Embedding presets' : 'Inference presets';

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">{title}</h2>
            <p className="card-description">
              A preset is a named configuration of an engine. {DESCRIPTIONS[kind]}
            </p>
          </div>
          <button type="button" className="btn btn-primary btn-sm" onClick={startCreate} disabled={engines.length === 0}>
            + New preset
          </button>
        </div>

        <div className="card-body preset-body">
          {error && (
            <div className="alert alert-error" role="alert">
              <div style={{ flex: 1 }}>{error}</div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setError(null)} aria-label="Dismiss">✕</button>
            </div>
          )}

          {loading ? (
            <div className="state-loading">
              <span className="spinner" />
              <div className="state-title">Loading presets…</div>
            </div>
          ) : presets.length === 0 && !draft ? (
            <div className="state-empty">
              <div className="state-title">No preset yet</div>
              <p className="state-desc">
                {engines.length === 0
                  ? `No ${kind} engine is installed.`
                  : `Create a preset to start using ${kind}. The first preset becomes the default.`}
              </p>
            </div>
          ) : (
            <ul className="preset-list">
              {presets.map((preset) => {
                const engine = engineById.get(api.engineIdOf(preset));
                return (
                  <li key={preset.id} className={`preset-item${preset.default ? ' is-default' : ''}`}>
                    <div className="preset-main">
                      <span className="preset-name">{preset.name}</span>
                      <span className="badge badge-muted">{engine?.name ?? 'unknown engine'}</span>
                      {preset.default && <span className="badge badge-success">Default</span>}
                      {!preset.valid && <span className="badge badge-error">Needs attention</span>}
                    </div>
                    {!preset.valid && (
                      <ul className="preset-errors">
                        {Object.entries(preset.errors).map(([field, message]) => (
                          <li key={field}>
                            {field === '__root__' ? message : `${engine?.kwargs_key[field]?.title ?? field}: ${message}`}
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="preset-actions">
                      {!preset.default && (
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => run(() => api.updatePreset(preset.id, { default: true }))}>
                          Make default
                        </button>
                      )}
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => startEdit(preset)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm preset-delete"
                        onClick={() => {
                          if (window.confirm(`Delete the preset "${preset.name}"?`)) void run(() => api.deletePreset(preset.id));
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {draft && (
            <form
              className="preset-editor"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <h3 className="preset-editor-title">{draft.id == null ? 'New preset' : `Edit “${draft.name}”`}</h3>
              <div className="preset-editor-row">
                <div className="form-group">
                  <label className="form-label" htmlFor="preset-name">Name</label>
                  <input
                    id="preset-name"
                    className="form-input"
                    value={draft.name}
                    required
                    onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                  />
                  {fieldErrors.name && <div className="form-error">{fieldErrors.name}</div>}
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="preset-engine">Engine</label>
                  <select
                    id="preset-engine"
                    className="form-select"
                    value={draft.engineId ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, engineId: Number(event.target.value), kwargs: {}, formKey: Date.now() })
                    }
                  >
                    {engines.map((engine) => (
                      <option key={engine.id} value={engine.id} disabled={!engine.available}>
                        {engine.name}{engine.available ? '' : ' (unavailable)'}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {draftEngine && (
                <SettingsForm
                  key={`${draft.formKey}-${draftEngine.id}`}
                  kwargsKey={draftEngine.kwargs_key}
                  values={draft.kwargs}
                  errors={fieldErrors}
                  onChange={(kwargs) => setDraft((current) => (current ? { ...current, kwargs } : current))}
                />
              )}
              <div className="preset-editor-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving || !draft.name.trim() || draft.engineId == null}>
                  {saving ? 'Saving…' : 'Save preset'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
