import { describe, expect, it } from 'vitest';
import { libraryExtensions, librarySelection } from './library';
describe('library navigation', () => {
  it('retains default and custom, discovers other extensions, and preserves empty selections', () => {
    const items = [{ extension: 'acme' }, { extension: 'default' }, { extension: 'acme' }];
    expect(libraryExtensions(items)).toEqual([{ extension: 'default', count: 1 }, { extension: 'custom', count: 0 }, { extension: 'acme', count: 2 }]);
    expect(librarySelection(items, 'custom')).toBe('custom');
    expect(librarySelection(items, 'unknown')).toBe('default');
    expect(librarySelection([{ extension: 'acme' }])).toBe('acme');
    expect(librarySelection([])).toBe('default');
  });
});
