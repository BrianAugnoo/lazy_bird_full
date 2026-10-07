import { useState } from 'react';
import { files as filesApi } from '@/api/endpoints/files';
import { buildHash } from '@/core/router';
import type { FileItem } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { Drawer } from '@/ui/Modal';
import { useToast } from '@/ui/toastContext';
import { formatSize } from './paths';
import { FILE_STATES, PROCESSING_STATES, fileLabel, processingLabel } from './states';

function Chunks({ fileId }: { fileId: number }) {
  const chunks = useResource(() => filesApi.chunks(fileId), [fileId]);
  return (
    <AsyncState {...chunks} onRetry={chunks.reload} empty={<span className="muted">No chunk yet.</span>}>
      {(list) => (
        <div className="chunk-list">
          {list.map((chunk) => (
            <div key={chunk.id} className="chunk">
              <div className="chunk-meta">
                #{chunk.position + 1} · lines {chunk.start_line}–{chunk.end_line}
                {chunk.token_count ? ` · ${chunk.token_count} tokens` : ''}
              </div>
              <pre className="chunk-content">{chunk.content}</pre>
            </div>
          ))}
        </div>
      )}
    </AsyncState>
  );
}

/** Processing states of a file (with reprocessing) and its chunks. */
export function FileDetails({ file, onClose, onChanged }: { file: FileItem; onClose: () => void; onChanged: (file: FileItem) => void }) {
  const toast = useToast();
  const [tab, setTab] = useState<'processing' | 'chunks'>('processing');
  const state = FILE_STATES[file.state] ?? FILE_STATES.new;

  const act = async (action: () => Promise<FileItem>, done: string) => {
    try {
      onChanged(await action());
      toast.show(done);
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <Drawer
      title={fileLabel(file)}
      subtitle={file.relative_path}
      onClose={onClose}
      footer={
        <>
          <a className="btn btn-ghost" href={buildHash('files', { dir: file.directory, file: file.id })} onClick={onClose}>
            Open
          </a>
          <span className="grow" />
          <button type="button" className="btn btn-primary" onClick={() => act(() => filesApi.process(file.id), 'Processing queued')}>
            Process what is missing
          </button>
        </>
      }
    >
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <span className={`chip ${state.chip}`}>{state.label}</span>
        <span className="muted small">{state.help}</span>
      </div>
      <dl className="facts">
        <dt>Size</dt>
        <dd>{formatSize(file.size)}</dd>
        <dt>Chunks</dt>
        <dd>{file.chunk_count}</dd>
        <dt>Content hash</dt>
        <dd className="mono truncate" title={file.content_hash ?? ''}>
          {file.content_hash?.slice(0, 16) ?? '–'}
        </dd>
        <dt>On disk</dt>
        <dd className="mono small" style={{ wordBreak: 'break-all' }}>
          {file.path}
        </dd>
      </dl>

      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'processing'} className={`tab ${tab === 'processing' ? 'is-active' : ''}`} onClick={() => setTab('processing')}>
          Processing
        </button>
        <button type="button" role="tab" aria-selected={tab === 'chunks'} className={`tab ${tab === 'chunks' ? 'is-active' : ''}`} onClick={() => setTab('chunks')}>
          Chunks ({file.chunk_count})
        </button>
      </div>

      {tab === 'processing' ? (
        file.processing.length === 0 ? (
          <p className="muted">Not processed yet. Use “Process what is missing”.</p>
        ) : (
          <div className="list">
            {file.processing.map((row) => {
              const rowState = PROCESSING_STATES[row.state];
              return (
                <div key={`${row.processor}-${row.target}`} className="list-row">
                  <div className="list-row-main">
                    <div className="list-row-title">
                      {processingLabel(row)} <span className={`chip ${rowState.chip}`}>{rowState.label}</span>
                    </div>
                    <div className="list-row-meta">
                      Updated {new Date(row.updated_at).toLocaleString()}
                      {row.task_id && (
                        <>
                          {' · '}
                          <a href={buildHash('tasks')}>task #{row.task_id}</a>
                        </>
                      )}
                    </div>
                    {row.error && <div className="form-error">{row.error.message}</div>}
                  </div>
                  <div className="list-row-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={row.state === 'running' || row.state === 'queued'}
                      onClick={() => act(() => filesApi.reprocess(file.id, row.processor, row.target), 'Queued again')}
                    >
                      Redo
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        <Chunks fileId={file.id} />
      )}
    </Drawer>
  );
}
