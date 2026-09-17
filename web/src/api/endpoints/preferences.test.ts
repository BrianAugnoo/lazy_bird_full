import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getPreferences, updatePreferences } from './preferences';

describe('Preferences API Endpoint', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches current preferences', async () => {
    const mockData = { 'auto-embedding': { enable: true } };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockData,
    } as Response);

    const result = await getPreferences();
    expect(result).toEqual(mockData);
  });

  it('updates preferences successfully', async () => {
    const payload = { 'auto-embedding': { enable: false } };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => payload,
    } as Response);

    const result = await updatePreferences(payload);
    expect(result).toEqual(payload);
  });
});
