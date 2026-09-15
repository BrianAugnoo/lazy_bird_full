import { request } from '../client';
import type { EmbeddingEngine, SelectedEmbeddingEngine } from '@/core/types/api';

/**
 * Liste des moteurs d'embedding configurés
 * GET /embedding-engines/
 */
export async function getEmbeddingEngines(): Promise<EmbeddingEngine[]> {
  return request<EmbeddingEngine[]>('/embedding-engines/');
}

/**
 * Met à jour les arguments spécifiques d'un moteur
 * PUT /embedding-engines/{engine_id}
 */
export async function updateEngineKwargs(
  engineId: number,
  kwargs: Record<string, any>
): Promise<EmbeddingEngine | { success: boolean; invalid_keys: string[] }> {
  return request<EmbeddingEngine | { success: boolean; invalid_keys: string[] }>(
    `/embedding-engines/${engineId}`,
    {
      method: 'PUT',
      body: JSON.stringify({ kwargs }),
    }
  );
}

/**
 * Récupère le moteur d'embedding actif
 * GET /selected-embedding-engine/
 */
export async function getSelectedEmbeddingEngine(): Promise<SelectedEmbeddingEngine> {
  return request<SelectedEmbeddingEngine>('/selected-embedding-engine/');
}

/**
 * Sélectionne le moteur d'embedding actif
 * PUT /selected-embedding-engine/
 */
export async function setSelectedEmbeddingEngine(
  embedding_engine_id: number
): Promise<SelectedEmbeddingEngine> {
  return request<SelectedEmbeddingEngine>('/selected-embedding-engine/', {
    method: 'PUT',
    body: JSON.stringify({ embedding_engine_id }),
  });
}
