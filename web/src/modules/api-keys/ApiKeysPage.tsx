import { useState } from 'react';
import { apiKeys } from '@/api/endpoints/system';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Modal } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

function KeyForm({ name, onClose, onSaved }: { name: string | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [keyName, setKeyName] = useState(name ?? '');
  const [secret, setSecret] = useState('');

  const save = async () => {
    try {
      if (name) await apiKeys.update(name, secret);
      else await apiKeys.create(keyName.trim(), secret);
      toast.show(name ? 'Key replaced' : 'Key saved');
      onSaved();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Modal
      title={name ? `Replace the ${name} key` : 'Add an API key'}
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="key-form" className="btn btn-primary" disabled={!keyName.trim() || !secret}>
            Save
          </button>
        </>
      }
    >
      <form
        id="key-form"
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        {!name && (
          <div className="form-group">
            <label className="form-label" htmlFor="key-name">
              Name
            </label>
            <input id="key-name" className="form-input" value={keyName} onChange={(event) => setKeyName(event.target.value)} placeholder="e.g. HuggingFace, OpenAI" autoFocus />
            <div className="form-hint">Extensions look keys up by name: a key named HuggingFace logs in to Hugging Face.</div>
          </div>
        )}
        <div className="form-group">
          <label className="form-label" htmlFor="key-secret">
            Key
          </label>
          <input id="key-secret" type="password" autoComplete="off" className="form-input form-mono" value={secret} onChange={(event) => setSecret(event.target.value)} autoFocus={Boolean(name)} />
          <div className="form-hint">Keys are stored on the server and never shown again.</div>
        </div>
      </form>
    </Modal>
  );
}

export function ApiKeysPage() {
  const toast = useToast();
  const dialogs = useDialogs();
  const keys = useResource(apiKeys.list, []);
  const [editing, setEditing] = useState<{ name: string | null } | null>(null);

  const remove = async (name: string) => {
    if (!(await dialogs.confirm({ title: `Delete the ${name} key?`, confirmLabel: 'Delete', danger: true }))) return;
    try {
      await apiKeys.remove(name);
      toast.show('Key deleted');
      await keys.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="API keys"
        description="Secrets for external services used by extensions (model hubs, LLM providers, tools)."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setEditing({ name: null })}>
            <Icon name="plus" /> Add a key
          </button>
        }
      />
      <AsyncState {...keys} onRetry={keys.reload} empty={<span className="muted">No key yet.</span>}>
        {(list) => (
          <div className="list">
            {list.map((key) => (
              <div key={key.name} className="list-row">
                <div className="list-row-main">
                  <div className="list-row-title">
                    <Icon name="key" size={16} /> {key.name}
                  </div>
                  <div className="list-row-meta mono">••••••••••••</div>
                </div>
                <div className="list-row-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing({ name: key.name })}>
                    Replace
                  </button>
                  <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => remove(key.name)} aria-label={`Delete ${key.name}`}>
                    <Icon name="trash" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </AsyncState>
      {editing && (
        <KeyForm
          name={editing.name}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void keys.reload();
          }}
        />
      )}
    </>
  );
}
