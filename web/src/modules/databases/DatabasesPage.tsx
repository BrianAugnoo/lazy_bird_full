import { useState } from 'react';
import { ApiError } from '@/api/client';
import { databases } from '@/api/endpoints/system';
import type { SettingsValues } from '@/core/fields/types';
import type { DatabaseAdapter, DatabaseKind } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

const KINDS: Record<DatabaseKind, { title: string; description: string }> = {
  sql: { title: 'Data', description: 'Files, chunks, agents, conversations and tasks. Another database must be migrated first.' },
  vector: { title: 'Vectors', description: 'Embeddings used by search. Switching marks every embedding as outdated, so files are embedded again.' },
};

function Connect({ kind, name, adapter, onClose, onDone }: { kind: DatabaseKind; name: string; adapter: DatabaseAdapter; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [values, setValues] = useState<SettingsValues>({ ...adapter.settings });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const connect = async () => {
    setBusy(true);
    setErrors({});
    try {
      await databases.select(kind, name, values);
      toast.show(`Connected to ${name}`);
      onDone();
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      title={`Connect to ${name}`}
      subtitle={adapter.messages.initialize}
      onClose={onClose}
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={connect} disabled={busy}>
            {busy ? 'Connecting…' : adapter.selected ? 'Reconnect' : 'Connect'}
          </button>
        </>
      }
    >
      <SettingsForm kwargsKey={adapter.kwargs_key} values={values} errors={errors} onChange={setValues} />
    </Drawer>
  );
}

function VectorTables() {
  const toast = useToast();
  const dialogs = useDialogs();
  const tables = useResource(databases.vectorTables, []);

  const drop = async (modelName: string) => {
    const ok = await dialogs.confirm({
      title: `Delete the vectors of ${modelName}?`,
      message: 'Files lose their embedding with this model; they are embedded again if it is the default model.',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    try {
      await databases.dropVectorTable(modelName);
      toast.show('Vectors deleted');
      await tables.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <section>
      <h2 className="section-title">Vectors per model</h2>
      <AsyncState {...tables} onRetry={tables.reload} empty={<span className="muted">No vector stored yet.</span>}>
        {(list) => (
          <div className="list">
            {list.map((table) => (
              <div key={table.model_name} className="list-row">
                <div className="list-row-main">
                  <div className="list-row-title mono">{table.model_name}</div>
                  <div className="list-row-meta">{table.vectors.toLocaleString()} vectors</div>
                </div>
                <div className="list-row-actions">
                  <button type="button" className="btn btn-ghost btn-sm btn-danger-text" onClick={() => drop(table.model_name)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </AsyncState>
    </section>
  );
}

export function DatabasesPage() {
  const toast = useToast();
  const dialogs = useDialogs();
  const catalog = useResource(databases.catalog, []);
  const [connecting, setConnecting] = useState<{ kind: DatabaseKind; name: string; adapter: DatabaseAdapter } | null>(null);

  const disconnect = async (kind: DatabaseKind, name: string, adapter: DatabaseAdapter) => {
    const choice = await dialogs.prompt({
      title: `Disconnect ${name}?`,
      label: 'Its data',
      confirmLabel: 'Disconnect',
      hint: adapter.messages.disconnect,
      options: [
        { value: 'keep', label: 'Keep it (you can reconnect later)' },
        { value: 'drop', label: 'Delete it' },
      ],
    });
    if (!choice) return;
    try {
      await databases.disconnect(kind, name, choice === 'drop');
      toast.show(`${name} disconnected`);
      await catalog.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader title="Databases" description="Where lazy_bird stores its data and vectors. Each database type is an extension with its own settings." />
      <AsyncState {...catalog} onRetry={catalog.reload}>
        {(data) => (
          <>
            {(['sql', 'vector'] as DatabaseKind[]).map((kind) => (
              <section key={kind}>
                <h2 className="section-title">{KINDS[kind].title}</h2>
                <p className="muted small" style={{ marginBottom: 8 }}>
                  {KINDS[kind].description}
                </p>
                <div className="list">
                  {Object.entries(data.available[kind]).map(([name, adapter]) => (
                    <div key={name} className={`list-row ${adapter.selected ? 'is-highlighted' : ''}`}>
                      <div className="list-row-main">
                        <div className="list-row-title">
                          {name}
                          {adapter.selected && <span className="chip chip-accent">in use</span>}
                        </div>
                        {adapter.messages.initialize && <div className="list-row-meta">{adapter.messages.initialize}</div>}
                      </div>
                      <div className="list-row-actions">
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setConnecting({ kind, name, adapter })}>
                          {adapter.selected ? 'Settings' : 'Connect'}
                        </button>
                        {adapter.selected && (
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => disconnect(kind, name, adapter)}>
                            <Icon name="close" /> Disconnect
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </AsyncState>
      <VectorTables />
      {connecting && (
        <Connect
          {...connecting}
          onClose={() => setConnecting(null)}
          onDone={() => {
            setConnecting(null);
            void catalog.reload();
          }}
        />
      )}
    </>
  );
}
