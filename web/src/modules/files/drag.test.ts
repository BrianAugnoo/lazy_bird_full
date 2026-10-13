import { describe, expect, it } from 'vitest';
import { parseFileDrag, validDestination } from './drag';

describe('file manager drag contracts', () => {
  it('accepts unique positive IDs and ignores external or malformed transfers', () => {
    expect(parseFileDrag('{"kind":"files","ids":[1,2,1]}')).toEqual({ kind: 'files', ids: [1, 2] });
    for (const value of ['', '{}', '{"kind":"files","ids":[]}', '{"kind":"files","ids":[-1]}', '{"kind":"files","ids":["1"]}', '{"kind":"folder","path":"../docs"}']) expect(parseFileDrag(value)).toBeNull();
  });
  it('rejects folder self, descendant and unchanged-parent drops', () => {
    const drag = { kind: 'folder' as const, path: 'docs/notes' };
    expect(validDestination(drag, 'docs/notes')).toBe(false);
    expect(validDestination(drag, 'docs/notes/old')).toBe(false);
    expect(validDestination(drag, 'docs')).toBe(false);
    expect(validDestination(drag, 'archive')).toBe(true);
    expect(validDestination(drag, '')).toBe(true);
    expect(validDestination({ kind: 'files', ids: [1] }, 'docs')).toBe(true);
  });
});
