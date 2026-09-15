import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  getFiles,
  uploadFiles,
  deleteFiles,
  deleteAllFiles,
  processFile,
} from '@/api/endpoints/files';
import { progressWs } from '@/api/ws';
import type { FileItem, FileProgressItem } from '@/core/types/api';
import { FileViewerModal } from '@/modules/file-viewers/FileViewerModal';

export const FileExplorer: React.FC = () => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [currentDir, setCurrentDir] = useState<string>('documents');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [activeFileForViewer, setActiveFileForViewer] = useState<FileItem | null>(null);
  const [activeFileContent, setActiveFileContent] = useState<string>('');
  
  // Modale de création de fichier texte
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newFileName, setNewFileName] = useState<string>('note.md');
  const [newFileContent, setNewFileContent] = useState<string>('# Nouveau document\n\n');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Chargement des fichiers
  const loadFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFiles();
      setFiles(data);
    } catch (err: any) {
      setError(err?.message || 'Erreur lors du chargement des fichiers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();

    // Écoute temps réel de la progression via WebSocket
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

  // Arborescence de dossiers déduite des chemins
  const availableDirectories = useMemo(() => {
    const dirs = new Set<string>(['documents']);
    for (const f of files) {
      if (f.path) {
        // Normaliser les séparateurs de chemin Windows et Unix
        const normalized = f.path.replace(/\\/g, '/');
        const parts = normalized.split('/');
        // Si le chemin contient des dossiers
        if (parts.length > 1) {
          // Extraire le dossier parent
          const parentDir = parts.slice(0, -1).join('/');
          const cleanDir = parentDir.split('storages/').pop() || parentDir;
          dirs.add(cleanDir);
        }
      }
    }
    return Array.from(dirs);
  }, [files]);

  // Filtrage des fichiers selon le dossier courant (ou affichage de tous si sélection globale)
  const filteredFiles = useMemo(() => {
    if (!currentDir || currentDir === 'all') return files;
    return files.filter((f) => {
      const normalized = (f.path || '').replace(/\\/g, '/');
      return normalized.includes(currentDir);
    });
  }, [files, currentDir]);

  // Sélection multiple
  const handleSelectAll = () => {
    if (selectedIds.length === filteredFiles.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredFiles.map((f) => f.id).filter((id): id is number => id !== undefined));
    }
  };

  const handleToggleSelect = (id?: number) => {
    if (id === undefined) return;
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Upload par bouton ou drag & drop
  const handleUploadFiles = async (fileList: FileList | File[]) => {
    const filesToUpload = Array.from(fileList);
    if (filesToUpload.length === 0) return;

    setIsUploading(true);
    setError(null);
    try {
      await uploadFiles(currentDir === 'all' ? 'documents' : currentDir, filesToUpload);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || "Erreur lors de l'upload des fichiers");
    } finally {
      setIsUploading(false);
    }
  };

  // Drag and drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleUploadFiles(e.dataTransfer.files);
    }
  };

  // Suppression sélectionnée
  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Confirmez-vous la suppression de ${selectedIds.length} fichier(s) ?`)) return;

    setLoading(true);
    try {
      await deleteFiles(selectedIds);
      setSelectedIds([]);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Erreur lors de la suppression');
    } finally {
      setLoading(false);
    }
  };

  // Suppression totale
  const handleDeleteAll = async () => {
    if (!window.confirm('ATTENTION : Voulez-vous vraiment supprimer TOUS les fichiers enregistrés ?')) return;

    setLoading(true);
    try {
      await deleteAllFiles();
      setSelectedIds([]);
      await loadFiles();
    } catch (err: any) {
      setError(err?.message || 'Erreur lors de la suppression totale');
    } finally {
      setLoading(false);
    }
  };

  // Déclencher le traitement
  const handleProcess = async (fileId: number) => {
    try {
      await processFile(fileId);
      // Mettre à jour immédiatement l'état local en queued
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, status: 'queued' } : f))
      );
    } catch (err: any) {
      setError(err?.message || `Échec du déclenchement du traitement pour le fichier #${fileId}`);
    }
  };

  // Création d'un nouveau fichier texte
  const handleCreateNewFile = async () => {
    if (!newFileName.trim()) return;
    const blob = new Blob([newFileContent], { type: 'text/plain;charset=utf-8' });
    const file = new File([blob], newFileName.trim(), { type: 'text/plain' });

    setShowCreateModal(false);
    await handleUploadFiles([file]);
  };

  // Sauvegarde depuis l'éditeur
  const handleSaveFromViewer = async (newContent: string) => {
    if (!activeFileForViewer) return;
    const blob = new Blob([newContent], { type: 'text/plain;charset=utf-8' });
    const file = new File([blob], `${activeFileForViewer.name}${activeFileForViewer.extension}`, {
      type: 'text/plain',
    });
    // On upload la nouvelle version
    await uploadFiles(currentDir === 'all' ? 'documents' : currentDir, [file]);
    await loadFiles();
  };

  return (
    <div className="content-container">
      {/* Barre d'outils et actions de l'explorateur */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '1.25rem' }}>📂</span>
            <div>
              <h2 className="card-title">Gestionnaire de fichiers</h2>
              <p className="card-description">
                Stockage de documents, découpage et pipeline RAG
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {selectedIds.length > 0 && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={handleDeleteSelected}
              >
                🗑️ Supprimer ({selectedIds.length})
              </button>
            )}

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowCreateModal(true)}
            >
              + Nouveau fichier
            </button>

            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? 'Upload en cours...' : '⬆️ Uploader des fichiers'}
            </button>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              multiple
              onChange={(e) => e.target.files && handleUploadFiles(e.target.files)}
            />

            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleDeleteAll}
              title="Vider tous les fichiers"
              style={{ color: 'var(--color-error)' }}
            >
              Purger tout
            </button>
          </div>
        </div>

        {/* Sélecteur de dossier / breadcrumbs */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: 'rgba(0,0,0,0.1)' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Dossier actif :</span>
          <div style={{ display: 'flex', gap: '6px', overflowX: 'auto' }}>
            <button
              type="button"
              className={`btn btn-sm ${currentDir === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setCurrentDir('all')}
            >
              Tous les dossiers
            </button>
            {availableDirectories.map((dir) => (
              <button
                key={dir}
                type="button"
                className={`btn btn-sm ${currentDir === dir ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setCurrentDir(dir)}
              >
                📁 {dir}
              </button>
            ))}
          </div>
        </div>

        {/* Alerte d'erreur si présente */}
        {error && (
          <div style={{ padding: '0 20px', marginTop: '16px' }}>
            <div className="alert alert-error">
              <span>⚠️</span>
              <div style={{ flex: 1 }}>{error}</div>
              <button type="button" className="btn btn-sm btn-ghost" onClick={loadFiles}>
                Réessayer
              </button>
            </div>
          </div>
        )}

        {/* Zone de Drag & Drop */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            margin: '16px 20px',
            padding: '24px',
            border: isDragging ? '2px dashed var(--accent-primary)' : '2px dashed var(--border-base)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: isDragging ? 'var(--accent-glow)' : 'rgba(255,255,255,0.01)',
            textAlign: 'center',
            transition: 'all var(--transition-fast)',
            cursor: 'pointer',
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <span style={{ fontSize: '1.8rem', display: 'block', marginBottom: '6px' }}>
            {isDragging ? '📥 Déposez vos fichiers ici' : '☁️ Glissez-déposez vos fichiers ici'}
          </span>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
            Supporte le multi-upload de documents texte, markdown, code ou binaires dans "{currentDir}"
          </p>
        </div>

        {/* Tableau des fichiers */}
        <div style={{ padding: '0 20px 20px 20px' }}>
          {loading ? (
            <div className="state-loading">
              <span className="spinner" />
              <div className="state-title">Chargement des fichiers...</div>
            </div>
          ) : filteredFiles.length === 0 ? (
            <div className="state-empty">
              <span style={{ fontSize: '2.5rem' }}>📄</span>
              <div className="state-title">Aucun fichier dans ce répertoire</div>
              <p className="state-desc">
                Glissez-déposez des documents ci-dessus ou cliquez sur "Nouveau fichier" pour démarrer l'indexation.
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowCreateModal(true)}
              >
                Créer un fichier
              </button>
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.length === filteredFiles.length && filteredFiles.length > 0}
                        onChange={handleSelectAll}
                        aria-label="Tout sélectionner"
                      />
                    </th>
                    <th>Nom du fichier</th>
                    <th>Statut RAG</th>
                    <th>Taille</th>
                    <th>ID</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFiles.map((file) => {
                    const isSelected = file.id !== undefined && selectedIds.includes(file.id);
                    return (
                      <tr key={`${file.id ?? file.path}-${file.name}`}>
                        <td>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelect(file.id)}
                            aria-label={`Sélectionner ${file.name}`}
                          />
                        </td>
                        <td>
                          <div
                            style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
                            onClick={() => {
                              setActiveFileForViewer(file);
                              setActiveFileContent('');
                            }}
                          >
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
                            {file.status === 'processing' && <span className="spinner" style={{ width: 10, height: 10 }} />}
                            {file.status}
                          </span>
                        </td>
                        <td style={{ color: 'var(--text-secondary)' }}>
                          {(file.size / 1024).toFixed(1)} Ko
                        </td>
                        <td style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                          {file.id ?? '—'}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setActiveFileForViewer(file);
                                setActiveFileContent('');
                              }}
                              title="Visualiser ou éditer"
                            >
                              👁️ Ouvrir
                            </button>
                            {file.id && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleProcess(file.id!)}
                                title="Déclencher le découpage & embedding"
                              >
                                ⚡ Traiter
                              </button>
                            )}
                            {file.id && (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => {
                                  if (window.confirm(`Supprimer ${file.name}${file.extension} ?`)) {
                                    deleteFiles([file.id!]).then(loadFiles);
                                  }
                                }}
                                title="Supprimer ce fichier"
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

      {/* Modale de création d'un nouveau fichier texte */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-window" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Nouveau fichier texte</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCreateModal(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Nom du document (avec extension, ex: .md, .txt)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  placeholder="notes.md"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Contenu initial</label>
                <textarea
                  className="form-textarea"
                  style={{ minHeight: '160px', fontFamily: 'monospace' }}
                  value={newFileContent}
                  onChange={(e) => setNewFileContent(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowCreateModal(false)}
              >
                Annuler
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleCreateNewFile}
                disabled={!newFileName.trim()}
              >
                Créer et enregistrer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modale de visualisation / édition dynamique */}
      <FileViewerModal
        file={activeFileForViewer}
        content={activeFileContent}
        onClose={() => setActiveFileForViewer(null)}
        onSave={handleSaveFromViewer}
        onProcess={async (id) => {
          await handleProcess(id);
          setActiveFileForViewer(null);
        }}
      />
    </div>
  );
};
