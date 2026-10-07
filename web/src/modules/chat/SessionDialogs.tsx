import { useMemo, useState } from 'react';
import { agents as agentsApi, sessions } from '@/api/endpoints/agents';
import { agentPresets, sessionPresets, tools as toolsApi } from '@/api/endpoints/extensions';
import type { Agent, Session } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { KeyValueEditor } from '@/ui/KeyValueEditor';
import { Drawer, Modal } from '@/ui/Modal';
import { useToast } from '@/ui/toastContext';

/** Choose a session preset, or start from an empty session. */
export function NewSessionDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (session: Session) => void }) {
  const toast = useToast();
  const presets = useResource(sessionPresets.list, []);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);

  const create = async (presetId: string | null) => {
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

  return (
    <Modal title="New session" subtitle="A session is a team of agents sharing the same settings." onClose={onClose}>
      <div className="form-group">
        <label className="form-label" htmlFor="session-title">
          Title <span className="muted">(optional)</span>
        </label>
        <input id="session-title" className="form-input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Research on solar panels" />
      </div>
      <div className="form-label">Start from</div>
      <AsyncState {...presets} onRetry={presets.reload}>
        {(list) => (
          <div className="choice-list">
            {list.map((preset) => (
              <button key={preset.id} type="button" className="choice" disabled={busy || !preset.valid} onClick={() => create(preset.id)}>
                <span className="choice-title">
                  {preset.data?.name ?? preset.name} <span className="chip chip-outline">{preset.extension}</span>
                </span>
                <span className="choice-desc">
                  {preset.valid ? preset.data?.description || `${preset.data?.agents.length ?? 0} agents` : Object.values(preset.errors).join(' ')}
                </span>
              </button>
            ))}
            <button type="button" className="choice" disabled={busy} onClick={() => create(null)}>
              <span className="choice-title">Empty session</span>
              <span className="choice-desc">Add agents yourself afterwards.</span>
            </button>
          </div>
        )}
      </AsyncState>
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
  const [busy, setBusy] = useState(false);

  const create = async (presetId: string) => {
    setBusy(true);
    try {
      onCreated(await agentsApi.fromPreset(sessionId, presetId));
    } catch (reason) {
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Add an agent" subtitle="Presets come with their instructions, tools and sub-agents." onClose={onClose}>
      <AsyncState {...presets} onRetry={presets.reload}>
        {(list) => (
          <div className="choice-list">
            {list.map((preset) => (
              <button key={preset.id} type="button" className="choice" disabled={busy || !preset.valid} onClick={() => create(preset.id)}>
                <span className="choice-title">
                  {preset.name} <span className="chip chip-outline">{preset.extension}</span>
                </span>
                <span className="choice-desc">
                  {preset.valid ? preset.data?.description || 'No description' : Object.values(preset.errors).join(' ')}
                </span>
              </button>
            ))}
            <button type="button" className="choice" disabled={busy} onClick={onBlank}>
              <span className="choice-title">Blank agent</span>
              <span className="choice-desc">Choose its model, instructions and tools yourself.</span>
            </button>
          </div>
        )}
      </AsyncState>
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
