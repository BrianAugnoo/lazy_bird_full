import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import { files as filesApi } from '@/api/endpoints/files';
import { useRouteActions } from '@/core/router';
import { onFileChange } from '@/core/tasks/store';
import type { FileItem } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { FileIcon } from '@/ui/FileIcon';
import { SearchInput } from '@/ui/SearchInput';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';
import { FileDetails } from './FileDetails';
import { baseName, breadcrumbs, childFolders, formatSize, joinPath, parentOf } from './paths';
import { FILE_STATES, fileLabel, processingSummary } from './states';
import { FILE_DRAG_TYPE, parseFileDrag, validDestination, type FileDrag } from './drag';

function loadAll() {
  return Promise.all([filesApi.list(), filesApi.directories()]).then(([list, directories]) => ({ list, directories }));
}

export function FileBrowser({ dir }: { dir: string }) {
  const { setParams } = useRouteActions();
  const toast = useToast();
  const dialogs = useDialogs();
  const data = useResource(loadAll, []);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [details, setDetails] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(0);
  const [search, setSearch] = useState('');
  const [moving, setMoving] = useState(false);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const internalDrag = useRef<FileDrag | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);

  // Live states: refresh a file whenever one of its processings changes.
  const { setData } = data;
  useEffect(
    () =>
      onFileChange((fileId) => {
        filesApi
          .get(fileId)
          .then((file) => setData((current) => (current ? { ...current, list: current.list.map((item) => (item.id === file.id ? file : item)) } : current)))
          .catch(() => undefined);
      }),
    [setData],
  );

  const list = useMemo(() => data.data?.list ?? [], [data.data]);
  const directories = useMemo(() => data.data?.directories ?? [], [data.data]);
  const folders = useMemo(() => childFolders(dir, directories).filter(path => baseName(path).toLowerCase().includes(search.toLowerCase())), [dir, directories, search]);
  const here = useMemo(() => list.filter((file) => file.directory === dir && fileLabel(file).toLowerCase().includes(search.toLowerCase())).sort((a, b) => fileLabel(a).localeCompare(fileLabel(b))), [list, dir, search]);
  const selectedFiles = here.filter((file) => selected.has(file.id));
  const detailFile = list.find((file) => file.id === details) ?? null;

  const go = (path: string) => {
    setSelected(new Set());
    setParams({ dir: path || null, file: null });
  };

  const run = async (action: () => Promise<unknown>, done?: string) => {
    try {
      await action();
      if (done) toast.show(done);
      await data.reload();
    } catch (reason) {
      toast.error(reason);
      await data.reload();
    }
  };

  const startDrag = (event: DragEvent, payload: FileDrag) => {
    if (moving) { event.preventDefault(); return; }
    internalDrag.current = payload;
    event.dataTransfer.setData(FILE_DRAG_TYPE, JSON.stringify(payload));
    event.dataTransfer.effectAllowed = 'move';
  };
  const dropFolder = (destination: string) => ({
    onDragOver: (event: DragEvent) => {
      const payload = internalDrag.current;
      if (!event.dataTransfer.types.includes(FILE_DRAG_TYPE) || !payload || !validDestination(payload, destination) || moving) return;
      event.preventDefault(); event.stopPropagation(); event.dataTransfer.dropEffect = 'move'; setDropTarget(destination);
    },
    onDragLeave: (event: DragEvent) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDropTarget(null); },
    onDrop: (event: DragEvent) => {
      if (!event.dataTransfer.types.includes(FILE_DRAG_TYPE)) return;
      event.preventDefault(); event.stopPropagation(); setDropTarget(null);
      const payload = parseFileDrag(event.dataTransfer.getData(FILE_DRAG_TYPE));
      internalDrag.current = null;
      if (!payload || !validDestination(payload, destination) || moving || (destination && !directories.includes(destination))) return;
      setMoving(true);
      void run(async () => {
        if (payload.kind === 'folder') await filesApi.moveDirectory(payload.path, joinPath(destination, baseName(payload.path)));
        else for (const id of payload.ids) { const file = list.find(item => item.id === id); if (file && file.directory !== destination) await filesApi.patch(id, { dir: destination }); }
        setSelected(new Set());
      }, 'Moved').finally(() => setMoving(false));
    },
  });

  const upload = async (picked: File[]) => {
    if (picked.length === 0) return;
    setUploading((count) => count + picked.length);
    try {
      const stored = await filesApi.upload(dir, picked);
      const renamed = stored.filter((file, index) => fileLabel(file) !== picked[index]?.name);
      toast.show(
        `${stored.length} file${stored.length === 1 ? '' : 's'} uploaded${renamed.length ? ` (${renamed.map(fileLabel).join(', ')} renamed: the name was taken)` : ''}`,
      );
      await data.reload();
    } catch (reason) {
      toast.error(reason);
    } finally {
      setUploading((count) => count - picked.length);
    }
  };

  const newFolder = async () => {
    const name = await dialogs.prompt({ title: 'New folder', label: 'Folder name', confirmLabel: 'Create' });
    if (name) await run(() => filesApi.createDirectory(joinPath(dir, name)), 'Folder created');
  };

  const newTextFile = async () => {
    const name = await dialogs.prompt({ title: 'New text file', label: 'File name', initial: 'notes.md', confirmLabel: 'Create', hint: 'Markdown (.md) and text files can be edited here.' });
    if (!name) return;
    try {
      const [created] = await filesApi.upload(dir, [new File([''], name, { type: 'text/plain' })]);
      await data.reload();
      setParams({ file: created.id });
    } catch (reason) {
      toast.error(reason);
    }
  };

  const renameFile = async (file: FileItem) => {
    const name = await dialogs.prompt({ title: 'Rename', label: `New name (the ${file.extension || 'same'} extension is kept)`, initial: file.name, confirmLabel: 'Rename' });
    if (name && name !== file.name) await run(() => filesApi.patch(file.id, { name }), 'File renamed');
  };

  const chooseFolder = (title: string) =>
    dialogs.prompt({
      title,
      label: 'Destination folder',
      confirmLabel: 'Move',
      options: [{ value: '', label: 'Root of the storage' }, ...directories.map((path) => ({ value: path, label: path }))],
    });

  const moveFiles = async (targets: FileItem[]) => {
    const destination = await chooseFolder(targets.length === 1 ? `Move ${fileLabel(targets[0])}` : `Move ${targets.length} files`);
    if (destination === null) return;
    await run(async () => {
      for (const file of targets) await filesApi.patch(file.id, { dir: destination });
      setSelected(new Set());
    }, 'Moved');
  };

  const deleteFiles = async (targets: FileItem[]) => {
    const ok = await dialogs.confirm({
      title: targets.length === 1 ? `Delete ${fileLabel(targets[0])}?` : `Delete ${targets.length} files?`,
      message: 'Their chunks and vectors are deleted too.',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    await run(async () => {
      await filesApi.remove(targets.map((file) => file.id));
      setSelected(new Set());
    }, 'Deleted');
  };

  const renameFolder = async (path: string) => {
    const name = await dialogs.prompt({ title: 'Rename folder', label: 'Folder name', initial: baseName(path), confirmLabel: 'Rename' });
    if (name && name !== baseName(path)) await run(() => filesApi.moveDirectory(path, joinPath(parentOf(path), name)), 'Folder renamed');
  };

  const deleteFolder = async (path: string) => {
    const count = list.filter((file) => file.directory === path || file.directory.startsWith(`${path}/`)).length;
    const ok = await dialogs.confirm({
      title: `Delete the folder ${baseName(path)}?`,
      message: count ? `It contains ${count} file${count === 1 ? '' : 's'}, deleted with it.` : 'It is empty.',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (ok) await run(() => filesApi.removeDirectory(path), 'Folder deleted');
  };

  const deleteEverything = async () => {
    const ok = await dialogs.confirm({ title: 'Delete every file?', message: 'All files of the storage, their chunks and vectors are deleted.', confirmLabel: 'Delete everything', danger: true });
    if (ok) await run(() => filesApi.removeAll(), 'Every file was deleted');
  };

  const dropProps = {
    onDragEnter: (event: DragEvent) => {
      if (!event.dataTransfer.types.includes('Files')) return;
      dragDepth.current += 1;
      setDragging(true);
    },
    onDragLeave: () => {
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setDragging(false);
    },
    onDragOver: (event: DragEvent) => {
      if (event.dataTransfer.types.includes('Files')) event.preventDefault();
    },
    onDrop: (event: DragEvent) => {
      if (event.dataTransfer.types.includes(FILE_DRAG_TYPE)) return;
      event.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      void upload([...event.dataTransfer.files]);
    },
  };

  const toggle = (id: number) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  return (
    <div className="file-browser" {...dropProps} onDragEnd={() => { internalDrag.current = null; setDropTarget(null); }} aria-busy={moving}>
      <PageHeader
        title="Files"
        description="Your knowledge, in one place. Drop files to upload, or drag them onto a folder to move."
        actions={
          <>
            <button type="button" className="btn btn-primary" onClick={() => picker.current?.click()}>
              <Icon name="upload" /> Upload
            </button>
            <button type="button" className="btn btn-secondary" onClick={newFolder}>
              <Icon name="files" /> New folder
            </button>
            <button type="button" className="btn btn-secondary" onClick={newTextFile}>
              <Icon name="edit" /> New text file
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => run(() => filesApi.scan(), 'Checking files for changes…')} title="Detect files changed or removed on disk">
              <Icon name="refresh" /> Check for changes
            </button>
          </>
        }
      />
      <SearchInput label="Search this folder" value={search} onChange={setSearch} />
      <input
        ref={picker}
        type="file"
        multiple
        hidden
        onChange={(event) => {
          void upload([...(event.target.files ?? [])]);
          event.target.value = '';
        }}
      />

      <nav className="breadcrumb" aria-label="Folder">
        {moving && <span className="chip chip-live" role="status"><span className="spinner" /> Moving…</span>}
        <button type="button" className={`breadcrumb-item ${dir ? '' : 'is-current'} ${dropTarget === '' ? 'is-drop-target' : ''}`} onClick={() => go('')} {...dropFolder('')}>
          Storage
        </button>
        {breadcrumbs(dir).map((crumb) => (
          <span key={crumb.path} className="breadcrumb-part">
            <Icon name="chevronRight" size={14} />
            <button type="button" className={`breadcrumb-item ${crumb.path === dir ? 'is-current' : ''} ${dropTarget === crumb.path ? 'is-drop-target' : ''}`} onClick={() => go(crumb.path)} {...dropFolder(crumb.path)}>
              {crumb.name}
            </button>
          </span>
        ))}
        {uploading > 0 && (
          <span className="chip chip-live" style={{ marginLeft: 'auto' }}>
            <span className="spinner" /> Uploading {uploading}…
          </span>
        )}
      </nav>

      {selectedFiles.length > 0 && (
        <div className="selection-toolbar">
          <strong>{selectedFiles.length} selected</strong>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => run(async () => { for (const file of selectedFiles) await filesApi.process(file.id); }, 'Processing queued')}>
            Process
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveFiles(selectedFiles)}>
            Move…
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={() => deleteFiles(selectedFiles)}>
            Delete
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
        </div>
      )}

      <AsyncState {...data} onRetry={data.reload}>
        {() =>
          folders.length === 0 && here.length === 0 ? (
            <div className="state-empty drop-hint">
              <Icon name="upload" size={32} />
              <div className="state-title">{search ? 'No matching files or folders' : dir ? 'This folder is empty' : 'No file yet'}</div>
              <p className="state-desc">{search ? 'Try another search or clear the filter.' : 'Drop files here, or use Upload.'}</p>
            </div>
          ) : (
            <div className="table-container">
              <table className="table file-table">
                <thead>
                  <tr>
                    <th style={{ width: 32 }}>
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={here.length > 0 && selectedFiles.length === here.length}
                        onChange={(event) => setSelected(new Set(event.target.checked ? here.map((file) => file.id) : []))}
                      />
                    </th>
                    <th>Name</th>
                    <th>State</th>
                    <th className="num">Chunks</th>
                    <th className="num">Size</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {dir && (
                    <tr className={`file-row is-folder ${dropTarget === parentOf(dir) ? 'is-drop-target' : ''}`} onDoubleClick={() => go(parentOf(dir))} {...dropFolder(parentOf(dir))}>
                      <td />
                      <td colSpan={5}>
                        <button type="button" className="file-name" onClick={() => go(parentOf(dir))}>
                          <Icon name="back" size={16} /> ..
                        </button>
                      </td>
                    </tr>
                  )}
                  {folders.map((path) => (
                    <tr key={path} className={`file-row is-folder ${dropTarget === path ? 'is-drop-target' : ''}`} draggable={!moving} onDragStart={event => startDrag(event, { kind: 'folder', path })} {...dropFolder(path)}>
                      <td />
                      <td>
                        <button type="button" className="file-name" onClick={() => go(path)}>
                          <FileIcon folder /> {baseName(path)}
                        </button>
                      </td>
                      <td colSpan={3} className="muted small">
                        {list.filter((file) => file.directory === path || file.directory.startsWith(`${path}/`)).length || 'empty'}
                        {list.some((file) => file.directory === path || file.directory.startsWith(`${path}/`)) ? ' files' : ''}
                      </td>
                      <td className="row-actions">
                        <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => renameFolder(path)} aria-label={`Rename ${baseName(path)}`} title="Rename">
                          <Icon name="edit" />
                        </button>
                        <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => deleteFolder(path)} aria-label={`Delete ${baseName(path)}`} title="Delete">
                          <Icon name="trash" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {here.map((file) => {
                    const state = FILE_STATES[file.state] ?? FILE_STATES.new;
                    return (
                      <tr key={file.id} className={`file-row ${selected.has(file.id) ? 'is-selected' : ''}`} draggable={!moving} onDragStart={event => startDrag(event, { kind: 'files', ids: selected.has(file.id) ? selectedFiles.map(item => item.id) : [file.id] })}>
                        <td>
                          <input type="checkbox" aria-label={`Select ${fileLabel(file)}`} checked={selected.has(file.id)} onChange={() => toggle(file.id)} />
                        </td>
                        <td>
                          <button type="button" className="file-name" onClick={() => setParams({ file: file.id })} title="Open">
                            <FileIcon extension={file.extension} /> {fileLabel(file)}
                          </button>
                        </td>
                        <td>
                          <button type="button" className={`chip ${state.chip} chip-button`} title={processingSummary(file)} onClick={() => setDetails(file.id)}>
                            {file.state === 'processing' && <span className="dot dot-live" />}
                            {state.label}
                          </button>
                        </td>
                        <td className="num">{file.chunk_count || '–'}</td>
                        <td className="num">{formatSize(file.size)}</td>
                        <td className="row-actions">
                          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => setDetails(file.id)} aria-label="Details" title="Processing and chunks">
                            <Icon name="info" />
                          </button>
                          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => filesApi.download(file.id, fileLabel(file)).catch(toast.error)} aria-label="Download" title="Download">
                            <Icon name="download" />
                          </button>
                          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => renameFile(file)} aria-label="Rename" title="Rename">
                            <Icon name="edit" />
                          </button>
                          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => moveFiles([file])} aria-label="Move" title="Move">
                            <Icon name="move" />
                          </button>
                          <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => deleteFiles([file])} aria-label="Delete" title="Delete">
                            <Icon name="trash" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        }
      </AsyncState>

      {list.length > 0 && (
        <div className="row-between small muted">
          <span>
            {list.length} file{list.length === 1 ? '' : 's'} · {formatSize(list.reduce((total, file) => total + file.size, 0))}
          </span>
          <button type="button" className="btn btn-ghost btn-sm btn-danger-text" onClick={deleteEverything}>
            Delete every file
          </button>
        </div>
      )}

      {dragging && (
        <div className="drop-overlay">
          <Icon name="upload" size={36} />
          <div>Drop to upload to {dir ? <strong>{dir}</strong> : 'the storage root'}</div>
        </div>
      )}
      {detailFile && <FileDetails file={detailFile} onClose={() => setDetails(null)} onChanged={(file) => setData((current) => (current ? { ...current, list: current.list.map((item) => (item.id === file.id ? file : item)) } : current))} />}
    </div>
  );
}
