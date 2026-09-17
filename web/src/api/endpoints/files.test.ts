import { describe, expect, it, vi } from 'vitest';
import { deleteFiles } from './files';

describe('file deletion API', () => {
  it('sends selected IDs as a JSON array body', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ message: 'Files deleted successfully.' }),
    } as Response);

    await deleteFiles([1, 2]);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/files/',
      expect.objectContaining({
        method: 'DELETE',
        body: JSON.stringify([1, 2]),
      }),
    );
  });
});
