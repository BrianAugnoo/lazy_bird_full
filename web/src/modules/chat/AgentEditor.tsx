import { useMemo, useState } from 'react';
import { ApiError } from '@/api/client';
import { agents as agentsApi } from '@/api/endpoints/agents';
import { engineApi } from '@/api/endpoints/engines';
import { hooks, instructions, skills, tools } from '@/api/endpoints/extensions';
import type { SettingsValues } from '@/core/fields/types';
import { buildHash } from '@/core/router';
import type { Agent, AgentFields, AgentInferenceMeta } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { CallableField } from '@/modules/tools/CallableField';
import { Drawer } from '@/ui/Modal';
import { MultiSelect } from '@/ui/MultiSelect';
import { useToast } from '@/ui/toastContext';
import { useDialogs } from '@/ui/dialogContext';
import { SearchInput } from '@/ui/SearchInput';

const inference = engineApi('inference');
const INFERENCE_KEYS = ['preset_inference_engine_id', 'inference_engine_id', 'inference_settings'];

interface AgentEditorProps {
  /** The agent to edit, or null to create one in `sessionId`. */
  agent: Agent | null;
  sessionId: number;
  sessionAgents: Agent[];
  onClose: () => void;
  onSaved: (agent: Agent) => void;
  onDeleted: (agentId: number) => void;
}

const blank: AgentFields = {
  name: '',
  description: '',
  instructions: '',
  instruction_fulls: [],
  instruction_subs: [],
  skills: [],
  tools: [],
  hooks: [],
  master: false,
  meta: null,
  sub_agents_ids: [],
};

function loadOptions() {
  return Promise.all([
    tools.list(),
    hooks.list(),
    skills.list(),
    instructions.list('full'),
    instructions.list('sub'),
    inference.listPresets(),
    inference.listEngines(),
  ]).then(([toolList, hookList, skillList, fulls, subs, presets, engines]) => ({ toolList, hookList, skillList, fulls, subs, presets, engines }));
}

/** Everything about one agent: model, instructions, tools, skills, hooks, sub-agents. */
export function AgentEditor({ agent, sessionId, sessionAgents, onClose, onSaved, onDeleted }: AgentEditorProps) {
  const dialogs = useDialogs();
  const toast = useToast();
  const options = useResource(loadOptions, []);
  const seen = useResource(() => (agent ? agentsApi.tools(agent.id) : Promise.resolve([])), [agent?.id]);
  const [draft, setDraft] = useState<AgentFields>(() => (agent ? { ...blank, ...agent } : { ...blank, master: sessionAgents.length === 0 }));
  const meta: AgentInferenceMeta = draft.meta ?? {};
  const [mode, setMode] = useState<'preset' | 'custom'>(meta.inference_engine_id ? 'custom' : 'preset');
  const [settingsKey, setSettingsKey] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [modelSearch, setModelSearch] = useState('');

  const set = <K extends keyof AgentFields>(key: K, value: AgentFields[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const setMeta = (changes: AgentInferenceMeta) => set('meta', { ...meta, ...changes });

  const presets = options.data?.presets ?? [];
  const engines = options.data?.engines ?? [];
  const defaultPreset = presets.find((preset) => preset.default);
  const engine = engines.find((item) => item.id === meta.inference_engine_id);

  const settingsErrors = useMemo(() => {
    const prefix = 'meta.inference_settings.';
    return Object.fromEntries(Object.entries(errors).filter(([key]) => key.startsWith(prefix)).map(([key, value]) => [key.slice(prefix.length), value]));
  }, [errors]);

  const payload = (): AgentFields => {
    const others = Object.fromEntries(Object.entries(meta).filter(([key]) => !INFERENCE_KEYS.includes(key)));
    const chosen: AgentInferenceMeta =
      mode === 'preset'
        ? meta.preset_inference_engine_id
          ? { preset_inference_engine_id: meta.preset_inference_engine_id }
          : {}
        : { inference_engine_id: meta.inference_engine_id ?? null, inference_settings: meta.inference_settings ?? {} };
    return { ...draft, meta: { ...others, ...chosen } };
  };

  const save = async () => {
    setSaving(true);
    setErrors({});
    try {
      const body = payload();
      const saved = agent ? await agentsApi.update(agent.id, body) : await agentsApi.create(sessionId, body);
      toast.show(agent ? 'Agent saved' : 'Agent created');
      onSaved(saved);
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!agent || !await dialogs.confirm({ title: `Delete ${agent.name}?`, message: 'Its conversations will be deleted too.', confirmLabel: 'Delete agent', danger: true })) return;
    try {
      await agentsApi.remove(agent.id);
      toast.show('Agent deleted');
      onDeleted(agent.id);
    } catch (reason) {
      toast.error(reason);
    }
  };

  const others = sessionAgents.filter((item) => item.id !== agent?.id);
  const opt = options.data;

  return (
    <Drawer
      title={agent ? agent.name : 'New agent'}
      subtitle={agent?.preset ? `Created from the preset ${agent.preset}` : 'Configure how this agent thinks and what it can do.'}
      onClose={onClose}
      footer={
        <>
          {agent && (
            <button type="button" className="btn btn-danger-text" onClick={remove}>
              Delete agent
            </button>
          )}
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !draft.name.trim()}>
            {saving ? 'Saving…' : agent ? 'Save' : 'Create agent'}
          </button>
        </>
      }
    >
      {agent && !agent.valid && (
        <div className="alert alert-warning">
          This agent refers to things that are not installed anymore: {Object.values(agent.errors).join(' ')}
        </div>
      )}
      {errors.__root__ && <div className="alert alert-error">{errors.__root__}</div>}

      <section className="form-section">
        <h3 className="form-section-title">Identity</h3>
        <div className="form-group">
          <label className="form-label" htmlFor="agent-name">
            Name
          </label>
          <input id="agent-name" className="form-input" value={draft.name} onChange={(event) => set('name', event.target.value)} />
          {errors.name && <div className="form-error">{errors.name}</div>}
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="agent-description">
            Description
          </label>
          <input
            id="agent-description"
            className="form-input"
            value={draft.description ?? ''}
            placeholder="What it is good at (other agents read this to delegate)"
            onChange={(event) => set('description', event.target.value)}
          />
        </div>
        <label className="field-checkbox">
          <input type="checkbox" checked={draft.master} onChange={(event) => set('master', event.target.checked)} />
          <span>
            Master agent
            <small className="form-hint">Receives your messages when you chat with the session.</small>
          </span>
        </label>
      </section>

      <section className="form-section">
        <h3 className="form-section-title">Model</h3>
        <div className="segmented" role="radiogroup" aria-label="Model source">
          <button type="button" role="radio" aria-checked={mode === 'preset'} className={mode === 'preset' ? 'is-active' : ''} onClick={() => setMode('preset')}>
            Inference preset
          </button>
          <button type="button" role="radio" aria-checked={mode === 'custom'} className={mode === 'custom' ? 'is-active' : ''} onClick={() => setMode('custom')}>
            Custom settings
          </button>
        </div>
        {mode === 'preset' ? (
          presets.length === 0 && opt ? (
            <div className="alert alert-warning">
              No inference preset yet. <a href={buildHash('inference')}>Create one</a> so this agent can answer.
            </div>
          ) : (
            <div className="form-group">
              <SearchInput label="Search inference presets" value={modelSearch} onChange={setModelSearch} />
              <select
                className="form-input"
                value={meta.preset_inference_engine_id ?? ''}
                onChange={(event) => setMeta({ preset_inference_engine_id: event.target.value ? Number(event.target.value) : null })}
                aria-label="Inference preset"
              >
                <option value="">Default preset{defaultPreset ? ` (${defaultPreset.name})` : ''}</option>
                {presets.filter(preset => preset.id === meta.preset_inference_engine_id || preset.name.toLowerCase().includes(modelSearch.toLowerCase())).map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                    {preset.default ? ' — default' : ''}
                  </option>
                ))}
              </select>
              <div className="form-hint">Presets are managed on the Inference page.</div>
            </div>
          )
        ) : (
          <>
            <div className="form-group">
              <SearchInput label="Search inference engines" value={modelSearch} onChange={setModelSearch} />
              <select
                className="form-input"
                value={meta.inference_engine_id ?? ''}
                onChange={(event) => {
                  setMeta({ inference_engine_id: event.target.value ? Number(event.target.value) : null, inference_settings: {} });
                  setSettingsKey((key) => key + 1);
                }}
                aria-label="Inference engine"
              >
                <option value="">Choose an engine…</option>
                {engines.filter(item => item.id === meta.inference_engine_id || item.name.toLowerCase().includes(modelSearch.toLowerCase())).map((item) => (
                  <option key={item.id} value={item.id} disabled={!item.available}>
                    {item.name}
                    {item.available ? '' : ' (unavailable)'}
                  </option>
                ))}
              </select>
            </div>
            {engine && (
              <SettingsForm
                key={`${engine.id}-${settingsKey}`}
                kwargsKey={engine.kwargs_key}
                values={(meta.inference_settings ?? {}) as SettingsValues}
                errors={settingsErrors}
                onChange={(values) => setMeta({ inference_settings: values })}
              />
            )}
          </>
        )}
        {errors.meta && <div className="form-error">{errors.meta}</div>}
      </section>

      <section className="form-section">
        <h3 className="form-section-title">Instructions</h3>
        <p className="form-hint">The system prompt is built from the full instructions, then the additions, then the text below.</p>
        <div className="form-group">
          <label className="form-label">Base instructions</label>
          <MultiSelect
            options={(opt?.fulls ?? []).map((item) => ({ value: item.id, label: item.name, description: item.extension }))}
            value={draft.instruction_fulls}
            onChange={(value) => set('instruction_fulls', value)}
            emptyText="No instructions installed. Create them on the Instructions page."
          />
        </div>
        <div className="form-group">
          <label className="form-label">Additions</label>
          <MultiSelect
            options={(opt?.subs ?? []).map((item) => ({ value: item.id, label: item.name, description: item.extension }))}
            value={draft.instruction_subs}
            onChange={(value) => set('instruction_subs', value)}
            emptyText="No additions installed."
          />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="agent-instructions">
            Own instructions
          </label>
          <textarea
            id="agent-instructions"
            className="form-textarea"
            rows={5}
            value={draft.instructions ?? ''}
            placeholder="Anything specific to this agent…"
            onChange={(event) => set('instructions', event.target.value)}
          />
        </div>
      </section>

      <section className="form-section">
        <h3 className="form-section-title">Abilities</h3>
        <div className="form-group">
          <label className="form-label">Tools</label>
          <CallableField kind="tools" items={opt?.toolList ?? []} value={draft.tools} onChange={(value) => set('tools', value)} emptyText="No tools installed." />
        </div>
        <div className="form-group">
          <label className="form-label">Skills</label>
          <MultiSelect
            options={(opt?.skillList ?? []).map((item) => ({ value: item.id, label: item.name, description: item.description }))}
            value={draft.skills}
            onChange={(value) => set('skills', value)}
            emptyText="No skills installed."
          />
        </div>
        <div className="form-group">
          <label className="form-label">Hooks</label>
          <CallableField kind="hooks" items={opt?.hookList ?? []} value={draft.hooks} onChange={(value) => set('hooks', value)} emptyText="No hooks installed." />
          <div className="form-hint">Hooks run before every call to the model (inject context, compress history…).</div>
        </div>
      </section>

      <section className="form-section">
        <h3 className="form-section-title">Team</h3>
        <div className="form-group">
          <label className="form-label">Sub-agents</label>
          <MultiSelect
            options={others.map((item) => ({ value: String(item.id), label: item.name, description: item.description ?? undefined }))}
            value={draft.sub_agents_ids.map(String)}
            onChange={(value) => set('sub_agents_ids', value.map(Number))}
            emptyText="Add other agents to this session to delegate tasks to them."
          />
          <div className="form-hint">This agent can give tasks to its sub-agents with the delegate_to_agent tool.</div>
          {errors.sub_agents_ids && <div className="form-error">{errors.sub_agents_ids}</div>}
        </div>
      </section>

      {agent && (seen.data?.length ?? 0) > 0 && (
        <section className="form-section">
          <h3 className="form-section-title">What the model sees</h3>
          <ul className="plain-list">
            {seen.data?.map((tool) => (
              <li key={tool.id}>
                <span className="mono">{tool.name}</span>
                {tool.description && <span className="muted"> — {tool.description.split('\n')[0]}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </Drawer>
  );
}
