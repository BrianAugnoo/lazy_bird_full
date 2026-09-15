import React, { useState } from 'react';
import type { FileViewerProps } from '@/core/file-viewers/types';

export const MarkdownViewer: React.FC<FileViewerProps> = ({
  file,
  content = '',
  onSave,
  onClose,
  onProcess,
}) => {
  const [isEditing, setIsEditing] = useState<boolean>(!content);
  const [currentContent, setCurrentContent] = useState<string>(content);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

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

  // Rendu simple et sécurisé du Markdown (paragraphes, titres, listes, code)
  const renderMarkdown = (text: string) => {
    if (!text.trim()) {
      return (
        <p style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
          Ce fichier est vide. Cliquez sur "Éditer" pour commencer la rédaction.
        </p>
      );
    }

    const lines = text.split('\n');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', lineHeight: 1.6 }}>
        {lines.map((line, idx) => {
          if (line.startsWith('# ')) {
            return <h1 key={idx} style={{ fontSize: '1.5rem', margin: '12px 0 6px', borderBottom: '1px solid var(--border-base)', paddingBottom: '4px' }}>{line.slice(2)}</h1>;
          }
          if (line.startsWith('## ')) {
            return <h2 key={idx} style={{ fontSize: '1.25rem', margin: '10px 0 4px' }}>{line.slice(3)}</h2>;
          }
          if (line.startsWith('### ')) {
            return <h3 key={idx} style={{ fontSize: '1.1rem', margin: '8px 0 4px' }}>{line.slice(4)}</h3>;
          }
          if (line.startsWith('- ') || line.startsWith('* ')) {
            return <li key={idx} style={{ marginLeft: '20px' }}>{line.slice(2)}</li>;
          }
          if (line.startsWith('```')) {
            return <div key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '4px 8px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.85rem' }}>{line}</div>;
          }
          if (!line.trim()) {
            return <div key={idx} style={{ height: '8px' }} />;
          }
          return <p key={idx}>{line}</p>;
        })}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-base)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>📝</span>
          <div>
            <strong>{file.name}{file.extension}</strong>
            <span style={{ marginLeft: '8px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              ({(file.size / 1024).toFixed(1)} Ko)
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {saveSuccess && <span style={{ color: 'var(--color-success)', fontSize: '0.8rem' }}>✓ Enregistré</span>}
          {onSave && (
            <button
              type="button"
              className={`btn btn-sm ${isEditing ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setIsEditing(!isEditing)}
            >
              {isEditing ? 'Visualiser' : 'Éditer'}
            </button>
          )}
          {isEditing && onSave && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Enregistrement...' : 'Sauvegarder'}
            </button>
          )}
          {file.id && onProcess && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onProcess(file.id!)}
              title="Lancer le traitement RAG (chunking/embedding)"
            >
              ⚡ Traiter
            </button>
          )}
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: '350px', maxHeight: '55vh', overflowY: 'auto' }}>
        {isEditing ? (
          <textarea
            className="form-textarea"
            style={{
              width: '100%',
              height: '100%',
              minHeight: '340px',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              resize: 'vertical',
            }}
            value={currentContent}
            onChange={(e) => setCurrentContent(e.target.value)}
            placeholder="Rédigez votre document Markdown ici..."
          />
        ) : (
          <div style={{ padding: '8px 12px' }}>{renderMarkdown(currentContent)}</div>
        )}
      </div>
    </div>
  );
};
