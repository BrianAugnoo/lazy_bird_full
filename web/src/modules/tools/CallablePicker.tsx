import { useMemo, useState } from 'react';
import type { CallableItem } from '@/core/types/api';
import { Modal } from '@/ui/Modal';
import { SearchInput } from '@/ui/SearchInput';
import { groupByExtension, selectionState, setSelected, type CallableKind } from './catalog';
import { ExtensionNav } from './ExtensionNav';
import { GroupCheckbox } from './GroupCheckbox';

const NOUN: Record<CallableKind, { many: string; help: string }> = {
  tools: { many: 'tools', help: 'The agent can call every tool you choose.' },
  hooks: { many: 'hooks', help: 'Hooks run before every call to the model, in the order you choose them.' },
};

interface CallablePickerProps {
  kind: CallableKind;
  items: CallableItem[];
  value: string[];
  onConfirm: (value: string[]) => void;
  onClose: () => void;
}

const ids = (items: CallableItem[]) => items.map((item) => item.id);

/** Choose tools or hooks extension by extension and module by module; nothing changes until Confirm. */
export function CallablePicker({ kind, items, value, onConfirm, onClose }: CallablePickerProps) {
  const extensions = useMemo(() => groupByExtension(items), [items]);
  const [draft, setDraft] = useState(value);
  const [search, setSearch] = useState('');
  const [active, setActive] = useState(() => (extensions.find((entry) => entry.items.some((item) => value.includes(item.id))) ?? extensions[0]).extension);
  const current = extensions.find((entry) => entry.extension === active) ?? extensions[0];
  const noun = NOUN[kind];
  const toggle = (group: CallableItem[], on: boolean) => setDraft((selected) => setSelected(selected, ids(group), on));

  return (
    <Modal
      title={`Choose ${noun.many}`}
      subtitle={noun.help}
      onClose={onClose}
      width={880}
      footer={
        <>
          <span className="muted small">{draft.length} selected</span>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="callable-picker" className="btn btn-primary">
            Confirm
          </button>
        </>
      }
    >
      <form
        id="callable-picker"
        className="extension-browser"
        onSubmit={(event) => {
          event.preventDefault();
          onConfirm(draft);
        }}
      >
        <ExtensionNav
          label="Extensions"
          extensions={extensions}
          active={current.extension}
          onSelect={setActive}
          badge={(entry) => `${entry.items.filter((item) => draft.includes(item.id)).length}/${entry.items.length}`}
        />
        <div className="stack">
          <SearchInput label={`Search ${noun.many}`} value={search} onChange={setSearch} />
          <div className="row-between">
            <h3 className="card-title">{current.extension}</h3>
            {current.items.length > 0 && (
              <label className="field-checkbox">
                <GroupCheckbox label={`All ${noun.many} of ${current.extension}`} state={selectionState(ids(current.items), draft)} onChange={(on) => toggle(current.items, on)} />
                Select all
              </label>
            )}
          </div>
          {current.modules.length === 0 && <p className="muted">No {noun.many} in {current.extension}.</p>}
          {current.modules.map(module => ({ ...module, items: module.items.filter(item => `${item.name} ${item.description} ${item.id}`.toLowerCase().includes(search.toLowerCase())) })).filter(module => module.items.length > 0).map((module) => (
            <section key={module.filePath} className="picker-section" aria-label={module.module}>
              <label className="picker-section-head">
                <GroupCheckbox label={`All ${noun.many} of ${module.filePath}`} state={selectionState(ids(module.items), draft)} onChange={(on) => toggle(module.items, on)} />
                <span className="callable-name">{module.module}</span>
                <span className="mono muted small">{module.filePath}</span>
              </label>
              {module.items.map((item) => (
                <label key={item.id} className="picker-item">
                  <input type="checkbox" checked={draft.includes(item.id)} onChange={(event) => toggle([item], event.target.checked)} />
                  <span>
                    <span className="mono">{item.name}</span>
                    {item.description && <small className="picker-item-description">{item.description}</small>}
                  </span>
                </label>
              ))}
            </section>
          ))}
          {search && !current.items.some(item => `${item.name} ${item.description} ${item.id}`.toLowerCase().includes(search.toLowerCase())) && <p className="muted small">No matching {noun.many}.</p>}
        </div>
      </form>
    </Modal>
  );
}
