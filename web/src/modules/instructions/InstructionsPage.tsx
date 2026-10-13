import { useState } from 'react';
import { ApiError } from '@/api/client';
import { instructions } from '@/api/endpoints/extensions';
import { useRoute, useRouteActions } from '@/core/router';
import type { InstructionKind } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { MarkdownEditor } from '@/modules/viewers/MarkdownViewer';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { LibraryBrowser } from '@/ui/LibraryBrowser';
import { SearchInput } from '@/ui/SearchInput';
import { libraryExtensions, librarySelection } from '@/core/library';
import { useToast } from '@/ui/toastContext';

const KINDS: Record<InstructionKind, { label: string; help: string }> = {
  full: { label: 'Base instructions', help: 'Complete system prompts: who the agent is and how it works.' },
  sub: { label: 'Additions', help: 'Short fragments added after the base instructions (tone, rules, formats).' },
};

function InstructionEditor({ kind, id, onClose, onSaved }: { kind: InstructionKind; id: string | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const dialogs = useDialogs();
  const loaded = useResource(() => (id ? instructions.get(kind, id) : Promise.resolve(null)), [kind, id]);
  const item = loaded.data ?? null;
  const [name, setName] = useState('');
  const [content, setContent] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const editable = !id || Boolean(item?.editable);
  const text = content ?? item?.content ?? '';

  const save = async () => {
    setErrors({});
    try {
      if (item) await instructions.update(kind, item.id, text);
      else await instructions.create(kind, name.trim(), text);
      toast.show('Saved');
      onSaved();
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    }
  };

  const duplicate = async () => {
    if (!item) return;
    const copy = await dialogs.prompt({ title: 'Duplicate as custom', label: 'Name of the copy', initial: `${item.name}-custom`, confirmLabel: 'Duplicate' });
    if (!copy) return;
    try {
      await instructions.create(kind, copy, item.content ?? '');
      toast.show('Copy created');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const remove = async () => {
    if (!item || !(await dialogs.confirm({ title: `Delete ${item.name}?`, message: 'Agents using it will show a warning until you remove it from them.', confirmLabel: 'Delete', danger: true }))) return;
    try {
      await instructions.remove(kind, item.id);
      toast.show('Deleted');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title={item ? item.name : `New ${KINDS[kind].label.toLowerCase().replace(/s$/, '')}`}
      subtitle={item ? `${item.id}${item.editable ? '' : ' · read-only'}` : KINDS[kind].help}
      onClose={onClose}
      footer={
        <>
          {item?.editable && (
            <button type="button" className="btn btn-danger-text" onClick={remove}>
              Delete
            </button>
          )}
          {item && !item.editable && (
            <button type="button" className="btn btn-secondary" onClick={duplicate}>
              <Icon name="copy" /> Duplicate as custom
            </button>
          )}
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {editable ? 'Cancel' : 'Close'}
          </button>
          {editable && (
            <button type="button" className="btn btn-primary" onClick={save} disabled={!id && !name.trim()}>
              Save
            </button>
          )}
        </>
      }
    >
      {!id && (
        <div className="form-group">
          <label className="form-label" htmlFor="instruction-name">
            Name
          </label>
          <input id="instruction-name" className="form-input form-mono" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
          {errors.name && <div className="form-error">{errors.name}</div>}
        </div>
      )}
      <AsyncState data={id ? loaded.data : null} error={loaded.error} loading={loaded.loading} isEmpty={() => false} onRetry={loaded.reload}>
        {() => (
          <div className="skill-content">
            <MarkdownEditor content={text} onChange={editable ? setContent : undefined} />
          </div>
        )}
      </AsyncState>
    </Drawer>
  );
}

export function InstructionsPage() {
  const { setParams } = useRouteActions();
  const { params } = useRoute();
  const kind: InstructionKind = params.kind === 'sub' ? 'sub' : 'full';
  const list = useResource(() => instructions.list(kind), [kind]);
  const [open, setOpen] = useState<{ id: string | null } | null>(null);
  const [search, setSearch] = useState('');
  const extension = librarySelection(list.data ?? [], params.extension);

  return (
    <>
      <PageHeader
        title="Instructions"
        description="Reusable system prompts. An agent's prompt is its base instructions, then its additions, then its own text."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setOpen({ id: null })}>
            <Icon name="plus" /> New
          </button>
        }
      />
      <div className="tabs" role="tablist">
        {(Object.keys(KINDS) as InstructionKind[]).map((item) => (
          <button key={item} type="button" role="tab" aria-selected={kind === item} className={`tab ${kind === item ? 'is-active' : ''}`} onClick={() => setParams({ kind: item === 'full' ? null : item })}>
            {KINDS[item].label}
          </button>
        ))}
      </div>
      <p className="muted small">{KINDS[kind].help}</p>
      <SearchInput label="Search instructions" value={search} onChange={setSearch} />
      <AsyncState {...list} onRetry={list.reload} isEmpty={() => false}>
        {(items) => (
          <LibraryBrowser label="Instruction extensions" extensions={libraryExtensions(items)} active={extension} onSelect={extension => setParams({ extension })}>
          <div className="list">
            {items.filter(item => item.extension === extension && `${item.name} ${item.id}`.toLowerCase().includes(search.toLowerCase())).map((item) => (
              <button key={item.id} type="button" className="list-row list-row-button" onClick={() => setOpen({ id: item.id })}>
                <div className="list-row-main">
                  <div className="list-row-title">
                    <Icon name="instruction" size={16} /> {item.name}
                    <span className={`chip ${item.editable ? 'chip-accent' : 'chip-outline'}`}>{item.editable ? 'custom' : item.extension}</span>
                  </div>
                  <div className="list-row-meta mono">{item.id}</div>
                </div>
                <Icon name="chevronRight" />
              </button>
            ))}
            {!items.some(item => item.extension === extension && `${item.name} ${item.id}`.toLowerCase().includes(search.toLowerCase())) && <div className="state-empty">{search ? 'No matching instructions.' : `No instructions in ${extension}.`}</div>}
          </div>
          </LibraryBrowser>
        )}
      </AsyncState>
      {open && (
        <InstructionEditor
          kind={kind}
          id={open.id}
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
