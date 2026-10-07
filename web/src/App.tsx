import { useEffect, useState } from 'react';
import { AppHeader } from '@/modules/app-header/AppHeader';
import { ApiKeyManager } from '@/modules/api-keys/ApiKeyManager';
import { DatabaseSettings } from '@/modules/database-settings/DatabaseSettings';
import { EnginePresets } from '@/modules/engine-presets/EnginePresets';
import { FileExplorer } from '@/modules/file-explorer/FileExplorer';
import { Preferences } from '@/modules/preferences/Preferences';
import { registerAllBuiltinViewers } from '@/modules/file-viewers';
import { resolveViewer } from '@/core/file-viewers/registry';
import { ModelManager } from '@/modules/model-manager/ModelManager';
import { SemanticSearch } from '@/modules/semantic-search/SemanticSearch';
import { getFileContent, updateFileContent, processFile } from '@/api/endpoints/files';
import type { TabType } from '@/core/types/common';
import type { FileItem } from '@/core/types/api';

const navigation: Array<{ id: TabType; label: string; icon: string }> = [
  { id: 'files', label: 'Files', icon: '▦' },
  { id: 'models', label: 'Models', icon: '◈' },
  { id: 'embeddings', label: 'Embeddings', icon: '⌁' },
  { id: 'inference', label: 'Inference', icon: '✦' },
  { id: 'search', label: 'Search', icon: '⌕' },
  { id: 'databases', label: 'Databases', icon: '▤' },
  { id: 'api-keys', label: 'API Keys', icon: '⚿' },
  { id: 'preferences', label: 'Preferences', icon: '⚙' },
];

interface OpenFileSession {
  file: FileItem;
  content: string;
}

const activeTabStorageKey = 'lazy-bird-active-nav-item';

const getStoredActiveTab = (): TabType => {
  const storedTab = window.localStorage.getItem(activeTabStorageKey);
  return navigation.some((item) => item.id === storedTab) ? (storedTab as TabType) : 'files';
};

function App() {
  const [activeTab, setActiveTab] = useState<TabType>(getStoredActiveTab);
  const [openFiles, setOpenFiles] = useState<OpenFileSession[]>([]);
  const [activeOpenFileId, setActiveOpenFileId] = useState<number | null>(null);
  const [fileOpenError, setFileOpenError] = useState<string | null>(null);

  useEffect(() => {
    registerAllBuiltinViewers();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(activeTabStorageKey, activeTab);
  }, [activeTab]);

  // Open a file in a new editor tab
  const handleOpenFile = async (file: FileItem) => {
    if (!file.id) return;

    // Check if file is already open
    const existing = openFiles.find((s) => s.file.id === file.id);
    if (existing) {
      setActiveOpenFileId(file.id);
      return;
    }

    setFileOpenError(null);
    try {
      const content = await getFileContent(file.id);
      setOpenFiles((prev) => [...prev, { file, content }]);
      setActiveOpenFileId(file.id);
    } catch (err: any) {
      setFileOpenError(err?.message || `Impossible d'ouvrir ${file.name}${file.extension}.`);
    }
  };

  // Close an open file tab
  const handleCloseFileTab = (fileId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setOpenFiles((prev) => {
      const next = prev.filter((s) => s.file.id !== fileId);
      if (activeOpenFileId === fileId) {
        if (next.length > 0) {
          setActiveOpenFileId(next[next.length - 1].file.id ?? null);
        } else {
          setActiveOpenFileId(null);
        }
      }
      return next;
    });
  };

  // Save file content from editor
  const handleSaveFile = async (fileId: number, nextContent: string) => {
    const updated = await updateFileContent(fileId, nextContent);
    setOpenFiles((prev) =>
      prev.map((s) => (s.file.id === fileId ? { file: updated, content: nextContent } : s))
    );
  };

  // Process file from editor
  const handleProcessFile = async (fileId: number) => {
    await processFile(fileId);
  };

  const activeOpenFileSession = openFiles.find((s) => s.file.id === activeOpenFileId);
  const activeViewer = activeOpenFileSession ? resolveViewer(activeOpenFileSession.file.extension) : null;

  const renderActiveModule = () => {
    // If a file tab is active, render its dedicated editor
    if (activeOpenFileSession && activeViewer) {
      const ViewerComponent = activeViewer.Component;
      return (
        <div className="content-container" style={{ height: 'calc(100vh - 150px)' }}>
          <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div className="card-body" style={{ flex: 1, overflow: 'hidden', padding: '20px' }}>
              <ViewerComponent
                file={activeOpenFileSession.file}
                content={activeOpenFileSession.content}
                onSave={(next) => handleSaveFile(activeOpenFileSession.file.id!, next)}
                onClose={() => handleCloseFileTab(activeOpenFileSession.file.id!)}
                onProcess={() => handleProcessFile(activeOpenFileSession.file.id!)}
              />
            </div>
          </div>
        </div>
      );
    }

    // Otherwise render standard workspace views
    switch (activeTab) {
      case 'files':
        return <FileExplorer onOpenFile={handleOpenFile} />;
      case 'models':
        return <ModelManager />;
      case 'embeddings':
        return <EnginePresets kind="embedding" />;
      case 'inference':
        return <EnginePresets kind="inference" />;
      case 'search':
        return <SemanticSearch />;
      case 'databases':
        return <DatabaseSettings />;
      case 'api-keys':
        return <ApiKeyManager />;
      case 'preferences':
        return <Preferences />;
      default:
        return <FileExplorer onOpenFile={handleOpenFile} />;
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo-icon" aria-hidden="true">L</div>
          <div>
            <div className="sidebar-title">lazy_bird</div>
            <div className="sidebar-subtitle">RAG workspace</div>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Workspaces">
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activeTab === item.id && activeOpenFileId === null ? 'active' : ''}`}
              onClick={() => {
                setActiveTab(item.id);
                setActiveOpenFileId(null);
              }}
              aria-current={activeTab === item.id && activeOpenFileId === null ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="badge badge-muted">Local Backend</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Documents, models & vector indices
          </span>
        </div>
      </aside>
      <main className="main-wrapper">
        <AppHeader />

        {/* Tab Bar for Open Files */}
        {openFiles.length > 0 && (
          <div className="file-tab-bar">
            <button
              type="button"
              className={`file-tab-item ${activeOpenFileId === null ? 'active' : ''}`}
              onClick={() => setActiveOpenFileId(null)}
            >
              <span>📂 Files</span>
            </button>
            {openFiles.map((session) => {
              const isActive = session.file.id === activeOpenFileId;
              const ext = session.file.extension.toLowerCase();
              const icon = ext === '.md' ? '📝' : '📄';
              return (
                <div
                  key={session.file.id}
                  className={`file-tab-item ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveOpenFileId(session.file.id!)}
                  title={session.file.path}
                >
                  <span>{icon}</span>
                  <span>{session.file.name}{session.file.extension}</span>
                  <button
                    type="button"
                    className="file-tab-close"
                    onClick={(e) => handleCloseFileTab(session.file.id!, e)}
                    title="Close tab"
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="content-viewport">{renderActiveModule()}</div>
      </main>
      {fileOpenError && (
        <div className="modal-backdrop" onClick={() => setFileOpenError(null)}>
          <div className="modal-window" style={{ maxWidth: '480px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Impossible d'ouvrir le fichier</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFileOpenError(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)' }}>{fileOpenError}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
