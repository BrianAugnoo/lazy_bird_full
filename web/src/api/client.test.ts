import { describe, it, expect, vi, beforeEach } from 'vitest';
import { request, ApiError } from './client';

describe('API Client Layer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('gère les réponses avec succès', async () => {
    const mockData = { success: true, message: 'Welcome' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockData,
    } as Response);

    const result = await request<{ success: boolean; message: string }>('/');
    expect(result).toEqual(mockData);
  });

  it('intercepte les erreurs 503 (startup failure) et extrait le message d’erreur', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ success: false, error: 'Database is migrating' }),
    } as Response);

    await expect(request('/files/')).rejects.toThrow('Database is migrating');
  });

  it('formate lisiblement les erreurs de validation FastAPI 422', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        detail: [
          { loc: ['body', 'query'], msg: 'Field required', type: 'missing' },
        ],
      }),
    } as Response);

    try {
      await request('/search/', { method: 'POST' });
      expect.unreachable('Devrait échouer avec 422');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(422);
      expect((err as ApiError).message).toContain('body.query: Field required');
    }
  });

  it('remonte une erreur réseau claire si le serveur est inaccessible', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(request('/')).rejects.toThrow(/Unable to connect to Lazy Bird server/);
  });
});
