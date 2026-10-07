import React, { useState, useEffect, useCallback } from 'react';
import { getModels, createModel, setModelFormat, deleteModel, importModel } from '@/api/endpoints/models';
import type { LLMModel } from '@/core/types/api';

const POPULAR_MODELS = [
  'sentence-transformers/all-MiniLM-L6-v2',
  'BAAI/bge-small-en-v1.5',
  'intfloat/e5-small-v2',
];

export const ModelManager: React.FC = () => {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Hugging Face add form
  const [hfPath, setHfPath] = useState<string>('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setModels(await getModels());
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
      setSuccessMessage(`Download of "${targetPath}" queued. It appears here when finished.`);
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

  // Import a model folder or weight file from the server's disk
  const [importPath, setImportPath] = useState<string>('');
  const [importName, setImportName] = useState<string>('');
  const handleImport = async () => {
    setError(null);
    try {
      await importModel(importPath.trim(), importName.trim());
      setSuccessMessage(`Import of "${importName}" queued. It appears here when finished.`);
      setImportPath('');
      setImportName('');
    } catch (err: any) {
      setError(err?.message || 'Failed to import the model');
    }
  };

  const handleDelete = async (model: LLMModel) => {
    const removeFiles = window.confirm(
      `Remove "${model.name}"?\n\nOK: also delete its files from the Hugging Face cache.\nCancel: keep the files (it comes back at the next cache sync).`,
    );
    try {
      await deleteModel(model.id, removeFiles);
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete the model');
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
                Install Hugging Face models and choose the format each one is loaded with. Embedding presets decide which model is used.
              </p>
            </div>
          </div>

          <button type="button" className="btn btn-ghost btn-sm" onClick={() => loadData()}>
            Refresh
          </button>
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

          {/* Local import */}
          <form
            style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: '16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-base)' }}
            onSubmit={(event) => {
              event.preventDefault();
              void handleImport();
            }}
          >
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px' }}>Import a Local Model</h3>
            <p className="form-hint" style={{ marginBottom: '8px' }}>
              A folder or a single weight file (.gguf, .safetensors, .bin, .pth, .ckpt, .onnx…) on the server&apos;s disk.
              It is copied into the Hugging Face cache, so it stays available even if the original is moved.
            </p>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="form-input"
                style={{ flex: 2, minWidth: '260px' }}
                placeholder="/path/to/model-folder or /path/to/model.gguf"
                value={importPath}
                onChange={(event) => setImportPath(event.target.value)}
              />
              <input
                type="text"
                className="form-input"
                style={{ flex: 1, minWidth: '160px' }}
                placeholder="Name"
                value={importName}
                onChange={(event) => setImportName(event.target.value)}
              />
              <button type="submit" className="btn btn-secondary" disabled={!importPath.trim() || !importName.trim()}>
                Import
              </button>
            </div>
          </form>

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
                  return (
                    <div key={m.id} className="card" style={{ border: '1px solid var(--border-base)' }}>
                      <div className="card-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 600 }}>{m.name}</span>
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
                            value={m.selected_format ?? ''}
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

                      <div className="card-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="form-hint">
                          {m.source === 'local' ? 'Imported' : 'Hugging Face'}
                          {m.size_mb != null ? ` · ${m.size_mb.toLocaleString()} MiB` : ''}
                          {!m.available ? ' · files missing' : ''}
                        </span>
                        <button type="button" className="btn btn-ghost btn-sm" style={{ color: 'var(--color-error)' }} onClick={() => handleDelete(m)}>
                          Delete
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
