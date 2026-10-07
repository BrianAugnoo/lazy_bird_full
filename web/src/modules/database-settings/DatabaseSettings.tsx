import React, { useState, useEffect, useCallback } from 'react';
import {
  getDatabases,
  selectDatabase,
  disconnectDatabase,
} from '@/api/endpoints/databases';
import { getFiles } from '@/api/endpoints/files';
import { getPreferences } from '@/api/endpoints/preferences';
import type {
  DatabasesCatalogResponse,
  DatabaseCatalogItem,
} from '@/core/types/api';

export const DatabaseSettings: React.FC = () => {
  const [catalog, setCatalog] = useState<DatabasesCatalogResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Configuration modal for selecting an adapter
  const [modalKind, setModalKind] = useState<'sql' | 'vector' | null>(null);
  const [modalAdapterName, setModalAdapterName] = useState<string>('');
  const [modalSettings, setModalSettings] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Vector switch impact warning
  const [vectorImpactNotice, setVectorImpactNotice] = useState<{
    affectedCount: number;
    currentVectorDb: string;
    autoEmbeddingEnabled: boolean;
  } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDatabases();
      setCatalog(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve database adapters');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Open configuration / switch modal
  const handleOpenSelectModal = async (kind: 'sql' | 'vector', name: string, adapter: DatabaseCatalogItem) => {
    setModalKind(kind);
    setModalAdapterName(name);

    // Initialize default values from JSON schema if present
    const initialSettings: Record<string, any> = {};
    if (adapter.settings_schema && adapter.settings_schema.properties) {
      for (const [key, prop] of Object.entries<any>(adapter.settings_schema.properties)) {
        initialSettings[key] = prop.default ?? '';
      }
    }
    setModalSettings(initialSettings);

    // Check impact for vector databases
    if (kind === 'vector' && catalog && catalog.selected_vector !== name) {
      try {
        const [fileList, prefs] = await Promise.all([getFiles(), getPreferences()]);
        const autoEmbeddingEnabled = prefs['auto-embedding']?.enable ?? true;
        const currentVectorDb = catalog.selected_vector;
        // Vectors stay in the previous database: every chunked file must be embedded again.
        const affectedFiles = fileList.filter((f) => (f.chunk_count ?? 0) > 0);
        if (affectedFiles.length > 0) {
          setVectorImpactNotice({
            affectedCount: affectedFiles.length,
            currentVectorDb,
            autoEmbeddingEnabled,
          });
        } else {
          setVectorImpactNotice(null);
        }
      } catch {
        setVectorImpactNotice(null);
      }
    } else {
      setVectorImpactNotice(null);
    }
  };

  // Submit database change
  const handleConfirmSelect = async () => {
    if (!modalKind || !modalAdapterName) return;
    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await selectDatabase({
        kind: modalKind,
        name: modalAdapterName,
        settings: modalSettings,
      });
      setSuccessMessage(`${modalKind.toUpperCase()} database successfully switched to "${result.selected}"!`);
      setModalKind(null);
      setVectorImpactNotice(null);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to switch database adapter');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Disconnect an adapter
  const handleDisconnect = async (kind: 'sql' | 'vector', name: string, drop: boolean = false) => {
    const actionDesc = drop ? 'disconnect and PERMANENTLY DELETE data for' : 'disconnect';
    if (!window.confirm(`Are you sure you want to ${actionDesc} adapter "${name}"?`)) return;

    setLoading(true);
    setError(null);
    try {
      await disconnectDatabase({ kind, name, drop });
      setSuccessMessage(`Adapter "${name}" disconnected. Returned to default adapter.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to disconnect adapter');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>🗄️</span>
            <div>
              <h2 className="card-title">Databases (SQL & Vector)</h2>
              <p className="card-description">
                Switch between relational persistence engines and high-performance vector databases
              </p>
            </div>
          </div>
        </div>

        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {error && (
            <div className="alert alert-error">
              <span>⚠️</span>
              <div style={{ flex: 1 }}>{error}</div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setError(null)}>✕</button>
            </div>
          )}

          {successMessage && (
            <div className="alert alert-success">
              <span>✓</span>
              <div style={{ flex: 1 }}>{successMessage}</div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSuccessMessage(null)}>✕</button>
            </div>
          )}

          {loading && !catalog ? (
            <div className="state-loading">
              <span className="spinner" />
              <div className="state-title">Loading database adapters...</div>
            </div>
          ) : (
            <>
              {/* Active Databases Summary */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="card" style={{ padding: '16px', border: '1px solid rgba(99, 102, 241, 0.3)', backgroundColor: 'rgba(99, 102, 241, 0.05)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Active SQL Database
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {catalog?.selected_sql ?? 'sqlite'}
                    </div>
                    <span className="badge badge-success">Connected</span>
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', border: '1px solid rgba(6, 182, 212, 0.3)', backgroundColor: 'rgba(6, 182, 212, 0.05)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Active Vector Database
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {catalog?.selected_vector ?? 'lancedb'}
                    </div>
                    <span className="badge badge-info">Connected</span>
                  </div>
                </div>
              </div>

              {/* SQL Adapters Section */}
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '12px' }}>
                  Available SQL Adapters
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
                  {Object.entries(catalog?.available.sql || {}).map(([name, adapter]) => {
                    const isCurrent = catalog?.selected_sql === name;
                    return (
                      <div
                        key={name}
                        className="card"
                        style={{
                          border: isCurrent ? '1px solid var(--accent-primary)' : '1px solid var(--border-base)',
                        }}
                      >
                        <div className="card-header">
                          <strong style={{ textTransform: 'capitalize' }}>{name}</strong>
                          {isCurrent && <span className="badge badge-success">Active</span>}
                        </div>
                        <div className="card-body" style={{ fontSize: '0.825rem' }}>
                          {adapter.messages && adapter.messages.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {adapter.messages.map((msg, i) => (
                                <p key={i} style={{ color: 'var(--text-secondary)' }}>• {msg}</p>
                              ))}
                            </div>
                          ) : (
                            <p style={{ color: 'var(--text-muted)' }}>Standard supported relational adapter.</p>
                          )}
                        </div>
                        <div className="card-footer">
                          {isCurrent ? (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              style={{ color: 'var(--color-error)' }}
                              onClick={() => handleDisconnect('sql', name, false)}
                            >
                              Disconnect
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenSelectModal('sql', name, adapter)}
                            >
                              Switch to {name}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Vector Adapters Section */}
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '12px' }}>
                  Available Vector Adapters
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
                  {Object.entries(catalog?.available.vector || {}).map(([name, adapter]) => {
                    const isCurrent = catalog?.selected_vector === name;
                    return (
                      <div
                        key={name}
                        className="card"
                        style={{
                          border: isCurrent ? '1px solid var(--accent-secondary)' : '1px solid var(--border-base)',
                        }}
                      >
                        <div className="card-header">
                          <strong style={{ textTransform: 'capitalize' }}>{name}</strong>
                          {isCurrent && <span className="badge badge-info">Active</span>}
                        </div>
                        <div className="card-body" style={{ fontSize: '0.825rem' }}>
                          {adapter.messages && adapter.messages.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {adapter.messages.map((msg, i) => (
                                <p key={i} style={{ color: 'var(--text-secondary)' }}>• {msg}</p>
                              ))}
                            </div>
                          ) : (
                            <p style={{ color: 'var(--text-muted)' }}>High-performance vector index.</p>
                          )}
                        </div>
                        <div className="card-footer">
                          {isCurrent ? (
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                style={{ color: 'var(--color-error)' }}
                                onClick={() => handleDisconnect('vector', name, true)}
                                title="Disconnect and purge vector data"
                              >
                                Purge & Disconnect
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDisconnect('vector', name, false)}
                              >
                                Disconnect
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenSelectModal('vector', name, adapter)}
                            >
                              Switch to {name}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Configuration & Connection Modal */}
      {modalKind && (
        <div className="modal-backdrop" onClick={() => setModalKind(null)}>
          <div className="modal-window" style={{ maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">
                Configure & Switch to {modalAdapterName} ({modalKind.toUpperCase()})
              </h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setModalKind(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Vector switch impact notice */}
              {vectorImpactNotice && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: vectorImpactNotice.autoEmbeddingEnabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                    border: `1px solid ${vectorImpactNotice.autoEmbeddingEnabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                    fontSize: '0.85rem',
                    lineHeight: 1.5,
                  }}
                >
                  <p style={{ margin: '0 0 6px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    ⚠️ {vectorImpactNotice.affectedCount} file(s) have chunks in "{vectorImpactNotice.currentVectorDb}".
                  </p>
                  {vectorImpactNotice.autoEmbeddingEnabled ? (
                    <span style={{ color: 'var(--text-secondary)' }}>
                      Since auto-embedding is <strong>ENABLED</strong>, switching to "{modalAdapterName}" will automatically re-queue and index these files into the new vector database.
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-secondary)' }}>
                      Since auto-embedding is <strong>DISABLED</strong>, files will NOT be indexed into the new database automatically. You must re-process them manually.
                    </span>
                  )}
                </div>
              )}

              {Object.keys(modalSettings).length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  This adapter uses its default configuration. No additional parameters are required.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {Object.entries(modalSettings).map(([key, val]) => (
                    <div key={key} className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">{key}</label>
                      <input
                        type="text"
                        className="form-input"
                        value={val}
                        onChange={(e) =>
                          setModalSettings((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setModalKind(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleConfirmSelect}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Connecting...' : 'Confirm & Switch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
