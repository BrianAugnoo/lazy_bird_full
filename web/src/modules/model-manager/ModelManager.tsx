import React, { useState, useEffect, useCallback } from 'react';
import {
  getModels,
  createModel,
  setModelFormat,
  destroyAllModels,
  getSelectedModel,
  setSelectedModel,
} from '@/api/endpoints/models';
import { getFiles } from '@/api/endpoints/files';
import { getPreferences } from '@/api/endpoints/preferences';
import type { LLMModel, SelectedModel } from '@/core/types/api';

const POPULAR_MODELS = [
  'sentence-transformers/all-MiniLM-L6-v2',
  'BAAI/bge-small-en-v1.5',
  'intfloat/e5-small-v2',
];

interface ModelSwitchWarning {
  newModelId: number | null;
  newBatch: number;
  affectedCount: number;
  autoEmbeddingEnabled: boolean;
}

export const ModelManager: React.FC = () => {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [selectedModel, setSelectedModelState] = useState<SelectedModel | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Hugging Face add form
  const [hfPath, setHfPath] = useState<string>('');

  // Active model config
  const [activeModelId, setActiveModelId] = useState<number | null>(null);
  const [batchSize, setBatchSize] = useState<number>(1);
  const [savingActive, setSavingActive] = useState<boolean>(false);

  // Switch confirmation modal
  const [switchWarning, setSwitchWarning] = useState<ModelSwitchWarning | null>(null);

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
      setError(err?.message || 'Failed to load LLM models');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Download HF model
  const handleDownloadModel = async (pathOverride?: string) => {
    const targetPath = (pathOverride || hfPath).trim();
    if (!targetPath) return;

    setDownloading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await createModel(targetPath);
      setSuccessMessage(`Model "${targetPath}" downloaded and registered successfully!`);
      setHfPath('');
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to download model');
    } finally {
      setDownloading(false);
    }
  };

  // Change model format
  const handleFormatChange = async (modelId: number, format: string) => {
    try {
      await setModelFormat(modelId, format);
      setSuccessMessage(`Format updated to ${format}`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to update model format');
    }
  };

  // Check impact before changing active model
  const requestChangeActiveModel = async (newId: number | null, batch: number) => {
    const previousModelId = selectedModel?.llm_model_id ?? null;
    if (previousModelId === newId) {
      // No change
      return;
    }

    try {
      const [fileList, prefs] = await Promise.all([getFiles(), getPreferences()]);
      const autoEmbeddingEnabled = prefs['auto-embedding']?.enable ?? true;

      // Count files embedded by previous model
      const affectedFiles = fileList.filter((f) =>
        previousModelId !== null && f.embedded_by && f.embedded_by.includes(previousModelId)
      );

      if (affectedFiles.length > 0) {
        setSwitchWarning({
          newModelId: newId,
          newBatch: batch,
          affectedCount: affectedFiles.length,
          autoEmbeddingEnabled,
        });
        return;
      }
    } catch {
      // Continue if checks fail
    }

    await executeSaveActiveModel(newId, batch);
  };

  // Execute actual save
  const executeSaveActiveModel = async (newId: number | null, batch: number) => {
    setSavingActive(true);
    setError(null);
    try {
      const updated = await setSelectedModel(newId, batch);
      setSelectedModelState(updated);
      setActiveModelId(updated.llm_model_id);
      setSuccessMessage('Active embedding model and batch size updated successfully.');
      setTimeout(() => setSuccessMessage(null), 3500);
      setSwitchWarning(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to update active model');
    } finally {
      setSavingActive(false);
    }
  };

  // Delete all models
  const handleDeleteAll = async () => {
    if (!window.confirm('WARNING: Are you sure you want to delete ALL registered models?')) return;
    setLoading(true);
    try {
      await destroyAllModels();
      await loadData();
      setSuccessMessage('All models have been deleted.');
    } catch (err: any) {
      setError(err?.message || 'Failed to delete models');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-container">
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.25rem' }}>🤖</span>
            <div>
              <h2 className="card-title">LLM & Embedding Models</h2>
              <p className="card-description">
                Install Hugging Face models, select formats, and configure the active embedding model
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
              Delete All Models
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

          {/* Hugging Face Download Form */}
          <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-base)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px' }}>
              Download a Hugging Face Model
            </h3>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="form-input"
                style={{ flex: 1, minWidth: '280px' }}
                placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2"
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
                    Downloading...
                  </>
                ) : (
                  '📥 Download Model'
                )}
              </button>
            </div>

            {/* Quick Suggestions */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Suggestions:</span>
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

          {/* Active Model Configuration */}
          <div style={{ backgroundColor: 'rgba(99, 102, 241, 0.05)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px', color: 'var(--text-primary)' }}>
              Active Embedding Model Configuration
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', alignItems: 'end' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Assigned Model</label>
                <select
                  className="form-select"
                  value={activeModelId ?? ''}
                  onChange={(e) => setActiveModelId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">-- No model selected --</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} (dim: {m.dimension}, format: {m.selected_format})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Batch Size</label>
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
                onClick={() => requestChangeActiveModel(activeModelId, Number(batchSize) || 1)}
                disabled={savingActive}
              >
                {savingActive ? 'Saving...' : 'Apply as Active Model'}
              </button>
            </div>
          </div>

          {/* Installed Models List */}
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px' }}>
              Installed Models ({models.length})
            </h3>

            {loading ? (
              <div className="state-loading">
                <span className="spinner" />
                <div className="state-title">Loading models...</div>
              </div>
            ) : models.length === 0 ? (
              <div className="state-empty">
                <span style={{ fontSize: '2rem' }}>🤖</span>
                <div className="state-title">No models installed</div>
                <p className="state-desc">
                  Download a Hugging Face model above to enable embedding and semantic search features.
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
                          {isActive && <span className="badge badge-success">Active</span>}
                        </div>
                        <span className="badge badge-muted">ID #{m.id}</span>
                      </div>

                      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.825rem' }}>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Hugging Face: </span>
                          <span style={{ fontFamily: 'monospace' }}>{m.hf_path}</span>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Vector Dimension: </span>
                          <strong>{m.dimension}</strong>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Max Context: </span>
                          <span>{m.max_context_length ?? 'N/A'} tokens</span>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted)' }}>Local Path: </span>
                          <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>{m.local_path}</span>
                        </div>

                        {/* Format selector */}
                        <div style={{ marginTop: '6px' }}>
                          <label className="form-label" style={{ fontSize: '0.75rem' }}>Active Format</label>
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
                          onClick={() => requestChangeActiveModel(m.id, batchSize)}
                        >
                          {isActive ? '✓ Active Model' : 'Set as Active'}
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

      {/* Model Switch Confirmation Modal */}
      {switchWarning && (
        <div className="modal-backdrop" onClick={() => setSwitchWarning(null)}>
          <div className="modal-window" style={{ maxWidth: '520px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.4rem' }}>⚠️</span>
                <h3 className="card-title">Change Active Embedding Model</h3>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSwitchWarning(null)}>✕</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px', lineHeight: 1.5 }}>
              <p style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                <strong>{switchWarning.affectedCount} document(s)</strong> have already been embedded with the currently selected model.
              </p>
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: switchWarning.autoEmbeddingEnabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                  border: `1px solid ${switchWarning.autoEmbeddingEnabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                  fontSize: '0.85rem',
                }}
              >
                {switchWarning.autoEmbeddingEnabled ? (
                  <div>
                    <strong>Auto-embedding is ENABLED:</strong> If you switch to this new model, these documents will be automatically re-queued and re-embedded in the background.
                  </div>
                ) : (
                  <div>
                    <strong>Auto-embedding is DISABLED:</strong> If you switch to this new model, these documents will NOT be re-embedded automatically. You will need to re-process them manually from the File Explorer.
                  </div>
                )}
              </div>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
                Do you want to proceed with this model switch?
              </p>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSwitchWarning(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => executeSaveActiveModel(switchWarning.newModelId, switchWarning.newBatch)}
                disabled={savingActive}
              >
                {savingActive ? 'Applying...' : 'Confirm & Switch Model'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
