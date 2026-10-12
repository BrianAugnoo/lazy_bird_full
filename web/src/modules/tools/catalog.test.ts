import { describe, expect, it } from 'vitest';
import { callable } from '@/test/callables';
import { groupByExtension, selectionState, setSelected } from './catalog';

describe('groupByExtension', () => {
  it('lists default and custom first, even empty, then the other extensions, each by module', () => {
    const items = [callable('zeta', 'mail', 'send'), callable('default', 'smtp', 'send_email'), callable('default', 'kb', 'search'), callable('acme', 'web', 'fetch'), callable('default', 'kb', 'read')];

    const groups = groupByExtension(items);

    expect(groups.map((group) => group.extension)).toEqual(['default', 'custom', 'acme', 'zeta']);
    expect(groups[0].modules.map((module) => [module.module, module.filePath, module.items.map((item) => item.name)])).toEqual([
      ['kb', 'default/kb.py', ['search', 'read']],
      ['smtp', 'default/smtp.py', ['send_email']],
    ]);
    expect(groups[1]).toEqual({ extension: 'custom', items: [], modules: [] });
  });
});

describe('selection helpers', () => {
  it('tells whether none, some or all of a group is selected', () => {
    expect(selectionState(['a', 'b'], [])).toBe('none');
    expect(selectionState(['a', 'b'], ['b', 'x'])).toBe('some');
    expect(selectionState(['a', 'b'], ['b', 'a'])).toBe('all');
    expect(selectionState([], ['a'])).toBe('none');
  });

  it('selects a group after what was already chosen and deselects it without touching the rest', () => {
    expect(setSelected(['x', 'b'], ['a', 'b', 'c'], true)).toEqual(['x', 'b', 'a', 'c']);
    expect(setSelected(['x', 'b', 'a'], ['a', 'b'], false)).toEqual(['x']);
  });
});
