import React, { useState, useEffect, useCallback } from 'react';
import {
  getModels,
  createModel,
  setModelFormat,
  destroyAllModels,
  getSelectedModel,
  setSelectedModel,
} from '@/api/endpoints/models';
import type { LLMModel, SelectedModel } from '@/core/types/api';

const POPULAR_MODELS = [
  'sentence-transformers/all-MiniLM-L6-v2',
  'BAAI/bge-small-en-v1.5',
  'intfloat/e5-small-v2',
];

export const ModelManager: React.FC = () => {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [selectedModel, setSelectedModelState] = useState<SelectedModel | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Formulaire d'ajout HF
  const [hfPath, setHfPath] = useState<string>('');

  // Configuration du modèle actif
  const [activeModelId, setActiveModelId] = useState<number | null>(null);
  const [batchSize, setBatchSize] = useState<number>(1);
  const [savingActive, setSavingActive] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelsList, currentSelected] = await Promise.all([
        getModels(),
        getSelectedModel(),
      ]);
      setModels(modelsList);
      setSelectedModelState(currentSelected);
      setActiveModelId(currentSelected?.llm_model_id ?? null);
      setBatchSize(currentSelected?.batch ?? 1);
    } catch (err: any) {
      setError(err?.message || 'Erreur lors du chargement des modèles LLM');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Enregistrer / Télécharger un modèle HF
  const handleDownloadModel = async (pathOverride?: string) => {
    const targetPath = (pathOverride || hfPath).trim();
    if (!targetPath) return;

    setDownloading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await createModel(targetPath);
      setSuccessMessage(`Modèle ${targetPath} téléchargé et enregistré avec succès !`);
      setHfPath('');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Échec du téléchargement du modèle');
    } finally {
      setDownloading(false);
    }
  };

  // Changer le format d'un modèle
  const handleFormatChange = async (modelId: number, format: string) => {
    try {
      await setModelFormat(modelId, format);
      setSuccessMessage(`Format mis à jour en ${format}`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Échec de modification du format');
    }
  };

  // Sauvegarder le modèle actif et batch
  const handleSaveActiveModel = async () => {
    setSavingActive(true);
    setError(null);
    try {
      const updated = await setSelectedModel(activeModelId, Number(batchSize) || 1);
      setSelectedModelState(updated);
      setSuccessMessage('Modèle actif et taille de lot (batch) mis à jour avec succès');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Échec de mise à jour du modèle actif');
    } finally {
      setSavingActive(false);
    }
  };

  // Supprimer tous les modèles
  const handleDeleteAll = async () => {
    if (!window.confirm('Voulez-vous vraiment supprimer tous les modèles enregistrés ?')) return;
    setLoading(true);
    try {
      await destroyAllModels();
      await loadData();
      setSuccessMessage('Tous les modèles ont été supprimés.');
    } catch (err: any) {
      setError(err?.message || 'Échec de la suppression des modèles');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-container">
      {/* En-tête et alertes */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>🤖</span>
            <div>
              <h2 className="card-title">Modèles LLM & Embedding</h2>
              <p className="card-description">
                Installation depuis Hugging Face, sélection des formats et du modèle actif
              </p>
            </div>
          </div>

          {models.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleDeleteAll}
              style={{ color: 'var(--color-error)' }}
            >
              Supprimer tous les modèles
            </button>
          )}
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

          {/* Formulaire de téléchargement Hugging Face */}
          <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-base)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px' }}>
              Télécharger un modèle Hugging Face
            </h3>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="form-input"
                style={{ flex: 1, minWidth: '280px' }}
                placeholder="ex: sentence-transformers/all-MiniLM-L6-v2"
                value={hfPath}
                onChange={(e) => setHfPath(e.target.value)}
                disabled={downloading}
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleDownloadModel()}
                disabled={downloading || !hfPath.trim()}
              >
                {downloading ? (
                  <>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    Téléchargement en cours...
                  </>
                ) : (
                  '📥 Télécharger le modèle'
                )}
              </button>
            </div>

            {/* Suggestions rapides */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Suggestions :</span>
              {POPULAR_MODELS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="badge badge-muted"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    setHfPath(item);
                    handleDownloadModel(item);
                  }}
                >
                  + {item}
                </button>
              ))}
            </div>
          </div>

          {/* Configuration du Modèle Actif */}
          <div style={{ backgroundColor: 'rgba(99, 102, 241, 0.05)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px', color: 'var(--text-primary)' }}>
              Configuration du Modèle Actif pour l'Embedding
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', alignItems: 'end' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Modèle assigné</label>
                <select
                  className="form-select"
                  value={activeModelId ?? ''}
                  onChange={(e) => setActiveModelId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">-- Aucun modèle sélectionné --</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} (dim: {m.dimension}, format: {m.selected_format})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Taille de lot (Batch Size)</label>
                <input
                  type="number"
                  min="1"
                  max="128"
                  className="form-input"
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                />
              </div>

              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveActiveModel}
                disabled={savingActive}
              >
                {savingActive ? 'Application...' : 'Appliquer comme modèle actif'}
              </button>
            </div>
          </div>

          {/* Liste des Modèles Enregistrés */}
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px' }}>
              Modèles installés ({models.length})
            </h3>

            {loading ? (
              <div className="state-loading">
                <span className="spinner" />
                <div className="state-title">Chargement des modèles...</div>
              </div>
            ) : models.length === 0 ? (
              <div className="state-empty">
                <span style={{ fontSize: '2rem' }}>🤖</span>
                <div className="state-title">Aucun modèle installé</div>
                <p className="state-desc">
                  Téléchargez un modèle Hugging Face ci-dessus pour activer les fonctionnalités d'embedding et de recherche sémantique.
                </p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
                {models.map((m) => {
                  const isActive = selectedModel?.llm_model_id === m.id;
                  return (
                    <div
                      key={m.id}
                      className="card"
                      style={{
                        border: isActive ? '1px solid var(--accent-primary)' : '1px solid var(--border-base)',
                        boxShadow: isActive ? '0 0 12px var(--accent-glow)' : 'none',
                      }}
                    >
                      <div className="card-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 600 }}>{m.name}</span>
                          {isActive && <span className="badge badge-success">Actif</span>}
                        </div>
                        <span className="badge badge-muted">ID #{m.id}</span>
                      </div>

                      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.825rem' }}>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Hugging Face : </span>
                          <span style={{ fontFamily: 'monospace' }}>{m.hf_path}</span>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Dimension du vecteur : </span>
                          <strong>{m.dimension}</strong>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Contexte max : </span>
                          <span>{m.max_context_length ?? 'N/A'} tokens</span>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Chemin local : </span>
                          <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>{m.local_path}</span>
                        </div>

                        {/* Sélecteur de format */}
                        <div style={{ marginTop: '6px' }}>
                          <label className="form-label" style={{ fontSize: '0.75rem' }}>Format utilisé</label>
                          <select
                            className="form-select"
                            style={{ fontSize: '0.8rem', padding: '4px 8px' }}
                            value={m.selected_format}
                            onChange={(e) => handleFormatChange(m.id, e.target.value)}
                          >
                            {m.formats.map((fmt) => (
                              <option key={fmt} value={fmt}>
                                {fmt}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="card-footer">
                        <button
                          type="button"
                          className={`btn btn-sm ${isActive ? 'btn-secondary' : 'btn-primary'}`}
                          onClick={() => {
                            setActiveModelId(m.id);
                            setSelectedModel(m.id, batchSize).then(loadData);
                          }}
                        >
                          {isActive ? '✓ Modèle actif' : 'Définir comme actif'}
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
