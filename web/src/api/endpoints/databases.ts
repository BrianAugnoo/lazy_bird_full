import { request } from '../client';
import type {
  DatabasesCatalogResponse,
  SelectedDatabaseOut,
  DatabaseSelectionIn,
  DatabaseDisconnectIn,
} from '@/core/types/api';

/**
 * Retourne le catalogue des adaptateurs disponibles et la sélection courante
 * GET /databases/
 */
export async function getDatabases(): Promise<DatabasesCatalogResponse> {
  return request<DatabasesCatalogResponse>('/databases/');
}

/**
 * Retourne uniquement les adaptateurs SQL et Vector sélectionnés
 * GET /databases/selected_db
 */
export async function getSelectedDatabases(): Promise<SelectedDatabaseOut> {
  return request<SelectedDatabaseOut>('/databases/selected_db');
}

/**
 * Bascule la base SQL ou Vector sélectionnée
 * PUT /databases/select
 */
export async function selectDatabase(
  payload: DatabaseSelectionIn
): Promise<{ selected: string; messages: string[] }> {
  return request<{ selected: string; messages: string[] }>('/databases/select', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/**
 * Déconnecte un adaptateur de base de données (avec option drop pour purger)
 * PUT /databases/disconnect
 */
export async function disconnectDatabase(
  payload: DatabaseDisconnectIn
): Promise<{ selected_sql: string; selected_vector: string }> {
  return request<{ selected_sql: string; selected_vector: string }>(
    '/databases/disconnect',
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    }
  );
}
