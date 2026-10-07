import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FileItem } from '@/core/types/api';
import { MarkdownViewer } from './MarkdownViewer';

const file = { id: 1, name: 'readme', extension: '.md' } as FileItem;

describe('MarkdownViewer', () => {
  it('renders the markdown preview', () => {
    render(<MarkdownViewer file={file} content={'# Title\n\nText'} />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Title');
    expect(screen.queryByLabelText('Markdown source')).toBeNull();
  });

  it('reports edits and switches between modes', () => {
    const onChange = vi.fn();
    render(<MarkdownViewer file={file} content="" onChange={onChange} />);
    expect(screen.getByText('This document is empty.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Markdown source'), { target: { value: '# New' } });
    expect(onChange).toHaveBeenCalledWith('# New');
    fireEvent.click(screen.getByText('Preview'));
    expect(screen.queryByLabelText('Markdown source')).toBeNull();
  });
});
