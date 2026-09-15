import { request } from '../client';
import type { APIKeyOut } from '@/core/types/api';

/**
 * Crée une nouvelle clé API
 * POST /api-keys/api-keys
 */
export async function createApiKey(name: string, key: string): Promise<APIKeyOut> {
  return request<APIKeyOut>('/api-keys/api-keys', {
    method: 'POST',
    body: JSON.stringify({ name, key }),
  });
}

/**
 * Liste les clés API enregistrées (sans exposer le secret)
 * GET /api-keys/api-keys
 */
export async function listApiKeys(): Promise<APIKeyOut[]> {
  return request<APIKeyOut[]>('/api-keys/api-keys');
}

/**
 * Récupère une clé API par son nom
 * GET /api-keys/api-keys/{name}
 */
export async function getApiKey(name: string): Promise<APIKeyOut> {
  return request<APIKeyOut>(`/api-keys/api-keys/${encodeURIComponent(name)}`);
}
