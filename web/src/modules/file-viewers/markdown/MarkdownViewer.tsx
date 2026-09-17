import React, { useState, useEffect, useMemo, useRef } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import type { FileViewerProps } from '@/core/file-viewers/types';

export const MarkdownViewer: React.FC<FileViewerProps> = ({
  file,
  content = '',
  onSave,
  onClose,
  onProcess,
}) => {
  const [currentContent, setCurrentContent] = useState<string>(content);
  const [viewMode, setViewMode] = useState<'edit' | 'split' | 'preview'>('split');
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setCurrentContent(content);
    setHasUnsavedChanges(false);
  }, [content]);

  const handleContentChange = (val: string) => {
    setCurrentContent(val);
    setHasUnsavedChanges(val !== content);
  };

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      await onSave(currentContent);
      setSaveSuccess(true);
      setHasUnsavedChanges(false);
      setTimeout(() => setSaveSuccess(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  // Safe markdown html rendering via marked and dompurify
  const renderedHtml = useMemo(() => {
    if (!currentContent.trim()) {
      return '<p class="text-muted" style="font-style: italic;">This document is empty. Start typing or use the toolbar to format.</p>';
    }
    try {
      const rawHtml = marked.parse(currentContent, { async: false, gfm: true, breaks: true }) as string;
      return DOMPurify.sanitize(rawHtml);
    } catch {
      return '<p style="color: var(--color-error)">Failed to parse markdown.</p>';
    }
  }, [currentContent]);

  // Insert markdown helpers
  const insertText = (before: string, after: string = '') => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selection = currentContent.substring(start, end);
    const replacement = `${before}${selection || 'text'}${after}`;
    const nextVal = currentContent.substring(0, start) + replacement + currentContent.substring(end);
    handleContentChange(nextVal);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + before.length, start + replacement.length - after.length);
    }, 0);
  };

  const lineCount = currentContent ? currentContent.split('\n').length : 0;
  const wordCount = currentContent.trim() ? currentContent.trim().split(/\s+/).length : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '12px' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-base)',
          paddingBottom: '12px',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.25rem' }}>📝</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <strong>{file.name}{file.extension}</strong>
              {hasUnsavedChanges && (
                <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>
                  Unsaved changes
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {lineCount} lines · {wordCount} words · {(file.size / 1024).toFixed(1)} KB
            </div>
          </div>
        </div>

        {/* View Mode controls & Save */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'inline-flex', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', padding: '2px', border: '1px solid var(--border-subtle)' }}>
            <button
              type="button"
              className={`btn btn-sm ${viewMode === 'edit' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setViewMode('edit')}
              title="Editor only"
            >
              Edit
            </button>
            <button
              type="button"
              className={`btn btn-sm ${viewMode === 'split' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setViewMode('split')}
              title="Side-by-side Editor & Preview"
            >
              Split
            </button>
            <button
              type="button"
              className={`btn btn-sm ${viewMode === 'preview' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setViewMode('preview')}
              title="Preview only"
            >
              Preview
            </button>
          </div>

          {saveSuccess && <span style={{ color: 'var(--color-success)', fontSize: '0.8rem' }}>✓ Saved</span>}

          {onSave && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving || !hasUnsavedChanges}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          )}

          {file.id && onProcess && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onProcess(file.id!)}
              title="Trigger chunking and embedding pipeline"
            >
              ⚡ Process RAG
            </button>
          )}

          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} title="Close editor">
            ✕
          </button>
        </div>
      </div>

      {/* Formatting Toolbar in Edit/Split mode */}
      {viewMode !== 'preview' && (
        <div
          style={{
            display: 'flex',
            gap: '4px',
            padding: '6px 10px',
            backgroundColor: 'rgba(0,0,0,0.15)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            flexWrap: 'wrap',
          }}
        >
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('**', '**')} title="Bold">
            <strong>B</strong>
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('*', '*')} title="Italic">
            <em>I</em>
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('# ')} title="Heading 1">
            H1
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('## ')} title="Heading 2">
            H2
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('- ')} title="Bullet List">
            • List
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('1. ')} title="Numbered List">
            1. List
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('`', '`')} title="Inline Code">
            &lt;/&gt;
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('```\n', '\n```')} title="Code Block">
            Code Block
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('[', '](https://)')} title="Link">
            Link
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => insertText('| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |\n')} title="Table">
            Table
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div style={{ flex: 1, minHeight: '400px', display: 'flex', gap: '16px', overflow: 'hidden' }}>
        {/* Editor Pane */}
        {(viewMode === 'edit' || viewMode === 'split') && (
          <div
            style={{
              flex: 1,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'var(--bg-input)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
            }}
          >
            <textarea
              ref={textareaRef}
              style={{
                width: '100%',
                height: '100%',
                minHeight: '380px',
                fontFamily: 'monospace',
                fontSize: '0.9rem',
                lineHeight: 1.6,
                padding: '16px',
                background: 'transparent',
                color: 'var(--text-primary)',
                border: 'none',
                outline: 'none',
                resize: 'none',
              }}
              value={currentContent}
              onChange={(e) => handleContentChange(e.target.value)}
              placeholder="Write your Markdown document here..."
            />
          </div>
        )}

        {/* Preview Pane */}
        {(viewMode === 'preview' || viewMode === 'split') && (
          <div
            style={{
              flex: 1,
              height: '100%',
              minHeight: '380px',
              overflowY: 'auto',
              padding: '16px 20px',
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              lineHeight: 1.7,
            }}
          >
            <div
              className="markdown-body"
              dangerouslySetInnerHTML={{ __html: renderedHtml }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
