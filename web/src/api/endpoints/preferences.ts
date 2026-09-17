import { request } from '../client';
import type { PreferencesPayload } from '@/core/types/api';

/**
 * Get current application preferences
 * GET /preferences/
 */
export async function getPreferences(): Promise<PreferencesPayload> {
  return request<PreferencesPayload>('/preferences/');
}

/**
 * Update application preferences
 * PUT /preferences/
 */
export async function updatePreferences(preferences: PreferencesPayload): Promise<PreferencesPayload> {
  return request<PreferencesPayload>('/preferences/', {
    method: 'PUT',
    body: JSON.stringify(preferences),
  });
}
