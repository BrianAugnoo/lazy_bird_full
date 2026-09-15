import React, { useState, useEffect, useCallback } from 'react';
import { createApiKey, listApiKeys, getApiKey } from '@/api/endpoints/apiKeys';
import type { APIKeyOut } from '@/core/types/api';

export const ApiKeyManager: React.FC = () => {
  const [keys, setKeys] = useState<APIKeyOut[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Formulaire d'ajout
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
      setError(err?.message || 'Erreur lors de la récupération des clés API');
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
      setSuccessMessage(`Clé "${newKeyName.trim()}" enregistrée avec succès !`);
      setNewKeyName('');
      setNewKeyValue('');
      await loadKeys();
    } catch (err: any) {
      setError(err?.message || 'Échec de l’enregistrement de la clé API');
    } finally {
      setIsCreating(false);
    }
  };

  const handleInspectKey = async (name: string) => {
    try {
      const keyData = await getApiKey(name);
      setInspectedKey(keyData);
    } catch (err: any) {
      setError(err?.message || `Impossible de récupérer la clé ${name}`);
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>🔑</span>
            <div>
              <h2 className="card-title">Clés API Externes</h2>
              <p className="card-description">
                Gestion sécurisée des jetons d'accès pour les services tiers (OpenAI, Hugging Face, etc.)
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

          {/* Formulaire d'ajout sécurisé */}
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
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Enregistrer une nouvelle clé API</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Note de sécurité : la valeur secrète de la clé est acceptée et stockée de manière sécurisée, mais n'est jamais renvoyée en clair par le serveur.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Nom du service ou identifiant</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="ex: OpenAI, Cohere, HuggingFace"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Valeur du secret / Token API</label>
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
                {isCreating ? 'Enregistrement...' : 'Enregistrer la clé'}
              </button>
            </div>
          </form>

          {/* Liste des clés enregistrées */}
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px' }}>
              Clés configurées ({keys.length})
            </h3>

            {loading ? (
              <div className="state-loading">
                <span className="spinner" />
                <div className="state-title">Chargement des clés API...</div>
              </div>
            ) : keys.length === 0 ? (
              <div className="state-empty">
                <span style={{ fontSize: '2rem' }}>🔑</span>
                <div className="state-title">Aucune clé API configurée</div>
                <p className="state-desc">
                  Utilisez le formulaire ci-dessus pour associer des clés d'accès aux services externes.
                </p>
              </div>
            ) : (
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Nom du service</th>
                      <th>Statut</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((k) => (
                      <tr key={k.name}>
                        <td style={{ fontWeight: 500 }}>{k.name}</td>
                        <td>
                          <span className="badge badge-success">Configuré (secret masqué)</span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleInspectKey(k.name)}
                          >
                            Détails
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

      {/* Modale d'inspection */}
      {inspectedKey && (
        <div className="modal-backdrop" onClick={() => setInspectedKey(null)}>
          <div className="modal-window" style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Détails de la clé API</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setInspectedKey(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="card" style={{ padding: '16px', gap: '8px' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Nom enregistré : </span>
                  <strong>{inspectedKey.name}</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>État : </span>
                  <span className="badge badge-success">Actif dans le trousseau</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  Conformément aux directives de sécurité, le serveur backend ne diffuse jamais le secret en clair après son enregistrement.
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setInspectedKey(null)}>
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
