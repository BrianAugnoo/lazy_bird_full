import { request } from '../client';
import type { LLMModel, SelectedModel } from '@/core/types/api';

/**
 * Liste des modèles LLM / embedding enregistrés
 * GET /models/
 */
export async function getModels(): Promise<LLMModel[]> {
  return request<LLMModel[]>('/models/');
}

/**
 * Récupère un modèle par son ID
 * GET /models/{id}
 */
export async function getModel(id: number): Promise<LLMModel | null> {
  return request<LLMModel | null>(`/models/${id}`);
}

/**
 * Télécharge et enregistre un modèle Hugging Face
 * POST /models/
 */
export async function createModel(hf_path: string): Promise<LLMModel> {
  return request<LLMModel>('/models/', {
    method: 'POST',
    body: JSON.stringify({ hf_path }),
  });
}

/**
 * Sélectionne le format d'un modèle (ex: safetensors)
 * PUT /models/{id}/format
 */
export async function setModelFormat(
  id: number,
  selected_format: string
): Promise<LLMModel> {
  return request<LLMModel>(`/models/${id}/format`, {
    method: 'PUT',
    body: JSON.stringify({ selected_format }),
  });
}

/**
 * Supprime tous les modèles enregistrés
 * DELETE /models/destroy
 */
export async function destroyAllModels(): Promise<{ message: string }> {
  return request<{ message: string }>('/models/destroy', {
    method: 'DELETE',
  });
}

/**
 * Retourne le modèle actif pour l'embedding
 * GET /selected-models/
 */
export async function getSelectedModel(): Promise<SelectedModel> {
  return request<SelectedModel>('/selected-models/');
}

/**
 * Définit ou remplace le modèle actif pour l'embedding
 * PUT /selected-models/
 */
export async function setSelectedModel(
  llm_model_id: number | null,
  batch: number = 1
): Promise<SelectedModel> {
  return request<SelectedModel>('/selected-models/', {
    method: 'PUT',
    body: JSON.stringify({ llm_model_id, batch }),
  });
}
