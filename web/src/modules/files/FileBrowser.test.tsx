import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FileItem } from '@/core/types/api';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { FileBrowser } from './FileBrowser';

vi.mock('@/core/tasks/store', () => ({ onFileChange: () => () => undefined }));

const file = (id: number, name: string, directory: string, state: FileItem['state'] = 'ready'): FileItem => ({
  id,
  name,
  extension: '.md',
  size: 1200,
  path: `/storage/${directory}/${name}.md`,
  relative_path: `${directory ? `${directory}/` : ''}${name}.md`,
  directory,
  content_hash: 'abc',
  missing: false,
  chunk_count: 3,
  state,
  processing: [],
});

describe('FileBrowser', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';
  });

  it('shows the folders and files of the current folder with their state', async () => {
    mockApi({
      'GET /files/': [file(1, 'readme', ''), file(2, 'deep', 'docs/old', 'processing'), file(3, 'guide', 'docs', 'error')],
      'GET /files/directories': ['docs', 'docs/old', 'empty'],
    });

    render(
      <ToastProvider>
        <FileBrowser dir="docs" />
      </ToastProvider>,
    );

    expect(await screen.findByText('guide.md')).toBeTruthy();
    expect(screen.getByText('Error')).toBeTruthy();
    expect(screen.getByText('old')).toBeTruthy();
    expect(screen.queryByText('readme.md')).toBeNull();
    expect(screen.queryByText('deep.md')).toBeNull();

    fireEvent.click(screen.getByText('old'));
    expect(window.location.hash).toBe('#/?dir=docs%2Fold');
  });
});
