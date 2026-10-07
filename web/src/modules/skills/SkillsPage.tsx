import { useState } from 'react';
import { ApiError } from '@/api/client';
import { skills } from '@/api/endpoints/extensions';
import type { Skill } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { MarkdownEditor } from '@/modules/viewers/MarkdownViewer';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Drawer, Modal } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

const NAME_HINT = 'Letters, digits, “-”, “_” and “.”; it cannot be changed later.';

function SkillFile({ skillId, path, onClose }: { skillId: string; path: string; onClose: () => void }) {
  const content = useResource(() => skills.file(skillId, path), [skillId, path]);
  return (
    <Modal title={path} onClose={onClose} width={820}>
      <AsyncState {...content} onRetry={content.reload}>
        {(text) => <pre className="code" style={{ maxHeight: '60vh', overflow: 'auto', whiteSpace: 'pre-wrap' }}>{typeof text === 'string' ? text : JSON.stringify(text, null, 2)}</pre>}
      </AsyncState>
    </Modal>
  );
}

function SkillEditor({ skillId, onClose, onSaved }: { skillId: string | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const dialogs = useDialogs();
  const loaded = useResource(() => (skillId ? skills.get(skillId) : Promise.resolve(null)), [skillId]);
  const skill = loaded.data ?? null;
  const [name, setName] = useState('');
  const [description, setDescription] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [file, setFile] = useState<string | null>(null);
  const editable = !skillId || Boolean(skill?.editable);
  const currentDescription = description ?? skill?.description ?? '';
  const currentContent = content ?? skill?.content ?? '';

  const save = async () => {
    setErrors({});
    try {
      if (skill) await skills.update(skill.id, currentDescription, currentContent);
      else await skills.create(name.trim(), currentDescription, currentContent);
      toast.show('Skill saved');
      onSaved();
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    }
  };

  const duplicate = async () => {
    if (!skill) return;
    const copy = await dialogs.prompt({ title: 'Duplicate as a custom skill', label: 'Name of the copy', initial: `${skill.name}-custom`, hint: NAME_HINT, confirmLabel: 'Duplicate' });
    if (!copy) return;
    try {
      await skills.create(copy, skill.description, skill.content ?? '');
      toast.show('Copy created (resource files are not copied)');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const remove = async () => {
    if (!skill || !(await dialogs.confirm({ title: `Delete the skill ${skill.name}?`, message: 'Its folder and resource files are deleted.', confirmLabel: 'Delete', danger: true }))) return;
    try {
      await skills.remove(skill.id);
      toast.show('Skill deleted');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title={skill ? skill.name : 'New skill'}
      subtitle={skill ? (skill.editable ? `Custom skill · ${skill.id}` : `Built-in skill · ${skill.id} · read-only`) : 'Instructions an agent loads only when it needs them.'}
      onClose={onClose}
      footer={
        <>
          {skill?.editable && (
            <button type="button" className="btn btn-danger-text" onClick={remove}>
              Delete
            </button>
          )}
          {skill && !skill.editable && (
            <button type="button" className="btn btn-secondary" onClick={duplicate}>
              <Icon name="copy" /> Duplicate as custom
            </button>
          )}
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {editable ? 'Cancel' : 'Close'}
          </button>
          {editable && (
            <button type="button" className="btn btn-primary" onClick={save} disabled={!skillId && !name.trim()}>
              Save
            </button>
          )}
        </>
      }
    >
      <AsyncState data={skillId ? loaded.data : null} error={loaded.error} loading={loaded.loading} isEmpty={() => false} onRetry={loaded.reload}>
        {() => (
          <>
            {!skillId && (
              <div className="form-group">
                <label className="form-label" htmlFor="skill-name">
                  Name
                </label>
                <input id="skill-name" className="form-input form-mono" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
                <div className="form-hint">{NAME_HINT}</div>
                {errors.name && <div className="form-error">{errors.name}</div>}
              </div>
            )}
            <div className="form-group">
              <label className="form-label" htmlFor="skill-description">
                When to use it
              </label>
              <textarea
                id="skill-description"
                className="form-textarea"
                rows={2}
                value={currentDescription}
                readOnly={!editable}
                placeholder="e.g. How to write PDF reports. Use when the user asks for a report."
                onChange={(event) => setDescription(event.target.value)}
              />
              <div className="form-hint">Agents only see this description until they load the skill.</div>
              {errors.description && <div className="form-error">{errors.description}</div>}
            </div>
            <div className="form-group skill-content">
              <label className="form-label">Instructions</label>
              <MarkdownEditor content={currentContent} onChange={editable ? setContent : undefined} />
            </div>
            {skill && skill.files.length > 0 && (
              <section className="form-section">
                <h3 className="form-section-title">Resource files</h3>
                <ul className="plain-list">
                  {skill.files.map((path) => (
                    <li key={path}>
                      <button type="button" className="link-button mono" onClick={() => setFile(path)}>
                        {path}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </AsyncState>
      {file && skill && <SkillFile skillId={skill.id} path={file} onClose={() => setFile(null)} />}
    </Drawer>
  );
}

export function SkillsPage() {
  const list = useResource(skills.list, []);
  const [open, setOpen] = useState<{ id: string | null } | null>(null);

  return (
    <>
      <PageHeader
        title="Skills"
        description="Know-how an agent loads on demand: agents see each skill's description and read the instructions when a task calls for them."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setOpen({ id: null })}>
            <Icon name="plus" /> New skill
          </button>
        }
      />
      <AsyncState {...list} onRetry={list.reload} empty={<span className="muted">No skill yet.</span>}>
        {(items: Skill[]) => (
          <div className="card-grid">
            {items.map((skill) => (
              <button key={skill.id} type="button" className="item-card" onClick={() => setOpen({ id: skill.id })}>
                <span className="item-card-title">
                  <Icon name="skill" size={16} /> {skill.name}
                  <span className={`chip ${skill.editable ? 'chip-accent' : 'chip-outline'}`}>{skill.editable ? 'custom' : skill.extension}</span>
                </span>
                <span className="item-card-desc">{skill.description}</span>
                {skill.files.length > 0 && <span className="muted small">{skill.files.length} resource files</span>}
              </button>
            ))}
          </div>
        )}
      </AsyncState>
      {open && (
        <SkillEditor
          skillId={open.id}
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
