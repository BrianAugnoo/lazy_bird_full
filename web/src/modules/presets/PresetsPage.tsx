import { useState, type ReactNode } from 'react';
import { ApiError } from '@/api/client';
import { agentPresets, hooks, instructions, sessionPresets, skills, tools } from '@/api/endpoints/extensions';
import type { AgentPresetData, ExtensionPreset, SessionPresetData } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { useRoute, useRouteActions } from '@/core/router';
import { libraryExtensions, librarySelection } from '@/core/library';
import { CallableField } from '@/modules/tools/CallableField';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { KeyValueEditor } from '@/ui/KeyValueEditor';
import { Drawer } from '@/ui/Modal';
import { MultiSelect } from '@/ui/MultiSelect';
import { PageHeader } from '@/ui/PageHeader';
import { LibraryBrowser } from '@/ui/LibraryBrowser';
import { SearchInput } from '@/ui/SearchInput';
import { useToast } from '@/ui/toastContext';

type Kind = 'agent' | 'session';
type Data = AgentPresetData | SessionPresetData;

const API = { agent: agentPresets, session: sessionPresets } as const;

const TEXT: Record<Kind, { title: string; description: string; folder: string }> = {
  agent: {
    title: 'Agent presets',
    description: 'Ready-made agents: instructions, tools, skills, hooks and the sub-agents they direct. Add one to any session from the chat.',
    folder: 'agents/agent_preset',
  },
  session: {
    title: 'Session presets',
    description: 'Ready-made teams: the agents a new session starts with, which one you talk to, and the values their tools read.',
    folder: 'agents/session_preset',
  },
};

const NAME_HINT = 'Letters, digits, “-”, “_” and “.”. It is also the file name, so it cannot be changed later.';

function loadOptions() {
  return Promise.all([tools.list(), hooks.list(), skills.list(), instructions.list('full'), instructions.list('sub'), agentPresets.list()]).then(
    ([toolList, hookList, skillList, fulls, subs, agents]) => ({ toolList, hookList, skillList, fulls, subs, agents }),
  );
}

type Options = Awaited<ReturnType<typeof loadOptions>>;

function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {children}
      {hint && <div className="form-hint">{hint}</div>}
      {error && <div className="form-error">{error}</div>}
    </div>
  );
}

function AgentFields({ data, set, options, selfId, readOnly, errors }: { data: AgentPresetData; set: (data: AgentPresetData) => void; options: Options; selfId: string | null; readOnly: boolean; errors: Record<string, string> }) {
  const list = (key: keyof AgentPresetData) => ((data[key] as string[] | undefined) ?? []);
  const select = (key: keyof AgentPresetData, items: Array<{ value: string; label: string; description?: string }>, empty: string) =>
    readOnly ? (
      <div className="row" style={{ flexWrap: 'wrap', gap: 4 }}>
        {list(key).length ? list(key).map((value) => <span key={value} className="chip chip-outline mono">{value}</span>) : <span className="muted small">None</span>}
      </div>
    ) : (
      <MultiSelect options={items} value={list(key)} onChange={(value) => set({ ...data, [key]: value })} emptyText={empty} />
    );
  return (
    <>
      <section className="form-section">
        <h3 className="form-section-title">Instructions</h3>
        <Field label="Base instructions" error={errors.instruction_fulls}>
          {select('instruction_fulls', options.fulls.map((item) => ({ value: item.id, label: item.name, description: item.extension })), 'No instructions installed.')}
        </Field>
        <Field label="Additions" error={errors.instruction_subs}>
          {select('instruction_subs', options.subs.map((item) => ({ value: item.id, label: item.name, description: item.extension })), 'No additions installed.')}
        </Field>
      </section>
      <section className="form-section">
        <h3 className="form-section-title">Abilities</h3>
        <Field label="Tools" error={errors.tools}>
          <CallableField kind="tools" items={options.toolList} value={list('tools')} onChange={readOnly ? undefined : (tools) => set({ ...data, tools })} emptyText="No tools installed." />
        </Field>
        <Field label="Skills" error={errors.skills}>
          {select('skills', options.skillList.map((item) => ({ value: item.id, label: item.name, description: item.description })), 'No skills installed.')}
        </Field>
        <Field label="Hooks" error={errors.hooks}>
          <CallableField kind="hooks" items={options.hookList} value={list('hooks')} onChange={readOnly ? undefined : (hooks) => set({ ...data, hooks })} emptyText="No hooks installed." />
        </Field>
      </section>
      <section className="form-section">
        <h3 className="form-section-title">Team</h3>
        <Field label="Sub-agents" hint="Agent presets this agent directs; they are created with it." error={errors.sub_agents}>
          {select(
            'sub_agents',
            options.agents.filter((item) => item.id !== selfId).map((item) => ({ value: item.id, label: item.name, description: item.data?.description })),
            'No other agent preset.',
          )}
        </Field>
      </section>
    </>
  );
}

function SessionFields({ data, set, options, readOnly, errors }: { data: SessionPresetData; set: (data: SessionPresetData) => void; options: Options; readOnly: boolean; errors: Record<string, string> }) {
  return (
    <section className="form-section">
      <h3 className="form-section-title">Team</h3>
      <Field label="Agents" hint="Created in every new session made from this preset." error={errors.agents}>
        {readOnly ? (
          <div className="row" style={{ flexWrap: 'wrap', gap: 4 }}>
            {data.agents.map((value) => (
              <span key={value} className="chip chip-outline mono">
                {value}
              </span>
            ))}
          </div>
        ) : (
          <MultiSelect
            options={options.agents.map((item) => ({ value: item.id, label: item.name, description: item.data?.description }))}
            value={data.agents}
            onChange={(agents) => set({ ...data, agents, master: agents.includes(data.master) ? data.master : (agents[0] ?? '') })}
            emptyText="Create an agent preset first."
          />
        )}
      </Field>
      <Field label="Master" hint="The agent receiving your messages." error={errors.master}>
        <select className="form-input" value={data.master} disabled={readOnly} onChange={(event) => set({ ...data, master: event.target.value })}>
          {data.agents.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Shared values" hint="Values the tools of the session read (copied into each new session)." error={errors.meta}>
        {readOnly ? (
          <pre className="code">{JSON.stringify(data.meta ?? {}, null, 2)}</pre>
        ) : (
          <KeyValueEditor value={data.meta ?? {}} onChange={(meta) => set({ ...data, meta })} />
        )}
      </Field>
    </section>
  );
}

function PresetEditor({ kind, preset, onClose, onSaved }: { kind: Kind; preset: ExtensionPreset<Data> | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const dialogs = useDialogs();
  const options = useResource(loadOptions, []);
  const empty: Data = kind === 'agent' ? { name: '', description: '' } : { name: '', description: '', agents: [], master: '', meta: {} };
  const [data, setData] = useState<Data>(preset?.data ?? { ...empty, name: preset?.name ?? '' });
  const [errors, setErrors] = useState<Record<string, string>>(preset?.errors ?? {});
  const readOnly = Boolean(preset && !preset.editable);
  const api = API[kind];

  const save = async () => {
    setErrors({});
    try {
      if (preset) await (api.update as (id: string, data: Data) => Promise<unknown>)(preset.id, data);
      else await (api.create as (data: Data) => Promise<unknown>)({ ...data, name: data.name.trim() });
      toast.show('Preset saved');
      onSaved();
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    }
  };

  const duplicate = async () => {
    const name = await dialogs.prompt({ title: 'Duplicate as custom', label: 'Name of the copy', initial: `${data.name}-custom`, hint: NAME_HINT, confirmLabel: 'Duplicate' });
    if (!name) return;
    try {
      await (api.create as (data: Data) => Promise<unknown>)({ ...data, name });
      toast.show('Copy created');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const remove = async () => {
    if (!preset || !(await dialogs.confirm({ title: `Delete ${preset.name}?`, message: 'Sessions and agents already created from it are kept.', confirmLabel: 'Delete', danger: true }))) return;
    try {
      await api.remove(preset.id);
      toast.show('Preset deleted');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title={preset ? preset.name : `New ${kind} preset`}
      subtitle={preset ? `${preset.id}${readOnly ? ' · built-in, read-only' : ''}` : TEXT[kind].description}
      onClose={onClose}
      footer={
        <>
          {preset?.editable && (
            <button type="button" className="btn btn-danger-text" onClick={remove}>
              Delete
            </button>
          )}
          {readOnly && preset?.data && (
            <button type="button" className="btn btn-secondary" onClick={duplicate}>
              <Icon name="copy" /> Duplicate as custom
            </button>
          )}
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {readOnly ? 'Close' : 'Cancel'}
          </button>
          {!readOnly && (
            <button type="button" className="btn btn-primary" onClick={save} disabled={!data.name.trim()}>
              Save
            </button>
          )}
        </>
      }
    >
      {preset && !preset.valid && <div className="alert alert-warning">This preset refers to missing items: {Object.values(preset.errors).join(' ')}</div>}
      {errors.__root__ && <div className="alert alert-error">{errors.__root__}</div>}
      {!preset && (
        <Field label="Name" hint={NAME_HINT} error={errors.name}>
          <input className="form-input form-mono" value={data.name} onChange={(event) => setData({ ...data, name: event.target.value })} autoFocus />
        </Field>
      )}
      <Field label="Description" error={errors.description}>
        <textarea className="form-textarea" rows={2} value={data.description ?? ''} readOnly={readOnly} onChange={(event) => setData({ ...data, description: event.target.value })} />
      </Field>
      <AsyncState {...options} onRetry={options.reload}>
        {(loaded) =>
          kind === 'agent' ? (
            <AgentFields data={data as AgentPresetData} set={setData} options={loaded} selfId={preset?.id ?? null} readOnly={readOnly} errors={errors} />
          ) : (
            <SessionFields data={data as SessionPresetData} set={setData} options={loaded} readOnly={readOnly} errors={errors} />
          )
        }
      </AsyncState>
    </Drawer>
  );
}

export function PresetsPage({ kind }: { kind: Kind }) {
  const { params } = useRoute();
  const { setParams } = useRouteActions();
  const list = useResource(() => (API[kind].list as () => Promise<ExtensionPreset<Data>[]>)(), [kind]);
  const [open, setOpen] = useState<{ preset: ExtensionPreset<Data> | null } | null>(null);
  const text = TEXT[kind];
  const [search, setSearch] = useState('');
  const extension = librarySelection(list.data ?? [], params.extension);

  return (
    <>
      <PageHeader
        title={text.title}
        description={text.description}
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setOpen({ preset: null })}>
            <Icon name="plus" /> New preset
          </button>
        }
      />
      <AsyncState {...list} onRetry={list.reload} isEmpty={() => false}>
        {(items) => (
          <LibraryBrowser label={`${kind === 'agent' ? 'Agent' : 'Session'} preset extensions`} extensions={libraryExtensions(items)} active={extension} onSelect={extension => setParams({ extension })}>
          <SearchInput label={`Search ${kind} presets`} value={search} onChange={setSearch} />
          <div className="card-grid">
            {items.filter(preset => preset.extension === extension && `${preset.name} ${preset.data?.description ?? ''}`.toLowerCase().includes(search.toLowerCase())).map((preset) => (
              <button key={preset.id} type="button" className="item-card" onClick={() => setOpen({ preset })}>
                <span className="item-card-title">
                  <Icon name={kind === 'agent' ? 'agents' : 'team'} size={16} /> {preset.name}
                  <span className={`chip ${preset.editable ? 'chip-accent' : 'chip-outline'}`}>{preset.editable ? 'custom' : preset.extension}</span>
                  {!preset.valid && <span className="chip chip-error">broken</span>}
                </span>
                <span className="item-card-desc">{preset.data?.description || (preset.valid ? 'No description' : Object.values(preset.errors).join(' '))}</span>
                {kind === 'session' && preset.data && <span className="muted small">{(preset.data as SessionPresetData).agents.length} agents</span>}
                {kind === 'agent' && preset.data && (
                  <span className="muted small">
                    {[
                      (preset.data as AgentPresetData).tools?.length ? `${(preset.data as AgentPresetData).tools!.length} tools` : null,
                      (preset.data as AgentPresetData).sub_agents?.length ? `${(preset.data as AgentPresetData).sub_agents!.length} sub-agents` : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                )}
              </button>
            ))}
          </div>
          {!items.some(preset => preset.extension === extension && `${preset.name} ${preset.data?.description ?? ''}`.toLowerCase().includes(search.toLowerCase())) && <div className="state-empty">{search ? 'No matching presets.' : `No presets in ${extension}.`}</div>}
          </LibraryBrowser>
        )}
      </AsyncState>
      {open && (
        <PresetEditor
          kind={kind}
          preset={open.preset}
          onClose={() => setOpen(null)}
          onSaved={() => {
            setOpen(null);
            void list.reload();
          }}
        />
      )}
    </>
  );
}
