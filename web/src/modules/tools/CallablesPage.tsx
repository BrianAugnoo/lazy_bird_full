import { useMemo, useState } from 'react';
import { ApiError } from '@/api/client';
import { callableApi } from '@/api/endpoints/extensions';
import type { SettingsValues } from '@/core/fields/types';
import { setParams, useRoute } from '@/core/router';
import type { CallableItem, ModuleSettings } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';
import { groupByExtension, type CallableKind as Kind, type CallableModule } from './catalog';
import { ExtensionNav } from './ExtensionNav';

const TEXT: Record<Kind, { title: string; description: string; folder: string }> = {
  tools: {
    title: 'Tools',
    description: 'Functions agents can call, by extension (a folder of agents/tools/) and module (a Python file in it). Add or change files on disk, then reload.',
    folder: 'agents/tools',
  },
  hooks: {
    title: 'Hooks',
    description: 'Functions run before every call to the model, e.g. to add context or shorten long conversations, by extension (a folder of agents/hook/) and module.',
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

function CallableEntry({ kind, item }: { kind: Kind; item: CallableItem }) {
  return (
    <div className="callable">
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
  );
}

/** One module (Python file) of an extension: its tools or hooks and its settings. */
function ModuleSection({ kind, module, settings, onSettings }: { kind: Kind; module: CallableModule; settings: ModuleSettings | undefined; onSettings: (settings: ModuleSettings) => void }) {
  const configurable = settings && Object.keys(settings.kwargs_key).length > 0;
  return (
    <section className="card" aria-label={module.module}>
      <div className="card-header">
        <div>
          <h2 className="card-title mono">{module.module}</h2>
          <p className="card-description">
            <span className="mono">{module.filePath}</span> · {module.items.length} {module.items.length === 1 ? kind.slice(0, -1) : kind}
          </p>
        </div>
        {configurable && (
          <div className="row">
            {!settings.valid && <span className="chip chip-warning">needs settings</span>}
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onSettings(settings)}>
              <Icon name="settings" /> Settings
            </button>
          </div>
        )}
      </div>
      <div className="card-body callable-list">
        {module.items.map((item) => (
          <CallableEntry key={item.id} kind={kind} item={item} />
        ))}
      </div>
    </section>
  );
}

export function CallablesPage({ kind }: { kind: Kind }) {
  const api = useMemo(() => callableApi(kind), [kind]);
  const toast = useToast();
  const { params } = useRoute();
  const data = useResource(() => load(kind), [kind]);
  const [editing, setEditing] = useState<ModuleSettings | null>(null);
  const text = TEXT[kind];

  const extensions = useMemo(() => groupByExtension(data.data?.items ?? []), [data.data]);
  const current = extensions.find((entry) => entry.extension === params.extension) ?? extensions[0];

  const reload = async () => {
    try {
      const items = await api.reload();
      data.setData((loaded) => (loaded ? { ...loaded, items } : loaded));
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
      <AsyncState {...data} onRetry={data.reload} isEmpty={() => false}>
        {({ settings }) => (
          <div className="extension-browser">
            <ExtensionNav
              label={`${text.title} extensions`}
              extensions={extensions}
              active={current.extension}
              onSelect={(extension) => setParams({ extension: extension === extensions[0].extension ? null : extension })}
              badge={(entry) => entry.items.length}
            />
            <div className="stack">
              {current.modules.length === 0 && (
                <div className="state-empty">
                  <div className="state-title">
                    No {kind} in {current.extension}
                  </div>
                  <p className="state-desc">
                    Add a Python file in <span className="mono">{`${text.folder}/${current.extension}/`}</span> and reload.
                  </p>
                </div>
              )}
              {current.modules.map((module) => (
                <ModuleSection key={module.filePath} kind={kind} module={module} settings={settings.find((entry) => entry.file_path === module.filePath)} onSettings={setEditing} />
              ))}
            </div>
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
            data.setData((loaded) => (loaded ? { ...loaded, settings: loaded.settings.map((entry) => (entry.file_path === next.file_path ? next : entry)) } : loaded));
          }}
        />
      )}
    </>
  );
}
