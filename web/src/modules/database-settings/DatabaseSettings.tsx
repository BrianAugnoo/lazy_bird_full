import React, { useState, useEffect, useCallback } from 'react';
import {
  getDatabases,
  selectDatabase,
  disconnectDatabase,
} from '@/api/endpoints/databases';
import type {
  DatabasesCatalogResponse,
  DatabaseCatalogItem,
} from '@/core/types/api';

export const DatabaseSettings: React.FC = () => {
  const [catalog, setCatalog] = useState<DatabasesCatalogResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Formulaire de configuration pour la sélection d'une base
  const [modalKind, setModalKind] = useState<'sql' | 'vector' | null>(null);
  const [modalAdapterName, setModalAdapterName] = useState<string>('');
  const [modalSettings, setModalSettings] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDatabases();
      setCatalog(data);
    } catch (err: any) {
      setError(err?.message || 'Erreur lors de la récupération des bases de données');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Ouverture de la modale de configuration / bascule
  const handleOpenSelectModal = (kind: 'sql' | 'vector', name: string, adapter: DatabaseCatalogItem) => {
    setModalKind(kind);
    setModalAdapterName(name);

    // Initialiser les valeurs par défaut depuis le schéma JSON si présent
    const initialSettings: Record<string, any> = {};
    if (adapter.settings_schema && adapter.settings_schema.properties) {
      for (const [key, prop] of Object.entries<any>(adapter.settings_schema.properties)) {
        initialSettings[key] = prop.default ?? '';
      }
    }
    setModalSettings(initialSettings);
  };

  // Soumission du changement de base
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
      setSuccessMessage(`Base ${modalKind.toUpperCase()} basculée sur "${result.selected}" avec succès !`);
      setModalKind(null);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Échec du basculement de la base de données');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Déconnexion d'un adaptateur
  const handleDisconnect = async (kind: 'sql' | 'vector', name: string, drop: boolean = false) => {
    const actionDesc = drop ? 'déconnecter et SUPPRIMER définitivement les données' : 'déconnecter';
    if (!window.confirm(`Confirmez-vous vouloir ${actionDesc} de l'adaptateur ${name} ?`)) return;

    setLoading(true);
    setError(null);
    try {
      await disconnectDatabase({ kind, name, drop });
      setSuccessMessage(`Adaptateur ${name} déconnecté. Le système est revenu sur l'adaptateur par défaut.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Échec de la déconnexion');
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
              <h2 className="card-title">Bases de données (SQL & Vectorielles)</h2>
              <p className="card-description">
                Bascule entre moteurs de persistance relationnelle et bases vectorielles
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
              <div className="state-title">Chargement des adaptateurs de bases de données...</div>
            </div>
          ) : (
            <>
              {/* Résumé des bases actives */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="card" style={{ padding: '16px', border: '1px solid rgba(99, 102, 241, 0.3)', backgroundColor: 'rgba(99, 102, 241, 0.05)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Base SQL Active
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {catalog?.selected_sql ?? 'sqlite'}
                    </div>
                    <span className="badge badge-success">Connecté</span>
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', border: '1px solid rgba(6, 182, 212, 0.3)', backgroundColor: 'rgba(6, 182, 212, 0.05)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Base Vectorielle Active
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {catalog?.selected_vector ?? 'lancedb'}
                    </div>
                    <span className="badge badge-info">Connecté</span>
                  </div>
                </div>
              </div>

              {/* Section SQL Adapters */}
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '12px' }}>
                  Adaptateurs SQL Disponibles
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
                          {isCurrent && <span className="badge badge-success">Actif</span>}
                        </div>
                        <div className="card-body" style={{ fontSize: '0.825rem' }}>
                          {adapter.messages && adapter.messages.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {adapter.messages.map((msg, i) => (
                                <p key={i} style={{ color: 'var(--text-secondary)' }}>• {msg}</p>
                              ))}
                            </div>
                          ) : (
                            <p style={{ color: 'var(--text-muted)' }}>Adaptateur standard supporté.</p>
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
                              Déconnecter
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenSelectModal('sql', name, adapter)}
                            >
                              Bascule sur {name}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Section Vector Adapters */}
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '12px' }}>
                  Adaptateurs Vectoriels Disponibles
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
                          {isCurrent && <span className="badge badge-info">Actif</span>}
                        </div>
                        <div className="card-body" style={{ fontSize: '0.825rem' }}>
                          {adapter.messages && adapter.messages.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {adapter.messages.map((msg, i) => (
                                <p key={i} style={{ color: 'var(--text-secondary)' }}>• {msg}</p>
                              ))}
                            </div>
                          ) : (
                            <p style={{ color: 'var(--text-muted)' }}>Index vectoriel haute performance.</p>
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
                                title="Déconnecter et supprimer les données"
                              >
                                Purger & Déconnecter
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDisconnect('vector', name, false)}
                              >
                                Déconnecter
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleOpenSelectModal('vector', name, adapter)}
                            >
                              Bascule sur {name}
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

      {/* Modale de configuration et connexion */}
      {modalKind && (
        <div className="modal-backdrop" onClick={() => setModalKind(null)}>
          <div className="modal-window" style={{ maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">
                Configurer et activer {modalAdapterName} ({modalKind.toUpperCase()})
              </h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setModalKind(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              {Object.keys(modalSettings).length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Cet adaptateur utilise sa configuration par défaut. Aucune variable additionnelle n'est requise.
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
                Annuler
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleConfirmSelect}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Connexion...' : 'Confirmer et Basculer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
