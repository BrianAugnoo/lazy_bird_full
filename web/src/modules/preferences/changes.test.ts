import { describe, expect, it } from 'vitest';
import { changedPreferences } from './changes';

describe('changedPreferences', () => {
  it('keeps only the keys that differ', () => {
    const saved = { chunking: { max_tokens: 512 }, tasks: { workers: 4, resources: { vram_mb: 8000 } } };
    const draft = { chunking: { max_tokens: 512 }, tasks: { workers: 2, resources: { vram_mb: 8000 } } };
    expect(changedPreferences(saved, draft)).toEqual({ tasks: { workers: 2 } });
    expect(changedPreferences(saved, saved)).toEqual({});
  });
});
