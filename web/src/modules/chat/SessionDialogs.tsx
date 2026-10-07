import { useMemo, useState } from 'react';
import { agents as agentsApi, sessions } from '@/api/endpoints/agents';
import { agentPresets, sessionPresets, tools as toolsApi } from '@/api/endpoints/extensions';
import type { Agent, Session } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { ChoiceList, type Choice } from '@/ui/ChoiceList';
import { KeyValueEditor } from '@/ui/KeyValueEditor';
import { Drawer, Modal } from '@/ui/Modal';
import { useToast } from '@/ui/toastContext';

const BLANK = '';

/** Presets failing to load must not hide the blank option: show the problem next to it. */
function PresetLoadState({ loading, error, onRetry }: { loading: boolean; error: Error | null; onRetry: () => void }) {
  if (error) {
    return (
      <div className="alert alert-warning choice-load-error">
        <span>Presets could not be loaded: {error.message}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>
          Try again
        </button>
      </div>
    );
  }
  return loading ? (
    <div className="state-loading small">
      <span className="spinner" /> Loading presets…
    </div>
  ) : null;
}

/** Name the session and choose what it starts with: a preset team, or nothing. */
export function NewSessionDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (session: Session) => void }) {
  const toast = useToast();
  const presets = useResource(sessionPresets.list, []);
  const [title, setTitle] = useState('');
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstValid = presets.data?.find((preset) => preset.valid)?.id;
  // Until the user picks, the first valid preset is suggested (else an empty session).
  const choice = picked ?? (presets.loading && !presets.data ? null : (firstValid ?? BLANK));

  const create = async (presetId: string | null = choice) => {
    if (presetId === null || busy) return;
    setBusy(true);
    try {
      const session = presetId ? await sessions.fromPreset(presetId, title.trim() || undefined) : await sessions.create(title.trim() || 'New session');
      onCreated(session);
    } catch (reason) {
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  const choices: Choice[] = [
    ...(presets.data ?? []).map((preset) => ({
      value: preset.id,
      disabled: !preset.valid,
      title: (
        <>
          {preset.data?.name ?? preset.name} <span className="chip chip-outline">{preset.extension}</span>
        </>
      ),
      description: preset.valid ? preset.data?.description || `${preset.data?.agents.length ?? 0} agents` : Object.values(preset.errors).join(' '),
    })),
    { value: BLANK, title: 'Empty session', description: 'Add agents yourself afterwards.' },
  ];

  return (
    <Modal
      title="New session"
      subtitle="A session is a team of agents sharing the same settings."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="new-session-form" className="btn btn-primary" disabled={busy || choice === null}>
            {busy ? 'Creating…' : 'Create session'}
          </button>
        </>
      }
    >
      <form
        id="new-session-form"
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          void create();
        }}
      >
        <div className="form-group">
          <label className="form-label" htmlFor="session-title">
            Title <span className="muted">(optional)</span>
          </label>
          <input
            id="session-title"
            className="form-input"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Research on solar panels"
            autoFocus
          />
        </div>
        <div className="form-group">
          <div className="form-label">Start from</div>
          <PresetLoadState loading={presets.loading && !presets.data} error={presets.error} onRetry={presets.reload} />
          <ChoiceList label="Start from" choices={choices} value={choice} onChange={setPicked} onConfirm={(value) => void create(value)} />
        </div>
      </form>
    </Modal>
  );
}

/** Add an agent from a preset, or a blank one to configure. */
export function AddAgentDialog({
  sessionId,
  onClose,
  onCreated,
  onBlank,
}: {
  sessionId: number;
  onClose: () => void;
  onCreated: (agent: Agent) => void;
  onBlank: () => void;
}) {
  const toast = useToast();
  const presets = useResource(agentPresets.list, []);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstValid = presets.data?.find((preset) => preset.valid)?.id;
  const choice = picked ?? (presets.loading && !presets.data ? null : (firstValid ?? BLANK));

  const confirm = async (presetId: string | null = choice) => {
    if (presetId === null || busy) return;
    if (presetId === BLANK) {
      onBlank();
      return;
    }
    setBusy(true);
    try {
      onCreated(await agentsApi.fromPreset(sessionId, presetId));
    } catch (reason) {
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  const choices: Choice[] = [
    ...(presets.data ?? []).map((preset) => ({
      value: preset.id,
      disabled: !preset.valid,
      title: (
        <>
          {preset.name} <span className="chip chip-outline">{preset.extension}</span>
        </>
      ),
      description: preset.valid ? preset.data?.description || 'No description' : Object.values(preset.errors).join(' '),
    })),
    { value: BLANK, title: 'Blank agent', description: 'Choose its model, instructions and tools yourself.' },
  ];

  return (
    <Modal
      title="Add an agent"
      subtitle="Presets come with their instructions, tools and sub-agents."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="add-agent-form" className="btn btn-primary" disabled={busy || choice === null}>
            {busy ? 'Adding…' : choice === BLANK ? 'Continue' : 'Add agent'}
          </button>
        </>
      }
    >
      <form
        id="add-agent-form"
        onSubmit={(event) => {
          event.preventDefault();
          void confirm();
        }}
      >
        <PresetLoadState loading={presets.loading && !presets.data} error={presets.error} onRetry={presets.reload} />
        <ChoiceList label="Agent to add" choices={choices} value={choice} onChange={setPicked} onConfirm={(value) => void confirm(value)} />
      </form>
    </Modal>
  );
}

/** Rename a session, edit the values its tools read (meta), or delete it. */
export function SessionSettings({
  session,
  sessionAgents,
  onClose,
  onSaved,
  onDeleted,
}: {
  session: Session;
  sessionAgents: Agent[];
  onClose: () => void;
  onSaved: (session: Session) => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const [title, setTitle] = useState(session.title);
  const [meta, setMeta] = useState<Record<string, unknown>>(session.meta ?? {});
  const toolList = useResource(toolsApi.list, []);

  const needed = useMemo(() => {
    const used = new Set(sessionAgents.flatMap((agent) => agent.tools));
    const keys = new Set<string>();
    for (const tool of toolList.data ?? []) if (used.has(tool.id)) for (const key of tool.required_meta) keys.add(key);
    return [...keys];
  }, [sessionAgents, toolList.data]);

  const save = async () => {
    try {
      onSaved(await sessions.update(session.id, { title: title.trim() || session.title, meta }));
      toast.show('Session saved');
    } catch (reason) {
      toast.error(reason);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete the session "${session.title}", its agents and their conversations?`)) return;
    try {
      await sessions.remove(session.id);
      toast.show('Session deleted');
      onDeleted();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title="Session settings"
      subtitle={`Created ${new Date(session.created_at).toLocaleString()}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-danger-text" onClick={remove}>
            Delete session
          </button>
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
        <label className="form-label" htmlFor="session-name">
          Title
        </label>
        <input id="session-name" className="form-input" value={title} onChange={(event) => setTitle(event.target.value)} />
      </div>
      <section className="form-section">
        <h3 className="form-section-title">Shared values</h3>
        <p className="form-hint">Tools of this session's agents can read these values (a workspace, an email address…).</p>
        <KeyValueEditor value={meta} onChange={setMeta} suggestions={needed} />
      </section>
    </Drawer>
  );
}
