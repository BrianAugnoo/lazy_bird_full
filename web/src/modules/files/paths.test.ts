import { describe, expect, it } from 'vitest';
import { baseName, breadcrumbs, childFolders, formatSize, joinPath, parentOf } from './paths';

describe('storage paths', () => {
  it('joins and splits folder paths', () => {
    expect(joinPath('', 'a')).toBe('a');
    expect(joinPath('a/b', 'c')).toBe('a/b/c');
    expect(parentOf('a/b/c')).toBe('a/b');
    expect(parentOf('a')).toBe('');
    expect(baseName('a/b/c')).toBe('c');
  });

  it('lists direct sub-folders only', () => {
    const all = ['docs', 'docs/old', 'docs/old/2020', 'notes', 'docsx'];
    expect(childFolders('', all)).toEqual(['docs', 'docsx', 'notes']);
    expect(childFolders('docs', all)).toEqual(['docs/old']);
    expect(childFolders('docs/old/2020', all)).toEqual([]);
  });

  it('builds breadcrumbs and sizes', () => {
    expect(breadcrumbs('a/b')).toEqual([
      { name: 'a', path: 'a' },
      { name: 'b', path: 'a/b' },
    ]);
    expect(breadcrumbs('')).toEqual([]);
    expect(formatSize(512)).toBe('512 B');
    expect(formatSize(2048)).toBe('2.0 KB');
  });
});
