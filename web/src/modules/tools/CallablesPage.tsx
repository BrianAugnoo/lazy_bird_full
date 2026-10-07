import { useMemo, useState } from 'react';
import { ApiError } from '@/api/client';
import { callableApi } from '@/api/endpoints/extensions';
import type { SettingsValues } from '@/core/fields/types';
import type { CallableItem, ModuleSettings } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

type Kind = 'tools' | 'hooks';

const TEXT: Record<Kind, { title: string; description: string; folder: string }> = {
  tools: {
    title: 'Tools',
    description: 'Functions agents can call. Each Python file of agents/tools/{extension}/ is a module; add or change files on disk, then reload.',
    folder: 'agents/tools',
  },
  hooks: {
    title: 'Hooks',
    description: 'Functions run before every call to the model, e.g. to add context or shorten long conversations. Files live in agents/hook/{extension}/.',
    folder: 'agents/hook',
  },
};

interface Schema {
  properties?: Record<string, { type?: string; description?: string; enum?: unknown[] }>;
  required?: string[];
}

function Parameters({ item }: { item: CallableItem }) {
  const schema = ((item.parameters as { function?: { parameters?: Schema } } | null)?.function?.parameters ?? item.parameters) as Schema | null;
  const properties = Object.entries(schema?.properties ?? {});
  if (properties.length === 0) return null;
  return (
    <ul className="param-list">
      {properties.map(([name, spec]) => (
        <li key={name}>
          <span className="mono">{name}</span>
          <span className="muted small">
            {' '}
            {spec.type ?? 'any'}
            {schema?.required?.includes(name) ? '' : ', optional'}
          </span>
          {spec.description && <span className="small"> — {spec.description}</span>}
        </li>
      ))}
    </ul>
  );
}

function ModuleSettingsEditor({ kind, settings, onClose, onSaved }: { kind: Kind; settings: ModuleSettings; onClose: () => void; onSaved: (next: ModuleSettings) => void }) {
  const api = useMemo(() => callableApi(kind), [kind]);
  const toast = useToast();
  const [values, setValues] = useState<SettingsValues>({ ...settings.kwargs });
  const [errors, setErrors] = useState<Record<string, string>>(settings.errors ?? {});

  const save = async () => {
    try {
      const next = await api.saveSettings(settings.file_path, values);
      toast.show('Settings saved');
      onSaved(next);
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title="Settings"
      subtitle={<span className="mono">{settings.file_path}</span>}
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
      <p className="form-hint">These settings are shared by every agent using this module.</p>
      <SettingsForm kwargsKey={settings.kwargs_key} values={values} errors={errors} onChange={setValues} />
    </Drawer>
  );
}

function load(kind: Kind) {
  const api = callableApi(kind);
  return Promise.all([api.list(), api.settings()]).then(([items, settings]) => ({ items, settings }));
}

export function CallablesPage({ kind }: { kind: Kind }) {
  const api = useMemo(() => callableApi(kind), [kind]);
  const toast = useToast();
  const data = useResource(() => load(kind), [kind]);
  const [editing, setEditing] = useState<ModuleSettings | null>(null);
  const text = TEXT[kind];

  const modules = useMemo(() => {
    const groups = new Map<string, CallableItem[]>();
    for (const item of data.data?.items ?? []) groups.set(item.file_path, [...(groups.get(item.file_path) ?? []), item]);
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data.data]);

  const reload = async () => {
    try {
      const items = await api.reload();
      data.setData((current) => (current ? { ...current, items } : current));
      await data.reload();
      toast.show(`${items.length} ${kind} found`);
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title={text.title}
        description={text.description}
        actions={
          <button type="button" className="btn btn-secondary" onClick={reload}>
            <Icon name="refresh" /> Reload from disk
          </button>
        }
      />
      <AsyncState
        {...data}
        onRetry={data.reload}
        isEmpty={(value) => value.items.length === 0}
        empty={
          <>
            <div className="state-title">No {kind} installed</div>
            <p className="state-desc">
              Add a Python file in <span className="mono">{text.folder}/custom/</span> and reload.
            </p>
          </>
        }
      >
        {({ settings }) => (
          <div className="stack">
            {modules.map(([filePath, items]) => {
              const moduleSettings = settings.find((entry) => entry.file_path === filePath);
              const configurable = moduleSettings && Object.keys(moduleSettings.kwargs_key).length > 0;
              return (
                <div key={filePath} className="card">
                  <div className="card-header">
                    <div>
                      <h2 className="card-title mono">{filePath}</h2>
                      <p className="card-description">
                        <span className="chip chip-outline">{items[0].extension}</span> {items.length} {items.length === 1 ? kind.slice(0, -1) : kind}
                      </p>
                    </div>
                    {configurable && (
                      <div className="row">
                        {!moduleSettings.valid && <span className="chip chip-warning">needs settings</span>}
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(moduleSettings)}>
                          <Icon name="settings" /> Settings
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="card-body callable-list">
                    {items.map((item) => (
                      <div key={item.id} className="callable">
                        <div className="callable-head">
                          <span className="callable-name">{item.name}</span>
                          <span className="mono muted small">{item.id}</span>
                        </div>
                        {item.description && <p className="callable-description">{item.description}</p>}
                        {kind === 'tools' && <Parameters item={item} />}
                        {(item.meta_params.length > 0 || item.accepts_any_meta) && (
                          <div className="small muted">
                            Reads session values:{' '}
                            {item.accepts_any_meta
                              ? 'all of them'
                              : item.meta_params.map((name) => (
                                  <span key={name} className={`chip ${item.required_meta.includes(name) ? 'chip-warning' : 'chip-outline'}`} title={item.required_meta.includes(name) ? 'Required' : 'Optional'}>
                                    {name}
                                  </span>
                                ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </AsyncState>
      {editing && (
        <ModuleSettingsEditor
          kind={kind}
          settings={editing}
          onClose={() => setEditing(null)}
          onSaved={(next) => {
            setEditing(null);
            data.setData((current) => (current ? { ...current, settings: current.settings.map((entry) => (entry.file_path === next.file_path ? next : entry)) } : current));
          }}
        />
      )}
    </>
  );
}
