import { extensions } from '@/api/endpoints/system';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';

const AREAS = [
  { folder: 'embedding/engines/', what: 'Embedding engines' },
  { folder: 'inference/engines/', what: 'Inference engines' },
  { folder: 'chunker/extensions/', what: 'Chunkers (one file per file extension)' },
  { folder: 'database/sql_db/ · database/vector_db/', what: 'Databases' },
  { folder: 'tasks/{extension}/', what: 'Background task kinds' },
  { folder: 'agents/tools/{extension}/', what: 'Tools' },
  { folder: 'agents/hook/{extension}/', what: 'Hooks' },
  { folder: 'agents/skill/{extension}/', what: 'Skills' },
  { folder: 'agents/instruction/{full|sub}/{extension}/', what: 'Instructions' },
  { folder: 'agents/agent_preset/ · agents/session_preset/', what: 'Agent and session presets' },
];

export function ExtensionsPage() {
  const toast = useToast();
  const failures = useResource(extensions.failures, []);

  const reload = async () => {
    try {
      const list = await extensions.reload();
      failures.setData(list);
      toast.show(list.length ? `Reloaded with ${list.length} problem${list.length === 1 ? '' : 's'}` : 'Every extension loaded');
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="Extensions"
        description="Everything in lazy_bird is an extension: a file dropped in the right folder is found when the server starts or reloads."
        actions={
          <button type="button" className="btn btn-primary" onClick={reload}>
            <Icon name="refresh" /> Reload extensions
          </button>
        }
      />
      <section>
        <h2 className="section-title">Problems</h2>
        <AsyncState
          {...failures}
          onRetry={failures.reload}
          empty={
            <div className="row" style={{ justifyContent: 'center' }}>
              <span className="dot dot-success" /> Every extension loaded.
            </div>
          }
        >
          {(list) => (
            <div className="list">
              {list.map((failure) => (
                <div key={`${failure.kind}-${failure.source}`} className="list-row">
                  <div className="list-row-main">
                    <div className="list-row-title">
                      <span className="chip chip-error">{failure.kind}</span> <span className="mono">{failure.source}</span>
                    </div>
                    <pre className="code small">{failure.error}</pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </AsyncState>
      </section>
      <section>
        <h2 className="section-title">Where extensions live</h2>
        <p className="muted small" style={{ marginBottom: 8 }}>
          Folders inside the lazy_bird package. Ship yours in <span className="mono">custom/</span> (or your own extension folder); <span className="mono">default/</span> holds the
          built-in ones.
        </p>
        <div className="table-container">
          <table className="table">
            <tbody>
              {AREAS.map((area) => (
                <tr key={area.folder}>
                  <td>{area.what}</td>
                  <td className="mono small">{area.folder}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
