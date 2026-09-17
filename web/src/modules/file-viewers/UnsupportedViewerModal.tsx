import React from 'react';
import type { FileItem } from '@/core/types/api';
import { downloadFile } from '@/api/endpoints/files';

interface UnsupportedViewerModalProps {
  file: FileItem | null;
  onClose: () => void;
}

export const UnsupportedViewerModal: React.FC<UnsupportedViewerModalProps> = ({
  file,
  onClose,
}) => {
  if (!file) return null;

  const handleDownload = () => {
    downloadFile(file.id!, `${file.name}${file.extension}`);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-window"
        style={{ maxWidth: '480px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.4rem' }}>⚠️</span>
            <h3 className="card-title">Unsupported File Format</h3>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
            The system cannot preview or edit <strong>{file.name}{file.extension}</strong> in the browser because no compatible editor module is installed for <code>{file.extension || 'this format'}</code>.
          </p>
          <div
            style={{
              padding: '12px',
              backgroundColor: 'rgba(0, 0, 0, 0.2)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
            }}
          >
            <div>Size: {(file.size / 1024).toFixed(1)} KB</div>
            <div>Status: {file.status}</div>
            <div>Path: {file.path}</div>
          </div>
        </div>
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '16px 20px', borderTop: '1px solid var(--border-subtle)' }}>
          {file.id && (
            <button type="button" className="btn btn-primary btn-sm" onClick={handleDownload}>
              ⬇️ Download File
            </button>
          )}
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
