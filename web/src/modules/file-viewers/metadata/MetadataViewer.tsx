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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Metadata & Properties</div>
          </div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          ✕
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Identifier</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{file.id ?? 'Unassigned'}</div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Format / Extension</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{file.extension || 'None'}</div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>File Size</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {file.size >= 1048576
              ? `${(file.size / 1048576).toFixed(2)} MB`
              : `${(file.size / 1024).toFixed(1)} KB`}
          </div>
        </div>
        <div className="card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Processing</div>
          <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span className="badge badge-muted">{file.state ?? 'new'}</span>
            {(file.processing ?? []).map((row) => (
              <span key={`${row.processor}:${row.target}`} style={{ fontSize: '0.75rem' }} title={row.error?.message}>
                {row.processor}
                {row.target ? ` · ${row.target}` : ''}: <strong>{row.state}</strong>
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: '12px' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Server Storage Path</div>
        <div style={{ marginTop: '4px', fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all', color: 'var(--text-secondary)' }}>
          {file.path || 'Not specified'}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
        {file.id && onProcess && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => onProcess(file.id!)}
          >
            ⚡ Trigger RAG Processing
          </button>
        )}
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
};
