import { useState } from 'react';
import type { FileViewerProps } from '@/core/file-viewers/registry';
import { Markdown } from '@/ui/Markdown';

type Mode = 'write' | 'split' | 'preview';

/** Markdown with a live preview: write, side by side, or preview only. */
export function MarkdownEditor({ content, onChange }: { content: string; onChange?: (content: string) => void }) {
  const [mode, setMode] = useState<Mode>(onChange ? 'split' : 'preview');
  return (
    <div className="viewer-markdown">
      {onChange && (
        <div className="segmented" role="radiogroup" aria-label="Display">
          {(['write', 'split', 'preview'] as Mode[]).map((item) => (
            <button key={item} type="button" role="radio" aria-checked={mode === item} className={mode === item ? 'is-active' : ''} onClick={() => setMode(item)}>
              {item === 'write' ? 'Write' : item === 'split' ? 'Side by side' : 'Preview'}
            </button>
          ))}
        </div>
      )}
      <div className={`viewer-markdown-panes is-${mode}`}>
        {mode !== 'preview' && (
          <textarea className="viewer-text" value={content} spellCheck onChange={(event) => onChange?.(event.target.value)} aria-label="Markdown source" />
        )}
        {mode !== 'write' && (
          <div className="viewer-preview">
            {content.trim() ? <Markdown text={content} /> : <p className="muted">This document is empty.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export function MarkdownViewer({ content, onChange }: FileViewerProps) {
  return <MarkdownEditor content={content} onChange={onChange} />;
}
