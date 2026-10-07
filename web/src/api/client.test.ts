import { describe, it, expect, vi, beforeEach } from 'vitest';
import { request, ApiError } from './client';

describe('API Client Layer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns the JSON body of successful responses', async () => {
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

  it('surfaces the uniform error payload (code, message, details)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ error: { code: 'startup_failed', message: 'Database is migrating', details: {} } }),
    } as Response);

    await expect(request('/files/')).rejects.toMatchObject({ status: 503, code: 'startup_failed', message: 'Database is migrating' });
  });

  it('exposes per-field messages of invalid settings', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: { code: 'invalid_settings', message: 'Invalid settings', details: { fields: { model_id: 'Field required' } } },
      }),
    } as Response);

    try {
      await request('/embedding-presets/', { method: 'POST', body: '{}' });
      expect.unreachable('should fail with 422');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).code).toBe('invalid_settings');
      expect((err as ApiError).fieldErrors).toEqual({ model_id: 'Field required' });
    }
  });

  it('reports a clear network error when the server is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(request('/')).rejects.toThrow(/Unable to connect to Lazy Bird server/);
  });
});
