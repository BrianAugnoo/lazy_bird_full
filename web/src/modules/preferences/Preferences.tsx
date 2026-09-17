import React, { useState, useEffect, useCallback } from 'react';
import { getPreferences, updatePreferences } from '@/api/endpoints/preferences';
import type { PreferencesPayload } from '@/core/types/api';

export const Preferences: React.FC = () => {
  const [preferences, setPreferences] = useState<PreferencesPayload | null>(null);
  const [autoEmbedding, setAutoEmbedding] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadPreferences = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPreferences();
      setPreferences(data);
      setAutoEmbedding(data['auto-embedding']?.enable ?? true);
    } catch (err: any) {
      setError(err?.message || 'Failed to load preferences.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const handleToggleAutoEmbedding = async (newVal: boolean) => {
    setAutoEmbedding(newVal);
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await updatePreferences({
        'auto-embedding': {
          enable: newVal,
        },
      });
      setPreferences(updated);
      setAutoEmbedding(updated['auto-embedding']?.enable ?? newVal);
      setSuccessMessage(
        newVal
          ? 'Auto-embedding enabled. Pending documents and missing vector chunks will be queued automatically.'
          : 'Auto-embedding disabled. Files will remain pending until manually processed.'
      );
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err?.message || 'Failed to update preferences.');
      // Revert local state on error
      if (preferences) {
        setAutoEmbedding(preferences['auto-embedding']?.enable ?? true);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>⚙️</span>
            <div>
              <h2 className="card-title">Preferences</h2>
              <p className="card-description">
                Configure global workflow automation and RAG ingestion behavior
              </p>
            </div>
          </div>
          {saving && <span className="spinner" title="Saving preferences..." />}
        </div>

        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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

          {loading ? (
            <div className="state-loading">
              <span className="spinner" />
              <div className="state-title">Loading preferences...</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 20px',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div style={{ maxWidth: '70%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                      Auto-Embedding
                    </span>
                    <span className={`badge ${autoEmbedding ? 'badge-success' : 'badge-muted'}`}>
                      {autoEmbedding ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    When enabled, newly uploaded files or files affected by model / vector database changes are automatically queued in the background for chunking and vector embedding. If disabled, new files stay in pending state until manually processed.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <label
                    style={{
                      position: 'relative',
                      display: 'inline-block',
                      width: '48px',
                      height: '26px',
                      cursor: saving ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={autoEmbedding}
                      disabled={saving}
                      onChange={(e) => handleToggleAutoEmbedding(e.target.checked)}
                      style={{ opacity: 0, width: 0, height: 0 }}
                      aria-label="Toggle auto-embedding"
                    />
                    <span
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: autoEmbedding ? 'var(--accent-primary)' : 'var(--bg-card-hover)',
                        borderRadius: '24px',
                        transition: 'background-color var(--transition-fast)',
                        border: '1px solid var(--border-base)',
                      }}
                    >
                      <span
                        style={{
                          position: 'absolute',
                          content: '""',
                          height: '18px',
                          width: '18px',
                          left: autoEmbedding ? '24px' : '4px',
                          bottom: '3px',
                          backgroundColor: '#ffffff',
                          borderRadius: '50%',
                          transition: 'all var(--transition-fast)',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }}
                      />
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
