import { useMemo, useState } from 'react';
import { models as modelsApi } from '@/api/endpoints/models';
import { buildHash } from '@/core/router';
import type { HubFile } from '@/core/types/api';
import { formatSize } from '@/modules/files/paths';
import { Drawer } from '@/ui/Modal';
import { useToast } from '@/ui/toastContext';

/** Download from Hugging Face (choosing the weight files) or import from the server's disk. */
export function AddModel({ onClose, onQueued }: { onClose: () => void; onQueued: () => void }) {
  const toast = useToast();
  const [source, setSource] = useState<'hub' | 'local'>('hub');
  const [repo, setRepo] = useState('');
  const [revision, setRevision] = useState('');
  const [hubFiles, setHubFiles] = useState<HubFile[] | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [path, setPath] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  const weights = useMemo(() => (hubFiles ?? []).filter((file) => file.format), [hubFiles]);
  const formats = useMemo(() => [...new Set(weights.map((file) => file.format as string))], [weights]);
  const hasGguf = formats.includes('gguf');

  const listFiles = async () => {
    setBusy(true);
    try {
      const listed = await modelsApi.hubFiles(repo, revision || undefined);
      setHubFiles(listed);
      setChosen(new Set());
    } catch (reason) {
      toast.error(reason);
      setHubFiles(null);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (filePath: string) =>
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(filePath)) next.delete(filePath);
      else next.add(filePath);
      return next;
    });

  const download = async () => {
    setBusy(true);
    try {
      await modelsApi.download(repo.trim(), [...chosen], revision.trim() || undefined);
      toast.show('Download queued');
      onQueued();
    } catch (reason) {
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  const importLocal = async () => {
    setBusy(true);
    try {
      await modelsApi.importLocal(path.trim(), name.trim());
      toast.show('Import queued');
      onQueued();
    } catch (reason) {
      toast.error(reason);
    } finally {
      setBusy(false);
    }
  };

  const needsChoice = hasGguf && chosen.size === 0;

  return (
    <Drawer
      title="Add a model"
      subtitle="Models are stored in the Hugging Face cache and shared by every engine."
      onClose={onClose}
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          {source === 'hub' ? (
            <button type="button" className="btn btn-primary" onClick={download} disabled={busy || !repo.trim() || needsChoice}>
              Download
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={importLocal} disabled={busy || !path.trim() || !name.trim()}>
              Import
            </button>
          )}
        </>
      }
    >
      <div className="segmented" role="radiogroup" aria-label="Source">
        <button type="button" role="radio" aria-checked={source === 'hub'} className={source === 'hub' ? 'is-active' : ''} onClick={() => setSource('hub')}>
          From Hugging Face
        </button>
        <button type="button" role="radio" aria-checked={source === 'local'} className={source === 'local' ? 'is-active' : ''} onClick={() => setSource('local')}>
          From the server's disk
        </button>
      </div>

      {source === 'hub' ? (
        <>
          <div className="form-group">
            <label className="form-label" htmlFor="model-repo">
              Repository
            </label>
            <div className="row">
              <input
                id="model-repo"
                className="form-input form-mono grow"
                value={repo}
                placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2"
                onChange={(event) => {
                  setRepo(event.target.value);
                  setHubFiles(null);
                }}
                onKeyDown={(event) => event.key === 'Enter' && repo.trim() && void listFiles()}
              />
              <button type="button" className="btn btn-secondary" onClick={listFiles} disabled={busy || !repo.trim()}>
                List files
              </button>
            </div>
            <div className="form-hint">Private or gated models need a key named HuggingFace on the API keys page.</div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="model-revision">
              Revision <span className="muted">(optional)</span>
            </label>
            <input id="model-revision" className="form-input form-mono" value={revision} placeholder="main" onChange={(event) => setRevision(event.target.value)} />
          </div>
          {hubFiles && (
            <section className="form-section">
              <h3 className="form-section-title">Weights to download</h3>
              {weights.length === 0 ? (
                <p className="muted">No weight file found: the whole repository is downloaded.</p>
              ) : (
                <>
                  <p className="form-hint">
                    {hasGguf
                      ? 'GGUF repositories hold one file per quantization: choose the ones you want.'
                      : 'Leave everything unchecked to download every format.'}
                  </p>
                  <div className="hub-files">
                    {weights.map((file) => (
                      <label key={file.path} className="multi-select-option">
                        <input type="checkbox" checked={chosen.has(file.path)} onChange={() => toggle(file.path)} />
                        <span>
                          <span className="mono">{file.path}</span>
                          <small>
                            {file.format} · {formatSize(file.size)}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}
        </>
      ) : (
        <>
          <div className="form-group">
            <label className="form-label" htmlFor="model-path">
              Path on the server
            </label>
            <input id="model-path" className="form-input form-mono" value={path} placeholder="/models/my-model or /models/model.gguf" onChange={(event) => setPath(event.target.value)} />
            <div className="form-hint">A model folder or a single weight file (.gguf, .safetensors, .bin, .pth, .ckpt…). It is copied into the cache.</div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="model-name">
              Name
            </label>
            <input id="model-name" className="form-input" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
        </>
      )}
      <p className="muted small">
        Downloads and imports run in the background: follow them on the <a href={buildHash('tasks')}>Tasks</a> page.
      </p>
    </Drawer>
  );
}
