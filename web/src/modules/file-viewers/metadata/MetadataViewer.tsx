import React from 'react';
import type { FileViewerProps } from '@/core/file-viewers/types';

export const MetadataViewer: React.FC<FileViewerProps> = ({
  file,
  onClose,
  onProcess,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-base)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.4rem' }}>📁</span>
          <div>
            <strong>{file.name}{file.extension}</strong>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Détails et métadonnées</div>
          </div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          ✕
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Identifiant</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{file.id ?? 'Non assigné'}</div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Format / Extension</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{file.extension || 'Aucune'}</div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Taille du fichier</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {file.size >= 1048576
              ? `${(file.size / 1048576).toFixed(2)} Mo`
              : `${(file.size / 1024).toFixed(1)} Ko`}
          </div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Statut de traitement</div>
          <div style={{ marginTop: '4px' }}>
            <span className={`badge ${
              file.status === 'done' ? 'badge-success' :
              file.status === 'processing' ? 'badge-info' :
              file.status === 'pending' ? 'badge-warning' : 'badge-error'
            }`}>
              {file.status}
            </span>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: '12px' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Chemin de stockage serveur</div>
        <div style={{ marginTop: '4px', fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all', color: 'var(--text-secondary)' }}>
          {file.path || 'Non spécifié'}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
        {file.id && onProcess && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => onProcess(file.id!)}
          >
            ⚡ Lancer le traitement RAG
          </button>
        )}
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Fermer
        </button>
      </div>
    </div>
  );
};
