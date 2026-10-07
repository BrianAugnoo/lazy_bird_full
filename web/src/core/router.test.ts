import { afterEach, describe, expect, it } from 'vitest';
import { buildHash, navigate, parseHash, setParams } from './router';

describe('hash router', () => {
  afterEach(() => {
    window.location.hash = '';
  });

  it('parses and builds page addresses with parameters', () => {
    expect(parseHash('#/chat?session=1&conversation=3')).toEqual({ page: 'chat', params: { session: '1', conversation: '3' } });
    expect(parseHash('')).toEqual({ page: '', params: {} });
    expect(buildHash('files', { dir: 'a/b', file: null, empty: '' })).toBe('#/files?dir=a%2Fb');
    expect(parseHash(buildHash('files', { dir: 'a/b' })).params.dir).toBe('a/b');
  });

  it('changes some parameters without losing the others', () => {
    navigate('chat', { session: 1, conversation: 2 });
    setParams({ conversation: null, agent: 5 });
    expect(parseHash(window.location.hash)).toEqual({ page: 'chat', params: { session: '1', agent: '5' } });
  });
});
