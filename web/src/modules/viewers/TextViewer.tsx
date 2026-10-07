import type { FileViewerProps } from '@/core/file-viewers/registry';

/** Plain text and code, edited in a monospace area. */
export function TextViewer({ content, onChange }: FileViewerProps) {
  return (
    <textarea
      className="viewer-text"
      value={content}
      readOnly={!onChange}
      spellCheck={false}
      onChange={(event) => onChange?.(event.target.value)}
      aria-label="File content"
    />
  );
}
