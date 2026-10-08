import type { SearchPayload } from '@/core/types/api';

/** Embedding only returns the nearest passages; reranking scores the nearest ones with a cross-encoder. */
export type SearchMode = 'embedding' | 'rerank';

export const DEFAULT_RESULTS = { embedding: 8, rerank: 10 } as const;
export const DEFAULT_CANDIDATES = 50;
export const MAX_RESULTS = 50;
export const MAX_CANDIDATES = 500;

export interface SearchForm {
  mode: SearchMode;
  query: string;
  presetId: number | '';
  crossEncoderPresetId: number | '';
  /** `top_k`: how many results come back, in either mode. */
  results: number;
  /** `top_n`: how many embedding candidates the cross-encoder reads (reranking only). */
  candidates: number;
  fileIds: string[];
}

/** Why the candidates cannot feed the reranker, or null when they can: `top_n` must be greater than `top_k`. */
export function candidatesError(form: Pick<SearchForm, 'mode' | 'results' | 'candidates'>): string | null {
  if (form.mode !== 'rerank' || form.candidates > form.results) return null;
  return `Must be greater than the final results (${form.results}).`;
}

export function toPayload(form: SearchForm): SearchPayload {
  const payload: SearchPayload = {
    query: form.query.trim(),
    top_k: form.results,
    preset_id: form.presetId === '' ? null : form.presetId,
    file_ids: form.fileIds.length ? form.fileIds.map(Number) : null,
  };
  if (form.mode === 'embedding') return payload;
  return {
    ...payload,
    rerank: true,
    cross_encoder_preset_id: form.crossEncoderPresetId === '' ? null : form.crossEncoderPresetId,
    top_n: form.candidates,
  };
}
