import React, { useState, useEffect, useCallback } from 'react';
import { createApiKey, listApiKeys, getApiKey } from '@/api/endpoints/apiKeys';
import type { APIKeyOut } from '@/core/types/api';

export const ApiKeyManager: React.FC = () => {
  const [keys, setKeys] = useState<APIKeyOut[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Creation form
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [newKeyValue, setNewKeyValue] = useState<string>('');
  const [isCreating, setIsCreating] = useState<boolean>(false);

  // Inspection
  const [inspectedKey, setInspectedKey] = useState<APIKeyOut | null>(null);

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listApiKeys();
      setKeys(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve API keys');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || !newKeyValue.trim()) return;

    setIsCreating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await createApiKey(newKeyName.trim(), newKeyValue.trim());
      setSuccessMessage(`Key "${newKeyName.trim()}" registered successfully!`);
      setNewKeyName('');
      setNewKeyValue('');
      await loadKeys();
    } catch (err: any) {
      setError(err?.message || 'Failed to register API key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleInspectKey = async (name: string) => {
    try {
      const keyData = await getApiKey(name);
      setInspectedKey(keyData);
    } catch (err: any) {
      setError(err?.message || `Failed to fetch key "${name}"`);
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>🔑</span>
            <div>
              <h2 className="card-title">External API Keys</h2>
              <p className="card-description">
                Secure management of access tokens for third-party services (OpenAI, Hugging Face, etc.)
              </p>
            </div>
          </div>
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

          {/* Secure Add Form */}
          <form
            onSubmit={handleCreateKey}
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Register a New API Key</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Security Note: The secret value is accepted and encrypted/stored securely by the backend, and is never returned in plain text.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Service Name / Identifier</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. OpenAI, Cohere, HuggingFace"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Secret Value / API Token</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="sk-..."
                  value={newKeyValue}
                  onChange={(e) => setNewKeyValue(e.target.value)}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={isCreating || !newKeyName.trim() || !newKeyValue.trim()}
              >
                {isCreating ? 'Saving...' : 'Save API Key'}
              </button>
            </div>
          </form>

          {/* Configured Keys List */}
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px' }}>
              Configured Keys ({keys.length})
            </h3>

            {loading ? (
              <div className="state-loading">
                <span className="spinner" />
                <div className="state-title">Loading API keys...</div>
              </div>
            ) : keys.length === 0 ? (
              <div className="state-empty">
                <span style={{ fontSize: '2rem' }}>🔑</span>
                <div className="state-title">No API keys configured</div>
                <p className="state-desc">
                  Use the form above to add credentials for external providers.
                </p>
              </div>
            ) : (
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Service Name</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((k) => (
                      <tr key={k.name}>
                        <td style={{ fontWeight: 500 }}>{k.name}</td>
                        <td>
                          <span className="badge badge-success">Configured (Secret Masked)</span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleInspectKey(k.name)}
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Inspection Modal */}
      {inspectedKey && (
        <div className="modal-backdrop" onClick={() => setInspectedKey(null)}>
          <div className="modal-window" style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">API Key Details</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setInspectedKey(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="card" style={{ padding: '16px', gap: '8px' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Service: </span>
                  <strong>{inspectedKey.name}</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status: </span>
                  <span className="badge badge-success">Active in Keyring</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  In accordance with security best practices, the backend server never transmits the secret value in plain text after registration.
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setInspectedKey(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
