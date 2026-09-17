import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarkdownViewer } from './MarkdownViewer';
import type { FileItem } from '@/core/types/api';

describe('MarkdownViewer Component', () => {
  const mockFile: FileItem = {
    id: 1,
    name: 'readme',
    extension: '.md',
    size: 2048,
    path: 'documents/readme.md',
    status: 'done',
    embedded_by: [1],
    vector_db: ['lancedb'],
  };

  it('renders markdown content and parses headers', () => {
    const markdownContent = '# Test Document Title\n\nThis is a paragraph with bold text.';
    render(
      <MarkdownViewer
        file={mockFile}
        content={markdownContent}
        onClose={() => {}}
      />
    );

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toContain('Test Document Title');
    expect(screen.getByText('readme.md')).toBeDefined();
  });

  it('displays empty state notice when content is empty', () => {
    render(
      <MarkdownViewer
        file={mockFile}
        content=""
        onClose={() => {}}
      />
    );

    const emptyNotice = screen.getByText(/This document is empty/i);
    expect(emptyNotice).toBeDefined();
    expect(emptyNotice.textContent).toContain('This document is empty');
  });
});
