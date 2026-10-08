import { describe, expect, it } from 'vitest';
import { candidatesError, toPayload, type SearchForm } from './searchRequest';

const form = (changes: Partial<SearchForm> = {}): SearchForm => ({
  mode: 'embedding',
  query: '  green tea ',
  presetId: '',
  crossEncoderPresetId: '',
  results: 8,
  candidates: 50,
  fileIds: [],
  ...changes,
});

describe('search request', () => {
  it('sends an embedding-only search exactly as before', () => {
    expect(toPayload(form({ presetId: 2, fileIds: ['3'] }))).toEqual({ query: 'green tea', top_k: 8, preset_id: 2, file_ids: [3] });
  });

  it('sends the candidates and the cross-encoder when reranking', () => {
    expect(toPayload(form({ mode: 'rerank', results: 10, crossEncoderPresetId: 4 }))).toEqual({
      query: 'green tea',
      top_k: 10,
      preset_id: null,
      file_ids: null,
      rerank: true,
      cross_encoder_preset_id: 4,
      top_n: 50,
    });
  });

  it('requires more candidates than final results only when reranking', () => {
    expect(candidatesError(form({ mode: 'rerank', results: 10, candidates: 10 }))).toMatch(/greater than the final results \(10\)/);
    expect(candidatesError(form({ mode: 'rerank', results: 10, candidates: 11 }))).toBeNull();
    expect(candidatesError(form({ mode: 'embedding', results: 10, candidates: 1 }))).toBeNull();
  });
});
