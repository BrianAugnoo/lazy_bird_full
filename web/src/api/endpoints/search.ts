import { request } from '../client';
import type { SearchPayload, SearchResultChunk } from '@/core/types/api';

/**
 * Exécute une recherche sémantique sur la base vectorielle
 * POST /search/
 */
export async function searchChunks(
  query: string,
  topK: number = 5
): Promise<SearchResultChunk[]> {
  const payload: SearchPayload = {
    query: query.trim(),
    top_k: topK,
  };

  return request<SearchResultChunk[]>('/search/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
