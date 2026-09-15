import { request } from '../client';
import type { HealthResponse } from '@/core/types/api';

/**
 * Vérifie l'état de l'application et de la base de données
 * GET /
 */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/');
}
