import { useMemo, useRef, useState } from 'react';
import { ApiError } from '@/api/client';
import { models as modelsApi } from '@/api/endpoints/models';
import { buildHash } from '@/core/router';
import type { HubFile } from '@/core/types/api';
import { formatSize } from '@/modules/files/paths';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { useToast } from '@/ui/toastContext';
import { pickedFiles, suggestedName, type PickedFile } from './uploadFiles';

/** Download from Hugging Face (choosing the weight files) or upload a model from this computer. */
export function AddModel({ onClose, onQueued }: { onClose: () => void; onQueued: () => void }) {
  const toast = useToast();
  const [source, setSource] = useState<'hub' | 'local'>('hub');
  const [repo, setRepo] = useState('');
  const [revision, setRevision] = useState('');
  const [hubFiles, setHubFiles] = useState<HubFile[] | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [picked, setPicked] = useState<PickedFile[]>([]);
  const [name, setName] = useState('');
  const [sent, setSent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const folderPicker = useRef<HTMLInputElement>(null);
  const totalSize = picked.reduce((total, entry) => total + entry.file.size, 0);

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

  const pick = (list: FileList | null) => {
    const files = [...(list ?? [])];
    if (files.length === 0) return;
    setPicked(pickedFiles(files));
    if (!name.trim()) setName(suggestedName(files));
  };

  /** Send every file (overall progress), then queue the import; cancelling discards what was sent. */
  const upload = async () => {
    const modelName = name.trim();
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    setSent(0);
    let done = 0;
    try {
      for (const entry of picked) {
        await modelsApi.uploadFile(modelName, entry.path, entry.file, { signal: controller.signal, onProgress: (bytes) => setSent(done + bytes) });
        done += entry.file.size;
      }
      await modelsApi.importUpload(modelName);
      toast.show('Upload finished: the model is being imported');
      onQueued();
    } catch (reason) {
      if (!(reason instanceof ApiError && reason.code === 'upload_cancelled')) toast.error(reason);
      void modelsApi.discardUpload(modelName).catch(() => undefined);
      setSent(null);
    } finally {
      abort.current = null;
      setBusy(false);
    }
  };

  const close = () => {
    abort.current?.abort();
    onClose();
  };

  const needsChoice = hasGguf && chosen.size === 0;

  return (
    <Drawer
      title="Add a model"
      subtitle="Models are stored in the Hugging Face cache and shared by every engine."
      onClose={close}
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={close}>
            Cancel
          </button>
          {source === 'hub' ? (
            <button type="button" className="btn btn-primary" onClick={download} disabled={busy || !repo.trim() || needsChoice}>
              Download
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={upload} disabled={busy || picked.length === 0 || !name.trim()}>
              {busy ? 'Uploading…' : 'Upload'}
            </button>
          )}
        </>
      }
    >
      <div className="segmented" role="radiogroup" aria-label="Source">
        <button type="button" role="radio" aria-checked={source === 'hub'} className={source === 'hub' ? 'is-active' : ''} onClick={() => setSource('hub')}>
          From Hugging Face
        </button>
        <button type="button" role="radio" aria-checked={source === 'local'} className={source === 'local' ? 'is-active' : ''} onClick={() => setSource('local')} disabled={busy}>
          From your computer
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
            <div className="form-label">Model files</div>
            <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={() => filePicker.current?.click()} disabled={busy}>
                <Icon name="file" /> Choose files
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => folderPicker.current?.click()} disabled={busy}>
                <Icon name="files" /> Choose a folder
              </button>
            </div>
            <input ref={filePicker} type="file" multiple hidden onChange={(event) => { pick(event.target.files); event.target.value = ''; }} />
            <input
              ref={(node) => {
                folderPicker.current = node;
                node?.setAttribute('webkitdirectory', '');
              }}
              type="file"
              hidden
              onChange={(event) => { pick(event.target.files); event.target.value = ''; }}
            />
            <div className="form-hint">A single weight file (.gguf, .safetensors, .bin, .pth, .ckpt…) or a whole model folder (weights, config and tokenizer).</div>
          </div>
          {picked.length > 0 && (
            <div className="upload-files">
              {picked.map((entry) => (
                <div key={entry.path} className="row-between small">
                  <span className="mono truncate">{entry.path}</span>
                  <span className="muted">{formatSize(entry.file.size)}</span>
                </div>
              ))}
              <div className="row-between small upload-total">
                <strong>
                  {picked.length} file{picked.length === 1 ? '' : 's'}
                </strong>
                <strong>{formatSize(totalSize)}</strong>
              </div>
            </div>
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="model-name">
              Name
            </label>
            <input id="model-name" className="form-input" value={name} onChange={(event) => setName(event.target.value)} disabled={busy} />
          </div>
          {sent !== null && (
            <div className="task-progress">
              <div className="progress">
                <div className="progress-bar progress-live" style={{ width: `${totalSize ? Math.min(100, (sent / totalSize) * 100) : 100}%` }} />
              </div>
              <span className="small muted">
                {formatSize(sent)} / {formatSize(totalSize)}
              </span>
            </div>
          )}
        </>
      )}
      <p className="muted small">
        {source === 'hub' ? 'Downloads run' : 'After the upload, the import runs'} in the background: follow it on the <a href={buildHash('tasks')}>Tasks</a> page.
        {source === 'local' && busy && ' Keep this panel open until the upload ends.'}
      </p>
    </Drawer>
  );
}
