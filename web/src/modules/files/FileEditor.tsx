import { useEffect, useState } from 'react';
import { ApiError } from '@/api/client';
import { files as filesApi } from '@/api/endpoints/files';
import { getViewer, resolveViewer } from '@/core/file-viewers/registry';
import { useRouteActions } from '@/core/router';
import { onFileChange } from '@/core/tasks/store';
import type { FileItem } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { useToast } from '@/ui/toastContext';
import { FileDetails } from './FileDetails';
import { formatSize } from './paths';
import { FILE_STATES, fileLabel } from './states';

async function loadFile(id: number): Promise<{ file: FileItem; content: string | null }> {
  const file = await filesApi.get(id);
  try {
    return { file, content: await filesApi.content(id) };
  } catch (reason) {
    if (reason instanceof ApiError && reason.code === 'not_text') return { file, content: null };
    throw reason;
  }
}

/** A file opened full page: its viewer (editable for text), state and actions. */
export function FileEditor({ fileId }: { fileId: number }) {
  const { setParams, active } = useRouteActions();
  const toast = useToast();
  const dialogs = useDialogs();
  const data = useResource(() => loadFile(fileId), [fileId]);
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [details, setDetails] = useState(false);
  const file = data.data?.file;
  const saved = data.data?.content ?? null;
  const dirty = draft !== null && draft !== saved;

  const { setData } = data;
  useEffect(
    () =>
      onFileChange((changed) => {
        if (changed === fileId) void filesApi.get(fileId).then((next) => setData((current) => (current ? { ...current, file: next } : current)));
      }),
    [fileId, setData],
  );

  const save = async () => {
    if (draft === null || !dirty) return;
    setSaving(true);
    try {
      const next = await filesApi.saveContent(fileId, draft);
      setData({ file: next, content: draft });
      setDraft(null);
      toast.show('Saved. The file will be processed again.');
    } catch (reason) {
      toast.error(reason);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (active && (event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        void save();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const close = async () => {
    if (dirty && !(await dialogs.confirm({ title: 'Leave without saving?', message: 'Your changes will be lost.', confirmLabel: 'Leave', danger: true }))) return;
    setParams({ file: null, dir: file?.directory || null });
  };

  const viewer = file ? (resolveViewer(file.extension) ?? (saved !== null ? getViewer('text') : undefined)) : undefined;
  const state = file ? (FILE_STATES[file.state] ?? FILE_STATES.new) : null;

  return (
    <div className="file-editor" data-unsaved={dirty}>
      <div className="file-editor-head">
        <button type="button" className="btn btn-ghost btn-sm" onClick={close}>
          <Icon name="back" /> Files
        </button>
        <div className="file-editor-title">
          <span className="truncate">{file ? fileLabel(file) : 'Loading…'}</span>
          {dirty && <span className="chip chip-warning">unsaved</span>}
          {state && (
            <button type="button" className={`chip ${state.chip} chip-button`} onClick={() => setDetails(true)} title={state.help}>
              {state.label}
            </button>
          )}
        </div>
        {file && (
          <div className="row">
            <span className="muted small">{formatSize(file.size)}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDetails(true)}>
              <Icon name="info" /> Details
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => filesApi.download(file.id, fileLabel(file)).catch(toast.error)}>
              <Icon name="download" /> Download
            </button>
            {saved !== null && (
              <button type="button" className="btn btn-primary btn-sm" onClick={save} disabled={!dirty || saving} title="Save (Ctrl+S)">
                {saving ? 'Saving…' : 'Save'}
              </button>
            )}
          </div>
        )}
      </div>
      <AsyncState {...data} onRetry={data.reload}>
        {({ file: current, content }) =>
          viewer && content !== null ? (
            <div className="file-editor-body">
              <viewer.Component file={current} content={draft ?? content} onChange={setDraft} />
            </div>
          ) : (
            <div className="state-empty">
              <div className="state-title">No preview for {current.extension || 'this'} files</div>
              <p className="state-desc">Download it to open it with another application.</p>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => filesApi.download(current.id, fileLabel(current)).catch(toast.error)}>
                <Icon name="download" /> Download
              </button>
            </div>
          )
        }
      </AsyncState>
      {details && file && <FileDetails file={file} onClose={() => setDetails(false)} onChanged={(next) => setData((current) => (current ? { ...current, file: next } : current))} />}
    </div>
  );
}
