import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  getFiles,
  uploadFiles,
  deleteFiles,
  deleteAllFiles,
  processFile,
  createDirectory,
  deleteDirectory,
  getFileContent,
  downloadFile,
} from '@/api/endpoints/files';
import { progressWs } from '@/api/ws';
import { resolveViewer } from '@/core/file-viewers/registry';
import type { FileItem, FileProgressItem } from '@/core/types/api';
import { UnsupportedViewerModal } from '@/modules/file-viewers/UnsupportedViewerModal';

interface ClipboardItem {
  type: 'file' | 'folder';
  file?: FileItem;
  folderPath?: string;
  name: string;
}

interface FileExplorerProps {
  onOpenFile?: (file: FileItem) => void;
}

const normalizeStoragePath = (path: string): string => {
  const normalized = path.replace(/\\/g, '/');
  const storageMarker = normalized.toLowerCase().lastIndexOf('/storages/');
  if (storageMarker >= 0) {
    return normalized.slice(storageMarker + '/storages/'.length);
  }
  return normalized.replace(/^\/+/, '');
};

const joinStoragePath = (directory: string, name: string): string =>
  directory ? `${directory}/${name}` : name;

export const FileExplorer: React.FC<FileExplorerProps> = ({ onOpenFile }) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Current folder navigation
  const [currentDir, setCurrentDir] = useState<string>('');
  const [knownDirectories, setKnownDirectories] = useState<string[]>([]);

  // Selection
  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);

  // Clipboard (Copy & Paste)
  const [clipboard, setClipboard] = useState<ClipboardItem[] | null>(null);
  const [isPasting, setIsPasting] = useState<boolean>(false);

  // New Folder Modal
  const [showNewFolderModal, setShowNewFolderModal] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>('');
  const [isCreatingFolder, setIsCreatingFolder] = useState<boolean>(false);

  // Upload Modal
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [uploadFilesQueue, setUploadFilesQueue] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDraggingModal, setIsDraggingModal] = useState<boolean>(false);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);

  // New File Modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newFileName, setNewFileName] = useState<string>('note.md');
  const [newFileContent, setNewFileContent] = useState<string>('# New Document\n\n');

  // Unsupported File Modal
  const [unsupportedFile, setUnsupportedFile] = useState<FileItem | null>(null);

  // Load files
  const loadFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFiles();
      setFiles(data);

      // Extract all directories from files
      const dirs = new Set<string>();
      for (const f of data) {
        if (f.path) {
          const normalized = normalizeStoragePath(f.path);
          const parts = normalized.split('/');
          if (parts.length > 1) {
            let currentPath = '';
            for (let i = 0; i < parts.length - 1; i++) {
              currentPath = joinStoragePath(currentPath, parts[i]);
              dirs.add(currentPath);
            }
          }
        }
      }
      setKnownDirectories((prev) => Array.from(new Set([...prev, ...Array.from(dirs)])));
    } catch (err: any) {
      setError(err?.message || 'Failed to load files from server');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();

    // Listen to real-time progress via WebSocket
    const unsubscribe = progressWs.subscribe((progressUpdates: FileProgressItem[]) => {
      setFiles((prevFiles) => {
        const updateMap = new Map(progressUpdates.map((u) => [u.id, u]));
        return prevFiles.map((file) => {
          const update = file.id !== undefined
            ? updateMap.get(file.id)
            : progressUpdates.find((candidate) => candidate.name === file.name);
          if (update) {
            return {
              ...file,
              id: file.id ?? update.id,
              status: update.status === 'finished' ? 'done' : update.status,
            };
          }
          return file;
        });
      });
    });

    return () => {
      unsubscribe();
    };
  }, [loadFiles]);

  // Direct subdirectories inside currentDir
  const currentSubdirectories = useMemo(() => {
    const subdirs = new Set<string>();
    const prefix = currentDir ? `${currentDir}/` : '';

    for (const d of knownDirectories) {
      if (d !== currentDir && d.startsWith(prefix)) {
        const remaining = d.slice(prefix.length);
        const firstSegment = remaining.split('/')[0];
        if (firstSegment) {
          subdirs.add(prefix + firstSegment);
        }
      }
    }
    return Array.from(subdirs).sort();
  }, [knownDirectories, currentDir]);

  // Direct files inside currentDir
  const currentDirectoryFiles = useMemo(() => {
    return files.filter((f) => {
      if (!f.path) return currentDir === '';
      const normalized = normalizeStoragePath(f.path);
      const lastSlashIdx = normalized.lastIndexOf('/');
      const fileDir = lastSlashIdx >= 0 ? normalized.slice(0, lastSlashIdx) : '';
      return fileDir === currentDir;
    });
  }, [files, currentDir]);

  // Breadcrumbs path elements
  const breadcrumbSegments = useMemo(() => {
    if (!currentDir) return [];
    return currentDir.split('/');
  }, [currentDir]);

  const handleNavigateBreadcrumb = (index: number) => {
    const nextDir = breadcrumbSegments.slice(0, index + 1).join('/');
    setCurrentDir(nextDir);
    setSelectedFileIds([]);
    setSelectedFolders([]);
  };

  const handleNavigateRoot = () => {
    setCurrentDir('');
    setSelectedFileIds([]);
    setSelectedFolders([]);
  };

  // Selection handlers
  const handleToggleSelectFile = (id?: number) => {
    if (id === undefined) return;
    setSelectedFileIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleToggleSelectFolder = (folderPath: string) => {
    setSelectedFolders((prev) =>
      prev.includes(folderPath) ? prev.filter((item) => item !== folderPath) : [...prev, folderPath]
    );
  };

  // Open file or folder
  const handleFolderDoubleClick = (folderPath: string) => {
    setCurrentDir(folderPath);
    setSelectedFileIds([]);
    setSelectedFolders([]);
  };

  const handleFileOpen = (file: FileItem) => {
    const viewer = resolveViewer(file.extension);
    if (!viewer) {
      setUnsupportedFile(file);
      return;
    }
    if (onOpenFile) {
      onOpenFile(file);
    }
  };

  // Create folder
  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newFolderName.trim().replace(/[\\/]/g, '');
    if (!cleanName) return;

    const targetPath = joinStoragePath(currentDir, cleanName);
    setIsCreatingFolder(true);
    setError(null);
    try {
      await createDirectory(targetPath);
      setKnownDirectories((prev) => Array.from(new Set([...prev, targetPath])));
      setNewFolderName('');
      setShowNewFolderModal(false);
      setSuccessMessage(`Folder "${cleanName}" created successfully.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Failed to create folder');
    } finally {
      setIsCreatingFolder(false);
    }
  };

  // Upload modal actions
  const handleUploadStagedFiles = async () => {
    if (uploadFilesQueue.length === 0) return;
    setIsUploading(true);
    setError(null);
    try {
      await uploadFiles(currentDir, uploadFilesQueue);
      setUploadFilesQueue([]);
      setShowUploadModal(false);
      setSuccessMessage(`Uploaded ${uploadFilesQueue.length} file(s) to "${currentDir}".`);
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleAddFilesToQueue = (filesList: FileList | null) => {
    if (!filesList) return;
    const newFiles = Array.from(filesList);
    setUploadFilesQueue((prev) => [...prev, ...newFiles]);
  };

  // Create text file
  const handleCreateNewFile = async () => {
    if (!newFileName.trim()) return;
    const blob = new Blob([newFileContent], { type: 'text/plain;charset=utf-8' });
    const file = new File([blob], newFileName.trim(), { type: 'text/plain' });

    setShowCreateModal(false);
    setIsUploading(true);
    try {
      await uploadFiles(currentDir, [file]);
      await loadFiles();
      setSuccessMessage(`Created file "${newFileName.trim()}".`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Failed to create file');
    } finally {
      setIsUploading(false);
    }
  };

  // Delete selected
  const handleDeleteSelected = async () => {
    const totalCount = selectedFileIds.length + selectedFolders.length;
    if (totalCount === 0) return;
    if (!window.confirm(`Are you sure you want to delete ${totalCount} selected item(s)?`)) return;

    setLoading(true);
    setError(null);
    try {
      if (selectedFileIds.length > 0) {
        await deleteFiles(selectedFileIds);
      }
      for (const folder of selectedFolders) {
        await deleteDirectory(folder);
        setKnownDirectories((prev) => prev.filter((d) => d !== folder && !d.startsWith(`${folder}/`)));
      }
      setSelectedFileIds([]);
      setSelectedFolders([]);
      setSuccessMessage(`Deleted ${totalCount} item(s) successfully.`);
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete selected items');
    } finally {
      setLoading(false);
    }
  };

  // Delete single folder
  const handleDeleteFolder = async (folderPath: string) => {
    const folderName = folderPath.split('/').pop();
    if (!window.confirm(`Are you sure you want to delete folder "${folderName}" and all its contents?`)) return;
    setLoading(true);
    try {
      await deleteDirectory(folderPath);
      setKnownDirectories((prev) => prev.filter((d) => d !== folderPath && !d.startsWith(`${folderPath}/`)));
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete folder');
    } finally {
      setLoading(false);
    }
  };

  // Delete all
  const handleDeleteAll = async () => {
    if (!window.confirm('WARNING: Are you sure you want to permanently delete ALL files in storage?')) return;
    setLoading(true);
    try {
      await deleteAllFiles();
      setSelectedFileIds([]);
      setSelectedFolders([]);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete all files');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteFile = async (fileId: number, fileName: string) => {
    if (!window.confirm(`Delete ${fileName}?`)) return;
    setLoading(true);
    setError(null);
    try {
      await deleteFiles([fileId]);
      await loadFiles();
      setSuccessMessage(`Deleted ${fileName} successfully.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || `Failed to delete ${fileName}`);
    } finally {
      setLoading(false);
    }
  };

  // Process single file
  const handleProcess = async (fileId: number) => {
    try {
      await processFile(fileId);
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, status: 'queued' } : f))
      );
      setSuccessMessage(`File #${fileId} queued for RAG processing.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || `Failed to trigger processing for file #${fileId}`);
    }
  };

  // Copy selected items to clipboard
  const handleCopySelected = () => {
    const items: ClipboardItem[] = [];
    for (const id of selectedFileIds) {
      const f = files.find((item) => item.id === id);
      if (f) {
        items.push({ type: 'file', file: f, name: `${f.name}${f.extension}` });
      }
    }
    for (const folder of selectedFolders) {
      const folderName = folder.split('/').pop() || folder;
      items.push({ type: 'folder', folderPath: folder, name: folderName });
    }
    setClipboard(items);
    setSuccessMessage(`Copied ${items.length} item(s) to clipboard.`);
    setTimeout(() => setSuccessMessage(null), 2500);
  };

  // Paste clipboard items into current directory
  const handlePaste = async () => {
    if (!clipboard || clipboard.length === 0) return;
    setIsPasting(true);
    setError(null);
    try {
      let pastedCount = 0;
      for (const item of clipboard) {
        if (item.type === 'file' && item.file && item.file.id) {
          // Fetch content and re-upload into currentDir
          const content = await getFileContent(item.file.id);
          const isSameDir = item.file.path
            ? normalizeStoragePath(item.file.path).startsWith(`${currentDir}/`)
            : currentDir === '';
          const fileName = isSameDir ? `copy_${item.file.name}${item.file.extension}` : `${item.file.name}${item.file.extension}`;
          const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
          const fileToUpload = new File([blob], fileName, { type: 'text/plain' });
          await uploadFiles(currentDir, [fileToUpload]);
          pastedCount++;
        } else if (item.type === 'folder') {
          const destFolderPath = joinStoragePath(currentDir, item.name);
          await createDirectory(destFolderPath);
          setKnownDirectories((prev) => Array.from(new Set([...prev, destFolderPath])));
          pastedCount++;
        }
      }
      setSuccessMessage(`Pasted ${pastedCount} item(s) into "${currentDir}".`);
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Failed to paste items');
    } finally {
      setIsPasting(false);
    }
  };

  const totalSelectionCount = selectedFileIds.length + selectedFolders.length;

  return (
    <div className="content-container">
      {/* Top Header Card */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>📂</span>
            <div>
              <h2 className="card-title">File Explorer</h2>
              <p className="card-description">
                Browse documents, folders, manage embeddings and trigger RAG indexing
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {clipboard && clipboard.length > 0 && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handlePaste}
                disabled={isPasting}
                title={`Paste ${clipboard.length} item(s) into ${currentDir}`}
              >
                📋 {isPasting ? 'Pasting...' : `Paste (${clipboard.length})`}
              </button>
            )}

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowNewFolderModal(true)}
            >
              📁 + New Folder
            </button>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowCreateModal(true)}
            >
              📝 + New File
            </button>

            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => setShowUploadModal(true)}
            >
              ⬆️ Upload Files
            </button>

            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleDeleteAll}
              title="Purge all files from database and storage"
              style={{ color: 'var(--color-error)' }}
            >
              Purge All
            </button>
          </div>
        </div>

        {/* Google Drive-style Breadcrumb Bar */}
        <div
          style={{
            padding: '10px 20px',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'rgba(0,0,0,0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div className="breadcrumb-container">
            <span
              className="breadcrumb-item"
              onClick={handleNavigateRoot}
              title="Go to root"
            >
              🏠 Storage Root
            </span>
            {breadcrumbSegments.map((segment, idx) => {
              const isLast = idx === breadcrumbSegments.length - 1;
              return (
                <React.Fragment key={idx}>
                  <span>›</span>
                  <span
                    className={`breadcrumb-item ${isLast ? 'active' : ''}`}
                    onClick={() => !isLast && handleNavigateBreadcrumb(idx)}
                  >
                    📁 {segment}
                  </span>
                </React.Fragment>
              );
            })}
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {currentSubdirectories.length} folder(s) · {currentDirectoryFiles.length} file(s)
          </div>
        </div>

        {/* Action Bar when items are selected */}
        <div
          className="selection-toolbar"
          aria-hidden={totalSelectionCount === 0}
          style={{ visibility: totalSelectionCount > 0 ? 'visible' : 'hidden' }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>
                ✓ {totalSelectionCount} item(s) selected
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleCopySelected}
                title="Copy selected items"
              >
                📋 Copy
              </button>

              {selectedFileIds.length === 1 && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    const f = files.find((item) => item.id === selectedFileIds[0]);
                    if (f) downloadFile(f.id!, `${f.name}${f.extension}`);
                  }}
                  title="Download file"
                >
                  ⬇️ Download
                </button>
              )}

              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={handleDeleteSelected}
                title="Delete selected files and folders"
              >
                🗑️ Delete ({totalSelectionCount})
              </button>

              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setSelectedFileIds([]);
                  setSelectedFolders([]);
                }}
              >
                Deselect
              </button>
            </div>
        </div>

        {/* Feedback Alerts */}
        {error && (
          <div style={{ padding: '16px 20px 0' }}>
            <div className="alert alert-error">
              <span>⚠️</span>
              <div style={{ flex: 1 }}>{error}</div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setError(null)}>✕</button>
            </div>
          </div>
        )}

        {successMessage && (
          <div style={{ padding: '16px 20px 0' }}>
            <div className="alert alert-success">
              <span>✓</span>
              <div style={{ flex: 1 }}>{successMessage}</div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSuccessMessage(null)}>✕</button>
            </div>
          </div>
        )}

        {/* Vertical List / Table */}
        <div style={{ padding: '16px 20px 24px' }}>
          {loading ? (
            <div className="state-loading">
              <span className="spinner" />
              <div className="state-title">Loading files and folders...</div>
            </div>
          ) : currentSubdirectories.length === 0 && currentDirectoryFiles.length === 0 ? (
            <div className="state-empty">
              <span style={{ fontSize: '2.5rem' }}>📁</span>
              <div className="state-title">This folder is empty</div>
              <p className="state-desc">
                Upload documents or create a new folder or file to begin.
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowNewFolderModal(true)}
                >
                  + New Folder
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => setShowUploadModal(true)}
                >
                  Upload Files
                </button>
              </div>
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status / Type</th>
                    <th>Embedded By</th>
                    <th>Vector DB</th>
                    <th>Size</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Subdirectories */}
                  {currentSubdirectories.map((folderPath) => {
                    const isSelected = selectedFolders.includes(folderPath);
                    const folderName = folderPath.split('/').pop() || folderPath;
                    return (
                      <tr
                        key={folderPath}
                        className={isSelected ? 'row-selected' : ''}
                        onClick={() => handleToggleSelectFolder(folderPath)}
                        onDoubleClick={() => handleFolderDoubleClick(folderPath)}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '1.2rem' }}>📁</span>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                              {folderName}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="badge badge-muted">Folder</span>
                        </td>
                        <td style={{ color: 'var(--text-muted)' }}>—</td>
                        <td style={{ color: 'var(--text-muted)' }}>—</td>
                        <td style={{ color: 'var(--text-muted)' }}>—</td>
                        <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => handleDeleteFolder(folderPath)}
                              title="Delete folder"
                              style={{ color: 'var(--color-error)' }}
                            >
                              🗑️
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}

                  {/* Files */}
                  {currentDirectoryFiles.map((file) => {
                    const isSelected = file.id !== undefined && selectedFileIds.includes(file.id);
                    return (
                      <tr
                        key={`${file.id ?? file.path}-${file.name}`}
                        className={isSelected ? 'row-selected' : ''}
                        onClick={() => handleToggleSelectFile(file.id)}
                        onDoubleClick={() => handleFileOpen(file)}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span>{file.extension === '.md' ? '📝' : '📄'}</span>
                            <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                              {file.name}{file.extension}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              file.status === 'done'
                                ? 'badge-success'
                                : file.status === 'processing'
                                ? 'badge-info'
                                : file.status === 'queued' || file.status === 'pending'
                                ? 'badge-warning'
                                : 'badge-error'
                            }`}
                          >
                            {file.status === 'processing' && (
                              <span className="spinner" style={{ width: 10, height: 10 }} />
                            )}
                            {file.status}
                          </span>
                        </td>
                        <td>
                          {file.embedded_by && file.embedded_by.length > 0 ? (
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                              {file.embedded_by.map((modelId) => (
                                <span key={modelId} className="badge badge-muted" style={{ fontSize: '0.7rem' }}>
                                  Model #{modelId}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>None</span>
                          )}
                        </td>
                        <td>
                          {file.vector_db && file.vector_db.length > 0 ? (
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                              {file.vector_db.map((vdb) => (
                                <span key={vdb} className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                                  {vdb}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>None</span>
                          )}
                        </td>
                        <td style={{ color: 'var(--text-secondary)' }}>
                          {(file.size / 1024).toFixed(1)} KB
                        </td>
                        <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            {file.id && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleProcess(file.id!)}
                                title="Process chunking & embedding"
                              >
                                ⚡ Process
                              </button>
                            )}
                            {file.id && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => downloadFile(file.id!, `${file.name}${file.extension}`)}
                                title="Download binary file"
                              >
                                ⬇️
                              </button>
                            )}
                            {file.id && (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => handleDeleteFile(file.id!, `${file.name}${file.extension}`)}
                                title="Delete file"
                                style={{ color: 'var(--color-error)' }}
                              >
                                🗑️
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* New Folder Modal */}
      {showNewFolderModal && (
        <div className="modal-backdrop" onClick={() => setShowNewFolderModal(false)}>
          <div className="modal-window" style={{ maxWidth: '460px' }} onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreateFolder}>
              <div className="modal-header">
                <h3 className="card-title">New Folder</h3>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewFolderModal(false)}>
                  ✕
                </button>
              </div>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Create an empty folder inside: <code>{currentDir}/</code>
                </p>
                <div className="form-group">
                  <label className="form-label">Folder Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="e.g. reports, research, archive"
                    autoFocus
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewFolderModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={isCreatingFolder || !newFolderName.trim()}>
                  {isCreatingFolder ? 'Creating...' : 'Create Folder'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Upload Modal with Drag & Drop */}
      {showUploadModal && (
        <div className="modal-backdrop" onClick={() => !isUploading && setShowUploadModal(false)}>
          <div className="modal-window" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.25rem' }}>⬆️</span>
                <h3 className="card-title">Upload Files</h3>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowUploadModal(false)}
                disabled={isUploading}
              >
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Target destination directory: <strong>{currentDir}</strong>
              </div>

              {/* Drag and drop area */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDraggingModal(true);
                }}
                onDragLeave={() => setIsDraggingModal(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDraggingModal(false);
                  handleAddFilesToQueue(e.dataTransfer.files);
                }}
                onClick={() => uploadFileInputRef.current?.click()}
                style={{
                  padding: '36px 20px',
                  border: isDraggingModal ? '2px dashed var(--accent-primary)' : '2px dashed var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: isDraggingModal ? 'var(--accent-glow)' : 'rgba(255, 255, 255, 0.01)',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '8px' }}>
                  {isDraggingModal ? '📥' : '☁️'}
                </span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                  {isDraggingModal ? 'Drop files to add them' : 'Drag and drop files here, or click to browse'}
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Supports Markdown, Text, Code, PDF and document files
                </p>
                <input
                  type="file"
                  ref={uploadFileInputRef}
                  style={{ display: 'none' }}
                  multiple
                  onChange={(e) => handleAddFilesToQueue(e.target.files)}
                />
              </div>

              {/* Staged files list */}
              {uploadFilesQueue.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Files to upload ({uploadFilesQueue.length}):
                  </div>
                  <div
                    style={{
                      maxHeight: '180px',
                      overflowY: 'auto',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'rgba(0,0,0,0.15)',
                    }}
                  >
                    {uploadFilesQueue.map((f, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          borderBottom: idx < uploadFilesQueue.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                          fontSize: '0.825rem',
                        }}
                      >
                        <span style={{ color: 'var(--text-primary)' }}>{f.name}</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ color: 'var(--text-muted)' }}>{(f.size / 1024).toFixed(1)} KB</span>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            style={{ padding: '2px 6px', color: 'var(--color-error)' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setUploadFilesQueue((prev) => prev.filter((_, i) => i !== idx));
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowUploadModal(false)}
                disabled={isUploading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleUploadStagedFiles}
                disabled={isUploading || uploadFilesQueue.length === 0}
              >
                {isUploading ? 'Uploading...' : `Upload ${uploadFilesQueue.length} file(s)`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Text File Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-window" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">New Text Document</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCreateModal(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="form-group">
                <label className="form-label">File Name (with extension, e.g. .md, .txt, .json)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  placeholder="note.md"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Initial Content</label>
                <textarea
                  className="form-textarea"
                  style={{ minHeight: '180px', fontFamily: 'monospace', fontSize: '0.85rem' }}
                  value={newFileContent}
                  onChange={(e) => setNewFileContent(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
              <button type="button" className="btn btn-primary btn-sm" onClick={handleCreateNewFile}>
                Create Document
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Unsupported Format Modal */}
      {unsupportedFile && (
        <UnsupportedViewerModal
          file={unsupportedFile}
          onClose={() => setUnsupportedFile(null)}
        />
      )}
    </div>
  );
};
