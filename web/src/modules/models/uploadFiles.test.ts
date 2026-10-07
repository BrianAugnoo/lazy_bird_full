import { describe, expect, it } from 'vitest';
import { pickedFiles, suggestedName } from './uploadFiles';

const file = (name: string, relativePath = '') => {
  const value = new File(['x'], name);
  Object.defineProperty(value, 'webkitRelativePath', { value: relativePath });
  return value;
};

describe('model upload files', () => {
  it('keeps the structure of a picked folder without the folder itself', () => {
    const files = [file('config.json', 'qwen/config.json'), file('vocab.txt', 'qwen/tokenizer/vocab.txt'), file('HEAD', 'qwen/.git/HEAD')];
    expect(pickedFiles(files).map((entry) => entry.path)).toEqual(['config.json', 'tokenizer/vocab.txt']);
    expect(suggestedName(files)).toBe('qwen');
  });

  it('uses file names for loose files', () => {
    const files = [file('tiny-Q4_K_M.gguf')];
    expect(pickedFiles(files).map((entry) => entry.path)).toEqual(['tiny-Q4_K_M.gguf']);
    expect(suggestedName(files)).toBe('tiny-Q4_K_M');
    expect(suggestedName([])).toBe('');
  });
});
