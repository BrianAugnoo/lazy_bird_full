import { useEffect, useState } from 'react'
import { AppHeader } from '@/modules/app-header/AppHeader'
import { ApiKeyManager } from '@/modules/api-keys/ApiKeyManager'
import { DatabaseSettings } from '@/modules/database-settings/DatabaseSettings'
import { EmbeddingSettings } from '@/modules/embedding-settings/EmbeddingSettings'
import { FileExplorer } from '@/modules/file-explorer/FileExplorer'
import { registerAllBuiltinViewers } from '@/modules/file-viewers'
import { ModelManager } from '@/modules/model-manager/ModelManager'
import { SemanticSearch } from '@/modules/semantic-search/SemanticSearch'
import type { TabType } from '@/core/types/common'

const navigation: Array<{ id: TabType; label: string; icon: string }> = [
  { id: 'files', label: 'Explorateur', icon: '▦' },
  { id: 'models', label: 'Modèles', icon: '◈' },
  { id: 'embeddings', label: 'Embeddings', icon: '⌁' },
  { id: 'search', label: 'Recherche', icon: '⌕' },
  { id: 'databases', label: 'Bases de données', icon: '▤' },
  { id: 'api-keys', label: 'Clés API', icon: '⚿' },
]

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('files')

  useEffect(() => {
    registerAllBuiltinViewers()
  }, [])

  const renderActiveModule = () => {
    switch (activeTab) {
      case 'files': return <FileExplorer />
      case 'models': return <ModelManager />
      case 'embeddings': return <EmbeddingSettings />
      case 'search': return <SemanticSearch />
      case 'databases': return <DatabaseSettings />
      case 'api-keys': return <ApiKeyManager />
    }
  }

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
        <nav className="sidebar-nav" aria-label="Espaces de travail">
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
              aria-current={activeTab === item.id ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="badge badge-muted">Backend local</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Documents, modèles et index vectoriel
          </span>
        </div>
      </aside>
      <main className="main-wrapper">
        <AppHeader />
        <div className="content-viewport">{renderActiveModule()}</div>
      </main>
    </div>
  )
}

export default App
