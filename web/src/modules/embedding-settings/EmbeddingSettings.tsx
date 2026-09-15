import React, { useState, useEffect, useCallback } from 'react';
import {
  getEmbeddingEngines,
  updateEngineKwargs,
  getSelectedEmbeddingEngine,
  setSelectedEmbeddingEngine,
} from '@/api/endpoints/embeddings';
import type { EmbeddingEngine, SelectedEmbeddingEngine } from '@/core/types/api';

export const EmbeddingSettings: React.FC = () => {
  const [engines, setEngines] = useState<EmbeddingEngine[]>([]);
  const [selectedEngineState, setSelectedEngineState] = useState<SelectedEmbeddingEngine | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Valeurs locales éditables pour chaque moteur (engineId -> kwargs)
  const [editedKwargs, setEditedKwargs] = useState<Record<number, Record<string, any>>>({});
  const [savingEngineId, setSavingEngineId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [enginesList, activeEngine] = await Promise.all([
        getEmbeddingEngines(),
        getSelectedEmbeddingEngine(),
      ]);
      setEngines(enginesList);
      setSelectedEngineState(activeEngine);

      // Initialiser les kwargs locaux
      const initialMap: Record<number, Record<string, any>> = {};
      for (const eng of enginesList) {
        initialMap[eng.id] = { ...(eng.kwargs || {}) };
      }
      setEditedKwargs(initialMap);
    } catch (err: any) {
      setError(err?.message || 'Erreur lors de la récupération des moteurs d’embedding');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Modification d'un argument
  const handleKwargChange = (engineId: number, key: string, value: any) => {
    setEditedKwargs((prev) => ({
      ...prev,
      [engineId]: {
        ...prev[engineId],
        [key]: value,
      },
    }));
  };

  // Sauvegarde des kwargs
  const handleSaveKwargs = async (engineId: number) => {
    setSavingEngineId(engineId);
    setError(null);
    setSuccessMessage(null);
    try {
      const kwargs = editedKwargs[engineId] || {};
      await updateEngineKwargs(engineId, kwargs);
      setSuccessMessage(`Paramètres du moteur #${engineId} enregistrés avec succès`);
      setTimeout(() => setSuccessMessage(null), 3000);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Échec de sauvegarde des paramètres du moteur');
    } finally {
      setSavingEngineId(null);
    }
  };

  // Définir le moteur actif
  const handleSelectEngine = async (engineId: number) => {
    setError(null);
    try {
      const result = await setSelectedEmbeddingEngine(engineId);
      setSelectedEngineState(result);
      setSuccessMessage(`Moteur #${engineId} défini comme moteur actif pour l'application`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Échec de la sélection du moteur actif');
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>⚡</span>
            <div>
              <h2 className="card-title">Moteurs d'Embedding</h2>
              <p className="card-description">
                Configuration dynamique des backends de vectorisation et sélection du moteur actif
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

          {/* Résumé du moteur actif */}
          <div style={{ backgroundColor: 'rgba(99, 102, 241, 0.05)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Moteur Actif Courant
                </span>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {selectedEngineState?.configured && selectedEngineState.engine
                    ? `${selectedEngineState.engine.name} (ID #${selectedEngineState.engine.id})`
                    : 'Aucun moteur configuré'}
                </div>
              </div>
              <span className={`badge ${selectedEngineState?.configured ? 'badge-success' : 'badge-warning'}`}>
                {selectedEngineState?.configured ? 'Opérationnel' : 'Non configuré'}
              </span>
            </div>
          </div>

          {/* Liste des moteurs disponibles */}
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '14px' }}>
              Moteurs disponibles ({engines.length})
            </h3>

            {loading ? (
              <div className="state-loading">
                <span className="spinner" />
                <div className="state-title">Chargement des moteurs d'embedding...</div>
              </div>
            ) : engines.length === 0 ? (
              <div className="state-empty">
                <span style={{ fontSize: '2rem' }}>⚡</span>
                <div className="state-title">Aucun moteur d'embedding disponible</div>
                <p className="state-desc">
                  Vérifiez la configuration des extensions de calcul côté backend.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {engines.map((eng) => {
                  const isActive = selectedEngineState?.engine?.id === eng.id;
                  const currentKwargs = editedKwargs[eng.id] || {};
                  const keys = Object.entries(eng.kwargs_keys || {});

                  return (
                    <div
                      key={eng.id}
                      className="card"
                      style={{
                        border: isActive ? '1px solid var(--accent-primary)' : '1px solid var(--border-base)',
                        boxShadow: isActive ? '0 0 12px var(--accent-glow)' : 'none',
                      }}
                    >
                      <div className="card-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ fontWeight: 600, fontSize: '1rem' }}>{eng.name}</span>
                          {isActive && <span className="badge badge-success">Actif</span>}
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span className="badge badge-muted">Formats : {eng.formats.join(', ')}</span>
                          <span className="badge badge-muted">ID #{eng.id}</span>
                        </div>
                      </div>

                      <div className="card-body">
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                          Fichier source : <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{eng.file_path}</span>
                        </div>

                        {/* Formulaire dynamique généré depuis kwargs_keys */}
                        <h4 style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '10px' }}>
                          Paramètres spécifiques (kwargs)
                        </h4>

                        {keys.length === 0 ? (
                          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            Ce moteur ne requiert aucun paramètre spécifique.
                          </p>
                        ) : (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
                            {keys.map(([k, [expectedType, defaultVal]]) => {
                              const isRequired = defaultVal === 'required';
                              const val = currentKwargs[k] ?? '';

                              return (
                                <div key={k} className="form-group" style={{ marginBottom: 0 }}>
                                  <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>{k}</span>
                                    <span style={{ fontSize: '0.7rem', color: isRequired ? 'var(--color-error)' : 'var(--text-muted)' }}>
                                      {expectedType} {isRequired ? '(requis)' : '(opt)'}
                                    </span>
                                  </label>
                                  <input
                                    type="text"
                                    className="form-input"
                                    value={val}
                                    placeholder={defaultVal !== 'required' && defaultVal !== null ? String(defaultVal) : ''}
                                    onChange={(e) => handleKwargChange(eng.id, k, e.target.value)}
                                  />
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div className="card-footer">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleSaveKwargs(eng.id)}
                          disabled={savingEngineId === eng.id}
                        >
                          {savingEngineId === eng.id ? 'Enregistrement...' : 'Sauvegarder les paramètres'}
                        </button>
                        <button
                          type="button"
                          className={`btn btn-sm ${isActive ? 'btn-secondary' : 'btn-primary'}`}
                          onClick={() => handleSelectEngine(eng.id)}
                          disabled={isActive}
                        >
                          {isActive ? '✓ Moteur actif' : 'Activer ce moteur'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
