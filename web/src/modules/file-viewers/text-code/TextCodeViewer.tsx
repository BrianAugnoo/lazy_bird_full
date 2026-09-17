import React, { useState } from 'react';
import type { FileViewerProps } from '@/core/file-viewers/types';

export const TextCodeViewer: React.FC<FileViewerProps> = ({
  file,
  content = '',
  onSave,
  onClose,
  onProcess,
}) => {
  const [currentContent, setCurrentContent] = useState<string>(content);
  const [isEditing, setIsEditing] = useState<boolean>(!content);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const lines = currentContent.split('\n');

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      await onSave(currentContent);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-base)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>📄</span>
          <div>
            <strong>{file.name}{file.extension}</strong>
            <span style={{ marginLeft: '8px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              ({lines.length} lines · {(file.size / 1024).toFixed(1)} KB)
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {saveSuccess && <span style={{ color: 'var(--color-success)', fontSize: '0.8rem' }}>✓ Saved</span>}
          {onSave && (
            <button
              type="button"
              className={`btn btn-sm ${isEditing ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setIsEditing(!isEditing)}
            >
              {isEditing ? 'Read-only' : 'Edit'}
            </button>
          )}
          {isEditing && onSave && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          )}
          {file.id && onProcess && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onProcess(file.id!)}
              title="Trigger RAG processing"
            >
              ⚡ Process RAG
            </button>
          )}
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} title="Close">
            ✕
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: '350px', maxHeight: '55vh', overflowY: 'auto', display: 'flex', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-base)' }}>
        {isEditing ? (
          <textarea
            style={{
              width: '100%',
              height: '100%',
              minHeight: '340px',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              padding: '12px',
              background: 'transparent',
              color: 'var(--text-primary)',
              border: 'none',
              outline: 'none',
              resize: 'none',
              lineHeight: 1.5,
            }}
            value={currentContent}
            onChange={(e) => setCurrentContent(e.target.value)}
            placeholder="Type or paste code / text here..."
          />
        ) : (
          <div style={{ display: 'flex', width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}>
            <div style={{ padding: '12px 8px', borderRight: '1px solid var(--border-subtle)', color: 'var(--text-muted)', userSelect: 'none', textAlign: 'right', minWidth: '40px' }}>
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            <div style={{ padding: '12px', flex: 1, overflowX: 'auto', whiteSpace: 'pre' }}>
              {currentContent || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Empty file</span>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
